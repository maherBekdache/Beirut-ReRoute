"""MCLP proof-of-concept: design a feeder network for the B4 trunk line's catchment.

Scoped to ONE trunk line on real data as the integration smoke test called
for in the plan doc's Verification Approach ("run the full pipeline on one
trunk-line cluster first... before scaling to all 11") — B4 is used because
it's the most complete/QA'd OCFTC line (12/13 stops geocoded, 0 flagged).

Simplifications relative to the full citywide design (documented, not
hidden): candidate/demand coverage is straight-line-distance-in-metric-CRS
rather than a full walk-network shortest-path computation (which is what
`accessibility/scoring.py` correctly does elsewhere) — computing true
walk-network distance for every (candidate, demand) pair at this candidate
density is a real performance-engineering task appropriate for the full
9-line run, not this single-cluster proof of concept. A straight-line 700m
threshold approximates the ~10min / 750m walk radius used elsewhere.

Usage:
    python -m beirut_reroute.optimization.run_mclp_b4
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings
from beirut_reroute.optimization.mclp import solve_mclp
from beirut_reroute.optimization.route_chaining import build_feeder_route

CATCHMENT_RADIUS_M = 3000
WALK_COVERAGE_RADIUS_M = 700  # ~ settings.T_WALK_MAX_MIN at WALK_SPEED_KMH
CANDIDATE_MIN_SPACING_M = 150
FEEDER_STOP_BUDGET = 8


def load_b4_stops() -> gpd.GeoDataFrame:
    ocftc = gpd.read_file(settings.INTERIM_DIR / "ocftc_stops_geocoded.geojson")
    b4 = ocftc[(ocftc["line_id"] == "B4") & (~ocftc["qa_flagged_suspect"])].copy()
    return b4.sort_values("stop_order")


def underserved_demand_near_b4(b4_stops_m: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    grid = gpd.read_file(settings.PROCESSED_DIR / "status_quo_accessibility.geojson")
    grid_m = grid.to_crs(settings.CRS_METRIC)
    underserved = grid_m[grid_m["coverage_binary"] == 0].copy()

    b4_union = b4_stops_m.geometry.union_all()
    underserved["dist_to_b4_m"] = underserved.geometry.distance(b4_union)
    near = underserved[underserved["dist_to_b4_m"] <= CATCHMENT_RADIUS_M].copy()
    return near


def downsample_candidates(drive_graph: nx.MultiDiGraph, b4_stops_m: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    nodes_gdf = ox.graph_to_gdfs(drive_graph, edges=False)[["geometry"]].to_crs(settings.CRS_METRIC)
    b4_union = b4_stops_m.geometry.union_all()
    nodes_gdf["dist_to_b4_m"] = nodes_gdf.geometry.distance(b4_union)
    nearby = nodes_gdf[nodes_gdf["dist_to_b4_m"] <= CATCHMENT_RADIUS_M].copy()

    # Grid-snap dedup instead of a pairwise greedy filter: O(n) instead of
    # O(n^2), which matters once "nearby" is thousands of drive-graph nodes
    # (every intersection within 3km of a 9km-long corridor). One candidate
    # survives per CANDIDATE_MIN_SPACING_M grid cell (whichever sorts first).
    nearby["_grid_x"] = (nearby.geometry.x // CANDIDATE_MIN_SPACING_M).astype(int)
    nearby["_grid_y"] = (nearby.geometry.y // CANDIDATE_MIN_SPACING_M).astype(int)
    deduped = nearby.drop_duplicates(subset=["_grid_x", "_grid_y"])
    return deduped.drop(columns=["_grid_x", "_grid_y"])


def main() -> None:
    b4_stops = load_b4_stops()
    b4_stops_m = b4_stops.to_crs(settings.CRS_METRIC)
    print(f"B4 trunk stops: {len(b4_stops)}")

    demand = underserved_demand_near_b4(b4_stops_m)
    print(f"Underserved H3 cells within {CATCHMENT_RADIUS_M}m of B4: {len(demand)} "
          f"(population {demand['population'].sum():,.0f})")

    if len(demand) == 0:
        print("No underserved demand near B4 — nothing for MCLP to optimize. Stopping.")
        return

    drive_graph = ox.load_graphml(settings.PROCESSED_DIR / "gba_drive_congested.graphml")
    candidates = downsample_candidates(drive_graph, b4_stops_m)
    print(f"Candidate feeder stops after {CANDIDATE_MIN_SPACING_M}m-spacing downsample: {len(candidates)}")

    demand_weights = {str(i): float(w) for i, w in zip(demand.index, demand["population"])}
    coverage_sets: dict[str, set[str]] = {str(i): set() for i in demand.index}

    demand_idx = list(demand.index)
    candidate_idx = list(candidates.index)
    demand_tree = cKDTree([(p.x, p.y) for p in demand.geometry.centroid])
    candidate_tree = cKDTree([(p.x, p.y) for p in candidates.geometry])
    pairs = demand_tree.query_ball_tree(candidate_tree, r=WALK_COVERAGE_RADIUS_M)
    for d_pos, c_positions in enumerate(pairs):
        d_key = str(demand_idx[d_pos])
        coverage_sets[d_key] = {str(candidate_idx[c_pos]) for c_pos in c_positions}

    n_coverable = sum(1 for s in coverage_sets.values() if s)
    print(f"Demand cells with >=1 candidate in range: {n_coverable}/{len(demand)}")

    result = solve_mclp(demand_weights, coverage_sets, budget=FEEDER_STOP_BUDGET, solver="cbc")
    print(f"\nMCLP result (budget={FEEDER_STOP_BUDGET} stops, solver status={result.status}):")
    print(f"  Selected {len(result.selected_candidates)} feeder stops")
    print(f"  Newly-covered population: ~{result.covered_weight:,.0f} / "
          f"{result.total_weight:,.0f} underserved-near-B4 ({result.coverage_fraction:.1%})")

    if not result.selected_candidates:
        print("No candidates selected — stopping before route chaining.")
        return

    selected_geoms = candidates.loc[[int(j) for j in result.selected_candidates]]
    selected_latlon = selected_geoms.to_crs(settings.CRS_LATLON)

    trunk_access_point = b4_stops.iloc[0].geometry  # Lebanese University / Hadath end
    feeder_route = build_feeder_route(
        list(selected_latlon.geometry), trunk_access_point, drive_graph
    )

    out_stops = gpd.GeoDataFrame(
        {"stop_rank": range(1, len(selected_latlon) + 1)},
        geometry=list(selected_latlon.geometry), crs=settings.CRS_LATLON,
    )
    out_stops_path = settings.PROCESSED_DIR / "b4_feeder_stops.geojson"
    out_stops.to_file(out_stops_path, driver="GeoJSON")

    out_route = gpd.GeoDataFrame({"line_id": ["B4_feeder"]}, geometry=[feeder_route], crs=settings.CRS_LATLON)
    out_route_path = settings.PROCESSED_DIR / "b4_feeder_route.geojson"
    out_route.to_file(out_route_path, driver="GeoJSON")

    print(f"\nSaved feeder stops -> {out_stops_path}")
    print(f"Saved feeder route -> {out_route_path}")


if __name__ == "__main__":
    main()
