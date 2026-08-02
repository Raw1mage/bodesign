# C04 Layout (PCB) — turn the verified netlist into a DRC-clean, gated, fab-ready board

## Purpose & scope

C04 owns the **physical board**: placement, routing, the layer stackup, controlled-impedance
constraints, the routed `.kicad_pcb`, and the **gated fabrication + assembly output package**. It
takes C03's verified netlist plus the mechanical/interface constraints and produces a board that is
either still a **draft** or has passed the C04 gate (`bodesign_layout_drc_gate` + `c04_readiness`).

**Honour the feasibility tier C03 set** (`../../references/feasibility-triage.md`). **Tier 1–2** is
C04's autonomous lane — route + gate to a (near-)fab-ready board. **Tier 3** (HDI/any-layer / ≤0.4 mm
BGA / DDR/RF) is **not** routable on KiCad + the MCP: deliver the **concept+constraints** package and
hand routing to pro-EDA + human SI + HDI fab — cleanly, not as a half-routed dead-end. Emit it with
`emit_si_constraint_export(...)` (`../../references/si-constraint-handoff.md`): it writes
`SI_Constraint_Export.json` (source of truth) + `SI_Net_Classes.csv` (the table Allegro/Xpedition/
Altium import) + `SI_Constraint_Handoff.md` (per-tool mapping), with any constraint bodesign didn't
derive listed under `tbd[]` — never guessed. The net-classes come from C03's SI requirements + this
stage's stackup/floorplan; **the handoff package *is* the Tier-3 deliverable — make it whole.** If
placement reality diverges from C03's tier (denser/harder than estimated), that's a reconciliation
back to C03/C01, not a gate to stretch.

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

> **`readiness_pct: 100` ≠ done.** The readiness tools enforce this table as a machine-checkable
> manifest: the real gate is **`dod_ok: true`** in the readiness output — true only when every row
> below is `present` (or honestly deferred via a `dod_status.json` entry) and no `answered` field is
> fake-complete (a `TBC`/placeholder value). Read the `guide_compliance` block, not the bare percent.

Produce **all** of these before you report C04 done or hand off (see SKILL.md § "Definition of
Done"; deliverables land at the stage root, rendered previews in `02_build/`). Each exists **or** carries
an explicit `drafted`/`pending`/`not-run` status with a reason — fab outputs stay `pending` until
the board is frozen, which is honest, not missing.

| # | Required artifact | File | Bucket |
|---|---|---|---|
| 0 | **Placement review package + owner approval** | `renders/` (top 3D PNG + physical-scale SVG) + `placement_manifest.json` + `PLACEMENT_REVIEW.md` + `PLACEMENT_APPROVED.json` (owner-authorised) | `02_build/` — **gate: routing MUST NOT start before approval** |
| 1 | Layout + placement constraints | `Layout_Constraints.json` + `Placement_Constraints.md` | stage root |
| 2 | Stackup + routing rules | `Stackup.md` + `Routing_Rules.md` | stage root |
| 3 | Routed board + DRC report | `<board>.kicad_pcb` + `<board>.drc.rpt` | stage root |
| 4 | Gerbers + drill | `gerbers/` + `drill/` | stage root |
| 5 | Assembly package | CPL · IPC-2581 · assembly drawing | stage root |
| 6 | Per-layer copper PNGs + fab view | `copper_layers/`, `renders/` | `02_build/` |
| 7 | Length-match + SI reports | `<board>.lengthmatch.json`, `<board>.si.json` | stage root (high-speed only) |

**Placement-first contract (row 0):** placement is a **first-stage deliverable**, not an
internal step. After net2pcb (or any placement pass), emit the review package with
`gate.py c04_placement_review` (`board_pcb`, `out_dir`, `board_name`), show it to the owner,
and only after the owner authorises `PLACEMENT_APPROVED.json` may copper routing begin —
check with `gate.py c04_placement_gate` (`folder`). The AI must NOT write
`PLACEMENT_APPROVED.json` itself; it records the owner's explicit approval (with provenance)
or waits. `c04_readiness` warns (`placement_not_approved_before_routing`) when routed
artefacts exist without the approval marker.

**Self-verify:** run the gate — the MCP tool `bodesign_layout_drc_gate` (`board_path`) + the
landing verb `c04_readiness` (`gate.py c04_readiness --repo <abs-project>` — NOT an MCP tool) —
and report the verdict (see "Gate / done-criteria" below). Mechanical constraints are
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
- **The two signed stage-entry verdicts** — `C03-EE/check_c03.report.json` and
  `C03-EE/prd_bom_crosscheck.report.json`. These are **entry conditions, not reference material**:
  `c04_readiness` reads them and refuses layout unless both say `gate: PASS`. See the gate below.

### C03→C04 entry gate (machine-enforced — `assess_c04_layout_readiness`)

Entry is checked in two tiers, because "C03 ran" and "C03's delivery is acceptable" are different
questions and an existence check standing in an acceptance check's place returns green on a broken
BOM (BR_20260707):

- **Tier-0 — did C03 run?** `C03-EE/` + a `.net` + `Mechanical_Constraint_Export.json` on disk.
  Missing → `blocked_upstream_c03_missing`.
- **Tier-1 — is C03's delivery acceptable?** The two reports above, read at **pinned paths** (never
  searched for — a search chain is itself a silent fallback). Each distinct inadequacy gets its own
  status, because each has a different first action:

