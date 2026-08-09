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
        fg = folium.FeatureGroup(name="OCFTC B4 stops (geocoded, partial)")
        coords = []
        for _, row in ocftc.sort_values("stop_order").iterrows():
            folium.CircleMarker(
                [row.geometry.y, row.geometry.x], radius=5, color="#2ca02c",
                fill=True, fill_color="#2ca02c",
                tooltip=f"B4 #{row['stop_order']}: {row['stop_name']}",
            ).add_to(fg)
            coords.append([row.geometry.y, row.geometry.x])
        if len(coords) > 1:
            folium.PolyLine(coords, color="#2ca02c", weight=3, dash_array="6").add_to(fg)
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
