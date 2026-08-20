"""Static charts (matplotlib) summarizing Layer A and Layer B results.

Complements the interactive folium maps (`viz/maps.py`, `viz/national_map.py`,
`viz/results_map.py`) with print/embed-friendly PNGs for the report and video
— an .html map can't go in a 2-4 page PDF or a slide.

Every number plotted here is read from a file already saved by a real
pipeline run (`outputs/tables/*.csv`, `data/processed/*`) — nothing is
computed fresh or hardcoded in this module.

Usage:
    python -m beirut_reroute.viz.charts
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

# Shared palette, reused across every chart here rather than each function
# picking its own colors — so the report/video reads as one consistent set,
# not a pile of mismatched auto-colored matplotlib defaults.
_COLOR_STATUS_QUO = "#9aa5b1"
_COLOR_PROPOSED = "#1f78b4"
_COLOR_ACCENT = "#e31a1c"
_MODE_COLORS = {
    "bus": "#1f78b4", "road": "#999999", "historic_rail": "#8B4513",
    "rail": "#e31a1c", "ferry": "#00b3b3",
}
_KIND_COLORS = {
    "city_port": "#8B0000", "port": "#1f78b4", "inland_hub": "#33a02c",
    "rail_junction": "#ff7f00", "border_crossing": "#6a3d9a", "city": "#333333",
}

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "font.size": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "axes.axisbelow": True,
})


def _save(fig, name: str, tight: bool = True) -> Path:
    out_path = settings.FIGURES_DIR / name
    if tight:
        fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# Layer B (Beirut ReRoute)
# ---------------------------------------------------------------------------

def plot_trunk_speed_per_line() -> Path:
    df = pd.read_csv(settings.TABLES_DIR / "simulation_per_line.csv").sort_values("line_id")
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(df))
    width = 0.38
    ax.bar([i - width / 2 for i in x], df["trunk_speed_status_quo_kmh"], width,
           label="Status quo", color=_COLOR_STATUS_QUO)
    ax.bar([i + width / 2 for i in x], df["trunk_speed_proposed_kmh"], width,
           label="Proposed (signal priority)", color=_COLOR_PROPOSED)
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["line_id"])
    ax.set_ylabel("Trunk corridor avg. speed (km/h)")
    ax.set_title("Layer B — trunk corridor speed, status quo vs. proposed")
    ax.set_ylim(0, max(df["trunk_speed_proposed_kmh"].max(), df["trunk_speed_status_quo_kmh"].max()) * 1.22)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.14), ncol=2, frameon=False)
    for i, (sq, pr) in enumerate(zip(df["trunk_speed_status_quo_kmh"], df["trunk_speed_proposed_kmh"])):
        delta = pr - sq
        if abs(delta) > 0.05:
            ax.annotate(f"{delta:+.1f}", (i, max(sq, pr) + 1), ha="center", fontsize=9, color=_COLOR_ACCENT)
    return _save(fig, "layerB_trunk_speed_per_line.png")


def plot_coverage_gain_per_line() -> Path:
    df = pd.read_csv(settings.TABLES_DIR / "mclp_per_line.csv").sort_values("line_id")
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(df["line_id"], df["coverage_fraction"] * 100, color=_COLOR_PROPOSED)
    ax.set_ylabel("% of that line's underserved population newly covered")
    ax.set_ylim(0, 110)
    ax.set_title("Layer B — MCLP feeder-network coverage gain by line")
    for bar, pop in zip(bars, df["newly_covered_population"]):
        ax.annotate(f"{pop:,.0f} people", (bar.get_x() + bar.get_width() / 2, bar.get_height() + 2),
                    ha="center", fontsize=8, color="#444444")
    return _save(fig, "layerB_coverage_gain_per_line.png")


def plot_citywide_accessibility() -> Path:
    """GBA-wide spatial accessibility (walk-only baseline vs. baseline +
    MCLP-newly-covered population) — a different, larger-denominator number
    than plot_simulated_trip_completion()'s trip-completion rate. Kept as
    two separate charts on purpose; see README "Layer B results"."""
    grid = gpd.read_file(settings.PROCESSED_DIR / "status_quo_accessibility.geojson")
    total_pop = grid["population"].sum()
    covered_before = (grid["population"] * grid["coverage_binary"]).sum()

    mclp = pd.read_csv(settings.TABLES_DIR / "mclp_per_line.csv")
    newly_covered = mclp["newly_covered_population"].sum()
    covered_after = covered_before + newly_covered

    fig, ax = plt.subplots(figsize=(6, 5))
    labels = ["Today\n(walk-only)", "With AI-designed\nfeeder network"]
    values = [covered_before / total_pop * 100, covered_after / total_pop * 100]
    bars = ax.bar(labels, values, color=[_COLOR_STATUS_QUO, _COLOR_PROPOSED])
    ax.set_ylim(0, 110)
    ax.set_ylabel("% of GBA population within accessible reach of a stop")
    ax.set_title("Layer B — GBA-wide spatial accessibility")
    for bar, v in zip(bars, values):
        ax.annotate(f"{v:.1f}%", (bar.get_x() + bar.get_width() / 2, v + 2), ha="center", fontweight="bold")
    ax.annotate(f"+{newly_covered:,.0f} people\nnewly reached", xy=(1, values[1]), xytext=(0.15, 55),
                fontsize=9, color=_COLOR_ACCENT, arrowprops=dict(arrowstyle="->", color=_COLOR_ACCENT))
    return _save(fig, "layerB_citywide_accessibility.png")


def plot_simulated_trip_completion() -> Path:
    """Trip-completion rate WITHIN the simulation, among the population that
    was previously uncovered and got assigned a feeder-served line — not a
    GBA-wide population share (that's plot_citywide_accessibility())."""
    citywide = pd.read_csv(settings.PROCESSED_DIR / "citywide_simulation_comparison.csv", index_col="metric")
    coverage_row = citywide.loc["coverage_fraction (pop-weighted)"]
    dtd_row = citywide.loc["avg_door_to_door_min (pop-weighted)"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))

    ax = axes[0]
    values = [float(coverage_row["status_quo"]) * 100, float(coverage_row["proposed"]) * 100]
    bars = ax.bar(["Status quo\n(no feeder)", "Proposed\n(feeder + priority)"], values,
                   color=[_COLOR_STATUS_QUO, _COLOR_PROPOSED])
    ax.set_ylim(0, 110)
    ax.set_ylabel("Simulated trip completion rate (%)")
    ax.set_title("Trip completion, previously-uncovered riders")
    for bar, v in zip(bars, values):
        ax.annotate(f"{v:.1f}%", (bar.get_x() + bar.get_width() / 2, v + 2), ha="center", fontweight="bold")

    ax = axes[1]
    dtd_proposed = float(dtd_row["proposed"])
    ax.bar(["Proposed system\ndoor-to-door"], [dtd_proposed], color=_COLOR_PROPOSED, width=0.5)
    ax.set_ylabel("Minutes")
    ax.set_title("Avg. simulated trip time\n(status quo: trip didn't exist)")
    ax.annotate(f"{dtd_proposed:.0f} min", (0, dtd_proposed + 5), ha="center", fontweight="bold")

    fig.suptitle("Layer B — simulated feeder+trunk system performance", y=1.03)
    return _save(fig, "layerB_simulated_trip_completion.png")


