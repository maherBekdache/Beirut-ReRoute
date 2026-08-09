"""Geocode manually-transcribed OCFTC/ACTC stop names into real coordinates.

See `data/raw/ocftc_digitized/README.md` for why this manual-transcription +
geocoding approach was chosen over tracing a map image (no GTFS/GeoJSON is
publicly available — verified against OSM Overpass, AUB Beirut Urban Lab's
open data platform, and the World Bank GBA transport project ESIA).

Uses OSM Nominatim directly (no API key needed), respecting its usage policy:
max 1 request/second and an identifying User-Agent. Results are cached to
disk so re-runs after adding more lines to the CSV don't re-geocode stops
that already resolved.

Usage:
    python -m beirut_reroute.data_acquisition.ocftc_loader
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "beirut-reroute-lebnet-fellows-project (contact: maherbekdash05@gmail.com)"
CACHE_PATH = settings.OCFTC_DIGITIZED_DIR / "geocode_cache.json"


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def geocode(query: str, cache: dict) -> tuple[float, float] | None:
    if query in cache:
        return tuple(cache[query]) if cache[query] else None

    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json()
    time.sleep(1.0)  # Nominatim usage policy: max 1 req/s

    if not results:
        cache[query] = None
        return None

    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    cache[query] = [lat, lon]
    return lat, lon


def load_and_geocode_stops() -> gpd.GeoDataFrame:
    csv_path = settings.OCFTC_DIGITIZED_DIR / "ocftc_stops_manual.csv"
    stops = pd.read_csv(csv_path)
    cache = _load_cache()

    lats, lons, resolved = [], [], []
    for _, row in stops.iterrows():
        result = geocode(row["geocode_query"], cache)
        if result is None:
            print(f"WARNING: could not geocode '{row['geocode_query']}' "
                  f"(line {row['line_id']} stop {row['stop_order']} '{row['stop_name']}')")
            lats.append(None)
            lons.append(None)
            resolved.append(False)
        else:
            lats.append(result[0])
            lons.append(result[1])
            resolved.append(True)

    _save_cache(cache)

    stops["lat"] = lats
    stops["lon"] = lons
    stops["geocoded"] = resolved

    unresolved = stops[~stops["geocoded"]]
    if len(unresolved):
        print(f"{len(unresolved)}/{len(stops)} stops failed to geocode — "
              f"these need a manual coordinate fix before use downstream.")

    geo_stops = stops[stops["geocoded"]].copy()
    geometry = [Point(lon, lat) for lat, lon in zip(geo_stops["lat"], geo_stops["lon"])]
    return gpd.GeoDataFrame(geo_stops, geometry=geometry, crs=settings.CRS_LATLON)


def main() -> None:
    stops_gdf = load_and_geocode_stops()
    out_path = settings.INTERIM_DIR / "ocftc_stops_geocoded.geojson"
    stops_gdf.to_file(out_path, driver="GeoJSON")
    print(f"Geocoded {len(stops_gdf)} OCFTC stops across "
          f"{stops_gdf['line_id'].nunique()} line(s) -> {out_path}")
    print("Visually QA every point against the real route before trusting it "
          "(Nominatim can mismatch generic names like roundabouts).")


if __name__ == "__main__":
    main()
