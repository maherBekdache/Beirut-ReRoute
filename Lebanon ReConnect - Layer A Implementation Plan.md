# Lebanon ReConnect — Layer A Implementation Plan

Companion to the (referenced but not present in this repo) "Beirut ReRoute —
Implementation Plan." That plan covers Layer B, which is largely built and
run (see README "Real results," 2026-08-09). This plan covers **Layer A**:
the national/regional vision layer that generalizes the project from "Beirut
buses" to "Lebanon's full multimodal potential," per the proposal's two-layer
structure. Nothing in Layer B changes — Layer A is additive.

## 0. Timeline reality check

Today is **2026-08-12**. Final deliverables (code + 2-4 page report + 3-min
video) are due **2026-08-20** — **8 days**, not the 19 the original proposal
assumed. Layer B being substantially done is what makes Layer A affordable at
all. Layer A is scoped to be buildable in **2-3 days**, leaving the rest for
the final report, video, and repo cleanup (see §7 schedule). If it starts
running long, cut the map (§5) before cutting the centrality analysis (§4) —
the numbers are the deliverable, the map is a nice-to-have.

## 1. What Layer A is (and isn't)

Layer A is a **topological network graph + centrality analysis**, not a
physical simulation. It answers: "if Lebanon's dormant/planned regional links
(rail, ferry) were restored alongside today's domestic bus network, how much
more central would Beirut/Lebanon become in the regional network?" — a
quantitative stand-in for "envision all of Lebanon reconnected," sized to fit
in days. Simulating ports, ships, or trains nationwide is explicitly out of
scope (see proposal Evaluation Plan risk #1) and not attempted here.

## 2. Data — already seeded

`data/raw/national_network/nodes_manual.csv` (18 nodes) and
`edges_manual.csv` (18 edges) are written and sourced — see that folder's
`README.md` for the full sourcing/QA notes. Three of the five Lebanese
hub-city edges (Beirut→Chtaura/Bekaa, Beirut→Tripoli, Beirut→Tyre) reuse this
repo's own real, already-geocoded OCFTC ML1/ML4/B6-ML2 data — no new data
collection needed for those. Only the regional (Syria/Jordan/Saudi/Cyprus/
Turkey) nodes and the historic-rail/ferry edges needed fresh research, which
is done and cited.

## 3. New module: `src/beirut_reroute/national_network/`

Mirrors the existing `data_acquisition/` → `processing/` → `optimization/` →
`viz/` pipeline shape. Proposed files:

```
src/beirut_reroute/national_network/
    __init__.py
    geocode_nodes.py        # geocode nodes_manual.csv -> data/interim/national_nodes_geocoded.geojson
    build_regional_graph.py # build_status_quo_graph() / build_proposed_graph() -> nx.Graph
    centrality.py           # compute_centrality(), compare_status_quo_vs_proposed()
    run_vision_analysis.py  # orchestrates the above; writes outputs/tables/ + calls viz

src/beirut_reroute/viz/national_map.py   # new sibling file, doesn't touch maps.py

tests/test_centrality.py    # synthetic small-graph tests, same style as test_mclp.py
```

**`geocode_nodes.py`** — `beirut_hub` skips geocoding (reuse
`settings.GBA_CENTER_LATLON` directly); every other node is geocoded via
Nominatim. `ocftc_loader.py` already has a solid retry-ladder geocode
function — **recommended**: extract it into a new
`data_acquisition/geocoding.py` (`geocode(name, cache, viewbox=None) -> ...`)
and have both `ocftc_loader.py` and this module import it, rather than
duplicating the retry logic. This is a small, mechanical refactor (move code,
update two imports) — low risk to the working Layer B pipeline, but if there
is zero appetite to touch `ocftc_loader.py` this week, duplicating a ~15-line
geocode helper locally is an acceptable fallback. No viewbox bias is needed
here (all 17 non-Beirut nodes are real, well-known city/place names, unlike
OCFTC's ambiguous roundabout/intersection names) — a plain
`f"{name}, {country}"` query should resolve all 17 without the fallback
ladder OCFTC needed.

**`build_regional_graph.py`**:
```python
def load_nodes() -> gpd.GeoDataFrame: ...          # from national_nodes_geocoded.geojson
def load_edges() -> pd.DataFrame: ...              # from edges_manual.csv
def _edge_weight_km(nodes, source_id, target_id) -> float: ...  # haversine distance
def build_status_quo_graph() -> nx.Graph: ...       # status in {formal_2024_unconfirmed_operation, informal_only}
def build_proposed_graph() -> nx.Graph: ...          # all statuses
```
Edge weight = great-circle distance (haversine), not a travel time — Layer A
has no speed/mode-performance model, and pretending otherwise would overstate
its precision. This matches the "topological, not engineering-grade" framing
in the proposal and the folder README.

**`centrality.py`**:
```python
@dataclass
class CentralityResult:
    node_id: str
    betweenness: float
    closeness: float

def compute_centrality(graph: nx.Graph) -> dict[str, CentralityResult]: ...
def compare_status_quo_vs_proposed(sq: nx.Graph, proposed: nx.Graph) -> pd.DataFrame: ...
    # columns: node_id, betweenness_sq, betweenness_proposed, betweenness_pct_change, closeness_sq, closeness_proposed, closeness_pct_change
```
Uses `networkx.betweenness_centrality` / `networkx.closeness_centrality`
(already a dependency, no new package needed) with `weight="distance_km"`.
The one number the report needs: `beirut_hub`'s betweenness % change,
status-quo → proposed.

**`run_vision_analysis.py`** — `main()`: geocode → build both graphs →
compare → write `outputs/tables/national_centrality.csv` → call
`national_map.build_national_network_map()` → save
`outputs/maps/national_network_map.html`. Same shape as
`accessibility/run_status_quo.py`.

**`viz/national_map.py`** — one function,
`build_national_network_map() -> folium.Map`: two toggleable layers
(status-quo edges solid, proposed-only edges dashed/colored by `mode`), nodes
colored by `kind`. Reuses the `folium.Map(..., tiles="cartodbpositron")`
pattern from `maps.py` but at a country/region zoom level, not GBA.

## 4. Config additions (`config/settings.py`)

```python
NATIONAL_NETWORK_DIR = RAW_DIR / "national_network"
NATIONAL_NODES_CSV = NATIONAL_NETWORK_DIR / "nodes_manual.csv"
NATIONAL_EDGES_CSV = NATIONAL_NETWORK_DIR / "edges_manual.csv"
STATUS_QUO_EDGE_STATUSES = {"formal_2024_unconfirmed_operation", "informal_only"}
```
(`NATIONAL_NETWORK_DIR` also needs adding to the existing `for _d in (...)`
mkdir loop.)

## 5. Pipeline integration (`run_pipeline.py`)

Add two stages after `qa_map`:
```python
("national_geocode", "beirut_reroute.national_network.geocode_nodes", "fetch"),
("national_vision", "beirut_reroute.national_network.run_vision_analysis", "compute"),
```

## 6. Tests (`tests/test_centrality.py`)

Synthetic, not real data — same philosophy as `test_mclp.py`/
`test_signal_priority.py` (real-data bugs get caught by actually running the
pipeline, per the README's "Bugs found and fixed" section; unit tests catch
logic errors). At minimum:
- A path graph A-B-C: B's betweenness should be the unique maximum.
- A two-cluster graph joined by one bridge edge: the bridge endpoints'
  betweenness must increase when the bridge is added vs. a graph without it
  — this is the actual claim the report will make about `beirut_hub`, so it
  should be tested directly, not just trusted.

## 7. Schedule for the remaining 8 days (2026-08-12 → 2026-08-20)

| Day | Work |
|---|---|
| Aug 12-13 | Layer A: `geocode_nodes.py`, `build_regional_graph.py`, `centrality.py`, `run_vision_analysis.py`, `test_centrality.py`. Run it, sanity-check the numbers. |
| Aug 14 | Layer A: `national_map.py`; write the short vision narrative section (grounded in `national_network/README.md`'s sourcing). |
| Aug 15-16 | Write the combined 2-4 page final report: Layer B's real results (already in README) + Layer A's centrality numbers + the phased action plan (Phase 1 pilot → Phase 2 replicate → Phase 3 domestic rail → Phase 4 regional integration, from the proposal). This is also where the still-"not started" Layer B reporting/phased-action-plan item from the pipeline-stage table gets done. |
| Aug 17 | Record the 3-minute demo video. |
| Aug 18 | GitHub repo cleanup: prune `cache/`, `.venv/`, confirm `.gitignore`, final README pass covering both layers. |
| Aug 19-20 | Buffer for debugging; submit. |

## 8. What this plan deliberately does not do

No new heavy dependency (networkx is already installed). No attempt to model
real rail/ferry travel times, schedules, or costs — that is explicitly future
work (proposal §8, risk #1). No changes to any Layer B file except the two
additive edits in §4-5 (`settings.py`, `run_pipeline.py`) and the optional
`geocoding.py` extraction in §3 — everything else is new files only.
