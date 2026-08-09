"""Scale the B4 MCLP proof-of-concept (run_mclp_b4.py) to all real OCFTC lines.

Unlike run_mclp_b4.py (which finds demand purely by distance to B4's own
stops), this uses `clustering.assign_nearest_line` to assign every
underserved H3 cell to its nearest trunk line by real DRIVE-NETWORK travel
time — computed once, globally, across all lines — so a cell equidistant
between e.g. B1 and B3 isn't double-counted as "newly covered" by both
lines' independent feeder networks. Candidates are still scoped per-line by
straight-line proximity to that line's own stops (a candidate feeder stop
only makes sense sited near the line it's meant to feed).

Per-line stop budget is allocated proportional to that line's assigned
underserved population (min 3, max 15) rather than a fixed budget for every
line — a lightweight version of the plan doc's "allocate budget proportional
to uncovered population per cluster", without a full joint citywide
optimization.

Usage:
    python -m beirut_reroute.optimization.run_mclp_all_lines
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
from beirut_reroute.optimization.clustering import assign_nearest_line
from beirut_reroute.optimization.mclp import solve_mclp
from beirut_reroute.optimization.route_chaining import build_feeder_route

CATCHMENT_RADIUS_M = 3000
WALK_COVERAGE_RADIUS_M = 700
CANDIDATE_MIN_SPACING_M = 150
MIN_BUDGET, MAX_BUDGET = 3, 15
TOTAL_BUDGET_DIVISOR = 15_000  # ~1 feeder stop per 15k uncovered people, then clamped


def load_trusted_stops() -> gpd.GeoDataFrame:
    ocftc = gpd.read_file(settings.INTERIM_DIR / "ocftc_stops_geocoded.geojson")
    return ocftc[~ocftc["qa_flagged_suspect"]].copy()


def downsample_candidates_for_line(
    drive_graph: nx.MultiDiGraph, line_stops_m: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    nodes_gdf = ox.graph_to_gdfs(drive_graph, edges=False)[["geometry"]].to_crs(settings.CRS_METRIC)
    line_union = line_stops_m.geometry.union_all()
    nodes_gdf["dist_m"] = nodes_gdf.geometry.distance(line_union)
    nearby = nodes_gdf[nodes_gdf["dist_m"] <= CATCHMENT_RADIUS_M].copy()

    nearby["_gx"] = (nearby.geometry.x // CANDIDATE_MIN_SPACING_M).astype(int)
    nearby["_gy"] = (nearby.geometry.y // CANDIDATE_MIN_SPACING_M).astype(int)
    return nearby.drop_duplicates(subset=["_gx", "_gy"]).drop(columns=["_gx", "_gy"])


def run_mclp_for_line(
    line_id: str,
    demand_m: gpd.GeoDataFrame,
    line_stops: gpd.GeoDataFrame,
    drive_graph: nx.MultiDiGraph,
) -> dict | None:
    line_stops_m = line_stops.to_crs(settings.CRS_METRIC)
    candidates = downsample_candidates_for_line(drive_graph, line_stops_m)

    demand_weights = {str(i): float(w) for i, w in zip(demand_m.index, demand_m["population"])}
    demand_idx = list(demand_m.index)
    candidate_idx = list(candidates.index)
    demand_tree = cKDTree([(p.x, p.y) for p in demand_m.geometry.centroid])
    candidate_tree = cKDTree([(p.x, p.y) for p in candidates.geometry])
    pairs = demand_tree.query_ball_tree(candidate_tree, r=WALK_COVERAGE_RADIUS_M)
    coverage_sets = {
        str(demand_idx[d_pos]): {str(candidate_idx[c]) for c in c_positions}
        for d_pos, c_positions in enumerate(pairs)
    }

    total_uncovered_pop = demand_m["population"].sum()
    budget = int(min(MAX_BUDGET, max(MIN_BUDGET, round(total_uncovered_pop / TOTAL_BUDGET_DIVISOR))))

    result = solve_mclp(demand_weights, coverage_sets, budget=budget, solver="cbc")
    print(f"  [{line_id}] demand={len(demand_m)} cells (pop {total_uncovered_pop:,.0f}), "
          f"candidates={len(candidates)}, budget={budget} -> "
          f"selected {len(result.selected_candidates)}, "
          f"newly covers {result.covered_weight:,.0f} ({result.coverage_fraction:.1%})")

    if not result.selected_candidates:
        return None

    selected_latlon = candidates.loc[[int(j) for j in result.selected_candidates]].to_crs(settings.CRS_LATLON)
    trunk_access_point = line_stops.sort_values("stop_order").iloc[0].geometry

    try:
        feeder_route = build_feeder_route(list(selected_latlon.geometry), trunk_access_point, drive_graph)
    except Exception as exc:  # noqa: BLE001 - report and keep going with other lines
        print(f"  [{line_id}] route chaining failed: {exc}")
        feeder_route = None

    return {
        "line_id": line_id,
        "budget": budget,
        "selected_stops": selected_latlon,
        "feeder_route": feeder_route,
        "covered_weight": result.covered_weight,
        "total_weight": result.total_weight,
    }


def main() -> None:
    grid = gpd.read_file(settings.PROCESSED_DIR / "status_quo_accessibility.geojson")
    underserved = grid[grid["coverage_binary"] == 0].copy()
    stops = load_trusted_stops()
    drive_graph = ox.load_graphml(settings.PROCESSED_DIR / "gba_drive_congested.graphml")

    line_ids = sorted(stops["line_id"].unique())
    print(f"Trusted OCFTC stops across {len(line_ids)} lines: {line_ids}")

    print("\nAssigning each underserved H3 cell to its nearest trunk line "
          "(real drive-network travel time, prevents double-counting)...")
    # Use the exact H3 centroid columns (from build_zones.py's h3.cell_to_latlng)
    # rather than shapely .centroid on unprojected lat/lon polygons, which is
    # both a correctness warning and a slightly worse approximation.
    from shapely.geometry import Point
    underserved_pts = underserved.copy()
    underserved_pts["geometry"] = [
        Point(lon, lat) for lon, lat in zip(underserved_pts["centroid_lon"], underserved_pts["centroid_lat"])
    ]
    assigned = assign_nearest_line(underserved_pts, stops, drive_graph, line_col="line_id")
    n_assigned = assigned["nearest_line"].notna().sum()
    print(f"{n_assigned}/{len(assigned)} underserved cells assigned to a line "
          f"within {settings.T_RIDE_MAX_MIN} min ride time")

    all_stops_out, all_routes_out = [], []
    total_newly_covered, total_uncovered_considered = 0.0, 0.0

    print("\nSolving MCLP per line:")
    for line_id in line_ids:
        line_stops = stops[stops["line_id"] == line_id]
        if len(line_stops) < 2:
            print(f"  [{line_id}] only {len(line_stops)} trusted stop(s) — skipping (can't chain a route)")
            continue

        line_demand_ids = assigned[assigned["nearest_line"] == line_id].index
        if len(line_demand_ids) == 0:
            print(f"  [{line_id}] no underserved demand assigned to this line — skipping")
            continue

        demand_m = underserved.loc[line_demand_ids].to_crs(settings.CRS_METRIC)
        total_uncovered_considered += demand_m["population"].sum()

        out = run_mclp_for_line(line_id, demand_m, line_stops, drive_graph)
        if out is None:
            continue

        total_newly_covered += out["covered_weight"]
        stops_gdf = out["selected_stops"].copy()
        stops_gdf["line_id"] = line_id
        stops_gdf["stop_rank"] = range(1, len(stops_gdf) + 1)
        all_stops_out.append(stops_gdf[["line_id", "stop_rank", "geometry"]])
        if out["feeder_route"] is not None:
            all_routes_out.append({"line_id": line_id, "geometry": out["feeder_route"]})

    if all_stops_out:
        combined_stops = gpd.GeoDataFrame(pd.concat(all_stops_out, ignore_index=True), crs=settings.CRS_LATLON)
        out_path = settings.PROCESSED_DIR / "feeder_stops_all_lines.geojson"
        combined_stops.to_file(out_path, driver="GeoJSON")
        print(f"\nSaved {len(combined_stops)} feeder stops across "
              f"{combined_stops['line_id'].nunique()} lines -> {out_path}")

    if all_routes_out:
        combined_routes = gpd.GeoDataFrame(all_routes_out, crs=settings.CRS_LATLON)
        out_path = settings.PROCESSED_DIR / "feeder_routes_all_lines.geojson"
        combined_routes.to_file(out_path, driver="GeoJSON")
        print(f"Saved {len(combined_routes)} feeder routes -> {out_path}")

    print(f"\nCitywide (of underserved cells with an assignable line): "
          f"{total_newly_covered:,.0f} / {total_uncovered_considered:,.0f} "
          f"newly covered ({total_newly_covered / total_uncovered_considered:.1%})"
          if total_uncovered_considered else "No assignable underserved demand found.")


if __name__ == "__main__":
    main()
