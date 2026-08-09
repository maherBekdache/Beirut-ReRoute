"""Population-weighted accessibility/coverage scoring for H3 demand cells.

This module is deliberately generic over its inputs: it consumes any GTFS-like
stop layer(s) (informal routes, OCFTC trunk stops) and a walk graph, rather
than hardcoding a data source, since the informal-route and OCFTC-trunk stop
layers are still being cleaned/digitized (see `data_acquisition/`).

Core formulation (see plan doc "Accessibility / Coverage Scoring"):
    total_time(c) = t_walk(c -> nearest_stop) + t_wait + t_ride_feeder(-> trunk access) + t_transfer
    A(c) = 1[total_time(c) <= T_MAX_MIN]                    -- binary, for MCLP input
    A(c) = exp(-DECAY_BETA * total_time(c))                 -- continuous, for reporting
    CoverageScore = sum(pop(c) * A(c)) / sum(pop(c))
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings


@dataclass
class AccessibilityResult:
    grid: gpd.GeoDataFrame  # input grid + walk_time_min, total_time_min, coverage_binary, coverage_decay
    coverage_score: float
    coverage_score_by_district: pd.Series | None = None


def nearest_stop_walk_times(
    grid: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    walk_graph: nx.MultiDiGraph,
) -> np.ndarray:
    """Walk time (minutes) from each grid cell centroid to its nearest stop,
    via the pedestrian network graph (not straight-line distance).
    """
    if len(stops) == 0:
        return np.full(len(grid), np.inf)

    cell_nodes = ox.distance.nearest_nodes(
        walk_graph, grid["centroid_lon"].values, grid["centroid_lat"].values
    )
    stop_nodes = ox.distance.nearest_nodes(
        walk_graph, stops.geometry.x.values, stops.geometry.y.values
    )
    stop_nodes = list(set(stop_nodes))

    # Multi-source Dijkstra from all stops simultaneously is far cheaper than
    # one shortest path per cell; networkx doesn't expose multi-source
    # dijkstra with a travel_time weight directly, so we add a virtual
    # "super stop" node connected to every stop node with zero-cost edges.
    #
    # We want dist(cell -> nearest stop), i.e. distance FROM each cell TO a
    # stop. The graph is directed (one-way streets), so that is NOT the same
    # as dist(stop -> cell). Running Dijkstra from a super-node with edges
    # super->stop over the graph as-is computes the latter (wrong direction).
    # Fix: reverse the graph first, so dist_rev(stop -> cell) = dist(cell ->
    # stop) in the original graph, then the same super-node trick gives the
    # correct quantity.
    G = walk_graph.reverse(copy=True)
    SUPER_STOP = "__super_stop__"
    G.add_node(SUPER_STOP)
    for n in stop_nodes:
        G.add_edge(SUPER_STOP, n, travel_time=0.0)

    lengths = nx.single_source_dijkstra_path_length(
        G, SUPER_STOP, weight="travel_time"
    )

    times_sec = np.array(
        [lengths.get(n, np.inf) for n in cell_nodes], dtype=float
    )
    return times_sec / 60.0


def score_grid(
    grid: gpd.GeoDataFrame,
    walk_time_min: np.ndarray,
    ride_time_min: np.ndarray | None = None,
    transfer_time_min: np.ndarray | None = None,
) -> gpd.GeoDataFrame:
    """Attach total_time_min / coverage_binary / coverage_decay columns to `grid`.

    `ride_time_min`/`transfer_time_min` default to 0 (i.e. a trunk/formal stop
    is reachable directly on foot) — pass real feeder-ride estimates once the
    feeder network exists (post-MCLP), so this same function scores both the
    status-quo (no feeder) and proposed (with feeder) scenarios.
    """
    grid = grid.copy()
    n = len(grid)
    ride = ride_time_min if ride_time_min is not None else np.zeros(n)
    transfer = transfer_time_min if transfer_time_min is not None else np.zeros(n)
    wait = np.where(ride > 0, settings.DEFAULT_WAIT_TIME_MIN, 0.0)

    total_time = walk_time_min + wait + ride + transfer
    grid["walk_time_min"] = walk_time_min
    grid["total_time_min"] = total_time
    grid["coverage_binary"] = (total_time <= settings.T_MAX_MIN).astype(int)
    grid["coverage_decay"] = np.exp(-settings.DECAY_BETA * np.nan_to_num(total_time, nan=1e9))
    return grid


def coverage_score(grid: gpd.GeoDataFrame, coverage_col: str = "coverage_binary") -> float:
    total_pop = grid["population"].sum()
    if total_pop == 0:
        return 0.0
    return float((grid["population"] * grid[coverage_col]).sum() / total_pop)


def coverage_score_by_district(
    grid: gpd.GeoDataFrame, coverage_col: str = "coverage_binary", district_col: str = "district"
) -> pd.Series:
    def _weighted(g: pd.DataFrame) -> float:
        pop = g["population"].sum()
        return float((g["population"] * g[coverage_col]).sum() / pop) if pop else 0.0

    return grid.groupby(district_col).apply(_weighted, include_groups=False)


def run(
    grid: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    walk_graph: nx.MultiDiGraph,
    district_col: str | None = None,
) -> AccessibilityResult:
    walk_time = nearest_stop_walk_times(grid, stops, walk_graph)
    scored = score_grid(grid, walk_time)
    score = coverage_score(scored)
    by_district = (
        coverage_score_by_district(scored, district_col=district_col)
        if district_col and district_col in scored.columns
        else None
    )
    return AccessibilityResult(grid=scored, coverage_score=score, coverage_score_by_district=by_district)
