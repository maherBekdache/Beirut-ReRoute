"""Build and run the status-quo and proposed simulation scenarios.

Both scenarios share the exact same trunk edge free-flow travel times and
vehicle/trip process code — the ONLY differences allowed are:
  1. `priority_enabled` on the signals (status quo: False, proposed: True)
  2. the feeder legs available to each trip (status quo: none/informal-only,
     proposed: the MCLP-designed feeder network)
This is the guardrail from the plan doc §5: since there are no dedicated
lanes in this proposal, any speed gain in `proposed` must come only from
signal-priority delay reduction, never a blanket road-speed boost. Do not
pass different `free_travel_time_s` values between scenarios for the same
edge.
"""

from __future__ import annotations

from dataclasses import dataclass

import simpy

from .network_sim import TripRecord, TrunkEdgeCrossing, trip_process, trunk_vehicle_process
from .signal_priority import SignalizedIntersection


@dataclass
class TripSpec:
    trip_id: str
    origin_cell: str
    covered: bool
    walk_time_s: float
    trunk_ride_time_s: float
    wait_time_s: float = 0.0
    feeder_ride_time_s: float = 0.0
    transfer_time_s: float = 0.0


@dataclass
class SignalSpec:
    node_id: object
    cycle_s: float = 90.0
    green_s: float = 45.0
    max_extension_s: float = 15.0


@dataclass
class VehicleSpec:
    vehicle_id: str
    # each element: (edge_tuple, free_travel_time_s, signal_node_id_or_None)
    edges: list[tuple[tuple, float, object | None]]


@dataclass
class ScenarioResult:
    name: str
    trip_records: list[TripRecord]
    vehicle_log: list[TrunkEdgeCrossing]
    signals: dict[object, SignalizedIntersection]


def run_scenario(
    name: str,
    trip_specs: list[TripSpec],
    vehicle_specs: list[VehicleSpec],
    signal_specs: list[SignalSpec],
    priority_enabled: bool,
    sim_duration_s: float,
) -> ScenarioResult:
    env = simpy.Environment()

    signals = {
        spec.node_id: SignalizedIntersection(
            env,
            spec.node_id,
            cycle_s=spec.cycle_s,
            green_s=spec.green_s,
            max_extension_s=spec.max_extension_s,
            priority_enabled=priority_enabled,
        )
        for spec in signal_specs
    }

    trip_records = []
    for spec in trip_specs:
        trip = TripRecord(trip_id=spec.trip_id, origin_cell=spec.origin_cell, covered=spec.covered)
        trip_records.append(trip)
        env.process(
            trip_process(
                env,
                trip,
                walk_time_s=spec.walk_time_s,
                wait_time_s=spec.wait_time_s,
                feeder_ride_time_s=spec.feeder_ride_time_s,
                transfer_time_s=spec.transfer_time_s,
                trunk_ride_time_s=spec.trunk_ride_time_s,
            )
        )

    vehicle_log: list[TrunkEdgeCrossing] = []
    for vspec in vehicle_specs:
        edge_plan = [
            (edge, t, signals.get(sig_node)) for edge, t, sig_node in vspec.edges
        ]
        env.process(trunk_vehicle_process(env, vspec.vehicle_id, edge_plan, vehicle_log))

    env.run(until=sim_duration_s)
    return ScenarioResult(name=name, trip_records=trip_records, vehicle_log=vehicle_log, signals=signals)


def status_quo(
    trip_specs: list[TripSpec],
    vehicle_specs: list[VehicleSpec],
    signal_specs: list[SignalSpec],
    sim_duration_s: float,
) -> ScenarioResult:
    return run_scenario(
        "status_quo", trip_specs, vehicle_specs, signal_specs,
        priority_enabled=False, sim_duration_s=sim_duration_s,
    )


def proposed(
    trip_specs: list[TripSpec],
    vehicle_specs: list[VehicleSpec],
    signal_specs: list[SignalSpec],
    sim_duration_s: float,
) -> ScenarioResult:
    return run_scenario(
        "proposed", trip_specs, vehicle_specs, signal_specs,
        priority_enabled=True, sim_duration_s=sim_duration_s,
    )