| `c04_readiness` status | Means | First action |
|---|---|---|
| `blocked_c03_entry_gate_not_run` | A report is absent — the gate **never ran**, which is not passing | Run it in C03 (the error names the exact command + expected path) |
| `blocked_c03_entry_gate_report_unusable` | Report present but corrupt / carries no `gate` field | Re-emit it; a report that cannot be read carries no verdict |
| `blocked_c03_entry_gate_failed` | `gate: FAIL` | Fix the design/BOM in C03 and re-run. **Never relax the gate to pass** |
| `blocked_c03_entry_gate_scope_incomplete` | `gate: PASS` but `netlist_crosscheck.status=not_run` | Re-run `check_c03` with `netlist_path=[...]` + `covers_boards=[...]` |

**Why a PASS can still be refused.** `check_c03` states in its own docstring that with no netlist
supplied, `gate=PASS` *"must NOT be read as 'every BOM row is drawn'"*. C04 placement rests on
exactly that guarantee, so C04 declines to read **not-checked** as **checked-and-clean**. This is not
C04 overruling C03 — it is C04 honouring the scope C03 itself declared. `ssot_crosscheck` and
`pin_polarity` are quality signals rather than preconditions for starting layout: they **warn** (on
both the blocked and the cleared path) and do not block.

**C04 never re-runs the C03 gates.** Their inputs — which CSV is the BOM, which `.net` covers which
boards — are knowledge only C03 holds; inferring `covers_boards` here "cannot tell 'no netlist covers
this board' from 'every row on it is undrawn'". The producer signs, the consumer reads the signature.
So C03 must pass `out_dir=<project>/C03-EE` when it runs both gates, or C04 entry stays shut.

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
reference board's own **point-in-time local copy** of these operations (“mirror” = worked example,
**not** a synced 1:1 twin — it can drift from current MCP behaviour) — read it for the deliverable
contract shape, but drive generation through the MCP, not those scripts; where the two disagree,
the MCP's current behaviour wins.

### 0. Ingest the refs SSOT first (refs-first gate)

Run the **`refs_ingest`** landing verb (`folder` = the stage dir or an explicit `01_refs/` path;
via `gate.py`) before assembling anything: it scans the stage's `01_refs/` SSOT (physical
constraints, board-edge→face mapping, stamp-hole definitions) into a read-only, authority-ranked
manifest (absent root → `root_visible: false`, loud — never a clean empty). Everything this stage
places or injects must trace back to it: `c04_face_placement` requires per-connector `provenance`,
`c04_castellation` requires an SSOT footprint anchor, and the Gate section's `c04_dod_traceback`
verifies every delivered item against these anchors. No manifest → nothing to trace against.

### 1. Assemble the layout constraints

