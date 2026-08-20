"""Layer B results map — the presentation-focused counterpart to `maps.py`.

`maps.py` is a QA tool (shows suspect/fallback geocode flags, one toggle per
line, population-only choropleth) and stays untouched for that job. This map
is for the report/video: an accessibility choropleth (status quo), one clean
trunk-network layer, and one clean AI-designed-feeder-network layer, with
popups that carry the real per-line numbers from `mclp_per_line.csv` and
`simulation_per_line.csv` rather than QA metadata.

Usage:
    python -m beirut_reroute.viz.results_map
"""

from __future__ import annotations

import sys
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

_LINE_PALETTE = [
    "#1f78b4", "#e31a1c", "#33a02c", "#ff7f00", "#6a3d9a",
    "#b15928", "#a6cee3", "#fb9a99", "#b2df8a",
]

_LEGEND_HTML = """
<div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999;
            background: white; padding: 10px 14px; border: 1px solid #999;
            border-radius: 6px; font-size: 12px; line-height: 1.6; box-shadow: 0 1px 4px rgba(0,0,0,0.3);">
  <b>Accessibility (status quo)</b><br>
  <span style="background:#1a9850; display:inline-block; width:12px; height:12px;"></span> Covered (&le;30 min walk)&nbsp;
  <span style="background:#d73027; display:inline-block; width:12px; height:12px;"></span> Uncovered
  <hr style="margin:6px 0;">
  <b>Network</b><br>
  Solid line + circle = OCFTC trunk stop<br>
  Dashed line + diamond = AI-designed feeder stop<br>
  Same color = same line
</div>
"""


def _line_color_map(line_ids: list[str]) -> dict[str, str]:
    return {lid: _LINE_PALETTE[i % len(_LINE_PALETTE)] for i, lid in enumerate(sorted(line_ids))}


def _per_line_lookup(path: Path, key: str = "line_id") -> dict[str, dict]:
    if not path.exists():
        return {}
    return pd.read_csv(path).set_index(key).to_dict("index")


def build_results_map() -> folium.Map:
    lat, lon = settings.GBA_CENTER_LATLON
    m = folium.Map(location=[lat, lon], zoom_start=11, tiles="cartodbpositron")

    mclp_results = _per_line_lookup(settings.TABLES_DIR / "mclp_per_line.csv")
    sim_results = _per_line_lookup(settings.TABLES_DIR / "simulation_per_line.csv")

    grid_path = settings.PROCESSED_DIR / "status_quo_accessibility.geojson"
    if grid_path.exists():
        grid = gpd.read_file(grid_path)
        folium.GeoJson(
            grid,
            name="Accessibility (status quo)",
            style_function=lambda f: {
                "fillColor": "#1a9850" if f["properties"]["coverage_binary"] else "#d73027",
                "color": "#555", "weight": 0.3,
                "fillOpacity": 0.45 if f["properties"]["coverage_binary"] else 0.55,
            },
            tooltip=folium.GeoJsonTooltip(fields=["population", "walk_time_min"],
                                           aliases=["Population", "Walk time to nearest stop (min)"]),
        ).add_to(m)

    ocftc_path = settings.INTERIM_DIR / "ocftc_stops_geocoded.geojson"
    trunk_layer = folium.FeatureGroup(name="OCFTC trunk network", show=True)
    line_colors: dict[str, str] = {}
    if ocftc_path.exists():
        ocftc = gpd.read_file(ocftc_path)
        if "qa_flagged_suspect" in ocftc.columns:
            ocftc = ocftc[~ocftc["qa_flagged_suspect"]]
        line_colors = _line_color_map(list(ocftc["line_id"].unique()))
        for line_id, grp in ocftc.groupby("line_id"):
            grp = grp.sort_values("stop_order")
            color = line_colors[line_id]
            sim = sim_results.get(line_id, {})
            line_popup = (
                f"<b>{line_id}</b><br>"
                + (f"Trunk speed: {sim['trunk_speed_status_quo_kmh']:.1f} &rarr; "
                   f"{sim['trunk_speed_proposed_kmh']:.1f} km/h<br>"
                   if sim.get("trunk_speed_status_quo_kmh") is not None else "")
                + (f"Simulated coverage among riders assigned this line: "
                   f"{sim['coverage_fraction_proposed'] * 100:.0f}%"
                   if sim.get("coverage_fraction_proposed") is not None else "")
            )
            coords = []
            for _, row in grp.iterrows():
                folium.CircleMarker(
                    [row.geometry.y, row.geometry.x], radius=4, color=color,
                    fill=True, fill_color=color, fill_opacity=0.9,
                    tooltip=f"{line_id} #{row['stop_order']}: {row['stop_name']}",
                    popup=folium.Popup(line_popup, max_width=260),
                ).add_to(trunk_layer)
                coords.append([row.geometry.y, row.geometry.x])
            if len(coords) > 1:
                folium.PolyLine(coords, color=color, weight=3, opacity=0.85).add_to(trunk_layer)
    trunk_layer.add_to(m)

    feeder_stops_path = settings.PROCESSED_DIR / "feeder_stops_all_lines.geojson"
    feeder_routes_path = settings.PROCESSED_DIR / "feeder_routes_all_lines.geojson"
    feeder_layer = folium.FeatureGroup(name="AI-designed feeder network", show=True)
    if feeder_stops_path.exists():
        feeder_stops = gpd.read_file(feeder_stops_path)
        feeder_routes = gpd.read_file(feeder_routes_path) if feeder_routes_path.exists() else None
        for line_id, grp in feeder_stops.groupby("line_id"):
            color = line_colors.get(line_id, "#17becf")
            mclp = mclp_results.get(line_id, {})
            feeder_popup = (
                f"<b>{line_id} feeder network</b><br>"
                + (f"{mclp['newly_covered_population']:,.0f} people newly covered "
                   f"({mclp['coverage_fraction'] * 100:.0f}% of this line's underserved demand)"
                   if mclp.get("newly_covered_population") is not None else "")
            )
            for _, row in grp.iterrows():
                # Diamond (rotated square) marker so feeder stops are visually
                # distinct from trunk stops' circles at a glance, even before
                # reading the legend.
                folium.RegularPolygonMarker(
                    location=[row.geometry.y, row.geometry.x], number_of_sides=4, rotation=45,
                    radius=7, color="#000", weight=1, fill=True, fill_color=color, fill_opacity=0.95,
                    tooltip=f"{line_id} feeder stop #{row['stop_rank']}",
                    popup=folium.Popup(feeder_popup, max_width=260),
                ).add_to(feeder_layer)
            if feeder_routes is not None:
                route_rows = feeder_routes[feeder_routes["line_id"] == line_id]
                for _, r in route_rows.iterrows():
                    folium.GeoJson(
                        r.geometry.__geo_interface__,
                        style_function=lambda _, c=color: {"color": c, "weight": 3, "dashArray": "6,4"},
                    ).add_to(feeder_layer)
    feeder_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    m.get_root().html.add_child(folium.Element(_LEGEND_HTML))
    title_html = (
        '<div style="position: fixed; top: 12px; left: 60px; z-index: 9999; '
        'background: white; padding: 6px 14px; border-radius: 6px; '
        'box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-size: 16px; font-weight: 600;">'
        "Beirut ReRoute — results: coverage, trunk & feeder network</div>"
    )
    m.get_root().html.add_child(folium.Element(title_html))
    return m


def main() -> None:
    m = build_results_map()
    out_path = settings.MAPS_DIR / "results_map.html"
    m.save(str(out_path))
    print(f"Saved results map -> {out_path}")


if __name__ == "__main__":
    main()
