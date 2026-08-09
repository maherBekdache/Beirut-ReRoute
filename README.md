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
| 3. Feeder network optimization (MCLP) | `src/beirut_reroute/optimization/` | done for 7/9 real lines (`run_mclp_all_lines.py`) — 22 feeder stops, 67.2% of underserved population newly covered |
| 4. Signal priority + simulation | `src/beirut_reroute/simulation/` | proof-of-concept done for B4 (`run_b4_simulation.py`) on its real route + real OSM traffic signals; not yet scaled to all 7 covered lines |
| 5. Visualization & reporting | `src/beirut_reroute/viz/`, `outputs/` | QA map done (`viz/maps.py`); final report/phased-action-plan not started |

## Known Limitations

- OD demand is representative hub-based flows, not a full four-step travel demand model.
- Feeder route geometry is heuristic stop-chaining, not full vehicle routing.
- Congestion multiplier on OSM free-flow speeds (`config/settings.py:CONGESTION_MULTIPLIER`)
  is a documented, unvalidated calibration placeholder pending a public source.
- General mixed traffic is represented as a stochastic per-edge delay distribution, not
  individually simulated vehicles.
- GBA boundary is currently a 15km radius around Beirut Central District (see
  `config/settings.py`), not a precise administrative polygon.
- **Calibration check (2026-08-09):** the B4 simulation's status-quo trunk
  travel time (Hadath -> Martyrs' Square) came out to 81.8 min, ~35% longer
  than the ~60min "end-to-end" figure `transitapp.com` publishes for B4.
  Free-flow (no congestion multiplier) would give ~49min — i.e. the real
  figure sits between our free-flow and congested estimates, suggesting
  `CONGESTION_MULTIPLIER=0.6` is somewhat too aggressive for this corridor,
  or the shortest-path stop-chaining doesn't perfectly follow the real bus
  alignment, or the published figure is itself a scheduled/optimistic
  estimate. Not re-tuned to force-match this one anecdotal figure (that
  would be curve-fitting to a single data point) — needs more real
  reference trip times before absolute travel-time numbers are trustworthy.
  The signal-priority *delta* (same route, same base congestion assumption
  in both scenarios) is less sensitive to this bias than the absolute times.
