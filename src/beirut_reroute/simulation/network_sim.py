"""Trip and vehicle agent processes for the status-quo vs proposed comparison.

Trips are representative flows (H3 population-weighted origins -> major
hubs/CBD), not a full four-step OD model — a documented simplification (see
README "Known Limitations"). Each trip agent walks to its nearest stop, rides
a feeder (if the scenario has one), transfers, rides the trunk line, and
arrives; every leg's start/end sim-time is recorded for `metrics.py` to
aggregate into the three comparison metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import simpy

from .signal_priority import SignalizedIntersection


@dataclass
class TripRecord:
    trip_id: str
    origin_cell: str
    covered: bool
    leg_times: dict[str, float] = field(default_factory=dict)  # leg -> duration (s)
    start_time: float = 0.0
    end_time: float | None = None

    @property
    def door_to_door_s(self) -> float | None:
        if self.end_time is None:
            return None
        return self.end_time - self.start_time


@dataclass
class TrunkEdgeCrossing:
    vehicle_id: str
    edge: tuple
    free_travel_time_s: float
    actual_time_s: float
    signal_wait_s: float


def trip_process(
    env: simpy.Environment,
    trip: TripRecord,
    walk_time_s: float,
    wait_time_s: float,
    feeder_ride_time_s: float,
    transfer_time_s: float,
    trunk_ride_time_s: float,
):
    """A single representative trip: walk -> [wait -> feeder -> transfer] -> trunk -> arrive.

    If the origin cell is uncovered (`trip.covered = False`), the trip is
    recorded but not timed further — it must not silently pull citywide
    averages toward "fast" by pretending an unreachable trip completed.
    """
    trip.start_time = env.now
    if not trip.covered:
        trip.end_time = None
        return

    yield env.timeout(walk_time_s)
    trip.leg_times["walk"] = walk_time_s

    if feeder_ride_time_s > 0:
        yield env.timeout(wait_time_s)
        trip.leg_times["wait"] = wait_time_s
        yield env.timeout(feeder_ride_time_s)
        trip.leg_times["feeder"] = feeder_ride_time_s
        yield env.timeout(transfer_time_s)
        trip.leg_times["transfer"] = transfer_time_s

    yield env.timeout(trunk_ride_time_s)
    trip.leg_times["trunk"] = trunk_ride_time_s

    trip.end_time = env.now


def trunk_vehicle_process(
    env: simpy.Environment,
    vehicle_id: str,
    edge_plan: list[tuple[tuple, float, SignalizedIntersection | None]],
    log: list[TrunkEdgeCrossing],
):
    """A trunk bus traversing a sequence of (edge, free_travel_time_s, signal_at_end)
    triples. `signal_at_end` is None for non-signalized edges. The bus always
    requests priority (is_trunk_bus=True) — the status-quo scenario should
    build its SignalizedIntersection objects with `priority_enabled=False` so
    the request is a no-op, keeping both scenarios' vehicle code identical.
    """
    for edge, free_time_s, signal in edge_plan:
        t0 = env.now
        yield env.timeout(free_time_s)

        signal_wait_start = env.now
        if signal is not None:
            yield from signal.cross(is_trunk_bus=True)
        signal_wait_s = env.now - signal_wait_start

        log.append(
            TrunkEdgeCrossing(
                vehicle_id=vehicle_id,
                edge=edge,
                free_travel_time_s=free_time_s,
                actual_time_s=env.now - t0,
                signal_wait_s=signal_wait_s,
            )
        )
