"""Build the Layer A national/regional network graph.

Two graphs are built from the same node/edge tables:
- `build_status_quo_graph()`: only edges reachable today (formal 2024 OCFTC
  lines + informal-only links) — `settings.STATUS_QUO_EDGE_STATUSES`.
- `build_proposed_graph()`: every edge, including historic-dormant rail,
  real-but-not-yet-built regional agreements, and the 2026 ferry launch.

Edge weight is great-circle distance in km (haversine), not a travel time —
this graph has no speed/mode-performance model, and pretending otherwise
would overstate its precision. See `data/raw/national_network/README.md`
("topological abstraction, not a routing-grade network") and the proposal's
Evaluation Plan risk #1.

Usage:
    python -m beirut_reroute.national_network.build_regional_graph
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings


def load_nodes() -> gpd.GeoDataFrame:
    path = settings.INTERIM_DIR / "national_nodes_geocoded.geojson"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run geocode_nodes.py first.")
    return gpd.read_file(path).set_index("id", drop=False)


def load_edges() -> pd.DataFrame:
    return pd.read_csv(settings.NATIONAL_EDGES_CSV)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_earth_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r_earth_km * math.asin(math.sqrt(a))


def _edge_distance_km(nodes: gpd.GeoDataFrame, source_id: str, target_id: str) -> float:
    src, tgt = nodes.loc[source_id], nodes.loc[target_id]
    return _haversine_km(src.geometry.y, src.geometry.x, tgt.geometry.y, tgt.geometry.x)


def _build_graph(nodes: gpd.GeoDataFrame, edges: pd.DataFrame, statuses: set[str] | None) -> nx.Graph:
    """`statuses=None` includes every edge (the proposed/full graph);
    otherwise only rows whose `status` is in the given set."""
    graph = nx.Graph()

    for node_id, row in nodes.iterrows():
        graph.add_node(node_id, name=row["name"], kind=row["kind"], country=row["country"])

    kept = edges if statuses is None else edges[edges["status"].isin(statuses)]
    missing_nodes = set(kept["source_id"]) | set(kept["target_id"])
    missing_nodes -= set(nodes.index)
    if missing_nodes:
        raise ValueError(
            f"edges_manual.csv references node id(s) not in nodes_manual.csv "
            f"(or not successfully geocoded): {sorted(missing_nodes)}"
        )

    for _, row in kept.iterrows():
        distance_km = _edge_distance_km(nodes, row["source_id"], row["target_id"])
        graph.add_edge(
            row["source_id"], row["target_id"],
            mode=row["mode"], status=row["status"], distance_km=distance_km,
        )
    return graph


def build_status_quo_graph() -> nx.Graph:
    nodes, edges = load_nodes(), load_edges()
    return _build_graph(nodes, edges, statuses=settings.STATUS_QUO_EDGE_STATUSES)


def build_proposed_graph() -> nx.Graph:
    nodes, edges = load_nodes(), load_edges()
    return _build_graph(nodes, edges, statuses=None)


def main() -> None:
    sq = build_status_quo_graph()
    proposed = build_proposed_graph()
    print(f"Status-quo graph: {sq.number_of_nodes()} nodes, {sq.number_of_edges()} edges")
    print(f"Proposed graph:   {proposed.number_of_nodes()} nodes, {proposed.number_of_edges()} edges "
          f"({proposed.number_of_edges() - sq.number_of_edges()} restored/added)")
    isolated = [n for n in sq.nodes if sq.degree(n) == 0]
    if isolated:
        print(f"NOTE: {len(isolated)} node(s) have no status-quo edge at all "
              f"(only reachable in the proposed graph): {isolated}")


if __name__ == "__main__":
    main()
