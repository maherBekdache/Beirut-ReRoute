"""Run the Layer A national/regional vision analysis end-to-end.

Builds the status-quo and proposed graphs, computes the centrality
comparison, and saves the table + map. Requires `geocode_nodes.py` to have
already run (this is a "compute" pipeline stage, not a "fetch" one — see
`run_pipeline.py`).

Usage:
    python -m beirut_reroute.national_network.run_vision_analysis
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings
from beirut_reroute.national_network.build_regional_graph import (
    build_proposed_graph,
    build_status_quo_graph,
)
from beirut_reroute.national_network.centrality import compare_status_quo_vs_proposed
from beirut_reroute.viz.national_map import build_national_network_map


def main() -> None:
    sq = build_status_quo_graph()
    proposed = build_proposed_graph()
    print(f"Status-quo graph:  {sq.number_of_nodes()} nodes, {sq.number_of_edges()} edges")
    print(f"Proposed graph:    {proposed.number_of_nodes()} nodes, {proposed.number_of_edges()} edges")

    comparison = compare_status_quo_vs_proposed(sq, proposed)

    table_path = settings.TABLES_DIR / "national_centrality.csv"
    comparison.to_csv(table_path, index=False)
    print(f"\nSaved centrality comparison ({len(comparison)} nodes) -> {table_path}")

    beirut = comparison[comparison["node_id"] == "beirut_hub"].iloc[0]
    pct = beirut["betweenness_pct_change"]
    pct_str = f"{pct:+.1f}%" if pct is not None else "undefined (0 in status quo)"
    print(
        f"\nbeirut_hub betweenness centrality: "
        f"{beirut['betweenness_status_quo']:.4f} (status quo) -> "
        f"{beirut['betweenness_proposed']:.4f} (proposed) [{pct_str}]"
    )
    print(
        f"beirut_hub closeness centrality:   "
        f"{beirut['closeness_status_quo']:.4f} (status quo) -> "
        f"{beirut['closeness_proposed']:.4f} (proposed)"
    )

    top5 = comparison.head(5)[["node_id", "name", "betweenness_proposed"]]
    print(f"\nTop 5 nodes by proposed betweenness centrality:\n{top5.to_string(index=False)}")

    map_ = build_national_network_map(sq, proposed)
    map_path = settings.MAPS_DIR / "national_network_map.html"
    map_.save(str(map_path))
    print(f"\nSaved national network map -> {map_path}")


if __name__ == "__main__":
    main()
