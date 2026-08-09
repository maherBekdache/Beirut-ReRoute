"""Fetch WorldPop Lebanon population-count raster and clip it to the GBA boundary.

Uses the WorldPop constrained, UN-adjusted, 100m population-count product
(2020, the most recent constrained release covering Lebanon at time of
writing) — population COUNTS per pixel, not density, so zonal sums over H3
cells are a direct sum rather than needing area-weighting.

Usage:
    python -m beirut_reroute.data_acquisition.fetch_worldpop
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import rasterio
import rasterio.mask
import requests
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/Population/"
    "Global_2000_2020_Constrained/2020/BSGM/LBN/"
    "lbn_ppp_2020_UNadj_constrained.tif"
)


def download_raster() -> Path:
    out_path = settings.WORLDPOP_RAW_DIR / "lbn_ppp_2020_UNadj_constrained.tif"
    if out_path.exists():
        print(f"Already downloaded -> {out_path}")
        return out_path

    resp = requests.get(WORLDPOP_URL, stream=True, timeout=60)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    with open(out_path, "wb") as f, tqdm(
        total=total, unit="B", unit_scale=True, desc="lbn_ppp_2020"
    ) as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))

    print(f"Downloaded WorldPop raster -> {out_path}")
    return out_path


def clip_to_gba(raster_path: Path) -> Path:
    boundary_path = settings.ADMIN_BOUNDARIES_DIR / "gba_boundary.geojson"
    if not boundary_path.exists():
        raise FileNotFoundError(
            f"{boundary_path} not found — run fetch_osm.py first to generate the GBA boundary."
        )
    boundary = gpd.read_file(boundary_path)

    with rasterio.open(raster_path) as src:
        boundary_native = boundary.to_crs(src.crs)
        # Use the raster's own nodata sentinel (-99999) as the fill value for
        # pixels outside the boundary, so it stays consistent with pixels
        # that were ALREADY nodata inside the boundary (e.g. the Mediterranean
        # covers part of the 15km GBA circle) — filling with 0 instead would
        # make "no data" indistinguishable from "zero population".
        clipped, transform = rasterio.mask.mask(
            src, boundary_native.geometry, crop=True, nodata=src.nodata
        )
        out_meta = src.meta.copy()
        out_meta.update(
            {
                "height": clipped.shape[1],
                "width": clipped.shape[2],
                "transform": transform,
            }
        )

    out_path = settings.PROCESSED_DIR / "gba_population_2020.tif"
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(clipped)

    print(f"Clipped population raster -> {out_path}")
    return out_path


def main() -> None:
    raster_path = download_raster()
    clip_to_gba(raster_path)


if __name__ == "__main__":
    main()
