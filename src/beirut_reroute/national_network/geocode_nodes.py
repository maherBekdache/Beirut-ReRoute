"""Geocode the Layer A national/regional network's node list.

See `data/raw/national_network/README.md` for what these 18 nodes are and
why they're there. Unlike `ocftc_loader.py`'s messy roundabout/intersection
stop names, every node here is a real, well-known place name (a city, port,
or border crossing), so no retry ladder is needed -- a plain
"<name>, <country>" query resolves all of them. `beirut_hub` is the one
exception: it reuses `settings.GBA_CENTER_LATLON` directly rather than being
geocoded, since it's meant to represent the same Beirut Central District
point the rest of the pipeline (Layer B) is built around, not whatever point
Nominatim happens to return for the bare word "Beirut".

Usage:
    python -m beirut_reroute.national_network.geocode_nodes
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings
from beirut_reroute.data_acquisition.geocoding import load_cache, query_nominatim, save_cache

CACHE_PATH = settings.NATIONAL_NETWORK_DIR / "geocode_cache.json"
BEIRUT_HUB_ID = "beirut_hub"


def geocode_node(name: str, country: str, cache: dict) -> tuple[float, float] | None:
    """Returns (lat, lon) or None. Cached by "<name>, <country>" so re-runs
    don't re-hit Nominatim."""
    cache_key = f"{name}, {country}"
    if cache_key in cache:
        cached = cache[cache_key]
        return tuple(cached) if cached else None

    result = query_nominatim(cache_key, countrycodes=None)
    cache[cache_key] = list(result) if result else None
    save_cache(CACHE_PATH, cache)  # incremental, same reasoning as ocftc_loader
    return result


def geocode_all_nodes() -> gpd.GeoDataFrame:
    nodes = pd.read_csv(settings.NATIONAL_NODES_CSV)
    cache = load_cache(CACHE_PATH)

    lat_center, lon_center = settings.GBA_CENTER_LATLON

    lats, lons, resolved = [], [], []
    for _, row in nodes.iterrows():
        if row["id"] == BEIRUT_HUB_ID:
            lats.append(lat_center)
            lons.append(lon_center)
            resolved.append(True)
            continue

        result = geocode_node(row["name"], row["country"], cache)
        if result is None:
            print(f"WARNING: could not geocode node '{row['id']}' ({row['name']}, {row['country']})")
            lats.append(None)
            lons.append(None)
            resolved.append(False)
        else:
            lats.append(result[0])
            lons.append(result[1])
            resolved.append(True)

    nodes["lat"] = lats
    nodes["lon"] = lons
    nodes["geocoded"] = resolved

    unresolved = nodes[~nodes["geocoded"]]
    if len(unresolved):
        print(f"{len(unresolved)}/{len(nodes)} nodes failed to geocode: "
              f"{list(unresolved['id'])} — these need a manual coordinate "
              f"fix in nodes_manual.csv or geocode_cache.json before use downstream.")

    geo_nodes = nodes[nodes["geocoded"]].copy()
    geometry = [Point(lon, lat) for lat, lon in zip(geo_nodes["lat"], geo_nodes["lon"])]
    return gpd.GeoDataFrame(geo_nodes, geometry=geometry, crs=settings.CRS_LATLON)


def main() -> None:
    nodes_gdf = geocode_all_nodes()
    out_path = settings.INTERIM_DIR / "national_nodes_geocoded.geojson"
    nodes_gdf.to_file(out_path, driver="GeoJSON")
    print(f"Geocoded {len(nodes_gdf)} national-network nodes -> {out_path}")


if __name__ == "__main__":
    main()
