import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from beirut_reroute.optimization.mclp import solve_mclp


def _toy_problem():
    demand_weights = {"i1": 10.0, "i2": 5.0, "i3": 1.0}
    coverage_sets = {
        "i1": {"jA", "jC"},
        "i2": {"jA"},
        "i3": {"jB"},
    }
    return demand_weights, coverage_sets


def test_mclp_cbc_picks_highest_weight_candidate_under_budget():
    demand_weights, coverage_sets = _toy_problem()
    result = solve_mclp(demand_weights, coverage_sets, budget=1, solver="cbc")

    assert result.selected_candidates == ["jA"]
    assert result.covered_weight == 15.0
    assert result.total_weight == 16.0
    assert result.coverage_fraction == 15.0 / 16.0


def test_mclp_cbc_full_budget_covers_everything():
    demand_weights, coverage_sets = _toy_problem()
    result = solve_mclp(demand_weights, coverage_sets, budget=3, solver="cbc")

    assert result.covered_weight == result.total_weight == 16.0
    assert set(result.covered_demand_ids) == {"i1", "i2", "i3"}


def test_mclp_uncoverable_demand_is_never_covered():
    demand_weights = {"i1": 10.0, "i_isolated": 100.0}
    coverage_sets = {"i1": {"jA"}}  # i_isolated has no candidate at all
    result = solve_mclp(demand_weights, coverage_sets, budget=5, solver="cbc")

    assert "i_isolated" not in result.covered_demand_ids
    assert result.covered_weight == 10.0
