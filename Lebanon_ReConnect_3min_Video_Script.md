# 3-Minute Submission Video — Script & Shot List

*Timed for ~180 seconds. Read each line at a natural, unhurried pace — this script runs slightly under 3 minutes read aloud, leaving room for pauses on visuals. Screen-record the listed slide/visual for each beat; the slide numbers refer to `Lebanon_ReConnect_Presentation.pptx`.*

**Recording tip:** screen-record at 1280×720 or 1920×1080, but export/compress at a *lower bitrate* (e.g. H.264, ~2–3 Mbps, or use Handbrake's "Fast 720p30" preset) to land under the 10MB cap for ~3 minutes of video. A straight high-quality export of 3 minutes will likely blow past 10MB.

---

### [0:00–0:15] — Hook + who/what (Slide 1: Title)

> "Hi, I'm Maher Bekdash. This is Beirut ReRoute — Lebanon ReConnect: an AI-designed, simulated, and regionally-envisioned public transport system for Lebanon, built for the LebNet Tech Fellows program. It starts with one underserved Beirut neighborhood and scales to a reconnected region."

### [0:15–0:35] — The problem (Slide 3: The Problem)

> "Lebanon runs on private cars because nothing else works well enough. 650,000 vehicles enter Greater Beirut every day, congestion costs 5 percent of GDP, and even though 92 percent of people can technically walk to some stop, that remaining 8 percent is 235,000 real people with no way in. The 2024 bus network runs in the same traffic as everyone else — no priority, no feeder network."

### [0:35–0:55] — Plan / aim + the evolution (Slide 4 → briefly Slide 8: Architecture)

> "My plan: design and prove, in simulation, an AI-driven path from Beirut's fragmented transit to a reconnected Lebanon. Not a diagnosis — an algorithm that actually designs a network, and a simulation that tests it. The project is split into two honestly-scoped layers: Layer B, a fully simulated Beirut pilot, and Layer A, a lightweight national vision — reconciling real ambition with what's actually buildable solo."

### [0:55–1:20] — Execution: how it works (Slide 9: Methodology Layer B)

> "Here's the execution. Using real OpenStreetMap roads, WorldPop population data, and Lebanon's actual 2024 bus network, I score today's coverage — 92.2 percent. Then a Maximal Covering Location Problem, an optimization algorithm, designs new feeder stops to reach the underserved remainder. Finally, a discrete-event simulation tests the whole system — feeder network plus signal priority representing V2X — against the status quo, on real roads."

### [1:20–1:45] — Layer B results (Slide 12 or 13: pick the accessibility chart)

> "The results are real, not estimated. Citywide accessibility rises from 92.2 to 97.4 percent — 156,594 additional people reached. In simulation, trip completion for previously-uncovered riders goes from 0 to 91.9 percent. Signal priority gives real, if modest, speed gains on corridors that actually have traffic signals to act on."

*(Show the chart on screen for ~10 seconds while narrating these numbers.)*

### [1:45–2:10] — Layer A: the regional vision (Slide 10 → Slide 15/16: centrality chart or map)

> "Layer A asks a different question: what if Lebanon reconnected regionally — restoring historic rail, the real Hejaz Railway revival, and the 2026 Jounieh-Cyprus ferry? Using a network graph and centrality analysis, Beirut's betweenness centrality — its role as a regional bridge — increases 400 percent. I also found and kept a counter-intuitive result: Beirut's closeness centrality actually falls, because newly-reachable places are genuinely far away. That's an honest finding, not a bug."

### [2:10–2:30] — Honesty about limits (Slide 18, spoken quickly)

> "I want to be upfront about scope: this is a topological vision layer, not a costed engineering plan, and some geocoding was pre-seeded due to a sandboxed dev environment without live internet access — both are documented in full in the repo and the write-up."

### [2:30–2:50] — Action plan (Slide 19)

> "The roadmap: this Beirut pilot is Phase 1. Phase 2 replicates the method around Tripoli, Saida, Tyre, and Jounieh. Phase 3 revives domestic rail to the Bekaa and Damascus. Phase 4 plugs into the Arab Mashreq and Hejaz Railway revival already being negotiated regionally right now."

### [2:50–3:00] — Close (Slide 22: Closing)

> "Lebanon ReConnect: from one Beirut neighborhood to a reconnected region. All code, results, and documentation are in the GitHub repo linked in my submission. Thank you."

---

## Quick shot list (in order)

1. Slide 1 — Title
2. Slide 3 — The Problem (stat callouts)
3. Slide 4 or 8 — Aim / Architecture
4. Slide 9 — Layer B methodology
5. Slide 12/13 — Layer B results chart
6. Slide 15/16 — Layer A centrality chart or network map
7. Slide 18 — Limitations (fast cut, just to show it's addressed)
8. Slide 19 — Action plan
9. Slide 22 — Closing

If you're short on recording time: you can also just narrate over the live `results_map.html` / `national_network_map.html` in a browser for 10–15 seconds instead of the static slide — it shows the interactivity, which static slides can't.
