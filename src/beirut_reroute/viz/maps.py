"""QA/exploration maps — visualize every parsed data layer before trusting it.

Per the plan doc "Verification Approach": every parsed route/stop layer must
be visualized on a basemap before being trusted downstream.

Usage:
    python -m beirut_reroute.viz.maps
"""

from __future__ import annotations

import sys
from pathlib import Path

import folium
import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings


def build_qa_map() -> folium.Map:
    lat, lon = settings.GBA_CENTER_LATLON
    m = folium.Map(location=[lat, lon], zoom_start=11, tiles="cartodbpositron")

    boundary_path = settings.ADMIN_BOUNDARIES_DIR / "gba_boundary.geojson"
    if boundary_path.exists():
        folium.GeoJson(
            gpd.read_file(boundary_path),
            name="GBA boundary (15km radius)",
            style_function=lambda _: {"color": "#333", "weight": 2, "fill": False},
        ).add_to(m)

    grid_path = settings.PROCESSED_DIR / "gba_h3_grid.geojson"
    if grid_path.exists():
        grid = gpd.read_file(grid_path)
        folium.Choropleth(
            geo_data=grid,
            data=grid,
            columns=["h3_id", "population"],
            key_on="feature.properties.h3_id",
            fill_color="YlOrRd",
            fill_opacity=0.6,
            line_opacity=0.1,
            legend_name="Population per H3 cell",
            name="Population (H3 grid)",
        ).add_to(m)

    lines_path = settings.INTERIM_DIR / "lebanese_bus_routes_lines.geojson"
    if lines_path.exists():
        lines = gpd.read_file(lines_path)
        colors = {"formal_city_bus": "#1f77b4", "informal_van": "#d62728"}
        fg = folium.FeatureGroup(name="Lebanese-Bus-Routes (informal network)")
        for _, row in lines.iterrows():
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda _, c=colors.get(row["route_type"], "#666"): {
                    "color": c, "weight": 3, "opacity": 0.8
                },
                tooltip=f"{row['route_id']} ({row['route_type']})",
            ).add_to(fg)
        fg.add_to(m)

    stops_path = settings.INTERIM_DIR / "lebanese_bus_routes_stops.geojson"
    if stops_path.exists():
        stops = gpd.read_file(stops_path)
        fg = folium.FeatureGroup(name="Informal-route stop placemarks")
        for _, row in stops.iterrows():
            folium.CircleMarker(
                [row.geometry.y, row.geometry.x], radius=4, color="#d62728",
                fill=True, tooltip=f"{row['route_id']}: {row.get('stop_name')}",
            ).add_to(fg)
        fg.add_to(m)

    ocftc_path = settings.INTERIM_DIR / "ocftc_stops_geocoded.geojson"
    if ocftc_path.exists():
        ocftc = gpd.read_file(ocftc_path)
        has_qa_flag = "qa_flagged_suspect" in ocftc.columns
        for line_id, grp in ocftc.groupby("line_id"):
            grp = grp.sort_values("stop_order")
            fg = folium.FeatureGroup(name=f"OCFTC {line_id} ({len(grp)} stops)")
            coords = []
            for _, row in grp.iterrows():
                suspect = bool(row["qa_flagged_suspect"]) if has_qa_flag else False
                is_fallback = row.get("matched_via") and row["matched_via"] != row["stop_name"]
                color = "#d62728" if suspect else ("#ff7f0e" if is_fallback else "#2ca02c")
                tooltip = f"{line_id} #{row['stop_order']}: {row['stop_name']}"
                if suspect:
                    tooltip += f" -- SUSPECT: {row.get('qa_flag_reason', '')}"
                elif is_fallback:
                    tooltip += f" (matched via fallback '{row['matched_via']}')"
                folium.CircleMarker(
                    [row.geometry.y, row.geometry.x], radius=5, color=color,
                    fill=True, fill_color=color, tooltip=tooltip,
                ).add_to(fg)
                coords.append([row.geometry.y, row.geometry.x])
            if len(coords) > 1:
                folium.PolyLine(coords, color="#2ca02c", weight=2, dash_array="6", opacity=0.6).add_to(fg)
            fg.add_to(m)

    status_quo_path = settings.PROCESSED_DIR / "status_quo_accessibility.geojson"
    if status_quo_path.exists():
        underserved = gpd.read_file(status_quo_path)
        underserved = underserved[underserved["coverage_binary"] == 0]
        fg = folium.FeatureGroup(name="Underserved cells (status quo, >30min to any stop)", show=False)
        for _, row in underserved.iterrows():
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda _: {"color": "#9467bd", "weight": 1, "fillOpacity": 0.3},
                tooltip=f"pop {row['population']:.0f}, {row['total_time_min']:.0f} min",
            ).add_to(fg)
        fg.add_to(m)

    all_feeder_stops_path = settings.PROCESSED_DIR / "feeder_stops_all_lines.geojson"
    all_feeder_routes_path = settings.PROCESSED_DIR / "feeder_routes_all_lines.geojson"
    if all_feeder_stops_path.exists():
        feeder_stops = gpd.read_file(all_feeder_stops_path)
        feeder_routes = gpd.read_file(all_feeder_routes_path) if all_feeder_routes_path.exists() else None
        line_ids = sorted(feeder_stops["line_id"].unique())
        palette = ["#17becf", "#e377c2", "#8c564b", "#bcbd22", "#7f7f7f", "#1a9850", "#762a83", "#fdae61", "#3288bd"]
        for i, line_id in enumerate(line_ids):
            color = palette[i % len(palette)]
            fg = folium.FeatureGroup(name=f"MCLP feeder stops: {line_id}")
            grp = feeder_stops[feeder_stops["line_id"] == line_id]
            for _, row in grp.iterrows():
                folium.CircleMarker(
                    [row.geometry.y, row.geometry.x], radius=7, color="#000", weight=1.5,
                    fill=True, fill_color=color,
                    tooltip=f"{line_id} feeder stop #{row['stop_rank']}",
                ).add_to(fg)
            if feeder_routes is not None:
                route_rows = feeder_routes[feeder_routes["line_id"] == line_id]
                for _, r in route_rows.iterrows():
                    folium.GeoJson(
                        r.geometry.__geo_interface__,
                        style_function=lambda _, c=color: {"color": c, "weight": 4},
                    ).add_to(fg)
            fg.add_to(m)
    else:
        # Fallback: single-line B4 proof-of-concept output, if the citywide
        # all-lines run hasn't been produced yet.
        b4_feeder_stops_path = settings.PROCESSED_DIR / "b4_feeder_stops.geojson"
        b4_feeder_route_path = settings.PROCESSED_DIR / "b4_feeder_route.geojson"
        if b4_feeder_stops_path.exists():
            stops = gpd.read_file(b4_feeder_stops_path)
            fg = folium.FeatureGroup(name="B4 MCLP-designed feeder stops")
            for _, row in stops.iterrows():
                folium.CircleMarker(
                    [row.geometry.y, row.geometry.x], radius=7, color="#000", weight=2,
                    fill=True, fill_color="#17becf",
                    tooltip=f"Feeder stop #{row['stop_rank']}",
                ).add_to(fg)
            if b4_feeder_route_path.exists():
                route = gpd.read_file(b4_feeder_route_path)
                folium.GeoJson(
                    route.geometry.iloc[0].__geo_interface__,
                    style_function=lambda _: {"color": "#17becf", "weight": 4},
                ).add_to(fg)
            fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def main() -> None:
    m = build_qa_map()
    out_path = settings.MAPS_DIR / "qa_map.html"
    m.save(str(out_path))
    print(f"Saved QA map -> {out_path}")


if __name__ == "__main__":
    main()
