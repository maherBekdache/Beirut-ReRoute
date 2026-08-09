"""Scrape ordered stop-name lists for every ACTCPT (OCFTC) line from transitapp.com
and append them to `data/raw/ocftc_digitized/ocftc_stops_manual.csv`.

This is the manual-digitization source documented in
`data/raw/ocftc_digitized/README.md`: no public GTFS/GeoJSON exists for the
network, but transitapp.com server-renders an ordered stop list per line
(under `id="stopslist"`, each stop a `<span class="text-pretty">NAME</span>`)
that we transcribe here and geocode separately in `ocftc_loader.py`. Only
stop NAMES are scraped — no coordinates are embedded in the page, and no
private API is used.

Usage:
    python -m beirut_reroute.data_acquisition.fetch_actcpt_stops
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

BASE_URL = "https://transitapp.com/en/region/beirut/actcpt/bus-{slug}"
USER_AGENT = "Mozilla/5.0 (beirut-reroute-lebnet-fellows-project; contact: maherbekdash05@gmail.com)"

# Confirmed via the ACTCPT region page's actual <a href> list (2026-08-09):
# https://transitapp.com/en/region/beirut/actcpt
LINE_SLUGS = {
    "B1": "b1",
    "B2": "b2",
    "B3": "b3",
    "B5": "b5",
    "B6-ML2": "b6-ml2",
    "ML1": "ml1",
    "ML3": "ml3",
    "ML4": "ml4",
}

STOPSLIST_RE = re.compile(r'id="stopslist"(.*?)</ul>', re.DOTALL)
STOP_NAME_RE = re.compile(r'data-testid="list-item".*?<span class="text-pretty">([^<]+)</span>', re.DOTALL)


def fetch_line_stops(slug: str) -> list[str]:
    resp = requests.get(
        BASE_URL.format(slug=slug), headers={"User-Agent": USER_AGENT}, timeout=20
    )
    resp.raise_for_status()
    html = resp.text

    block_match = STOPSLIST_RE.search(html)
    if not block_match:
        raise ValueError(f"Could not find #stopslist block for slug={slug!r}")

    names = STOP_NAME_RE.findall(block_match.group(1))
    # Unescape a few common HTML entities that show up in place names.
    names = [n.replace("&amp;", "&").replace("&#x27;", "'").strip() for n in names]
    return names


def main() -> None:
    csv_path = settings.OCFTC_DIGITIZED_DIR / "ocftc_stops_manual.csv"
    existing = pd.read_csv(csv_path)
    already_have = set(existing["line_id"].unique())

    new_rows = []
    for line_id, slug in LINE_SLUGS.items():
        if line_id in already_have:
            print(f"Skipping {line_id} — already in {csv_path.name}")
            continue

        print(f"Fetching {line_id} (bus-{slug})...")
        try:
            names = fetch_line_stops(slug)
        except Exception as exc:  # noqa: BLE001 - report and continue with other lines
            print(f"  FAILED: {exc}")
            continue

        print(f"  {len(names)} stops: {names[:3]}...")
        for i, name in enumerate(names, start=1):
            new_rows.append(
                {
                    "line_id": line_id,
                    "stop_order": i,
                    "stop_name": name,
                    "geocode_query": f"{name}, Beirut, Lebanon",
                    "source": f"transitapp.com/en/region/beirut/actcpt/bus-{slug}",
                }
            )
        time.sleep(1.0)  # be polite to transitapp.com

    if not new_rows:
        print("No new lines to add.")
        return

    combined = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    combined.to_csv(csv_path, index=False)
    print(f"Appended {len(new_rows)} stops across {len(LINE_SLUGS) - len(already_have.intersection(LINE_SLUGS))} "
          f"new lines -> {csv_path}")


if __name__ == "__main__":
    main()
