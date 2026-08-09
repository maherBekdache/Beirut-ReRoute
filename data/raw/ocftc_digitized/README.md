# OCFTC/ACTC trunk network — manual digitization tracker

No public GTFS/GeoJSON exists for the 2024-launched ACTCPT network (checked:
OSM Overpass `route=bus` relations for Lebanon — only 1 old pre-2024 OCFTC
minibus line tagged, nothing for B1-B7/ML1-4; AUB Beirut Urban Lab open data
platform — basemap/parcel/building layers only, no transit; World Bank
Greater Beirut Public Transport Project ESIA — describes future BRT corridor
alignments, not today's mixed-traffic B-lines).

**transitapp.com has ordered, named stop lists per line** (from GTFS data
Transit App ingested from ACTCPT), e.g.
`https://transitapp.com/en/region/beirut/actcpt/bus-b4` — this is a far
better digitization source than tracing a map image, since named
roundabouts/landmarks/streets can be geocoded precisely rather than needing
QGIS georeferencing of a raster.

`ocftc_stops_manual.csv` holds one row per stop, filled in from a
`transitapp.com` line page, geocoded by `ocftc_loader.py` via Nominatim.

## Status (as of 2026-08-09)

All 9 lines' stop names are transcribed (191 stops total, scraped
server-rendered from each line's `transitapp.com` page via
`fetch_actcpt_stops.py`, not fabricated). Geocoding via `ocftc_loader.py`
(OSM Nominatim, free, no API key) is in progress:

| Attempt | Query strategy | Resolved |
|---|---|---|
| 1 | `"<name>, Beirut, Lebanon"` | 13/191 — hard-appending "Beirut" broke matches for suburbs (Metn/Baabda/Chouf) |
| 2 | `"<name>"` / `"<name>, Lebanon"` + `countrycodes=lb` + GBA viewbox bias | 65/191 — better, but generic descriptor words ("Roundabout", "Intersection", "Bridge"...) aren't literal OSM names |
| 3 | + fallback ladder stripping generic suffixes, and trying the first segment of "A / B" compound names | **157/191 (82%)** — final result, see `ocftc_stops_geocoded.geojson` |

**QA findings (2026-08-09):** cross-checked consecutive-stop distances per
line against real Lebanon geography. Found 5 confirmed-wrong matches on the
long intercity corridors (ML1, ML4, B6-ML2) — short fallback names like
"Tyre" or "Chtaura" resolved to spurious matches near Beirut instead of the
real (70+ km distant) place, likely because the GBA viewbox soft-bias
actively hurts intercity stops that are *supposed* to be far from Beirut.
These 5 are marked `qa_flagged_suspect=true` in the GeoJSON (excluded from
any trusted use) — shown as red points on the QA map
(`outputs/maps/qa_map.html`). Stops matched via a fallback (not the exact
transcribed name) are shown in orange and should get a spot-check before
being trusted; exact-name matches are green.

**Remaining open items:**
- 34/191 stops never resolved — need a manual coordinate (e.g. via Google
  Maps) before use.
- The 5 flagged-suspect stops need a corrected manual coordinate.
- Every orange (fallback-matched) point should get at least a quick visual
  check on the QA map before the accessibility scoring / MCLP steps treat
  this as ground truth — the 5 confirmed-bad ones prove the fallback ladder
  can silently produce wrong-but-plausible-looking coordinates.

ACTCPT reportedly runs 9 lines / ~269 stops total (we found 191 named stops
across the 9 `transitapp.com` line pages — the discrepancy vs. 269 is
unexplained, possibly stops shared between lines or a stale published
count); as of the original source search only B1, B2, B3, ML3 were
confirmed actually operating regularly, so "planned" vs "operating" status
should be double-checked per line before this is treated as ground truth.