Author `Layout_Constraints.json` (schema `bodesign.c04.layout_constraints.v1`) and
`Placement_Constraints.md` from the C01/C03 inputs: `exposed_components`, `connector_edge_openings`,
`heat_zones`, `antenna_keepouts`, `battery_zone`, `emc_esd_notes`. Anything layout-owned that is not
yet decided (board outline, mounting holes, exact XY, stackup) goes in `open_decisions` with an
owner — do **not** silently fill it. Mark the file `"state": "drafted"` until the placement is done.

### 2. Define the stackup & compute impedance widths

Pick a layer count from density + the controlled-impedance net set, and write `Stackup.md` +
`Routing_Rules.md` (net classes: width / clearance / impedance / length-match). Compute trace
widths from the stackup rather than guessing — run the **`impedance_solve`** landing verb via
`gate.py` (`stackup`, `targets`): it returns microstrip/stripline Z0 → width for each target net class. (No MCP? Use any
microstrip/stripline solver and record the inputs.)

State honestly that final stackup + exact geometry must be **confirmed against the chosen fab's
controlled-impedance solver** — your computed widths are design starting points, an `assumption`
until fab-confirmed. Real example: `openmv/N6_board/C04_Layout/Stackup.md` and `Routing_Rules.md`.

### 3. Build the board via the MCP (one-shot, or step-by-step)

The bodesign MCP produces and gates the deliverable manifest — see `../../SKILL.md` § "Relationship
to the bodesign MCP server". Two ways in:

**One-shot:** the `c04_emit_layout_package` landing verb (`out_dir`, `c01`, `c03`; via `gate.py`)
assembles the whole C04 package (board + constraints + renders + assembly outputs) from the C01/C03
handoffs, then the `c04_readiness` landing verb (`folder`) reports the gate verdict.

**Step-by-step** (when you need control over routing/finishing):
1. **Bind connectors to their frozen faces first** — the `c04_face_placement` landing verb
   (`face_layout`; via `gate.py`) takes C01's frozen `Face_Layout.json` (every connector needs
   `ref`, `face`, and an SSOT `provenance` anchor — missing provenance is fail-fast, 天條 2) and
   returns deterministic placement bands, all `movable_by_c04: false` (DD-4: **the face is not a
   C04 degree of freedom** — C04 places *within* the frozen face, never across it). Convert the
   bands to concrete `{ref: [x_mm, y_mm, rot_deg]}` anchors with `placement_to_coords` (requires
   a real board outline — positive `width_mm`/`height_mm` — a frozen face without a physical
   board is fail-fast, never a fabricated coordinate) and feed the result to `route_net2pcb`'s
   `placement=` map: an explicit `placement` map always wins for the refs it names, so the frozen
   faces survive whatever `strategy` places the rest.
2. **Place + route from the netlist** — `bodesign_route_net2pcb` (`netlist_path`, `out_path`,
   `layers`, `plane_layers`, `track_mm`, `placement`, `fpdir`, `clearance_mm`, `connectors`,
   `strategy`, `seed`, `board_mm`) builds
   the board and the `net2pcb` pad-mapping sidecar (the unmapped-pad gate reads this). Placement:
   `strategy="deterministic"` runs the electrically-aware pure-python pre-placement (main-IC
   anchoring → decap/crystal pin-affinity clustering → largest-first greedy (R4) → fixed-seed SA)
   and returns source-anchored `placement_violations` (R1 decap distance / R8 die-shadow proxy),
   `hpwl_mm`, and echoed `effective` params; it REQUIRES `board_mm` and fails fast on missing
   footprint geometry — never silently falls back. `strategy="grid"` (default) keeps the naive
   8mm grid as the comparison baseline. An explicit `placement` map always wins for the refs it
   names. For bulk autorouting, `bodesign_autoroute` (`board_path`, `out_path`, `passes`).
3. **Finish** (high-speed) — step 4's tools.
4. **Export fab outputs** — `bodesign_emit_fab` (`board_path`, `out_dir`, `formats`, `pdf_layers`):
   gerbers / drill / pos (CPL) / step / pdf via `kicad-cli`.
5. **Gate** — step "Gate / done-criteria" below.

