"""Layer A national/regional network map.

Sibling to `maps.py` (which stays GBA-scoped/Layer-B-only) rather than an
edit to it, so Layer B's QA map is untouched. Two toggleable layers: today's
status-quo edges (solid) and the edges only present in the proposed,
reconnected network (dashed) — same status-quo/proposed split as
`build_regional_graph.py` and `centrality.py`. Nodes get an icon per kind
(port/rail junction/border crossing/city) and a click popup with the sourced
notes from `edges_manual.csv`/`nodes_manual.csv`, not just a bare tooltip —
so a reader can verify a claim (e.g. "why is this edge here?") without
leaving the map.

Usage:
    python -m beirut_reroute.viz.national_map
"""

from __future__ import annotations

import sys
from pathlib import Path

import folium
import geopandas as gpd
import networkx as nx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

# folium.Icon only accepts a fixed palette of named colors, not arbitrary
# hex -- picked to stay visually close to charts.py's _KIND_COLORS so the
# interactive map and the static figures read as the same project.
_KIND_ICON = {
    "city_port": ("star", "red"),
    "port": ("ship", "blue"),
    "inland_hub": ("road", "green"),
    "rail_junction": ("train", "orange"),
    "border_crossing": ("flag", "purple"),
    "city": ("building", "gray"),
}

_MODE_COLORS = {
    "bus": "#1f78b4",
    "road": "#999999",
    "historic_rail": "#8B4513",
    "rail": "#e31a1c",
    "ferry": "#00b3b3",
}

_LEGEND_HTML = """
<div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999;
            background: white; padding: 10px 14px; border: 1px solid #999;
            border-radius: 6px; font-size: 12px; line-height: 1.6; box-shadow: 0 1px 4px rgba(0,0,0,0.3);">
  <b>Node kind</b><br>
  <i class="fa fa-star" style="color:#d63e2a"></i> Beirut hub &nbsp;
  <i class="fa fa-ship" style="color:#38aadd"></i> Port &nbsp;
  <i class="fa fa-road" style="color:#72b026"></i> Inland hub<br>
  <i class="fa fa-train" style="color:#f69730"></i> Rail junction &nbsp;
  <i class="fa fa-flag" style="color:#d252b9"></i> Border crossing &nbsp;
  <i class="fa fa-building" style="color:#575757"></i> City
  <hr style="margin:6px 0;">
  <b>Edge mode</b><br>
  <span style="color:#1f78b4;">&#9644;&#9644;</span> Bus &nbsp;
  <span style="color:#8B4513;">&#9644;&#9644;</span> Historic rail &nbsp;
  <span style="color:#e31a1c;">&#9644;&#9644;</span> Rail<br>
  <span style="color:#00b3b3;">&#9644;&#9644;</span> Ferry &nbsp;
  <span style="color:#999999;">&#9644;&#9644;</span> Road
  <hr style="margin:6px 0;">
  Solid = status quo &nbsp;&mdash;&nbsp; dashed = proposed-only
</div>
"""


def _load_node_coords() -> gpd.GeoDataFrame:
    path = settings.INTERIM_DIR / "national_nodes_geocoded.geojson"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run geocode_nodes.py first.")
    return gpd.read_file(path).set_index("id", drop=False)


def _load_edge_notes() -> dict[frozenset, dict]:
    """Keyed by frozenset({source_id, target_id}) so lookup doesn't care
    about direction -- edges_manual.csv is written source->target but the
    graph/map treat the network as undirected."""
    edges = pd.read_csv(settings.NATIONAL_EDGES_CSV)
    return {
        frozenset((row["source_id"], row["target_id"])): row.to_dict()
        for _, row in edges.iterrows()
    }


def build_national_network_map(sq: nx.Graph, proposed: nx.Graph) -> folium.Map:
    nodes = _load_node_coords()
    edge_notes = _load_edge_notes()

    m = folium.Map(tiles="cartodbpositron")
    bounds = [[row.geometry.y, row.geometry.x] for _, row in nodes.iterrows()]
    m.fit_bounds(bounds, padding=(30, 30))

    status_quo_layer = folium.FeatureGroup(name="Status-quo edges (today)", show=True)
    proposed_layer = folium.FeatureGroup(name="Proposed-only edges (restored/added)", show=True)

    sq_edge_keys = {frozenset((u, v)) for u, v in sq.edges}

    for u, v, data in proposed.edges(data=True):
        u_row, v_row = nodes.loc[u], nodes.loc[v]
        coords = [(u_row.geometry.y, u_row.geometry.x), (v_row.geometry.y, v_row.geometry.x)]
        color = _MODE_COLORS.get(data["mode"], "#555555")
        is_status_quo = frozenset((u, v)) in sq_edge_keys
        note_row = edge_notes.get(frozenset((u, v)), {})
        notes_text = note_row.get("notes", "")
        citation = note_row.get("source_citation", "")

        popup_html = (
            f"<b>{u_row['name']} ↔ {v_row['name']}</b><br>"
            f"mode: {data['mode']} &middot; status: {data['status']} &middot; "
            f"{data['distance_km']:.0f} km<br>"
            + (f"<i>{notes_text}</i><br>" if isinstance(notes_text, str) and notes_text else "")
            + (f"source: {citation}" if isinstance(citation, str) and citation else "")
        )

        line = folium.PolyLine(
            coords,
            color=color,
            weight=3.5 if is_status_quo else 2.2,
            opacity=0.9 if is_status_quo else 0.65,
            dash_array=None if is_status_quo else "6,6",
            tooltip=f"{u_row['name']} ↔ {v_row['name']} ({data['mode']})",
            popup=folium.Popup(popup_html, max_width=320),
        )
        line.add_to(status_quo_layer if is_status_quo else proposed_layer)

    node_layer = folium.FeatureGroup(name="Nodes", show=True)
    for node_id, row in nodes.iterrows():
        icon_name, icon_color = _KIND_ICON.get(row["kind"], ("map-marker", "gray"))
        popup_html = f"<b>{row['name']}</b><br>{row['kind']} &middot; {row['country']}<br><i>{row['notes']}</i>"
        folium.Marker(
            location=(row.geometry.y, row.geometry.x),
            tooltip=f"{row['name']} ({row['kind']}, {row['country']})",
            popup=folium.Popup(popup_html, max_width=280),
            icon=folium.Icon(
                icon=icon_name, prefix="fa", color=icon_color,
                icon_color="white" if node_id != "beirut_hub" else "#ffe08a",
            ),
        ).add_to(node_layer)

    status_quo_layer.add_to(m)
    proposed_layer.add_to(m)
    node_layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.get_root().html.add_child(folium.Element(_LEGEND_HTML))
    title_html = (
        '<div style="position: fixed; top: 12px; left: 60px; z-index: 9999; '
        'background: white; padding: 6px 14px; border-radius: 6px; '
        'box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-size: 16px; font-weight: 600;">'
        "Lebanon ReConnect — national/regional network</div>"
    )
    m.get_root().html.add_child(folium.Element(title_html))
    return m


def main() -> None:
    from beirut_reroute.national_network.build_regional_graph import (
        build_proposed_graph,
        build_status_quo_graph,
    )

    sq, proposed = build_status_quo_graph(), build_proposed_graph()
    m = build_national_network_map(sq, proposed)
    out_path = settings.MAPS_DIR / "national_network_map.html"
    m.save(str(out_path))
    print(f"Saved national network map -> {out_path}")


if __name__ == "__main__":
    main()
