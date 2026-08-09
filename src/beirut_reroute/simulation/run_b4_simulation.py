"""Status-quo vs proposed simulation for the B4 corridor, on real data.

Second integration smoke test (after the B4 MCLP proof-of-concept): builds
B4's real trunk route by chaining shortest paths between its actual geocoded
stops on the congested drive graph, detects the REAL OSM traffic-signal
nodes along that route (`highway=traffic_signals`), and compares a fixed-
time-only signal scenario (status quo) against rule-based transit signal
priority (proposed) — the "modern-technology layer" from the proposal.

Guardrail from the plan doc: both scenarios use the IDENTICAL edge free-flow
travel times from the same congested graph; only `priority_enabled` differs.
Any speed gain must come from signal-priority delay reduction alone, never a
blanket road-speed boost.

Trip demand = the 3 real H3 cells MCLP assigned to B4 (from
`underserved_line_assignment.geojson`) — status-quo trips for these cells
are `covered=False` (matching the accessibility scoring's own >30min-walk
definition of uncovered) since there is no reliable existing connection;
proposed trips ride the new MCLP feeder stop -> B4 trunk -> Martyrs' Square.

Usage:
    python -m beirut_reroute.simulation.run_b4_simulation
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import simpy

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings
from beirut_reroute.simulation import metrics
from beirut_reroute.simulation.network_sim import TrunkEdgeCrossing, trunk_vehicle_process
from beirut_reroute.simulation.scenarios import SignalSpec, TripSpec, VehicleSpec, proposed, status_quo

TRANSFER_TIME_S = 2 * 60


def build_b4_edge_plan(drive_graph: nx.MultiDiGraph, b4_stops: gpd.GeoDataFrame):
    stop_nodes = ox.distance.nearest_nodes(
        drive_graph, b4_stops.geometry.x.values, b4_stops.geometry.y.values
    )
    edge_plan = []
    signal_specs = {}
    edge_length_m = {}

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
    travel time under a given priority setting — used as the shared
    trunk_ride_time_s fed into every rider TripSpec for that scenario.
    """
    env = simpy.Environment()
    from beirut_reroute.simulation.signal_priority import SignalizedIntersection

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


def main() -> None:
    b4 = gpd.read_file(settings.INTERIM_DIR / "ocftc_stops_geocoded.geojson")
    b4 = b4[(b4["line_id"] == "B4") & (~b4["qa_flagged_suspect"])].sort_values("stop_order")
    drive_graph = ox.load_graphml(settings.PROCESSED_DIR / "gba_drive_congested.graphml")
    walk_graph = ox.load_graphml(settings.PROCESSED_DIR / "gba_walk_timed.graphml")

    edge_plan, signal_specs, edge_length_m, trunk_access_node = build_b4_edge_plan(drive_graph, b4)
    print(f"B4 route: {len(edge_plan)} edges, {len(signal_specs)} real OSM traffic-signal intersections")

    sq_trunk_time_s = measure_trunk_time(edge_plan, signal_specs, priority_enabled=False)
    proposed_trunk_time_s = measure_trunk_time(edge_plan, signal_specs, priority_enabled=True)
    print(f"Trunk travel time (Hadath -> Martyrs' Square): "
          f"status quo {sq_trunk_time_s/60:.1f} min, proposed {proposed_trunk_time_s/60:.1f} min "
          f"({(sq_trunk_time_s - proposed_trunk_time_s)/60:.1f} min saved by signal priority)")

    demand = gpd.read_file(settings.PROCESSED_DIR / "underserved_line_assignment.geojson")
    demand = demand[demand["nearest_line"] == "B4"]
    print(f"B4-assigned demand cells: {len(demand)} (population {demand['population'].sum():,.0f})")

    feeder_stops = gpd.read_file(settings.PROCESSED_DIR / "feeder_stops_all_lines.geojson")
    feeder_stops = feeder_stops[feeder_stops["line_id"] == "B4"]

    feeder_nodes = ox.distance.nearest_nodes(
        drive_graph, feeder_stops.geometry.x.values, feeder_stops.geometry.y.values
    )
    feeder_ride_times_s = []
    for n in feeder_nodes:
        t = nx.shortest_path_length(drive_graph, n, trunk_access_node, weight="travel_time")
        feeder_ride_times_s.append(t)

    walk_nodes = ox.distance.nearest_nodes(
        walk_graph, demand["centroid_lon"].values, demand["centroid_lat"].values
    )
    feeder_walk_nodes = ox.distance.nearest_nodes(
        walk_graph, feeder_stops.geometry.x.values, feeder_stops.geometry.y.values
    )

    trip_weights = {}
    sq_trip_specs, prop_trip_specs = [], []
    for i, (cell_idx, walk_node) in enumerate(zip(demand.index, walk_nodes)):
        pop = float(demand.loc[cell_idx, "population"])
        trip_id = f"b4_cell_{cell_idx}"
        trip_weights[trip_id] = pop

        sq_trip_specs.append(TripSpec(
            trip_id=trip_id, origin_cell=str(cell_idx), covered=False,
            walk_time_s=0.0, trunk_ride_time_s=0.0,
        ))

        best = min(
            range(len(feeder_walk_nodes)),
            key=lambda j: nx.shortest_path_length(walk_graph, walk_node, feeder_walk_nodes[j], weight="travel_time"),
        )
        walk_time_s = nx.shortest_path_length(walk_graph, walk_node, feeder_walk_nodes[best], weight="travel_time")
        prop_trip_specs.append(TripSpec(
            trip_id=trip_id, origin_cell=str(cell_idx), covered=True,
            walk_time_s=walk_time_s, wait_time_s=settings.DEFAULT_WAIT_TIME_MIN * 60,
            feeder_ride_time_s=feeder_ride_times_s[best], transfer_time_s=TRANSFER_TIME_S,
            trunk_ride_time_s=proposed_trunk_time_s,
        ))

    for spec in sq_trip_specs:
        spec.trunk_ride_time_s = sq_trunk_time_s  # only relevant for covered=True trips; harmless here

    b4_vehicle = VehicleSpec(vehicle_id="B4_bus_1", edges=edge_plan)

    sq_result = status_quo(sq_trip_specs, [b4_vehicle], signal_specs, sim_duration_s=7200)
    prop_result = proposed(prop_trip_specs, [b4_vehicle], signal_specs, sim_duration_s=7200)

    sq_summary = metrics.summarize(sq_result, edge_length_m, trip_weights)
    prop_summary = metrics.summarize(prop_result, edge_length_m, trip_weights)
    comparison = metrics.compare(sq_summary, prop_summary)

    print("\nStatus quo vs proposed (B4 corridor):")
    print(comparison.to_string())


if __name__ == "__main__":
    main()
