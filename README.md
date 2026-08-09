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
| 1. Data acquisition & cleaning | `src/beirut_reroute/data_acquisition/` | in progress |
| 2. Zoning & accessibility scoring | `src/beirut_reroute/processing/`, `accessibility/` | pending |
| 3. Feeder network optimization (MCLP) | `src/beirut_reroute/optimization/` | pending |
| 4. Signal priority + simulation | `src/beirut_reroute/simulation/` | pending |
| 5. Visualization & reporting | `src/beirut_reroute/viz/`, `outputs/` | pending |

## Known Limitations

- OD demand is representative hub-based flows, not a full four-step travel demand model.
- Feeder route geometry is heuristic stop-chaining, not full vehicle routing.
- Congestion multiplier on OSM free-flow speeds (`config/settings.py:CONGESTION_MULTIPLIER`)
  is a documented, unvalidated calibration placeholder pending a public source.
- General mixed traffic is represented as a stochastic per-edge delay distribution, not
  individually simulated vehicles.
- GBA boundary is currently a 15km radius around Beirut Central District (see
  `config/settings.py`), not a precise administrative polygon.
