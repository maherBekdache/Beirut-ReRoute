import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from beirut_reroute.national_network.centrality import compare_status_quo_vs_proposed, compute_centrality


def _path_graph_abc() -> nx.Graph:
    g = nx.Graph()
    g.add_edge("A", "B", distance_km=1.0)
    g.add_edge("B", "C", distance_km=1.0)
    return g


def test_middle_node_of_a_path_has_the_unique_max_betweenness():
    result = compute_centrality(_path_graph_abc())

    assert result["B"].betweenness > result["A"].betweenness
    assert result["B"].betweenness > result["C"].betweenness
    assert result["A"].betweenness == result["C"].betweenness == 0.0


def test_middle_node_has_higher_closeness_than_endpoints():
    result = compute_centrality(_path_graph_abc())

    assert result["B"].closeness > result["A"].closeness
    assert result["B"].closeness > result["C"].closeness


def _node_attrs(node_id: str) -> dict:
    return {"name": node_id, "kind": "test", "country": "test"}


def _two_disjoint_edges() -> nx.Graph:
    """p-x and q-y, with no path between the two pairs -- the status-quo
    graph in the bridge test below."""
    g = nx.Graph()
    g.add_edge("p", "x", distance_km=1.0)
    g.add_edge("q", "y", distance_km=1.0)
    for n in g.nodes:
        g.nodes[n].update(_node_attrs(n))
    return g


def _same_edges_plus_bridge() -> nx.Graph:
    """Same two edges, plus a bridge x-y joining the two components into one
    path p-x-y-q -- the proposed graph in the bridge test below."""
    g = _two_disjoint_edges()
    g.add_edge("x", "y", distance_km=1.0)
    return g


def test_adding_a_bridge_edge_increases_the_bridge_endpoints_betweenness():
    """This is the actual claim the report makes about beirut_hub: restoring
    a link that bridges two otherwise-disconnected clusters increases the
    bridge endpoints' betweenness centrality. Tested directly here on a
    minimal synthetic graph rather than just trusted on the real one."""
    sq = _two_disjoint_edges()
    proposed = _same_edges_plus_bridge()

    comparison = compare_status_quo_vs_proposed(sq, proposed).set_index("node_id")

    # p and q were never on any shortest path in either graph (they're
    # degree-1 endpoints of the whole chain) -- betweenness stays 0.
    assert comparison.loc["p", "betweenness_status_quo"] == 0.0
    assert comparison.loc["p", "betweenness_proposed"] == 0.0

    # x and y are isolated-within-their-pair in the status quo (a single
    # edge has no third node to be "between"), so their betweenness starts
    # at 0 and is undefined as a percent change once the bridge exists...
    assert comparison.loc["x", "betweenness_status_quo"] == 0.0
    assert comparison.loc["y", "betweenness_status_quo"] == 0.0
    # ...but strictly positive once the bridge makes them the only route
    # between the two original pairs.
    assert comparison.loc["x", "betweenness_proposed"] > 0.0
    assert comparison.loc["y", "betweenness_proposed"] > 0.0
    assert comparison.loc["x", "betweenness_pct_change"] is None  # 0 -> positive: undefined, not inf
    assert comparison.loc["y", "betweenness_pct_change"] is None


def test_pct_change_is_a_normal_number_when_status_quo_is_nonzero():
    """A pure star's hub is already at the maximum possible normalized
    betweenness (1.0) regardless of size, so growing a star doesn't move the
    number -- this instead uses a hub that already carries some through
    traffic (a-hub-b, a length-2 route) alongside a longer alternate route
    (a-c-d-b, length 3), then adds a shortcut (hub-c) that gives the hub a
    genuinely larger share of shortest paths."""
    g_before = nx.Graph()
    g_before.add_edge("a", "hub", distance_km=1.0)
    g_before.add_edge("hub", "b", distance_km=1.0)
    g_before.add_edge("a", "c", distance_km=1.0)
    g_before.add_edge("c", "d", distance_km=1.0)
    g_before.add_edge("d", "b", distance_km=1.0)
    for n in g_before.nodes:
        g_before.nodes[n].update(_node_attrs(n))

    g_after = g_before.copy()
    g_after.add_edge("hub", "c", distance_km=1.0)  # shortcut -> hub captures more shortest paths

    comparison = compare_status_quo_vs_proposed(g_before, g_after).set_index("node_id")

    assert comparison.loc["hub", "betweenness_status_quo"] > 0.0
    assert comparison.loc["hub", "betweenness_pct_change"] > 0.0