> **Freerouting needs the network the first time.** `bodesign_autoroute` bootstraps a JRE +
> `freerouting.jar` on demand and runs headless — **not available offline**. If it cannot run,
> route interactively in KiCad (the honest path for fab-grade boards anyway — see step 4) and pass
> the already-routed `.kicad_pcb` straight to finishing/export. Do not claim a routed board exists
> if the autoroute step did not run.

### 3b. Stamp-module / castellated boards (`c04_castellation`)

A multi-board product built around a castellated core module (stamp module soldered onto carrier
boards) needs plated half-hole edge pads. The **only sanctioned path** is the `c04_castellation`
landing verb (`spec`, `board_outline`, optional `path`; via `gate.py`):

- **spec** — `{edge, pad_count, pitch_mm, pad_width_mm, pad_height_mm, drill_mm, net_names[],
  provenance}`. All numerics must be positive; `provenance` is **required** — a stamp-module edge
  must trace to an SSOT footprint anchor (天條 2 no-fabrication). `pad_count` stays parameterised
  until the SSOT freezes it — don't invent a count.
- **board_outline** — real `width_mm`/`height_mm` (> 0), never guessed; the verb centres the pad
  row along the frozen edge at `pitch_mm`.
- **output** — `{path, edge, pads[], sexpr_block}`: each pad as a deterministic, injectable KiCad
  S-expression (`thru_hole oval`, `*.Cu`/`*.Mask`, `castellated=true` property). The ee worker
  injects `sexpr_block` into the real `.kicad_pcb`.

**Why S-expr injection and nothing else (DD-5):** the pcbnew scripting mutation paths for edge-pad
construction are known SwigPyObject **segfault** paths that crash the interpreter and can corrupt
the board file (`issues/BR_20260704_pcbnew_scripting_segfault_hazards.md`). The verb hard-refuses
them (`BOARD_SURGERY_UNSAFE_PATH`) — do not hand-drive pcbnew for castellation.

**Net assignment discipline:** which nets may cross the castellated boundary is an upstream SSOT
constraint, not a C04 choice — typically low-speed signals and power only; high-speed memory buses
stay on-module. Pull the allowed `net_names` from the stage's `01_refs/` SSOT and let
`c04_dod_traceback` (Gate section) prove the assignment traces back to it.

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

> **How to actually do those human steps in KiCad** — the interactive-router modes
> (walk-around / shove / highlight-collisions), net-class-driven routing, keepout rule
> areas, copper-to-edge clearance, filleted outlines/cutouts, schematic⇔PCB cross-probe,
> STEP-model sourcing, and datum/hotkey throughput — are documented operationally in
> **`references/kicad-interactive-layout.md`**. It is a *usage manual for the KiCad UI*;
> every operation there produces copper the C04 gate grades — none of it relaxes the gate.

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

The gate is **`bodesign_layout_drc_gate`** (MCP tool; `board_path`) for the DRC verdict + the
**`c04_readiness`** landing verb (`gate.py c04_readiness --repo <abs-project>`) for package/SI
completeness; cross-check the schematic-intent side with the local
`fab_release_gate.py` engine (step "Cross-check" above). It is **HARD FAIL** on any of:

- routed `.kicad_pcb` missing;
- **DRC: copper violations > 0 OR unconnected items > 0** (`layout_drc_gate` parses the DRC JSON and
  splits copper / unconnected / silk; it does *not* trust the build to have produced a clean board);
- **unmapped pads > 0** in the `net2pcb` map sidecar — a footprint whose pad names don't match the
  symbol leaves pads floating (this is exactly the PSRAM bug; the gate catches it);
- any of gerbers / drill / per-layer PNGs / fab PNG / CPL / IPC-2581 / assembly missing;
- **SI `worst == "fail"`** (reflections/overshoot over limit);
- **DoD refs-traceback blocking** — run the `c04_dod_traceback` landing verb
  (`deliverable_items` = every delivered component/pin/coordinate with its `provenance` anchor of
  the form `<ssot_file>:<locator>`; `ssot_required_refs` = what the `01_refs/` SSOT requires the
  design to cover; optional `ssot_anchors` allowlist of valid SSOT filenames). Any `untraceable`
  entry (no SSOT anchor = 憑空發明) **or** any `unfulfilled` ref (SSOT-required but not delivered
  = 漏做) → `blocking: true`, and the stage's `dod_ok` is false. This upgrades the DoD from
  "files exist" to "every item traces to the SSOT" (EPIC 切面 5) — existence alone no longer
  passes a refs-derived board.

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

