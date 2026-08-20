"""Shared Nominatim geocoding helpers.

Extracted from `ocftc_loader.py`, which still owns the OCFTC-specific
candidate-name retry ladder (stripping "Roundabout"/"Intersection"/etc. and
trying compound-name segments) -- that logic is bespoke to messy transit-stop
names and doesn't belong here. This module is just the low-level HTTP call
plus the on-disk incremental cache, shared by `ocftc_loader.py` and
`national_network/geocode_nodes.py` so the request-throttling/caching logic
isn't duplicated between them.

Both callers still keep their own CACHE_PATH (different files, different
keys) -- only the load/save/query mechanics are shared here.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "beirut-reroute-lebnet-fellows-project (contact: maherbekdash05@gmail.com)"


def load_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    return {}


def save_cache(cache_path: Path, cache: dict) -> None:
    cache_path.write_text(json.dumps(cache, indent=2))


def query_nominatim(
    query: str,
    countrycodes: str | None = "lb",
    viewbox: str | None = None,
) -> tuple[float, float] | None:
    """One Nominatim search request, returns (lat, lon) or None if no match.

    Always sleeps 1s after the request (success, empty result, or error path
    all still count against Nominatim's "max 1 req/s" usage policy), so
    callers don't need to remember to throttle themselves.
    """
    params: dict[str, str | int] = {"q": query, "format": "json", "limit": 1}
    if countrycodes is not None:
        params["countrycodes"] = countrycodes
    if viewbox is not None:
        params["viewbox"] = viewbox
        params["bounded"] = 0

    try:
        resp = requests.get(
            NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=15
        )
        resp.raise_for_status()
        results = resp.json()
    finally:
        time.sleep(1.0)  # Nominatim usage policy: max 1 req/s

    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])
