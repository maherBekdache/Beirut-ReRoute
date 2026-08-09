"""Rule-based transit signal priority (TSP) at a single signalized intersection.

Represents, in simulation, what real-time V2X/IEEE 802.11p vehicle-to-
infrastructure communication would enable: a bus in the "detection zone"
triggers a green extension (if currently green) or an early green / red
truncation (if currently red), capped at one intervention per cycle — matching
real-world TSP conflict-monitoring limits so cross-traffic isn't starved.

`priority_enabled=False` reproduces today's fixed-time signal behavior, used
for the status-quo scenario so both scenarios share identical signal code and
only the priority rule itself differs.
"""

from __future__ import annotations

import simpy

GREEN = "green"
RED = "red"


class SignalizedIntersection:
    def __init__(
        self,
        env: simpy.Environment,
        node_id: int | str,
        cycle_s: float = 90.0,
        green_s: float = 45.0,
        max_extension_s: float = 15.0,
        detection_zone_m: float = 120.0,
        priority_enabled: bool = True,
    ):
        self.env = env
        self.node_id = node_id
        self.cycle_s = cycle_s
        self.green_s = green_s
        self.max_extension_s = max_extension_s
        self.detection_zone_m = detection_zone_m
        self.priority_enabled = priority_enabled

        self.phase = GREEN
        self._extended_this_cycle = False
        self.total_priority_events = 0
        self.green_event = env.event()
        self.action = env.process(self._run())

    def _run(self):
        while True:
            self.phase = GREEN
            evt, self.green_event = self.green_event, self.env.event()
            if not evt.triggered:
                evt.succeed()
            self._extended_this_cycle = False

            remaining = self.green_s
            while remaining > 0:
                start = self.env.now
                try:
                    yield self.env.timeout(remaining)
                    remaining = 0
                except simpy.Interrupt:
                    elapsed = self.env.now - start
                    remaining = (remaining - elapsed) + self.max_extension_s

            self.phase = RED
            red_duration = self.cycle_s - self.green_s
            try:
                yield self.env.timeout(red_duration)
            except simpy.Interrupt:
                pass  # red truncated -> loop restarts into green immediately

    def bus_approaching(self) -> None:
        """Call when a trunk bus enters the detection zone."""
        if not self.priority_enabled or self._extended_this_cycle:
            return
        self._extended_this_cycle = True
        self.total_priority_events += 1
        if self.action.is_alive:
            self.action.interrupt()

    def cross(self, is_trunk_bus: bool):
        """Simpy sub-generator: `yield from signal.cross(is_trunk_bus)`.

        Trunk buses request priority on approach; all other traffic just
        waits out the fixed-time cycle like today.
        """
        if is_trunk_bus:
            self.bus_approaching()
        if self.phase != GREEN:
            yield self.green_event