- **`references/kicad-interactive-layout.md`** — the *operator* layer behind the "what stays
  human" steps: the concrete KiCad PCB-editor operations (origin/datum, filleted outline +
  cutouts, keepout rule areas, schematic⇔PCB cross-probe, net classes, copper-to-edge
  clearance, interactive-router modes, STEP-model sourcing, text-align, hotkeys) that close
  what the autorouter + finishing chain leave open. Each operation maps back to the
  deliverable/gate it feeds — it teaches *how to produce* gate-gradable copper, never how to
  pass without it.
- **`references/stackup-and-placement.md`** — the *design-intent* layer behind the MCP calls:
  stackup choice (2L/4L/6L + plane adjacency), placement partitioning (power/noise/thermal,
  decoupling-at-pin), and how to **realise C03's SI requirements** (return-path continuity,
  via-stitching, length-match, 3W). It supplies the judgment; the MCP (`impedance_solve` /
  `length_match_bus` / `si_check` / `layout_drc_gate`) executes and the engine verifies — never
  relax a gate to pass (the floating-PSRAM lesson).
- **`references/layout-review-method.md`** — the *review-discipline* layer: forced-find prompting
  (kill "looks good to me"), the five review categories, independent multi-pass review, the
  dedup-ready **finding schema** (with `rule_ref`/`confidence`/`evidence_source` grounding every
  finding to the compendium + an evidence source), and the **Layout Review / Stackup Specification
  report templates**. It is how to conduct the G2 design-review walkthrough rigorously and structure
  its concerns; severities align to the deterministic gate's fail/warn split and the verdict slots
  into `_design_review/design_review.json` — it feeds the gates, never relaxes them.
- **KiCad analysis engine** — `../../engines/kicad/` (`ENGINE.md`). Key scripts in
  `engines/kicad/scripts/`: `analyze_pcb.py --full` (copper presence, fanout, length, DFM),
  `analyze_gerbers.py`, `cross_analysis.py` / `cross_verify.py` (schematic↔PCB sync, design intent),
  `fab_release_gate.py` (structured ready-for-fab verdict; `--strict` treats warns as fails),
  `diff_analysis.py` (revision deltas), `summarize_findings.py`. Bridges: `../../engines/emc` (run in
  C06), `../../engines/datasheets`.
- **The gated build workflow (bodesign MCP)** — generation runs through the MCP, not local scripts
  (see `../../SKILL.md` § "Relationship to the bodesign MCP server"): `c04_emit_layout_package`
  (one-shot build+gate) or the granular tools `impedance_solve` · `c04_face_placement` (frozen-face
  placement bands → `placement_to_coords`) · `route_net2pcb` / `autoroute` · `c04_castellation`
  (stamp-module edge pads, S-expr injection) · `pour_planes` · `widen_bus_tracks` ·
  `length_match_bus` · `via_in_pad` · `si_check` · `layout_drc_gate` · `emit_fab` ·
  `render_gerber_preview`, gated by `c04_readiness` + `c04_dod_traceback`. The
  `openmv/…/generated/tools/` scripts named throughout the worked examples are that reference
  board's point-in-time local copy of these same operations (can drift from current MCP
  behaviour) — read them for the contract shape, but drive the MCP; the MCP's current behaviour
  is authoritative where they disagree.
  Analysis stays local (the engine bullet above); only *generation* goes to the MCP.
- **`jlcpcb` / `pcbway`** — validate the manufacturer's design rules against your stackup/min
  trace-space and prepare the fab order (hand the *frozen* outputs over in C07; don't order a draft).
- **`spice` / `emc`** — SI/EMC *verdicts* belong to C06; here they inform routing decisions only.
- **`kidoc`** (`../../engines/kidoc/`) — render PCB SVGs, layer crops, and the layout section of the
  design-review/manufacturing package.
- **`docx` / `pdf` / `xlsx` / `pptx` + `docxmcp` MCP** — for the stackup drawing, fab notes, and
  assembly-drawing document artifacts.
