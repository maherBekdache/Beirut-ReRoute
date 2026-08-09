import sys
from pathlib import Path

import simpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from beirut_reroute.simulation.signal_priority import SignalizedIntersection


def _bus_arrival(env, signal, arrive_at, is_trunk_bus, results):
    yield env.timeout(arrive_at)
    t0 = env.now
    yield from signal.cross(is_trunk_bus=is_trunk_bus)
    results["wait_s"] = env.now - t0


def test_priority_truncates_red_phase():
    env = simpy.Environment()
    signal = SignalizedIntersection(
        env, "n1", cycle_s=20, green_s=10, max_extension_s=15, priority_enabled=True
    )
    results = {}
    # arrives 2s into red (green: [0,10), red: [10,20))
    env.process(_bus_arrival(env, signal, arrive_at=12, is_trunk_bus=True, results=results))
    env.run(until=30)

    assert results["wait_s"] == 0


def test_no_priority_waits_out_full_red_phase():
    env = simpy.Environment()
    signal = SignalizedIntersection(
        env, "n1", cycle_s=20, green_s=10, max_extension_s=15, priority_enabled=False
    )
    results = {}
    env.process(_bus_arrival(env, signal, arrive_at=12, is_trunk_bus=True, results=results))
    env.run(until=30)

    assert results["wait_s"] == 8  # waits until t=20 when red ends naturally


def test_priority_capped_at_one_intervention_per_cycle():
    # green: [0,10) then red: [10,20). Bus A arrives 2s before the scheduled
    # red at t=8 and extends green by 5s (green now ends at t=15). Bus B
    # arrives at t=12 -- still within that same (extended) green phase -- and
    # must NOT get a second extension, since only one intervention per cycle
    # is allowed. A third bus arriving after the (unextended-further) red
    # starts at t=15 must wait out the full red like status quo.
    env = simpy.Environment()
    signal = SignalizedIntersection(
        env, "n1", cycle_s=20, green_s=10, max_extension_s=5, priority_enabled=True
    )
    results_a, results_b, results_c = {}, {}, {}
    env.process(_bus_arrival(env, signal, arrive_at=8, is_trunk_bus=True, results=results_a))
    env.process(_bus_arrival(env, signal, arrive_at=12, is_trunk_bus=True, results=results_b))
    env.process(_bus_arrival(env, signal, arrive_at=16, is_trunk_bus=True, results=results_c))
    env.run(until=40)

    assert signal.total_priority_events == 1
    assert results_a["wait_s"] == 0  # arrived while green, no wait either way
    assert results_b["wait_s"] == 0  # still within the (once-)extended green
    assert results_c["wait_s"] == 9  # red now runs its full course: [15,25) minus the 16s arrival offset -> 24-16


def test_no_priority_when_not_a_trunk_bus():
    env = simpy.Environment()
    signal = SignalizedIntersection(
        env, "n1", cycle_s=20, green_s=10, max_extension_s=15, priority_enabled=True
    )
    results = {}
    env.process(_bus_arrival(env, signal, arrive_at=12, is_trunk_bus=False, results=results))
    env.run(until=30)

    assert results["wait_s"] == 8  # general traffic gets no priority request