# ---------------------------------------------------------------------------
# Layer A (Lebanon ReConnect)
# ---------------------------------------------------------------------------

def plot_national_centrality(top_n: int = 8) -> Path:
    df = pd.read_csv(settings.TABLES_DIR / "national_centrality.csv").head(top_n).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(df))
    width = 0.38
    ax.bar([i - width / 2 for i in x], df["betweenness_status_quo"], width,
           label="Status quo", color=_COLOR_STATUS_QUO)
    ax.bar([i + width / 2 for i in x], df["betweenness_proposed"], width,
           label="Proposed (reconnected)", color=_COLOR_PROPOSED)
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["name"], rotation=30, ha="right")
    ax.set_ylabel("Betweenness centrality")
    ax.set_title(f"Layer A — top {top_n} nodes by proposed betweenness centrality")
    ax.legend()
    beirut_rows = df.index[df["node_id"] == "beirut_hub"]
    if len(beirut_rows):
        i = beirut_rows[0]
        pct = df.loc[i, "betweenness_pct_change"]
        if pd.notna(pct):
            ax.annotate(f"{pct:+.0f}%", (i, df.loc[i, "betweenness_proposed"] + 0.02),
                        ha="center", color=_COLOR_ACCENT, fontweight="bold")
    return _save(fig, "layerA_centrality_comparison.png")


