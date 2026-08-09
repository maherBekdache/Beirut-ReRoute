"""Compute the three status-quo-vs-proposed comparison metrics from scenario output.

1. Population-weighted coverage       -> fraction of trips (weighted by
   origin-cell population) that completed at all (`trip.covered`).
2. Average door-to-door trip time      -> mean / population-weighted mean of
   completed trips' total duration, decomposed by leg.
3. Trunk corridor bus speed            -> distance / time over trunk vehicle
   edge crossings, isolating the signal-priority effect from `signal_wait_s`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .network_sim import TripRecord, TrunkEdgeCrossing
from .scenarios import ScenarioResult


@dataclass
class MetricsSummary:
    scenario_name: str
    coverage_fraction: float
    coverage_weighted_fraction: float | None
    avg_door_to_door_s: float | None
    avg_door_to_door_weighted_s: float | None
    avg_leg_times_s: dict[str, float]
    trunk_avg_speed_kmh: float | None
    trunk_total_signal_wait_s: float


def _weighted_mean(values: list[float], weights: list[float]) -> float | None:
    total_w = sum(weights)
    if total_w == 0:
        return None
    return sum(v * w for v, w in zip(values, weights)) / total_w


def summarize(
    result: ScenarioResult,
    edge_length_m: dict[tuple, float],
    trip_weights: dict[str, float] | None = None,
) -> MetricsSummary:
    trips = result.trip_records
    n = len(trips)
    covered = [t for t in trips if t.covered and t.end_time is not None]

    coverage_fraction = len(covered) / n if n else 0.0

    weighted_coverage = None
    if trip_weights:
        total_w = sum(trip_weights.get(t.trip_id, 0.0) for t in trips)
        covered_w = sum(trip_weights.get(t.trip_id, 0.0) for t in covered)
        weighted_coverage = covered_w / total_w if total_w else 0.0

    door_to_door = [t.door_to_door_s for t in covered]
    avg_door_to_door = sum(door_to_door) / len(door_to_door) if door_to_door else None

    avg_door_to_door_weighted = None
    if trip_weights and covered:
        w = [trip_weights.get(t.trip_id, 0.0) for t in covered]
        avg_door_to_door_weighted = _weighted_mean(door_to_door, w)

    leg_names = {leg for t in covered for leg in t.leg_times}
    avg_leg_times = {
        leg: sum(t.leg_times.get(leg, 0.0) for t in covered) / len(covered)
        for leg in leg_names
    } if covered else {}

    trunk_speed_kmh = None
    total_signal_wait = sum(c.signal_wait_s for c in result.vehicle_log)
    if result.vehicle_log:
        total_dist_m = sum(edge_length_m.get(c.edge, 0.0) for c in result.vehicle_log)
        total_time_s = sum(c.actual_time_s for c in result.vehicle_log)
        if total_time_s > 0:
            trunk_speed_kmh = (total_dist_m / 1000) / (total_time_s / 3600)

    return MetricsSummary(
        scenario_name=result.name,
        coverage_fraction=coverage_fraction,
        coverage_weighted_fraction=weighted_coverage,
        avg_door_to_door_s=avg_door_to_door,
        avg_door_to_door_weighted_s=avg_door_to_door_weighted,
        avg_leg_times_s=avg_leg_times,
        trunk_avg_speed_kmh=trunk_speed_kmh,
        trunk_total_signal_wait_s=total_signal_wait,
    )


def compare(status_quo_summary: MetricsSummary, proposed_summary: MetricsSummary) -> pd.DataFrame:
    rows = [
        {
            "metric": "coverage_fraction (pop-weighted)",
            "status_quo": status_quo_summary.coverage_weighted_fraction,
            "proposed": proposed_summary.coverage_weighted_fraction,
        },
        {
            "metric": "avg_door_to_door_min (pop-weighted)",
            "status_quo": (status_quo_summary.avg_door_to_door_weighted_s or 0) / 60,
            "proposed": (proposed_summary.avg_door_to_door_weighted_s or 0) / 60,
        },
        {
            "metric": "trunk_avg_speed_kmh",
            "status_quo": status_quo_summary.trunk_avg_speed_kmh,
            "proposed": proposed_summary.trunk_avg_speed_kmh,
        },
    ]
    df = pd.DataFrame(rows).set_index("metric")
    df["delta"] = df["proposed"] - df["status_quo"]
    df["pct_change"] = (df["delta"] / df["status_quo"].abs()) * 100
    return df
