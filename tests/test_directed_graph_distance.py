"""Regression test for a real bug found on real data: the multi-source
Dijkstra "nearest stop" trick must compute distance FROM each point TO the
nearest stop, not FROM the stop outward -- these differ on a directed graph
(one-way streets). Caught via B3/B5's trunk routes failing to chain on the
real drive graph, which led to auditing `nearest_stop_walk_times` and
`travel_time_to_each_line` for the same directional mistake.
"""

import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from beirut_reroute.accessibility.scoring import nearest_stop_walk_times


def _one_way_chain_graph() -> nx.MultiDiGraph:
    """A -> B -> C only (one-way), so a walker AT A can reach C, but nothing
    is reachable FROM C (it's a dead end in the forward direction) -- the
    signature of the real one-way-street failure mode found in production.
    """
    G = nx.MultiDiGraph()
    G.graph["crs"] = "EPSG:4326"
    G.add_node("A", x=0.0, y=0.0)
    G.add_node("B", x=1.0, y=0.0)
    G.add_node("C", x=2.0, y=0.0)
    G.add_edge("A", "B", travel_time=60.0)
    G.add_edge("B", "C", travel_time=60.0)
    return G


def test_nearest_stop_walk_time_follows_edge_direction_not_reverse():
    G = _one_way_chain_graph()

    grid = gpd.GeoDataFrame({
        "centroid_lon": [0.0, 2.0],
        "centroid_lat": [0.0, 0.0],
    })
    stops = gpd.GeoDataFrame(geometry=gpd.points_from_xy([2.0], [0.0]))

    walk_times_min = nearest_stop_walk_times(grid, stops, G)

    # Cell at A must reach the stop at C via A->B->C (120s = 2min) -- NOT
    # infinity, which is what the pre-fix reversed-direction bug produced
    # (it computed distance FROM C outward, and C has no outgoing edges).
    assert walk_times_min[0] == 2.0
    # Cell at C is already at the stop.
    assert walk_times_min[1] == 0.0
