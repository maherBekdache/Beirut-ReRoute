"""Central configuration for the Beirut ReRoute pipeline.

Import from this module rather than hardcoding paths/constants elsewhere.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

OSM_RAW_DIR = RAW_DIR / "osm"
WORLDPOP_RAW_DIR = RAW_DIR / "worldpop"
ADMIN_BOUNDARIES_DIR = RAW_DIR / "admin_boundaries"
LEBANESE_BUS_ROUTES_DIR = RAW_DIR / "lebanese_bus_routes"
OCFTC_DIGITIZED_DIR = RAW_DIR / "ocftc_digitized"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
MAPS_DIR = OUTPUTS_DIR / "maps"
FIGURES_DIR = OUTPUTS_DIR / "figures"
TABLES_DIR = OUTPUTS_DIR / "tables"
REPORTS_DIR = OUTPUTS_DIR / "reports"

for _d in (
    RAW_DIR, INTERIM_DIR, PROCESSED_DIR, OSM_RAW_DIR, WORLDPOP_RAW_DIR,
    ADMIN_BOUNDARIES_DIR, LEBANESE_BUS_ROUTES_DIR, OCFTC_DIGITIZED_DIR,
    MAPS_DIR, FIGURES_DIR, TABLES_DIR, REPORTS_DIR,
):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Coordinate reference systems
# ---------------------------------------------------------------------------
CRS_LATLON = "EPSG:4326"          # OSM / GPS / WorldPop native CRS
CRS_METRIC = "EPSG:32636"         # UTM Zone 36N — covers Lebanon, used for all
                                   # distance/area/speed calculations

# ---------------------------------------------------------------------------
# Study area — Greater Beirut Area (GBA)
# ---------------------------------------------------------------------------
# GBA has no single official OSM administrative boundary, so it is defined as
# a radius around the Beirut Central District (Martyrs' Square), matching the
# ~15km extent commonly used for "Greater Beirut" in World Bank GBA transport
# project documents. This can be swapped for a precise multi-caza polygon
# (Beirut + Baabda + Aley + Chouf + Metn + Keserwan cazas) later without
# touching any downstream code, since everything consumes `data/raw/admin_boundaries/gba_boundary.geojson`.
GBA_CENTER_LATLON = (33.8938, 35.5018)  # Martyrs' Square, Beirut
GBA_RADIUS_M = 15_000

# ---------------------------------------------------------------------------
# H3 hex grid
# ---------------------------------------------------------------------------
H3_RESOLUTION = 8  # ~0.46 km^2 per cell

# ---------------------------------------------------------------------------
# Accessibility scoring thresholds (minutes)
# ---------------------------------------------------------------------------
T_WALK_MAX_MIN = 10     # max walk time considered "covered" by a nearby stop
T_RIDE_MAX_MIN = 20     # max feeder ride time to a trunk access point
T_MAX_MIN = 30          # overall cutoff for binary coverage A(c)
DECAY_BETA = 0.0462     # exp(-beta * t) chosen so A(15 min) = 0.5 -> ln(2)/15

WALK_SPEED_KMH = 4.5
DEFAULT_WAIT_TIME_MIN = 7.0  # placeholder headway-based wait, refined once
                              # real frequency data is collected

# ---------------------------------------------------------------------------
# OCFTC/ACTC formal trunk lines (as of the 2024 launch)
# ---------------------------------------------------------------------------
TRUNK_LINE_IDS = [
    "B1", "B2", "B3", "B4", "B5", "B6", "B7",   # Beirut city lines
    "ML1", "ML2", "ML3", "ML4",                  # intercity lines
]

# ---------------------------------------------------------------------------
# Congestion calibration
# ---------------------------------------------------------------------------
# OSMnx's default free-flow speed table overstates real travel speed in
# Beirut traffic. This multiplier is applied to derived edge speeds and MUST
# be re-derived/documented from a public source (e.g. TomTom's published
# congestion-index city ranking) before being treated as anything more than
# a placeholder. See README/report "Known Limitations".
CONGESTION_MULTIPLIER = 0.6
