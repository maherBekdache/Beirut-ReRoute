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

| Line | Status |
|---|---|
| B4 | done — 13 stops transcribed + geocoded |
| B1, B2, B3, B5, B6-ML2, ML1, ML3, ML4 | **TODO** — fetch each line's stop list from `https://transitapp.com/en/region/beirut/actcpt/bus-<line>` and append rows to `ocftc_stops_manual.csv` in the same format, then re-run `ocftc_loader.py` |

ACTCPT reportedly runs 9 lines / ~269 stops total; as of the source search
only B1, B2, B3, ML3 were confirmed actually operating regularly, so
"planned" vs "operating" status should be double-checked per line before
this is treated as ground truth for the accessibility scoring / MCLP steps.
