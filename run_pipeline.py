"""Run the full Beirut ReRoute pipeline end-to-end, in dependency order.

Each stage's own module docstring explains what it does and why; this file
is just the ordered call sequence, so the entire project can be reproduced
with one command instead of 12 remembered `python -m ...` invocations.

Usage:
    .venv/Scripts/python.exe run_pipeline.py                # everything
    .venv/Scripts/python.exe run_pipeline.py --skip-fetch    # reuse already-downloaded raw data
    .venv/Scripts/python.exe run_pipeline.py --stop-after mclp
"""

from __future__ import annotations

import argparse
import time

STAGES = [
    # (name, module, "fetch"=external downloads, "compute"=local only)
    ("osm", "beirut_reroute.data_acquisition.fetch_osm", "fetch"),
    ("worldpop", "beirut_reroute.data_acquisition.fetch_worldpop", "fetch"),
    ("zones", "beirut_reroute.processing.build_zones", "compute"),
    ("network_graph", "beirut_reroute.processing.build_network_graph", "compute"),
    ("informal_routes", "beirut_reroute.data_acquisition.parse_lebanese_bus_routes", "compute"),
    ("informal_stops", "beirut_reroute.processing.sample_informal_stops", "compute"),
    ("ocftc_stop_names", "beirut_reroute.data_acquisition.fetch_actcpt_stops", "fetch"),
    ("ocftc_geocode", "beirut_reroute.data_acquisition.ocftc_loader", "fetch"),
    ("accessibility", "beirut_reroute.accessibility.run_status_quo", "compute"),
    ("mclp", "beirut_reroute.optimization.run_mclp_all_lines", "compute"),
    ("simulation", "beirut_reroute.simulation.run_simulation_all_lines", "compute"),
    ("qa_map", "beirut_reroute.viz.maps", "compute"),
    ("results_map", "beirut_reroute.viz.results_map", "compute"),
    # Layer A -- national/regional vision (see "Lebanon ReConnect - Layer A
    # Implementation Plan.md"). Independent of everything above except
    # sharing the same config/settings.py and output directories.
    ("national_geocode", "beirut_reroute.national_network.geocode_nodes", "fetch"),
    ("national_vision", "beirut_reroute.national_network.run_vision_analysis", "compute"),
    # Static charts for the report/video -- reads Layer A + Layer B outputs
    # above, must run last.
    ("charts", "beirut_reroute.viz.charts", "compute"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-fetch", action="store_true",
                         help="Skip stages that hit the network (OSM/WorldPop/transitapp.com/Nominatim); "
                              "reuse whatever is already in data/raw/.")
    parser.add_argument("--stop-after", default=None,
                         help="Stage name to stop after (see STAGES in this file for names).")
    args = parser.parse_args()

    for name, module, kind in STAGES:
        if args.skip_fetch and kind == "fetch":
            print(f"=== [{name}] SKIPPED (--skip-fetch) ===")
            continue

        print(f"\n=== [{name}] python -m {module} ===")
        t0 = time.time()
        mod = __import__(module, fromlist=["main"])
        mod.main()
        print(f"=== [{name}] done in {time.time() - t0:.1f}s ===")

        if args.stop_after == name:
            print(f"\nStopping after '{name}' as requested.")
            return

    print("\nPipeline complete. See README.md 'Real results' and outputs/maps/qa_map.html.")


if __name__ == "__main__":
    main()
