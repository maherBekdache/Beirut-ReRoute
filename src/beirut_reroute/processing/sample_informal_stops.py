"""Generate proxy "stop" points along informal-route LineStrings.

Lebanon's informal van/bus system is a hail-anywhere network — only 2/14
parsed routes have explicit stop placemarks (see
`data_acquisition/parse_lebanese_bus_routes.py`). Modeling accessibility as
"distance to nearest point ANYWHERE on the route line" would be the most
accurate representation of how riders actually use it, but the rest of the
pipeline (accessibility scoring, MCLP candidate/coverage sets) is built
around discrete stop points for tractability. This module bridges the two:
regularly-spaced points along each line stand in for "you can flag the van
down anywhere near here" — an approximation, not real fixed infrastructure.

Usage:
    python -m beirut_reroute.processing.sample_informal_stops
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

SAMPLE_SPACING_M = 400  # ~5 min walk between hail-points, reasonable for a
                         # hail-anywhere system without over-densifying


def sample_points_along_line(line, spacing_m: float) -> list:
    n_points = max(2, int(line.length // spacing_m) + 1)
    return [line.interpolate(i / (n_points - 1), normalized=True) for i in range(n_points)]


def build_informal_stops() -> gpd.GeoDataFrame:
    lines_path = settings.INTERIM_DIR / "lebanese_bus_routes_lines.geojson"
    lines = gpd.read_file(lines_path)
    lines_metric = lines.to_crs(settings.CRS_METRIC)

    records = []
    for (_, row), (_, row_m) in zip(lines.iterrows(), lines_metric.iterrows()):
        points_m = sample_points_along_line(row_m.geometry, SAMPLE_SPACING_M)
        points_latlon = gpd.GeoSeries(points_m, crs=settings.CRS_METRIC).to_crs(settings.CRS_LATLON)
        for i, pt in enumerate(points_latlon):
            records.append(
                {
                    "route_id": row["route_id"],
                    "route_type": row["route_type"],
                    "stop_index": i,
                    "geometry": pt,
                }
            )

    return gpd.GeoDataFrame(records, crs=settings.CRS_LATLON)


def main() -> None:
    stops = build_informal_stops()
    out_path = settings.PROCESSED_DIR / "informal_route_proxy_stops.geojson"
    stops.to_file(out_path, driver="GeoJSON")
    print(f"Generated {len(stops)} proxy stops (~{SAMPLE_SPACING_M}m spacing) "
          f"across {stops['route_id'].nunique()} informal routes -> {out_path}")


if __name__ == "__main__":
    main()
