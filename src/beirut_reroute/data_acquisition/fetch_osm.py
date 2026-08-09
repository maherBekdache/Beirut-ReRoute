"""Fetch the Greater Beirut Area (GBA) boundary and OSM drive/walk graphs.

Usage:
    python -m beirut_reroute.data_acquisition.fetch_osm
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings


def build_gba_boundary() -> gpd.GeoDataFrame:
    """Circle-buffer boundary around Beirut Central District (see settings docstring)."""
    lat, lon = settings.GBA_CENTER_LATLON
    center = gpd.GeoSeries([Point(lon, lat)], crs=settings.CRS_LATLON)
    center_m = center.to_crs(settings.CRS_METRIC)
    boundary_m = center_m.buffer(settings.GBA_RADIUS_M)
    boundary = gpd.GeoDataFrame(
        {"name": ["Greater Beirut Area (15km radius)"]},
        geometry=boundary_m.to_crs(settings.CRS_LATLON),
        crs=settings.CRS_LATLON,
    )
    return boundary


def fetch_and_save_boundary() -> gpd.GeoDataFrame:
    out_path = settings.ADMIN_BOUNDARIES_DIR / "gba_boundary.geojson"
    boundary = build_gba_boundary()
    boundary.to_file(out_path, driver="GeoJSON")
    print(f"Saved GBA boundary -> {out_path}")
    return boundary


def fetch_and_save_graphs(boundary: gpd.GeoDataFrame) -> None:
    polygon = boundary.geometry.iloc[0]

    print("Downloading drive network from OSM (this can take a few minutes)...")
    drive_graph = ox.graph_from_polygon(polygon, network_type="drive", simplify=True)
    drive_path = settings.OSM_RAW_DIR / "gba_drive.graphml"
    ox.save_graphml(drive_graph, drive_path)
    print(f"Saved drive graph ({len(drive_graph.nodes)} nodes, "
          f"{len(drive_graph.edges)} edges) -> {drive_path}")

    print("Downloading walk network from OSM...")
    walk_graph = ox.graph_from_polygon(polygon, network_type="walk", simplify=True)
    walk_path = settings.OSM_RAW_DIR / "gba_walk.graphml"
    ox.save_graphml(walk_graph, walk_path)
    print(f"Saved walk graph ({len(walk_graph.nodes)} nodes, "
          f"{len(walk_graph.edges)} edges) -> {walk_path}")


def main() -> None:
    boundary = fetch_and_save_boundary()
    fetch_and_save_graphs(boundary)


if __name__ == "__main__":
    main()
