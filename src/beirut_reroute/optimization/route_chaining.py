"""Chain MCLP-selected feeder stops into a route geometry toward the trunk line.

This is a deliberate simplification, not a full vehicle-routing solve (see
plan doc "Feeder Network Optimization" and README "Known Limitations"): stops
are connected via a minimum-spanning-tree ordering rooted at the trunk access
point, then each consecutive pair is joined by its shortest real-street path
so the output geometry is actually road-following.
"""

from __future__ import annotations

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import linemerge


def _mst_visit_order(
    stop_node_ids: list[int],
    trunk_access_node: int,
    graph: nx.MultiDiGraph,
) -> list[int]:
    """DFS pre-order over a minimum spanning tree of {stops + trunk access},
    using shortest-path travel time between each pair as the MST edge weight.
    Root the walk at the trunk access node so the route naturally runs stop
    -> ... -> stop -> trunk.
    """
    nodes = [trunk_access_node] + [n for n in stop_node_ids if n != trunk_access_node]
    complete = nx.Graph()
    complete.add_nodes_from(nodes)
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            try:
                w = nx.shortest_path_length(graph, a, b, weight="travel_time")
            except nx.NetworkXNoPath:
                w = float("inf")
            complete.add_edge(a, b, weight=w)

    mst = nx.minimum_spanning_tree(complete, weight="weight")
    order = list(nx.dfs_preorder_nodes(mst, source=trunk_access_node))
    return order


def build_feeder_route(
    stop_points: list[Point],
    trunk_access_point: Point,
    graph: nx.MultiDiGraph,
) -> LineString:
    """Return one road-following LineString visiting all `stop_points` and
    ending at `trunk_access_point`.
    """
    if not stop_points:
        raise ValueError("build_feeder_route requires at least one stop")

    all_points = stop_points + [trunk_access_point]
    node_ids = ox.distance.nearest_nodes(
        graph, [p.x for p in all_points], [p.y for p in all_points]
    )
    stop_nodes, trunk_node = node_ids[:-1], node_ids[-1]

    order = _mst_visit_order(list(stop_nodes), trunk_node, graph)

    segments = []
    for a, b in zip(order[:-1], order[1:]):
        path = nx.shortest_path(graph, a, b, weight="travel_time")
        coords = []
        for u, v in zip(path[:-1], path[1:]):
            edge_data = graph.get_edge_data(u, v)[0]
            geom = edge_data.get("geometry")
            if geom is not None:
                coords.extend(geom.coords)
            else:
                coords.append((graph.nodes[u]["x"], graph.nodes[u]["y"]))
        coords.append((graph.nodes[path[-1]]["x"], graph.nodes[path[-1]]["y"]))
        segments.append(LineString(coords))

    merged = linemerge(MultiLineString(segments))
    if isinstance(merged, LineString):
        return merged
    # linemerge can return a MultiLineString if segments aren't contiguous
    # (shouldn't happen given the DFS order above); fall back to concatenation.
    coords = [c for seg in segments for c in seg.coords]
    return LineString(coords)
