# C04 Layout (PCB) — turn the verified netlist into a DRC-clean, gated, fab-ready board

## Purpose & scope

C04 owns the **physical board**: placement, routing, the layer stackup, controlled-impedance
constraints, the routed `.kicad_pcb`, and the **gated fabrication + assembly output package**. It
takes C03's verified netlist plus the mechanical/interface constraints and produces a board that is
either still a **draft** or has passed the C04 gate (`bodesign_layout_drc_gate` + `c04_readiness`).

What C04 does **not** own:
- It does not invent connectivity. The netlist comes from C03; if a connection is unknown there
  (e.g. a boot-ROM-configured bus), it stays unknown here — you route what exists, not a guess.
- It does not own the *final* board outline / mounting holes — those are layout-and-ME decisions
  shared with C02. C04 records what it used and flags what is still open.
- It does not *certify* anything. DRC/SI are tool verdicts, not lab compliance. EMC/FCC/CE stay in
  C06/external labs.
- It does not "release" fab outputs. Gerbers exist as soon as you export them, but they are
  `pending` until the board is **frozen** — see the gate and the handoff to C07.

The central lesson this stage encodes (from this repo's own history): an earlier gate **falsely
passed a board with a floating PSRAM** — the BGA footprint's pad names didn't match the symbol, so
24 pads were silently unnetted, yet the gate said "COMPLETE". The fix was *not* to relax anything —
it was to make the gate parse DRC honestly (copper + unconnected = hard fail) and add an
unmapped-pad gate. **Never relax a threshold to make a board pass. Fix the board or report the
warn.** See `../../references/honesty-model.md` rule 5 and the C04 paragraph there.

## Required deliverables — Definition of Done

Produce **all** of these before you report C04 done or hand off (see SKILL.md § "Definition of
Done"; deliverables land in `03_output/`, rendered previews in `02_build/`). Each exists **or** carries
an explicit `drafted`/`pending`/`not-run` status with a reason — fab outputs stay `pending` until
the board is frozen, which is honest, not missing.

| # | Required artifact | File | Bucket |
|---|---|---|---|
| 1 | Layout + placement constraints | `Layout_Constraints.json` + `Placement_Constraints.md` | `03_output/` |
| 2 | Stackup + routing rules | `Stackup.md` + `Routing_Rules.md` | `03_output/` |
| 3 | Routed board + DRC report | `<board>.kicad_pcb` + `<board>.drc.rpt` | `03_output/` |
| 4 | Gerbers + drill | `gerbers/` + `drill/` | `03_output/` |
| 5 | Assembly package | CPL · IPC-2581 · assembly drawing | `03_output/` |
| 6 | Per-layer copper PNGs + fab view | `copper_layers/`, `renders/` | `02_build/` |
| 7 | Length-match + SI reports | `<board>.lengthmatch.json`, `<board>.si.json` | `03_output/` (high-speed only) |

**Self-verify:** run the gate — `bodesign_layout_drc_gate` (`board_path`) + `bodesign_c04_readiness`
(`folder`) — and report the verdict (see "Gate / done-criteria" below). Mechanical constraints are
**consumed from C03** (`01_refs/`), not re-authored. Model: `thesmart_products/rockbox/c04-layout/`.

## Inputs (from upstream)

From **C03 (EE)** — see `../c03-ee/GUIDE.md`:
- The **netlist** (`.net`) — the connectivity you route. This is the single source of truth for
  which pads connect. If C03 exported an honest subset (a bus excluded for lack of source data),
  you route the subset; you do not back-fill the missing nets.
- The **SI requirements as targets** — USB 90 Ω diff; MIPI CSI-2 100 Ω diff, length-matched; XSPI
  50 Ω SE with DQS↔DQ matching; SDMMC 50 Ω. C04 makes copper meet these; C03 only named them.
- **`Mechanical_Constraint_Export.json`** — component heights, connector edge openings, heat
  sources, antenna keepouts. Drives placement and the C02 enclosure.

From **C02 (ME)** — the **board outline** (and mounting-hole positions from the enclosure). If the
outline is not yet frozen, record it as an `assumption` and say so in `Layout_Constraints.json`.

From **C01 (ID)** — exposed-component intent (camera aperture, status LED, USB-C edge). Folded into
`Placement_Constraints.md` / `Layout_Constraints.json`.

Real examples of these constraint artifacts (constraint-first, layout-owned items left **open**):
`openmv/C04-Layout/03_output/Layout_Constraints.json` and `Placement_Constraints.md`.

## SOP

This stage has **two layers**: (1) the **execution engine** (`../../engines/kicad/`) for analysis,
cross-check, and the fab-release gate (local, shipped with this skill); and (2) the **bodesign MCP**
generation tools (`route_net2pcb`/`autoroute` → `pour_planes`/`widen_bus_tracks`/`length_match_bus`
→ `emit_fab` → `layout_drc_gate`/`c04_readiness`) which produce and gate the deliverable manifest.
Wire to both: generate with the MCP, analyse/cross-check/gate with the local engine.

The `openmv/C04-Layout/` worked example (its `generated/tools/` and `DELIVERABLES.md`) is that
reference board's own local mirror of these operations — read it for the deliverable contract and
ground truth, but drive generation through the MCP, not those scripts.

### 1. Assemble the layout constraints

Author `Layout_Constraints.json` (schema `bodesign.c04.layout_constraints.v1`) and
`Placement_Constraints.md` from the C01/C03 inputs: `exposed_components`, `connector_edge_openings`,
`heat_zones`, `antenna_keepouts`, `battery_zone`, `emc_esd_notes`. Anything layout-owned that is not
yet decided (board outline, mounting holes, exact XY, stackup) goes in `open_decisions` with an
owner — do **not** silently fill it. Mark the file `"state": "drafted"` until the placement is done.

### 2. Define the stackup & compute impedance widths

Pick a layer count from density + the controlled-impedance net set, and write `Stackup.md` +
`Routing_Rules.md` (net classes: width / clearance / impedance / length-match). Compute trace
widths from the stackup rather than guessing — call **`bodesign_impedance_solve`** (`stackup`,
`targets`): it returns microstrip/stripline Z0 → width for each target net class. (No MCP? Use any
microstrip/stripline solver and record the inputs.)

State honestly that final stackup + exact geometry must be **confirmed against the chosen fab's
controlled-impedance solver** — your computed widths are design starting points, an `assumption`
until fab-confirmed. Real example: `openmv/N6_board/C04_Layout/Stackup.md` and `Routing_Rules.md`.

### 3. Build the board via the MCP (one-shot, or step-by-step)

The bodesign MCP produces and gates the deliverable manifest — see `../../SKILL.md` § "Relationship
to the bodesign MCP server". Two ways in:

**One-shot:** `bodesign_c04_emit_layout_package` (`out_dir`, `c01`, `c03`) assembles the whole C04
package (board + constraints + renders + assembly outputs) from the C01/C03 handoffs, then
`bodesign_c04_readiness` (`folder`) reports the gate verdict.

**Step-by-step** (when you need control over routing/finishing):
1. **Place + route from the netlist** — `bodesign_route_net2pcb` (`netlist_path`, `out_path`,
   `layers`, `plane_layers`, `track_mm`, `placement`, `fpdir`, `clearance_mm`, `connectors`) builds
   the board and the `net2pcb` pad-mapping sidecar (the unmapped-pad gate reads this). For bulk
   autorouting, `bodesign_autoroute` (`board_path`, `out_path`, `passes`).
2. **Finish** (high-speed) — step 4's tools.
3. **Export fab outputs** — `bodesign_emit_fab` (`board_path`, `out_dir`, `formats`, `pdf_layers`):
   gerbers / drill / pos (CPL) / step / pdf via `kicad-cli`.
4. **Gate** — step "Gate / done-criteria" below.

> **Freerouting needs the network the first time.** `bodesign_autoroute` bootstraps a JRE +
> `freerouting.jar` on demand and runs headless — **not available offline**. If it cannot run,
> route interactively in KiCad (the honest path for fab-grade boards anyway — see step 4) and pass
> the already-routed `.kicad_pcb` straight to finishing/export. Do not claim a routed board exists
> if the autoroute step did not run.

### 4. The finishing chain (MCP) — and what stays human

For high-speed boards, run the post-route MCP tools in order (each takes `in_path` → `out_path`, so
they chain). The DRC-guarded discipline below is enforced *by you*: re-gate after each step and
revert any step that introduces a copper/unconnected violation.

1. **widen** the bus toward the target width where clearance allows —
   `bodesign_widen_bus_tracks` (`in_path`, `out_path`, `nets`, `target_mm`, `clearance_mm`);
2. **pour** the reserved plane layers and strip dangling stitch vias —
   `bodesign_pour_planes` (`in_path`, `out_path`, `planes`, `stitch`, `stitch_net`, `stitch_pitch_mm`…);
3. **length-match** — `bodesign_length_match_bus` (`in_path`, `out_path`, `nets`, `budget_ps`,
   `ps_per_mm`, `report_path`). **DRC-guarded:** keep the tuned board *only if it stays DRC-clean*
   (re-run `bodesign_layout_drc_gate`); otherwise revert, re-measure skew on the actually-shipped
   board, and record `"kept": false` with a note that interactive meander tuning is needed. Never
   ship new violations to make a number look good;
4. **SI gate** — `bodesign_si_check` (`board_path`, `nets`, `z0`, `rs`, `vdd`, `edge_ns`,
   `overshoot_pass_pct`…): per-net series-terminated T-line testbench, transient edge, grades
   overshoot/settling `pass/warn/fail`.

Keep the `lengthmatch`/`si` reports and the DRC report for the gate. The keep/revert decision counts
**copper + unconnected only** — silk overlaps are cosmetic and must not trigger a revert.

**What the autorouter + this chain do NOT finish** (do these interactively in KiCad, and say so):
fab-grade controlled-impedance routing, coupled/symmetric differential pairs, BGA escape
(dog-bone / via-in-pad / microvia for 0.4–0.5 mm pitch), and final length-match meander tuning. The
autorouter handles bulk; the finishing tools widen/pour/check; the human closes the impedance and
length budget. Reference: `openmv/N6_board/C04_Layout/Routing_Rules.md`.

For via-in-pad on dense BGAs: `bodesign_via_in_pad` (`in_path`, `out_path`, `refs`, `drill_mm`,
`pad_mm`, `keep_rings`).

### 5. Cross-check against C03 and run the fab-release gate (engine layer)

Beyond the build gate, run the KiCad engine to confirm the **PCB implements the C03 schematic
intent** and to get a structured fab-readiness verdict (read `../../engines/kicad/ENGINE.md`):

```bash
K=../../engines/kicad/scripts
python3 $K/analyze_pcb.py <board>.kicad_pcb --full --analysis-dir analysis/
python3 $K/cross_analysis.py -s analysis/<run>/schematic.json -p analysis/<run>/pcb.json --analysis-dir analysis/
python3 $K/cross_verify.py --schematic sch.json --pcb pcb.json          # design intent vs implementation
python3 $K/analyze_gerbers.py generated/routed/<board>/gerbers/ --analysis-dir analysis/
python3 $K/fab_release_gate.py --schematic sch.json --pcb pcb.json --gerbers g.json --text
```

`cross_analysis.py` catches the dangerous cross-domain bugs (connector current vs trace width, ESD
gaps, decoupling adequacy, schematic/PCB net & pad-mapping sync). `analyze_pcb.py --full` reports
copper presence at every pad (catches the floating-part class of bug), via fanout, per-net length,
and DFM scoring. Every finding carries a `confidence` label + `evidence_source` — preserve those in
your report, don't launder them into bare assertions.

## Deliverables

Modelled on `openmv/C04-Layout/03_output/DELIVERABLES.md` and the N6 manifest. Per board, under
`generated/routed/<board>/` and `png/<board>/`:

| # | Artifact | Path | Source-of-truth? |
|---|----------|------|------------------|
| — | Layout constraints | `Layout_Constraints.json` + `Placement_Constraints.md` | source (markdown/JSON) |
| — | Stackup / routing / DFM specs | `Stackup.md`, `Routing_Rules.md`, `DFM_DFA_Rules.md` | source (markdown) |
| 1 | Routed board + DRC report | `<board>.kicad_pcb` + `<board>.drc.rpt` | source / generated |
| — | Pad-mapping sidecar | `<board>.map.json` (`unmapped` count) | generated (gate input) |
| 2 | Gerbers + drill | `gerbers/` + `drill/` | generated |
| 3 | Per-layer copper PNGs (L1..Ln top→bottom) | `png/<board>/L1_top.png … Ln_bottom.png` | generated |
| 4 | Fab-view PNG | `png/<board>/fab_top.png` | generated |
| 5 | Assembly package (CPL · IPC-2581 · ODB++ · IPC-D-356 · assembly drawing) | `assembly/` | generated |
| 6 | BOM | `../../C03-EE/generated/sch_<sub>/*-bom.csv` | from C03 |
| 7 | Length-match report (high-speed) | `<board>.lengthmatch.json` | generated |
| 8 | SI report (high-speed) | `<board>.si.json` | generated |

Rows 7–8 apply only when the board declares a high-speed bus (`BD_BUS`). The generated artifacts are
expensive but reproducible — keep them in the run folder; the markdown specs are the human-editable
source of truth.

## Gate / done-criteria — the C04 gate contract

The gate is **`bodesign_layout_drc_gate`** (`board_path`) for the DRC verdict + **`bodesign_c04_readiness`**
(`folder`) for package/SI completeness; cross-check the schematic-intent side with the local
`fab_release_gate.py` engine (step "Cross-check" above). It is **HARD FAIL** on any of:

- routed `.kicad_pcb` missing;
- **DRC: copper violations > 0 OR unconnected items > 0** (`layout_drc_gate` parses the DRC JSON and
  splits copper / unconnected / silk; it does *not* trust the build to have produced a clean board);
- **unmapped pads > 0** in the `net2pcb` map sidecar — a footprint whose pad names don't match the
  symbol leaves pads floating (this is exactly the PSRAM bug; the gate catches it);
- any of gerbers / drill / per-layer PNGs / fab PNG / CPL / IPC-2581 / assembly missing;
- **SI `worst == "fail"`** (reflections/overshoot over limit).

It **WARNS** (does not fail) on:
- **silkscreen overlaps** — cosmetic;
- **length-match over budget** (`within_budget == false`) — flagged as "interactive meander tuning
  needed", the one named human step; it is a visible warn, never a silent omission.

A board is **C04-complete** only when the gate verdict is COMPLETE (warns allowed). Until then it is
a **draft**. The honest verdict can be "COMPLETE with warns" — see the worked example
`openmv/N6_board/derivative_official/README.md`, which ships C04-COMPLETE with two honest residual
warns (18 cosmetic silk overlaps; length-match 197 ps over a 50 ps budget) and an SI gate of `warn`
(PSDQS overshoot ~11.7%). That is a truthful done-state; a "clean pass" achieved by widening a
threshold would not be.

The thresholds inside these gate tools are the contract. **Do not pass alternative thresholds to
make a board pass.** If a board fails, fix the board (route the floating pads, clear the DRC
violation, re-pour) or report the warn — never move the line.

## Honesty notes for this stage

Applies `../../references/honesty-model.md`:

- **Draft until proven** (rule 3 + the C04 paragraph): the board is a `draft` until DRC-clean and
  gate-passed (`layout_drc_gate` + `c04_readiness`). Fab outputs are not "released" until the board
  is **frozen** for C07.
- **Never relax a gate to fake a pass** (rule 1 + 5): the floating-PSRAM false-pass is the cautionary
  tale this whole gate exists to prevent. Show the evidence (`190/190 pads netted`,
  `copper 0 / unconnected 0`) rather than asserting "production-ready".
- **State provenance** (rule 2): stackup/impedance widths are `assumption` until the fab's solver
  confirms them; routed lengths and SI verdicts come from real tool runs — keep the
  `confidence`/`evidence_source` the engine attaches.
- **External gates stay external** (rule 4): DRC and ngspice SI are *internal tool verdicts*. EMC,
  FCC/CE, and a physically-built board are C06/lab/C07 territory — never marked passed here.
- **Honest boundaries** (rule 6): if Freerouting can't run, or a bus was excluded upstream, record it
  as a limit and leave it out — don't fabricate a routed board or a missing net.

## Handoff to C06 (Verify) and C07 (MFG)

To **C06 (`../c06-verify/GUIDE.md`)** export the **DRC report**, the **SI report**
(`<board>.si.json`), the **length-match report**, and the engine analysis run (`analysis/<run>/`) as
the verification baseline. C06 turns these into `pass/warn/fail` verdicts, runs EMC pre-compliance /
thermal / SPICE, and cross-checks against the C03 reference netlist. C06 produces verdicts; C04
produces the artifacts they grade.

To **C07 (`../c07-mfg/GUIDE.md`)** the **frozen** fab + assembly outputs (Gerbers, drill, CPL,
IPC-2581, ODB++, IPC-D-356, assembly drawing, BOM) unblock the manufacturing transfer and inventory.
These remain `pending` against the C04-freeze gate until the gate (`layout_drc_gate` +
`c04_readiness`) passes and the board is frozen — C07 must not order against a draft board.

## Tools & companion skills

- **KiCad analysis engine** — `../../engines/kicad/` (`ENGINE.md`). Key scripts in
  `engines/kicad/scripts/`: `analyze_pcb.py --full` (copper presence, fanout, length, DFM),
  `analyze_gerbers.py`, `cross_analysis.py` / `cross_verify.py` (schematic↔PCB sync, design intent),
  `fab_release_gate.py` (structured ready-for-fab verdict; `--strict` treats warns as fails),
  `diff_analysis.py` (revision deltas), `summarize_findings.py`. Bridges: `../../engines/emc` (run in
  C06), `../../engines/datasheets`.
- **The gated build workflow (bodesign MCP)** — generation runs through the MCP, not local scripts
  (see `../../SKILL.md` § "Relationship to the bodesign MCP server"): `c04_emit_layout_package`
  (one-shot build+gate) or the granular tools `impedance_solve` · `route_net2pcb` / `autoroute` ·
  `pour_planes` · `widen_bus_tracks` · `length_match_bus` · `via_in_pad` · `si_check` ·
  `layout_drc_gate` · `emit_fab` · `render_gerber_preview`, gated by `c04_readiness`. The
  `openmv/…/generated/tools/` scripts named throughout the worked examples are that reference
  board's local mirror of these same operations — read them for ground truth, but drive the MCP.
  Analysis stays local (the engine bullet above); only *generation* goes to the MCP.
- **`jlcpcb` / `pcbway`** — validate the manufacturer's design rules against your stackup/min
  trace-space and prepare the fab order (hand the *frozen* outputs over in C07; don't order a draft).
- **`spice` / `emc`** — SI/EMC *verdicts* belong to C06; here they inform routing decisions only.
- **`kidoc`** (`../../engines/kidoc/`) — render PCB SVGs, layer crops, and the layout section of the
  design-review/manufacturing package.
- **`docx` / `pdf` / `xlsx` / `pptx` + `docxmcp` MCP** — for the stackup drawing, fab notes, and
  assembly-drawing document artifacts.
