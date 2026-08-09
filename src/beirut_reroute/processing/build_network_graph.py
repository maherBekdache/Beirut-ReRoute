"""Add speeds/travel times to the OSM drive graph and apply a congestion calibration.

OSMnx's default speed-imputation uses free-flow highway-type speeds, which
overstates real travel speed in Beirut traffic. `settings.CONGESTION_MULTIPLIER`
scales imputed free-flow speeds down to an approximate real-world speed; this
is a documented placeholder (see README "Known Limitations"), not a validated
calibration.

Usage:
    python -m beirut_reroute.processing.build_network_graph
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import osmnx as ox

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings


def build_congested_drive_graph() -> nx.MultiDiGraph:
    graph_path = settings.OSM_RAW_DIR / "gba_drive.graphml"
    if not graph_path.exists():
        raise FileNotFoundError(f"{graph_path} not found — run fetch_osm.py first.")

    G = ox.load_graphml(graph_path)

    # The graph is weakly connected but not strongly connected: one-way
    # streets can leave a node reachable FROM the rest of the network but
    # unable to reach anything back out (e.g. a one-way slip lane clipped at
    # the 15km extraction boundary) -- nx.shortest_path then fails with
    # NetworkXNoPath between two otherwise-normal points. Only ~28/24674
    # nodes (0.1%) are outside the largest strongly-connected component, so
    # restricting to it is a safe fix, not a meaningful loss of coverage.
    n_before = len(G.nodes)
    G = ox.truncate.largest_component(G, strongly=True)
    n_removed = n_before - len(G.nodes)
    if n_removed:
        print(f"Dropped {n_removed} nodes outside the largest strongly-connected "
              f"component (one-way dead-ends unreachable from the rest of the network)")

    G = ox.add_edge_speeds(G)  # sets free-flow 'speed_kph' per edge
    G = ox.add_edge_travel_times(G)  # sets free-flow 'travel_time' (seconds)

    for _, _, data in G.edges(data=True):
        data["speed_kph_freeflow"] = data["speed_kph"]
        data["speed_kph"] = data["speed_kph"] * settings.CONGESTION_MULTIPLIER
        data["travel_time"] = data["travel_time"] / settings.CONGESTION_MULTIPLIER

    return G


def build_walk_graph_with_times() -> nx.MultiDiGraph:
    graph_path = settings.OSM_RAW_DIR / "gba_walk.graphml"
    if not graph_path.exists():
        raise FileNotFoundError(f"{graph_path} not found — run fetch_osm.py first.")

    G = ox.load_graphml(graph_path)
    for _, _, data in G.edges(data=True):
        length_m = data.get("length", 0.0)
        data["travel_time"] = length_m / (settings.WALK_SPEED_KMH * 1000 / 3600)
    return G


def main() -> None:
    drive_graph = build_congested_drive_graph()
    out_path = settings.PROCESSED_DIR / "gba_drive_congested.graphml"
    ox.save_graphml(drive_graph, out_path)
    print(f"Saved congestion-calibrated drive graph -> {out_path}")

    walk_graph = build_walk_graph_with_times()
    out_path = settings.PROCESSED_DIR / "gba_walk_timed.graphml"
    ox.save_graphml(walk_graph, out_path)
    print(f"Saved timed walk graph -> {out_path}")


if __name__ == "__main__":
    main()
