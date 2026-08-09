"""Maximal Covering Location Problem (MCLP) solver for one trunk-line cluster.

    maximize   sum_i w_i * x_i
    s.t.       x_i <= sum_{j in N_i} y_j     for all demand points i
               sum_j y_j <= budget
               x_i, y_j in {0, 1}

    N_i = candidate stops within walk-time reach of demand point i.

Two backends are provided (see plan doc "Feeder Network Optimization"):
- "cbc" (via PuLP): simple, fine for small/intercity clusters.
- "cp_sat" (via OR-Tools): more robust at scale, use for dense city-center
  clusters where the candidate/demand count gets large.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MCLPResult:
    selected_candidates: list[str]
    covered_demand_ids: list[str]
    covered_weight: float
    total_weight: float
    status: str

    @property
    def coverage_fraction(self) -> float:
        return self.covered_weight / self.total_weight if self.total_weight else 0.0


def solve_mclp_cbc(
    demand_weights: dict[str, float],
    coverage_sets: dict[str, set[str]],
    budget: int,
    time_limit_s: int = 60,
) -> MCLPResult:
    import pulp

    demand_ids = list(demand_weights)
    candidate_ids = sorted({j for s in coverage_sets.values() for j in s})

    prob = pulp.LpProblem("MCLP", pulp.LpMaximize)
    y = {j: pulp.LpVariable(f"y_{i}", cat="Binary") for i, j in enumerate(candidate_ids)}
    y = dict(zip(candidate_ids, y.values()))
    x = {i: pulp.LpVariable(f"x_{k}", cat="Binary") for k, i in enumerate(demand_ids)}
    x = dict(zip(demand_ids, x.values()))

    prob += pulp.lpSum(demand_weights[i] * x[i] for i in demand_ids)

    for i in demand_ids:
        covering = coverage_sets.get(i, set())
        if covering:
            prob += x[i] <= pulp.lpSum(y[j] for j in covering)
        else:
            prob += x[i] == 0

    prob += pulp.lpSum(y.values()) <= budget

    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit_s))

    selected = [j for j, var in y.items() if var.value() and var.value() > 0.5]
    covered = [i for i in demand_ids if x[i].value() and x[i].value() > 0.5]
    covered_weight = sum(demand_weights[i] for i in covered)
    total_weight = sum(demand_weights.values())

    return MCLPResult(
        selected_candidates=selected,
        covered_demand_ids=covered,
        covered_weight=covered_weight,
        total_weight=total_weight,
        status=pulp.LpStatus[prob.status],
    )


def solve_mclp_cp_sat(
    demand_weights: dict[str, float],
    coverage_sets: dict[str, set[str]],
    budget: int,
    time_limit_s: int = 60,
) -> MCLPResult:
    from ortools.sat.python import cp_model

    demand_ids = list(demand_weights)
    candidate_ids = sorted({j for s in coverage_sets.values() for j in s})

    model = cp_model.CpModel()
    y = {j: model.NewBoolVar(f"y_{j}") for j in candidate_ids}
    x = {i: model.NewBoolVar(f"x_{i}") for i in demand_ids}

    # CP-SAT requires integer weights — scale to nearest integer.
    scaled_weights = {i: int(round(w)) for i, w in demand_weights.items()}
    model.Maximize(sum(scaled_weights[i] * x[i] for i in demand_ids))

    for i in demand_ids:
        covering = coverage_sets.get(i, set())
        if covering:
            model.Add(x[i] <= sum(y[j] for j in covering))
        else:
            model.Add(x[i] == 0)

    model.Add(sum(y.values()) <= budget)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    status = solver.Solve(model)

    selected = [j for j in candidate_ids if solver.Value(y[j])]
    covered = [i for i in demand_ids if solver.Value(x[i])]
    covered_weight = sum(demand_weights[i] for i in covered)
    total_weight = sum(demand_weights.values())

    return MCLPResult(
        selected_candidates=selected,
        covered_demand_ids=covered,
        covered_weight=covered_weight,
        total_weight=total_weight,
        status=solver.StatusName(status),
    )


def solve_mclp(
    demand_weights: dict[str, float],
    coverage_sets: dict[str, set[str]],
    budget: int,
    solver: str = "cbc",
    time_limit_s: int = 60,
) -> MCLPResult:
    if solver == "cbc":
        return solve_mclp_cbc(demand_weights, coverage_sets, budget, time_limit_s)
    if solver == "cp_sat":
        return solve_mclp_cp_sat(demand_weights, coverage_sets, budget, time_limit_s)
    raise ValueError(f"Unknown solver {solver!r} — expected 'cbc' or 'cp_sat'")
