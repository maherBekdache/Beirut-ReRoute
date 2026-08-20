"""Geocode manually-transcribed OCFTC/ACTC stop names into real coordinates.

See `data/raw/ocftc_digitized/README.md` for why this manual-transcription +
geocoding approach was chosen over tracing a map image (no GTFS/GeoJSON is
publicly available — verified against OSM Overpass, AUB Beirut Urban Lab's
open data platform, and the World Bank GBA transport project ESIA).

Uses OSM Nominatim directly (no API key needed), respecting its usage policy:
max 1 request/second and an identifying User-Agent. Results are cached to
disk INCREMENTALLY (after every request, not just at the end) so a crash or
interruption partway through a large batch doesn't throw away already-paid-for
API calls.

Query strategy: many stops (e.g. "Dora") are administratively in Metn/Baabda
suburbs, not "Beirut" proper, so hard-appending ", Beirut, Lebanon" as a
literal token made Nominatim's search fail even for well-known places. Instead
we try a short retry ladder (bare name -> name + ", Lebanon") with
`countrycodes=lb` and a soft viewbox bias toward the GBA boundary, without
requiring literal containment in "Beirut".

Usage:
    python -m beirut_reroute.data_acquisition.ocftc_loader
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings
from beirut_reroute.data_acquisition.geocoding import load_cache, query_nominatim, save_cache

# Windows' default console codepage (cp1252) can't print some transliterated
# place names; make stdout tolerant instead of crashing mid-batch.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE_PATH = settings.OCFTC_DIGITIZED_DIR / "geocode_cache.json"


def _gba_viewbox() -> str:
    boundary_path = settings.ADMIN_BOUNDARIES_DIR / "gba_boundary.geojson"
    boundary = gpd.read_file(boundary_path)
    minx, miny, maxx, maxy = boundary.total_bounds
    return f"{minx},{maxy},{maxx},{miny}"  # Nominatim order: left,top,right,bottom


# Generic transit-stop descriptor words that are almost never a literal OSM
# place name (e.g. OSM has a node named "Dora" / "الدورة", not "Dora
# Roundabout") — stripped as a fallback query. Order matters: longer/more
# specific phrases first so "Pedestrian Bridge" doesn't get half-stripped
# down to a stray "Bridge" match.
_GENERIC_SUFFIXES = [
    "Pedestrian Bridge", "Bridge Intersection", "Main Road",
    "Roundabout", "Intersection", "Interscetion", "Crossroads",
    "Bridge", "Municipality", "Entrance",
]
_SUFFIX_RE = re.compile(
    r"\s*\b(" + "|".join(re.escape(s) for s in _GENERIC_SUFFIXES) + r")\s*$",
    re.IGNORECASE,
)


def _candidate_names(stop_name: str) -> list[str]:
    """Query candidates in priority order: full name, name with a trailing
    generic descriptor stripped, and (for compound "A / B ..." names) just
    the first segment with the same stripping applied. Deduplicated,
    empty/too-short candidates dropped.
    """
    candidates = [stop_name]

    stripped = _SUFFIX_RE.sub("", stop_name).strip()
    if stripped and stripped != stop_name:
        candidates.append(stripped)

    if "/" in stop_name:
        first_segment = stop_name.split("/")[0].strip()
        first_segment_stripped = _SUFFIX_RE.sub("", first_segment).strip()
        for c in (first_segment, first_segment_stripped):
            if c:
                candidates.append(c)

    seen = set()
    unique = []
    for c in candidates:
        if len(c) >= 3 and c.lower() not in seen:
            seen.add(c.lower())
            unique.append(c)
    return unique


def geocode(stop_name: str, viewbox: str, cache: dict) -> tuple[float, float, str] | None:
    """Returns (lat, lon, matched_query) — matched_query is kept in the output
    so a QA pass can tell at a glance which stops resolved via the exact name
    vs. a stripped-down fallback (higher mismatch risk)."""
    cache_key = stop_name
    if cache_key in cache:
        cached = cache[cache_key]
        return tuple(cached) if cached else None

    for name_variant in _candidate_names(stop_name):
        for query in (name_variant, f"{name_variant}, Lebanon"):
            result = query_nominatim(query, countrycodes="lb", viewbox=viewbox)
            if result is not None:
                cache[cache_key] = [result[0], result[1], name_variant]
                save_cache(CACHE_PATH, cache)  # incremental — survive a mid-batch crash
                return result[0], result[1], name_variant

    cache[cache_key] = None
    save_cache(CACHE_PATH, cache)
    return None


def load_and_geocode_stops() -> gpd.GeoDataFrame:
    csv_path = settings.OCFTC_DIGITIZED_DIR / "ocftc_stops_manual.csv"
    stops = pd.read_csv(csv_path)
    cache = load_cache(CACHE_PATH)
    viewbox = _gba_viewbox()

    lats, lons, resolved, matched_via = [], [], [], []
    for _, row in stops.iterrows():
        result = geocode(row["stop_name"], viewbox, cache)
        if result is None:
            print(f"WARNING: could not geocode line {row['line_id']} stop "
                  f"{row['stop_order']} '{row['stop_name']}'")
            lats.append(None)
            lons.append(None)
            resolved.append(False)
            matched_via.append(None)
        else:
            lats.append(result[0])
            lons.append(result[1])
            resolved.append(True)
            matched_via.append(result[2])
            if result[2] != row["stop_name"]:
                print(f"NOTE: line {row['line_id']} stop {row['stop_order']} "
                      f"'{row['stop_name']}' matched via fallback name "
                      f"'{result[2]}' — verify on the QA map.")

    stops["lat"] = lats
    stops["lon"] = lons
    stops["geocoded"] = resolved
    stops["matched_via"] = matched_via

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
