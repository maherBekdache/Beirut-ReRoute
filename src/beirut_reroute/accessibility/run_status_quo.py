"""Run status-quo accessibility scoring on the real GBA data pulled so far.

"Current system" = informal-route proxy stops (hail-anywhere van network) +
trusted OCFTC/ACTC trunk stops (qa_flagged_suspect excluded) — i.e. whatever
a rider can walk to today, with NO coordinated feeder network connecting the
two layers (that's exactly the gap this project's MCLP step addresses).

Usage:
    python -m beirut_reroute.accessibility.run_status_quo
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings
from beirut_reroute.accessibility import scoring


def load_current_system_stops() -> gpd.GeoDataFrame:
    informal = gpd.read_file(settings.PROCESSED_DIR / "informal_route_proxy_stops.geojson")

    ocftc_path = settings.INTERIM_DIR / "ocftc_stops_geocoded.geojson"
    if ocftc_path.exists():
        ocftc = gpd.read_file(ocftc_path)
        if "qa_flagged_suspect" in ocftc.columns:
            n_before = len(ocftc)
            ocftc = ocftc[~ocftc["qa_flagged_suspect"]]
            print(f"Excluding {n_before - len(ocftc)} qa_flagged_suspect OCFTC stops from scoring")
        ocftc = ocftc[["geometry"]].copy()
        ocftc["route_id"] = "OCFTC_TRUNK"
        ocftc["route_type"] = "formal_trunk"
    else:
        ocftc = gpd.GeoDataFrame(columns=["geometry", "route_id", "route_type"], crs=settings.CRS_LATLON)

    combined = pd.concat(
        [informal[["geometry", "route_id", "route_type"]], ocftc], ignore_index=True
    )
    return gpd.GeoDataFrame(combined, crs=settings.CRS_LATLON)


def main() -> None:
    grid = gpd.read_file(settings.PROCESSED_DIR / "gba_h3_grid.geojson")
    walk_graph = ox.load_graphml(settings.PROCESSED_DIR / "gba_walk_timed.graphml")
    stops = load_current_system_stops()

    print(f"Grid: {len(grid)} H3 cells, total population {grid['population'].sum():,.0f}")
    print(f"Current-system stops: {len(stops)} "
          f"({(stops['route_type'] == 'formal_trunk').sum()} trunk, "
          f"{(stops['route_type'] != 'formal_trunk').sum()} informal-proxy)")

    result = scoring.run(grid, stops, walk_graph)

    print(f"\nStatus-quo population-weighted CoverageScore "
          f"(walk <= {settings.T_MAX_MIN} min to any stop): {result.coverage_score:.1%}")

    covered_pop = (result.grid["population"] * result.grid["coverage_binary"]).sum()
    total_pop = result.grid["population"].sum()
    uncovered_pop = total_pop - covered_pop
    print(f"  Covered population:   ~{covered_pop:,.0f}")
    print(f"  Uncovered population: ~{uncovered_pop:,.0f}")

    out_path = settings.PROCESSED_DIR / "status_quo_accessibility.geojson"
    result.grid.to_file(out_path, driver="GeoJSON")
    print(f"\nSaved scored grid -> {out_path}")


if __name__ == "__main__":
    main()
