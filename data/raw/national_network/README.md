# National/regional network graph — manual seed data

Node and edge lists for Layer A (the national/regional vision analysis). This
is a small, hand-curated topological graph -- not a GIS dataset -- so it is
tracked as plain CSVs rather than fetched, matching the `ocftc_digitized/`
pattern (manual transcription + geocoding, not a scraped/simplified dataset).

## Why manual, and why small (18 nodes / 18 edges)

There is no single public source for "Lebanon's real + historic + planned
multimodal network" the way transitapp.com exists for OCFTC's current bus
lines. Every row here is sourced individually (see `source_citation` in
`edges_manual.csv`) from a mix of: this repo's own real, already-geocoded
OCFTC data (Layer B); Lebanese rail-revival news coverage (2024-2025); ferry
launch coverage (2025-2026); and the ESCWA Arab Mashreq Railway agreement and
the 2025-2026 Turkey-Syria-Jordan-Saudi Hejaz Railway revival MoUs. Kept
deliberately small: this is a topological abstraction meant to evidence a
*directional* vision quantitatively (via centrality), not a routing-grade or
costed network -- see the main plan doc's "Layer A" section and the proposal's
Evaluation Plan risk #1.

## Node reuse from Layer B

`beirut_hub`, and the edges out of it, are not independently re-researched --
they reuse this repo's own real, geocoded OCFTC stop data:

- `beirut_hub` --> `chtaura` (Bekaa): OCFTC **ML1**, real route already
  parsed/geocoded in `data/raw/ocftc_digitized/ocftc_stops_manual.csv`.
- `beirut_hub` --> `tripoli` (via `jounieh`): OCFTC **ML4**, same source.
- `beirut_hub` --> `tyre` (via `saida`): OCFTC **B6-ML2**, same source.

Per `ocftc_digitized/README.md`, only B1/B2/B3/ML3 were confirmed as
regularly operating in the original source search -- ML1/ML4/B6-ML2's
day-to-day operating status (vs. "launched but irregular") is unconfirmed.
Edges sourced from them are tagged `formal_2024_unconfirmed_operation`, not
plain `existing_2024`, so this uncertainty survives into the centrality
analysis rather than being silently assumed away.

## Status categories (used to build the status-quo vs. proposed graphs)

| status | meaning | in status-quo graph? | in proposed graph? |
|---|---|---|---|
| `formal_2024_unconfirmed_operation` | OCFTC/ACTC 2024 bus lines | yes | yes |
| `informal_only` | reachable today only by private car / informal van | yes | yes |
| `historic_dormant` | real historic rail, unused since the network shut down | no | yes |
| `proposed_revival` | not built; part of a real, currently-signed regional agreement/MoU | no | yes |
| `proposed_2026` | not yet operating; a real, dated, currently-scheduled launch | no | yes |

## `geocode_cache.json`

The 17 non-`beirut_hub` nodes are all major, unambiguous places (cities,
ports, border crossings) — not fuzzy roundabout/intersection names like
OCFTC's stops — so `geocode_cache.json` was pre-seeded with known-accurate
coordinates rather than pulled live from Nominatim (the dev sandbox used to
build this had no route to `nominatim.openstreetmap.org`). `geocode_nodes.py`
still reads/writes this cache exactly as it would for live results — delete
the file (or individual keys) and re-run on a machine with normal internet
access to re-verify against live Nominatim if desired; results should match
closely since these are all standard, well-documented locations.

## Open items / things to double-check before treating this as final

- Exact historic Beirut-Damascus and Tripoli-Homs rail alignments (via Rayak
  / Aboudiyeh) are general historical record, not independently re-verified
  against a primary source for this project -- flagged in
  `edges_manual.csv`'s `source_citation` column wherever that applies.
- `aleppo`, `amman`, `riyadh` are real cities used as stand-ins for "the rest
  of the Hejaz Railway revival network beyond Lebanon/Syria" -- the graph
  does not model the real alignment inside Turkey/Jordan/Saudi Arabia, only
  that a link exists in principle per the cited MoUs.
- If any of the 2025-2026 rail/ferry agreements or launch dates change before
  submission, update `source_citation` and re-run -- don't leave stale dates
  in the final report.
