# Beirut ReRoute

An AI-designed and simulated redesign of Beirut's public transport as a **feeder-and-trunk**
network: informal van/bus routes and population-density data are used to find where
coverage is worst relative to the 2024-launched formal OCFTC/ACTC bus network (B1-B7 city
lines + ML1-4 intercity lines), a coverage-optimization method designs new feeder routes
connecting underserved areas to the nearest trunk line, and a rule-based transit signal
priority layer (representing V2X/802.11p) is simulated on the trunk corridors. Status quo
vs proposed system are compared on population-weighted coverage, door-to-door trip time,
and trunk corridor bus speed — citywide across the Greater Beirut Area (GBA).

LebNet Tech Fellows final project. See `Beirut ReRoute — Implementation Plan` for the full
design (data sources, MCLP formulation, simulation architecture, milestones).

## Setup

```bash
# Requires Python 3.14 (the geospatial stack — rasterio, h3, ortools — needs an official
# python.org build for prebuilt Windows wheels; a mingw-built Python will fail to install
# these from source). Create the venv, then:
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
```

## Pipeline stages

| Stage | Module | Status |
|---|---|---|
| 1. Data acquisition & cleaning | `src/beirut_reroute/data_acquisition/` | real OSM/WorldPop/informal-route data pulled; 157/191 OCFTC stops geocoded (9/9 lines) |
| 2. Zoning & accessibility scoring | `src/beirut_reroute/processing/`, `accessibility/` | done — status-quo baseline: 92.2% pop-weighted coverage (`run_status_quo.py`) |
| 3. Feeder network optimization (MCLP) | `src/beirut_reroute/optimization/` | done for 7/9 real lines (`run_mclp_all_lines.py`) — 22 feeder stops, 68.4% of underserved population newly covered |
| 4. Signal priority + simulation | `src/beirut_reroute/simulation/` | done for all 7/7 lines with a feeder network (`run_simulation_all_lines.py`) on real routes + real OSM traffic signals — citywide coverage 0%->91.9%, ~162min avg door-to-door for newly-connected riders |
| 5. Visualization & reporting | `src/beirut_reroute/viz/`, `outputs/` | QA map done (`viz/maps.py`); final report/phased-action-plan not started |

## Real results (as of 2026-08-09, all bugs below fixed)

- **Status quo**: 92.2% population-weighted coverage (30min walk threshold), ~234,700 people uncovered.
- **MCLP feeder design**: 22 stops across 7 lines (B1/B2 had no assignable underserved demand), 156,594/228,965 (68.4%) of underserved population newly covered.
- **Simulation** (all 7 lines): citywide coverage 0%->91.9% for the population assigned to a feeder-served line; ~162min average door-to-door for newly-connected riders (pulled up by ML1's genuinely long ~4.4hr intercity trunk — not a bug, a real long-haul corridor).
- **Trunk speed** (status quo -> proposed, per line — not blended citywide, corridors are too different to average meaningfully):
  B3 36.8->37.8, B4 29.2->30.2, B5 39.3->39.5, ML3 29.0->29.2, ML4 37.8->37.9 km/h (small real signal-priority gains);
  B6-ML2 and ML1 unchanged (41.0 / 31.6 km/h) because their chained routes contain zero real OSM traffic-signal nodes — priority has nothing to act on there.

## Known Limitations

- OD demand is representative hub-based flows, not a full four-step travel demand model.
- Feeder route geometry is heuristic stop-chaining, not full vehicle routing.
- Congestion multiplier on OSM free-flow speeds (`config/settings.py:CONGESTION_MULTIPLIER`)
  is a documented, unvalidated calibration placeholder pending a public source.
- General mixed traffic is represented as a stochastic per-edge delay distribution, not
  individually simulated vehicles.
- GBA boundary is currently a 15km radius around Beirut Central District (see
  `config/settings.py`), not a precise administrative polygon.
- **Calibration check:** the B4 simulation's status-quo trunk travel time
  (Hadath -> Martyrs' Square) came out to 81.8 min, ~35% longer than the
  ~60min "end-to-end" figure `transitapp.com` publishes for B4. Free-flow
  (no congestion multiplier) would give ~49min — i.e. the real figure sits
  between our free-flow and congested estimates, suggesting
  `CONGESTION_MULTIPLIER=0.6` is somewhat too aggressive for this corridor,
  or the shortest-path stop-chaining doesn't perfectly follow the real bus
  alignment, or the published figure is itself a scheduled/optimistic
  estimate. Not re-tuned to force-match this one anecdotal figure — needs
  more real reference trip times before absolute travel-time numbers are
  fully trustworthy. The signal-priority *delta* (same route, same base
  congestion assumption in both scenarios) is less sensitive to this bias
  than the absolute times.

### Bugs found and fixed while running this on real data (not caught by synthetic tests)

Real data surfaces failure modes synthetic unit tests don't — each of these
was found by an actual pipeline run producing an implausible or crashing
result, not by inspection:

1. **Directed-graph strong-connectivity.** The drive graph was weakly
   connected but not strongly connected: ~28/24,674 nodes (one-way
   dead-ends, mostly at the 15km extraction boundary) had zero out-degree,
   causing `nx.shortest_path` to fail with `NetworkXNoPath` for two of B3's
   and B5's real consecutive stops. Fixed by restricting the drive graph to
   its largest strongly-connected component (`build_network_graph.py`) —
   safe given it's only 0.1% of nodes.
2. **Wrong-direction multi-source Dijkstra.** Both `nearest_stop_walk_times`
   and `travel_time_to_each_line` used a "super-node -> stops -> Dijkstra"
   trick to get distance-to-nearest-stop in one pass, but ran it on the
   graph as-is — computing distance FROM the stop outward, not FROM each
   point TO the stop. On a directed graph these differ; fixed by running
   the trick on the *reversed* graph instead (see
   `tests/test_directed_graph_distance.py` for a minimal repro). Didn't
   change the walk-based accessibility number (pedestrian paths in OSM are
   largely bidirectional even when one-way for vehicles) but materially
   changed the drive-graph-based MCLP demand assignment (e.g. B4's assigned
   demand went from 3 cells/14,984 people to 18 cells/64,803 once fixed).
3. **Fixed 2-hour simulation window.** `env.run(until=7200)` was fine for
   B4 (~80min trunk) but silently broke ML1 (~261min trunk alone) — any
   trip including it never reached completion within the window, so
   `trip.end_time` stayed `None` and a real, correctly-covered trip was
   miscounted as "not covered" (citywide simulated coverage read 40.9%
   instead of the correct 91.9%). Fixed by sizing the window per-line off
   the line's own measured trunk time plus a buffer, not a fixed constant.
4. **`env.run()` with no bound.** A helper that ran one trunk vehicle alone
   to measure travel time called `env.run()` with no `until=`, but
   `SignalizedIntersection` processes loop forever (fixed-time cycling
   never stops on its own) — the simulation never terminated. Fixed by
   running until the vehicle process itself completes.
5. Assorted: WorldPop's `-99999` nodata sentinel leaking into population
   sums for H3 cells overlapping the sea; an O(n²) candidate-downsampling
   loop and an O(n²) MCLP coverage-set computation that never finished at
   real data scale (fixed with a grid-snap dedup and a KD-tree
   respectively); a Windows console `UnicodeEncodeError` crashing a
   geocoding batch partway through combined with a cache that only saved
   at the end (so the crash discarded already-completed, rate-limited API
   calls); Nominatim query strings that hard-appended ", Beirut, Lebanon"
   breaking matches for stops in Metn/Baabda/Chouf suburbs.