def _draw_network(ax, pos: dict, sq: nx.Graph, proposed: nx.Graph, *, label_fontsize: float = 7) -> None:
    sq_edges = {frozenset(e) for e in sq.edges}
    for u, v, data in proposed.edges(data=True):
        is_status_quo = frozenset((u, v)) in sq_edges
        ax.plot(
            [pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
            "-" if is_status_quo else "--",
            color=_MODE_COLORS.get(data["mode"], "#555555"),
            linewidth=2.2 if is_status_quo else 1.4,
            alpha=0.9 if is_status_quo else 0.6,
            zorder=1,
        )
    for node_id, (x, y) in pos.items():
        kind = proposed.nodes[node_id]["kind"]
        ax.scatter(x, y, s=160 if node_id == "beirut_hub" else 70,
                   color=_KIND_COLORS.get(kind, "#000000"), zorder=2,
                   edgecolor="white", linewidth=0.6)
        ax.annotate(proposed.nodes[node_id]["name"], (x, y), fontsize=label_fontsize,
                    xytext=(4, 4), textcoords="offset points")


def plot_national_network_diagram() -> Path:
    """Static geographic-layout complement to the interactive
    viz/national_map.py — for embedding directly in the report/slides,
    where an .html file can't go. Includes a Lebanon-only inset: at
    regional scale the 8 Lebanese nodes cluster into an illegible smear,
    so they get their own zoomed panel rather than just accepting that."""
    from beirut_reroute.national_network.build_regional_graph import (
        build_proposed_graph,
        build_status_quo_graph,
        load_nodes,
    )

    nodes = load_nodes()
    sq, proposed = build_status_quo_graph(), build_proposed_graph()
    pos = {node_id: (row.geometry.x, row.geometry.y) for node_id, row in nodes.iterrows()}

    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_axes((0.06, 0.08, 0.62, 0.84))
    _draw_network(ax, pos, sq, proposed, label_fontsize=7)
    mode_handles = [plt.Line2D([0], [0], color=c, lw=2, label=m) for m, c in _MODE_COLORS.items()]
    ax.legend(handles=mode_handles, loc="lower left", fontsize=8, title="mode (dashed = proposed-only)")
    ax.set_title("Layer A — national/regional network\n(solid = status quo, dashed = proposed-only)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")

    lebanon_ids = [n for n, d in proposed.nodes(data=True) if d["country"] == "Lebanon"]
    xs = [pos[n][0] for n in lebanon_ids]
    ys = [pos[n][1] for n in lebanon_ids]
    pad_x, pad_y = 0.12, 0.12
    x0, x1 = min(xs) - pad_x, max(xs) + pad_x
    y0, y1 = min(ys) - pad_y, max(ys) + pad_y

    ax_inset = fig.add_axes((0.71, 0.08, 0.27, 0.84))
    _draw_network(ax_inset, pos, sq, proposed, label_fontsize=8)
    ax_inset.set_xlim(x0, x1)
    ax_inset.set_ylim(y0, y1)
    ax_inset.set_aspect("equal")
    ax_inset.set_title("Lebanon (zoomed)")
    ax_inset.set_xticks([])
    ax_inset.set_yticks([])
    for spine in ax_inset.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor("#888888")

    # Mark the zoomed region on the main map so the inset's relationship to
    # the full picture is obvious, not just a floating unrelated panel.
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="#888888", linewidth=1, linestyle=":"))

    return _save(fig, "layerA_network_diagram.png", tight=False)


def main() -> None:
    plot_trunk_speed_per_line()
    plot_coverage_gain_per_line()
    plot_citywide_accessibility()
    plot_simulated_trip_completion()
    plot_national_centrality()
    plot_national_network_diagram()


if __name__ == "__main__":
    main()
