"""Scale the B4 signal-priority simulation (run_b4_simulation.py) to all real
lines that received an MCLP feeder network.

Same method as run_b4_simulation.py, generalized: for each line, chain its
real geocoded stops into a signalized trunk route, measure status-quo vs
proposed trunk time, build trip specs from its MCLP-assigned demand cells
riding its own MCLP-selected feeder stops, run both scenarios, then combine
every line's trip records into one citywide comparison.

Usage:
    python -m beirut_reroute.simulation.run_simulation_all_lines
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings
from beirut_reroute.simulation import metrics
from beirut_reroute.simulation.scenarios import ScenarioResult, TripSpec, VehicleSpec, proposed, status_quo
from beirut_reroute.simulation.trunk_route import build_edge_plan, measure_trunk_time

TRANSFER_TIME_S = 2 * 60


def build_trip_specs_for_line(
    line_id: str,
    demand: gpd.GeoDataFrame,
    feeder_stops: gpd.GeoDataFrame,
    drive_graph: nx.MultiDiGraph,
    walk_graph: nx.MultiDiGraph,
    trunk_access_node,
    sq_trunk_time_s: float,
    prop_trunk_time_s: float,
) -> tuple[list[TripSpec], list[TripSpec], dict[str, float]]:
    feeder_nodes = ox.distance.nearest_nodes(
        drive_graph, feeder_stops.geometry.x.values, feeder_stops.geometry.y.values
    )
    feeder_ride_times_s = [
        nx.shortest_path_length(drive_graph, n, trunk_access_node, weight="travel_time")
        for n in feeder_nodes
    ]

    walk_nodes = ox.distance.nearest_nodes(
        walk_graph, demand["centroid_lon"].values, demand["centroid_lat"].values
    )
    feeder_walk_nodes = ox.distance.nearest_nodes(
        walk_graph, feeder_stops.geometry.x.values, feeder_stops.geometry.y.values
    )

    trip_weights: dict[str, float] = {}
    sq_specs, prop_specs = [], []
    for cell_idx, walk_node in zip(demand.index, walk_nodes):
        pop = float(demand.loc[cell_idx, "population"])
        trip_id = f"{line_id}_cell_{cell_idx}"
        trip_weights[trip_id] = pop

        sq_specs.append(TripSpec(
            trip_id=trip_id, origin_cell=str(cell_idx), covered=False,
            walk_time_s=0.0, trunk_ride_time_s=sq_trunk_time_s,
        ))

        best = min(
            range(len(feeder_walk_nodes)),
            key=lambda j: nx.shortest_path_length(walk_graph, walk_node, feeder_walk_nodes[j], weight="travel_time"),
        )
        walk_time_s = nx.shortest_path_length(walk_graph, walk_node, feeder_walk_nodes[best], weight="travel_time")
        prop_specs.append(TripSpec(
            trip_id=trip_id, origin_cell=str(cell_idx), covered=True,
            walk_time_s=walk_time_s, wait_time_s=settings.DEFAULT_WAIT_TIME_MIN * 60,
            feeder_ride_time_s=feeder_ride_times_s[best], transfer_time_s=TRANSFER_TIME_S,
            trunk_ride_time_s=prop_trunk_time_s,
        ))

    return sq_specs, prop_specs, trip_weights


def simulate_line(
    line_id: str,
    stops: gpd.GeoDataFrame,
    demand: gpd.GeoDataFrame,
    feeder_stops: gpd.GeoDataFrame,
    drive_graph: nx.MultiDiGraph,
    walk_graph: nx.MultiDiGraph,
) -> dict | None:
    line_stops = stops[stops["line_id"] == line_id].sort_values("stop_order")
    if len(line_stops) < 2 or len(demand) == 0 or len(feeder_stops) == 0:
        print(f"  [{line_id}] insufficient data (stops={len(line_stops)}, demand={len(demand)}, "
              f"feeder_stops={len(feeder_stops)}) — skipping")
        return None

    try:
        edge_plan, signal_specs, edge_length_m, trunk_access_node = build_edge_plan(drive_graph, line_stops)
    except nx.NetworkXNoPath as exc:
        # The drive graph is weakly but not necessarily strongly connected
        # (one-way streets can make a directed path not exist between two
        # points even though they're connected ignoring direction). Rather
        # than silently drop a route segment (which would understate trunk
        # time) or crash the whole batch, skip this line with a clear reason.
        print(f"  [{line_id}] SKIPPED: no directed path between consecutive stops ({exc}) — "
              f"likely a one-way-street routing issue or a stop snapped near a disconnected segment")
        return None

    sq_trunk_s = measure_trunk_time(edge_plan, signal_specs, priority_enabled=False)
    prop_trunk_s = measure_trunk_time(edge_plan, signal_specs, priority_enabled=True)

    sq_specs, prop_specs, trip_weights = build_trip_specs_for_line(
        line_id, demand, feeder_stops, drive_graph, walk_graph, trunk_access_node, sq_trunk_s, prop_trunk_s
    )

    vehicle = VehicleSpec(vehicle_id=f"{line_id}_bus_1", edges=edge_plan)
    sq_result = status_quo(sq_specs, [vehicle], signal_specs, sim_duration_s=7200)
    prop_result = proposed(prop_specs, [vehicle], signal_specs, sim_duration_s=7200)

    sq_summary = metrics.summarize(sq_result, edge_length_m, trip_weights)
    prop_summary = metrics.summarize(prop_result, edge_length_m, trip_weights)

    print(f"  [{line_id}] trunk: {sq_trunk_s/60:.1f} -> {prop_trunk_s/60:.1f} min "
          f"({(sq_trunk_s - prop_trunk_s)/60:+.1f} min); "
          f"{len(demand)} demand cells (pop {demand['population'].sum():,.0f}), "
          f"signals={len(signal_specs)}, edges={len(edge_plan)}")

    return {
        "line_id": line_id,
        "sq_result": sq_result, "prop_result": prop_result,
        "sq_summary": sq_summary, "prop_summary": prop_summary,
        "trip_weights": trip_weights,
    }


def citywide_comparison(per_line: list[dict]) -> pd.DataFrame:
    all_sq_trips = [t for r in per_line for t in r["sq_result"].trip_records]
    all_prop_trips = [t for r in per_line for t in r["prop_result"].trip_records]
    all_weights: dict[str, float] = {}
    for r in per_line:
        all_weights.update(r["trip_weights"])

    combined_sq = ScenarioResult(name="status_quo_citywide", trip_records=all_sq_trips, vehicle_log=[], signals={})
    combined_prop = ScenarioResult(name="proposed_citywide", trip_records=all_prop_trips, vehicle_log=[], signals={})

    sq_summary = metrics.summarize(combined_sq, {}, all_weights)
    prop_summary = metrics.summarize(combined_prop, {}, all_weights)
    return metrics.compare(sq_summary, prop_summary)


def main() -> None:
    stops = gpd.read_file(settings.INTERIM_DIR / "ocftc_stops_geocoded.geojson")
    stops = stops[~stops["qa_flagged_suspect"]]
    demand_all = gpd.read_file(settings.PROCESSED_DIR / "underserved_line_assignment.geojson")
    feeder_all = gpd.read_file(settings.PROCESSED_DIR / "feeder_stops_all_lines.geojson")
    drive_graph = ox.load_graphml(settings.PROCESSED_DIR / "gba_drive_congested.graphml")
    walk_graph = ox.load_graphml(settings.PROCESSED_DIR / "gba_walk_timed.graphml")

    line_ids = sorted(feeder_all["line_id"].unique())
    print(f"Simulating {len(line_ids)} lines with an MCLP feeder network: {line_ids}\n")

    per_line = []
    for line_id in line_ids:
        result = simulate_line(
            line_id,
            stops,
            demand_all[demand_all["nearest_line"] == line_id],
            feeder_all[feeder_all["line_id"] == line_id],
            drive_graph, walk_graph,
        )
        if result:
            per_line.append(result)

    print("\nPer-line trunk speed (status quo -> proposed):")
    for r in per_line:
        print(f"  {r['line_id']}: {r['sq_summary'].trunk_avg_speed_kmh:.1f} -> "
              f"{r['prop_summary'].trunk_avg_speed_kmh:.1f} km/h")

    comparison = citywide_comparison(per_line)
    print("\nCitywide status quo vs proposed (all simulated lines combined):")
    print(comparison.to_string())

    out_path = settings.PROCESSED_DIR / "citywide_simulation_comparison.csv"
    comparison.to_csv(out_path)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
