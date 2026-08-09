"""Build an H3 hex grid over the GBA boundary and attach population per cell.

Usage:
    python -m beirut_reroute.processing.build_zones
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import h3
import pandas as pd
import rasterio
from rasterstats import zonal_stats
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings


def _shapely_polygon_to_h3_poly(polygon: Polygon) -> h3.LatLngPoly:
    """h3-py v4 expects rings as (lat, lng) tuples; shapely stores (lng, lat)."""
    outer = [(lat, lng) for lng, lat in polygon.exterior.coords]
    holes = [
        [(lat, lng) for lng, lat in interior.coords] for interior in polygon.interiors
    ]
    return h3.LatLngPoly(outer, *holes)


def _cell_to_shapely_polygon(cell: str) -> Polygon:
    boundary = h3.cell_to_boundary(cell)  # tuple of (lat, lng)
    return Polygon([(lng, lat) for lat, lng in boundary])


def build_h3_grid() -> gpd.GeoDataFrame:
    boundary_path = settings.ADMIN_BOUNDARIES_DIR / "gba_boundary.geojson"
    boundary = gpd.read_file(boundary_path)
    polygon = boundary.geometry.iloc[0]

    h3_poly = _shapely_polygon_to_h3_poly(polygon)
    cells = h3.polygon_to_cells(h3_poly, settings.H3_RESOLUTION)
    print(f"Generated {len(cells)} H3 cells at resolution {settings.H3_RESOLUTION}")

    records = []
    for cell in cells:
        lat, lng = h3.cell_to_latlng(cell)
        records.append(
            {
                "h3_id": cell,
                "centroid_lat": lat,
                "centroid_lon": lng,
                "geometry": _cell_to_shapely_polygon(cell),
            }
        )

    grid = gpd.GeoDataFrame(records, crs=settings.CRS_LATLON)
    return grid


def attach_population(grid: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    pop_raster_path = settings.PROCESSED_DIR / "gba_population_2020.tif"
    if not pop_raster_path.exists():
        raise FileNotFoundError(
            f"{pop_raster_path} not found — run fetch_worldpop.py first."
        )

    with rasterio.open(pop_raster_path) as src:
        raster_nodata = src.nodata

    stats = zonal_stats(
        grid.geometry,
        str(pop_raster_path),
        stats=["sum"],
        nodata=raster_nodata,
    )
    grid["population"] = [s["sum"] if s["sum"] is not None else 0.0 for s in stats]
    assert (grid["population"] >= 0).all(), "negative population sum indicates a nodata-handling bug"
    return grid


def main() -> None:
    grid = build_h3_grid()
    grid = attach_population(grid)

    out_path = settings.PROCESSED_DIR / "gba_h3_grid.geojson"
    grid.to_file(out_path, driver="GeoJSON")
    total_pop = grid["population"].sum()
    print(f"Saved {len(grid)} H3 cells (total population ~{total_pop:,.0f}) -> {out_path}")


if __name__ == "__main__":
    main()
