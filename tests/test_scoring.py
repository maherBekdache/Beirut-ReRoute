import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from beirut_reroute.accessibility.scoring import coverage_score, score_grid


def _toy_grid(populations):
    return pd.DataFrame({"population": populations})


def test_score_grid_binary_coverage_respects_threshold():
    grid = _toy_grid([100, 100])
    walk_times = np.array([5.0, 40.0])  # first under T_MAX_MIN, second way over

    scored = score_grid(grid, walk_times)

    assert scored.loc[0, "coverage_binary"] == 1
    assert scored.loc[1, "coverage_binary"] == 0


def test_coverage_score_is_population_weighted():
    grid = _toy_grid([90, 10])
    walk_times = np.array([5.0, 40.0])  # covered cell has 90% of the population
    scored = score_grid(grid, walk_times)

    assert coverage_score(scored) == 0.9


def test_coverage_score_handles_zero_population():
    grid = _toy_grid([0, 0])
    scored = score_grid(grid, np.array([1.0, 1.0]))
    assert coverage_score(scored) == 0.0


def test_score_grid_feeder_leg_adds_wait_time():
    grid = _toy_grid([100])
    walk_times = np.array([5.0])
    ride_times = np.array([10.0])

    no_feeder = score_grid(grid, walk_times)
    with_feeder = score_grid(grid, walk_times, ride_time_min=ride_times)

    assert with_feeder.loc[0, "total_time_min"] > no_feeder.loc[0, "total_time_min"]
