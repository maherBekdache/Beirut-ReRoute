"""Betweenness/closeness centrality for the Layer A status-quo vs proposed graphs.

This is the quantitative core of the "envision Lebanon reconnected" claim:
instead of just asserting that restoring rail/ferry links would make
Beirut/Lebanon more central regionally, compute it on the graphs from
`build_regional_graph.py` and report the delta.

Usage:
    python -m beirut_reroute.national_network.centrality
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from beirut_reroute.national_network.build_regional_graph import (
    build_proposed_graph,
    build_status_quo_graph,
)


@dataclass
class CentralityResult:
    node_id: str
    betweenness: float
    closeness: float


def compute_centrality(graph: nx.Graph) -> dict[str, CentralityResult]:
    """Weighted (by `distance_km`) betweenness and closeness. Isolated nodes
    (no edge in this particular graph) get 0.0 for both, which networkx
    already does by default -- not special-cased here, just relied on."""
    betweenness = nx.betweenness_centrality(graph, weight="distance_km")
    closeness = nx.closeness_centrality(graph, distance="distance_km")
    return {
        node_id: CentralityResult(node_id, betweenness[node_id], closeness[node_id])
        for node_id in graph.nodes
    }


def _pct_change(before: float, after: float) -> float | None:
    if before == 0:
        return None  # undefined (divide by zero) -- leave as null rather than inf/NaN
    return (after - before) / before * 100.0


def compare_status_quo_vs_proposed(sq: nx.Graph, proposed: nx.Graph) -> pd.DataFrame:
    """One row per node in `proposed`. In the real Layer A pipeline, `sq` and
    `proposed` are built from the same node table (see
    build_regional_graph._build_graph), so every node exists in both -- a
    node with zero status-quo edges just has 0.0 centrality there, which is
    itself the point being measured, not a missing-data gap. A node present
    in `proposed` but absent from `sq` entirely (not just edge-less, but
    never added) is treated the same way: 0.0 status-quo centrality."""
    sq_centrality = compute_centrality(sq)
    proposed_centrality = compute_centrality(proposed)
    zero = CentralityResult("", 0.0, 0.0)

    rows = []
    for node_id, node_data in proposed.nodes(data=True):
        before = sq_centrality.get(node_id, zero)
        b_before = before.betweenness
        c_before = before.closeness
        prop = proposed_centrality[node_id]
        rows.append({
            "node_id": node_id,
            "name": node_data["name"],
            "kind": node_data["kind"],
            "country": node_data["country"],
            "betweenness_status_quo": b_before,
            "betweenness_proposed": prop.betweenness,
            "betweenness_pct_change": _pct_change(b_before, prop.betweenness),
            "closeness_status_quo": c_before,
            "closeness_proposed": prop.closeness,
            "closeness_pct_change": _pct_change(c_before, prop.closeness),
        })
    return (
        pd.DataFrame(rows)
        .sort_values("betweenness_proposed", ascending=False)
        .reset_index(drop=True)
    )


def main() -> None:
    sq, proposed = build_status_quo_graph(), build_proposed_graph()
    comparison = compare_status_quo_vs_proposed(sq, proposed)
    beirut = comparison[comparison["node_id"] == "beirut_hub"].iloc[0]
    print(
        f"beirut_hub betweenness: {beirut['betweenness_status_quo']:.4f} (status quo) "
        f"-> {beirut['betweenness_proposed']:.4f} (proposed)"
        + (f" ({beirut['betweenness_pct_change']:+.1f}%)" if beirut["betweenness_pct_change"] is not None else "")
    )
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
