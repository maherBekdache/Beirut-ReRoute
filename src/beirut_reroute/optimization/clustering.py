"""Assign demand cells and candidate feeder stops to their nearest trunk line.

Nearest is measured by network travel time (not straight-line distance),
because road topology determines what's actually reachable. This produces
per-trunk-line catchment clusters so the citywide MCLP can be decomposed into
~11 independently solvable per-line problems (see plan doc
"Feeder Network Optimization").
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings


def travel_time_to_each_line(
    points: gpd.GeoDataFrame,
    trunk_stops: gpd.GeoDataFrame,
    graph: nx.MultiDiGraph,
    line_col: str = "line_id",
) -> pd.DataFrame:
    """Return a DataFrame indexed like `points` with one travel-time column
    (minutes) per distinct trunk line in `trunk_stops[line_col]`.
    """
    point_nodes = ox.distance.nearest_nodes(
        graph, points.geometry.x.values, points.geometry.y.values
    )

    results = {}
    for line_id, line_stops in trunk_stops.groupby(line_col):
        stop_nodes = list(
            set(
                ox.distance.nearest_nodes(
                    graph, line_stops.geometry.x.values, line_stops.geometry.y.values
                )
            )
        )
        G = graph.copy()
        SUPER = f"__super_{line_id}__"
        G.add_node(SUPER)
        for n in stop_nodes:
            G.add_edge(SUPER, n, travel_time=0.0)
        lengths = nx.single_source_dijkstra_path_length(G, SUPER, weight="travel_time")
        times_min = np.array([lengths.get(n, np.inf) for n in point_nodes]) / 60.0
        results[line_id] = times_min

    return pd.DataFrame(results, index=points.index)


def assign_nearest_line(
    points: gpd.GeoDataFrame,
    trunk_stops: gpd.GeoDataFrame,
    graph: nx.MultiDiGraph,
    line_col: str = "line_id",
    max_ride_min: float = settings.T_RIDE_MAX_MIN,
) -> gpd.GeoDataFrame:
    """Attach `nearest_line` and `ride_time_to_trunk_min` columns to `points`.

    Points whose nearest line is farther than `max_ride_min` get
    `nearest_line = None` — they are not assignable to any feeder cluster
    under the current ride-time budget and are reported as structurally
    uncovered rather than forced into a cluster.
    """
    times = travel_time_to_each_line(points, trunk_stops, graph, line_col)
    nearest_line = times.idxmin(axis=1)
    nearest_time = times.min(axis=1)

    out = points.copy()
    out["nearest_line"] = nearest_line.where(nearest_time <= max_ride_min, None)
    out["ride_time_to_trunk_min"] = nearest_time.where(nearest_time <= max_ride_min, np.inf)
    return out
