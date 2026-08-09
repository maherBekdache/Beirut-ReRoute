"""Build a real signalized trunk route from a line's geocoded stops, and
measure its status-quo vs proposed (signal priority) travel time.

Shared by run_b4_simulation.py (single-line smoke test) and
run_simulation_all_lines.py (citywide loop) so the route-building and
timing logic is defined once.
"""

from __future__ import annotations

import geopandas as gpd
import networkx as nx
import osmnx as ox
import simpy

from beirut_reroute.simulation.network_sim import TrunkEdgeCrossing, trunk_vehicle_process
from beirut_reroute.simulation.scenarios import SignalSpec
from beirut_reroute.simulation.signal_priority import SignalizedIntersection


def build_edge_plan(drive_graph: nx.MultiDiGraph, line_stops: gpd.GeoDataFrame):
    """line_stops must be sorted by stop_order already."""
    stop_nodes = ox.distance.nearest_nodes(
        drive_graph, line_stops.geometry.x.values, line_stops.geometry.y.values
    )
    edge_plan = []
    signal_specs: dict = {}
    edge_length_m: dict = {}

    for u_stop, v_stop in zip(stop_nodes[:-1], stop_nodes[1:]):
        path = nx.shortest_path(drive_graph, u_stop, v_stop, weight="travel_time")
        for u, v in zip(path[:-1], path[1:]):
            edge_data = drive_graph.get_edge_data(u, v)[0]
            travel_time_s = float(edge_data["travel_time"])
            length_m = float(edge_data.get("length", 0.0))
            is_signal = drive_graph.nodes[v].get("highway") == "traffic_signals"
            signal_node = v if is_signal else None
            if is_signal and v not in signal_specs:
                signal_specs[v] = SignalSpec(node_id=v, cycle_s=90.0, green_s=45.0, max_extension_s=15.0)
            edge_plan.append(((u, v), travel_time_s, signal_node))
            edge_length_m[(u, v)] = length_m

    return edge_plan, list(signal_specs.values()), edge_length_m, stop_nodes[0]


def measure_trunk_time(edge_plan, signal_specs, priority_enabled: bool) -> float:
    """Run a single trunk vehicle alone (no trips) to measure realized trunk
    travel time under a given priority setting.
    """
    env = simpy.Environment()
    signals = {
        s.node_id: SignalizedIntersection(
            env, s.node_id, cycle_s=s.cycle_s, green_s=s.green_s,
            max_extension_s=s.max_extension_s, priority_enabled=priority_enabled,
        )
        for s in signal_specs
    }
    plan_with_signals = [(edge, t, signals.get(n)) for edge, t, n in edge_plan]
    log: list[TrunkEdgeCrossing] = []
    vehicle_proc = env.process(trunk_vehicle_process(env, "measure", plan_with_signals, log))
    # SignalizedIntersection processes loop forever (fixed-time cycling), so
    # env.run() with no bound would never return on its own — run only until
    # the vehicle itself finishes its route.
    env.run(until=vehicle_proc)
    return sum(c.actual_time_s for c in log)
