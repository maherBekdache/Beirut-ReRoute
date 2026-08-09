"""Parse the Lebanese-Bus-Routes KML/KMZ files into cleaned GeoDataFrames.

Verified against the real repo (github.com/LebaneseDevelopers/Lebanese-Bus-Routes,
cloned 2026-08-09): 14 files under "KMLs KMZs/", each a single GDAL layer
containing one route LineString and, for some files, a handful of Point
placemarks (stops/waypoints). Filenames follow two conventions:
  - "Origin - Destination[ - Operator].kml/.kmz"  (intercity/suburban vans)
  - "Bus N[ (note)].kml"                           (Beirut city bus lines)

This is genuinely messy, crowd-sourced, hand-drawn data (see
plan doc "Data Sources") — every parsed route should be visually QA'd
(`viz/maps.py`) before being trusted downstream.

Usage:
    python -m beirut_reroute.data_acquisition.parse_lebanese_bus_routes
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

KML_DIR_NAME = "KMLs KMZs"
BUS_NUMBER_RE = re.compile(r"^Bus\s*(\d+)\s*(?:\((?P<note>.+)\))?", re.IGNORECASE)


def _parse_filename(stem: str) -> dict:
    """Best-effort extraction of route identity from the filename. Crowd-sourced
    filenames are inconsistent, so this is a heuristic, not a guaranteed parse —
    `route_name_raw` always preserves the original for manual review.
    """
    m = BUS_NUMBER_RE.match(stem)
    if m:
        return {
            "route_type": "formal_city_bus",
            "route_number": m.group(1),
            "origin": None,
            "destination": None,
            "operator": None,
            "route_name_raw": stem,
        }

    parts = [p.strip() for p in re.split(r"\s*-\s*", stem) if p.strip()]
    origin = parts[0] if len(parts) >= 1 else None
    destination = parts[1] if len(parts) >= 2 else None
    operator = parts[2] if len(parts) >= 3 else None
    return {
        "route_type": "informal_van",
        "route_number": None,
        "origin": origin,
        "destination": destination,
        "operator": operator,
        "route_name_raw": stem,
    }


def parse_all() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    kml_dir = settings.LEBANESE_BUS_ROUTES_DIR / KML_DIR_NAME
    files = sorted(list(kml_dir.glob("*.kml")) + list(kml_dir.glob("*.kmz")))
    if not files:
        raise FileNotFoundError(
            f"No .kml/.kmz files found in {kml_dir} — copy the "
            f"'{KML_DIR_NAME}' folder from the Lebanese-Bus-Routes repo there first."
        )

    line_rows = []
    stop_rows = []
    for path in files:
        route_id = path.stem
        meta = _parse_filename(route_id)
        gdf = gpd.read_file(path)
        if gdf.crs is None:
            gdf = gdf.set_crs(settings.CRS_LATLON)
        else:
            gdf = gdf.to_crs(settings.CRS_LATLON)

        lines = gdf[gdf.geometry.geom_type == "LineString"]
        points = gdf[gdf.geometry.geom_type == "Point"]

        for _, row in lines.iterrows():
            line_rows.append({"route_id": route_id, "source_file": path.name, **meta, "geometry": row.geometry})
        for i, (_, row) in enumerate(points.iterrows()):
            stop_rows.append(
                {
                    "route_id": route_id,
                    "stop_index": i,
                    "stop_name": row.get("Name"),
                    "source_file": path.name,
                    "geometry": row.geometry,
                }
            )

    lines_gdf = gpd.GeoDataFrame(line_rows, crs=settings.CRS_LATLON)
    stops_gdf = gpd.GeoDataFrame(stop_rows, crs=settings.CRS_LATLON)
    return lines_gdf, stops_gdf


def main() -> None:
    lines_gdf, stops_gdf = parse_all()

    lines_path = settings.INTERIM_DIR / "lebanese_bus_routes_lines.geojson"
    stops_path = settings.INTERIM_DIR / "lebanese_bus_routes_stops.geojson"
    lines_gdf.to_file(lines_path, driver="GeoJSON")
    if len(stops_gdf):
        stops_gdf.to_file(stops_path, driver="GeoJSON")

    print(f"Parsed {len(lines_gdf)} routes ({lines_gdf['route_type'].value_counts().to_dict()}) -> {lines_path}")
    print(f"Parsed {len(stops_gdf)} explicit stop placemarks -> {stops_path}")
    print("NOTE: most files have no explicit stop placemarks — stops for those "
          "routes still need to be derived (e.g. regular spacing along the "
          "LineString) or digitized, and every route should be visually QA'd "
          "before being trusted (see README Known Limitations).")


if __name__ == "__main__":
    main()
