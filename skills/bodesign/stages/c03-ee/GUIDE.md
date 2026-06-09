# C03 EE — Electrical Engineering: design definition → schematic → BOM → netlist → bridges

## Purpose & scope

C03 turns the product intent (C00) and interface constraints (C01) into the **electrical
truth** of the board: a design definition, a captured schematic (KiCad), a complete machine
BOM, a netlist (pin → net), a GPIO/interface pinmap, a power-frontend diagram, and the
`Mechanical_Constraint_Export.json` that bridges back to ME (C02) and forward to layout (C04).

This stage HAS an execution engine — the **KiCad analysis engine** at
`../../engines/kicad/` (full reference: `../../engines/kicad/ENGINE.md`). You do not eyeball a
schematic and assert it is correct; you run `analyze_schematic.py`, read its structured JSON,
and every finding you carry forward keeps its `confidence` label and `evidence_source`.

**C03 owns:** electrical architecture, schematic capture/review, regulator + power-tree design,
component selection (with provenance), pin allocation, net connectivity, signal-integrity
*requirements* (the numbers C04 must hit), and the C03→C02/C04 mechanical bridge.

**C03 does NOT own:** board outline, placement, routing, stackup, impedance *realisation*
(that is C04 — you hand it the target Z0 and length-match groups, it makes copper meet them);
SPICE/EMC/thermal *verdicts* (C06 runs those — you name the plan); final sourcing/ordering
(the `bom` skill + distributor skills do the pricing/stock/order). You produce the netlist and
the constraint export; you do not relax a requirement to make a downstream gate pass.

## Required deliverables — Definition of Done

Produce **all** of these before you report C03 done or hand off (see SKILL.md § "Definition of
Done"). Each exists on disk **or** carries an explicit `draft`/`blocked` status with a reason — a
connectivity gap is documented in `Netlist_Status.md`, never silently dropped.

| # | Required artifact | File | Notes |
|---|---|---|---|
| 1 | Design definition + architecture | `Design_Definition.md` / `EE_Design_Specification.md` + `Architecture.md` (or a merged `Architecture_and_BOM.md`) | `draft` until a named EE owner signs off |
| 2 | Power tree | `Power_Tree.md` (+ `..._power_frontend.svg`) | rails, decoupling, budget |
| 3 | Schematic | `generated/sch*/*.kicad_sch` | or the honest interface subset; MPNs on properties |
| 4 | Complete BOM | `BOM.csv` / `..._完整BOM.xlsx` | exported from the *verified* analyzer JSON |
| 5 | Netlist | `..._網路表.xlsx` / `.net` | full, or honest subset |
| 6 | GPIO/interface pinmap | `..._GPIO_pinout.xlsx` / `Pin_Allocation.csv` | drives C05 |
| 7 | Netlist status | `Netlist_Status.md` | required **iff** a full netlist is not recoverable |
| 8 | Mechanical bridge | `Mechanical_Constraint_Export.json` | `approval=false` |

**Self-verify:** run `analyze_schematic.py` and clear (or explicitly justify) every `high` finding —
no open DS-001 / SS-001 / PP-001 / RS-002. There is **no `c03_readiness` tool**; the analyzer's gate
is your self-check, plus `bodesign_package_readiness` for the roll-up. Model:
`thesmart_products/rockbox/c03-ee/` (note its merged `Architecture_and_BOM.md`).

## Inputs (from upstream)

- **From C00 (PRD):** the product thesis, target market / certification target (gates review
  severity — see `../../engines/kicad/references/design-intent.md`), power source (battery vs
  mains vs USB), feature list that drives the block diagram. Read `../c00-prd/`.
- **From C01 (ID/UX + interfaces):** the interface/connector list, external-port inventory
  (USB-C, RJ45, camera, SD…), user-I/O (LED, button), enclosure-driven edge preferences. Read
  `../c01-id/`. These become rows in your Interface Definitions and openings in the mechanical
  export.
- **For a *derived* or *reverse-engineered* board:** a reference schematic PDF / published
  pinout / glb model in the gitignored `refs/` vault. Treat it as evidence to cite, never as
  something to copy (honesty rule 7). Label every reconstructed fact as reverse-engineered.

## SOP

The flow is: define → capture → analyse → verify against datasheets → cross-check → export.
Steps 1–2 are authoring; 3–6 drive the engine; 7–8 are the bridges.

In all commands, `ENG=../../engines/kicad/scripts` (the KiCad engine script dir). Prefer
`--analysis-dir analysis/` so every run lands in one timestamped folder tracked by
`analysis/manifest.json`.

### 1. Write the Design Definition + Architecture

Author `Design_Definition.md` (or `EE_Design_Specification.md`): design intent, the block
architecture (a table of blocks → key parts → datasheet/reference provenance), the power tree,
the key interfaces, and a "design/verification notes for C06" section. Add an `Architecture.md`
block diagram. Model these on the real examples — see
`thesmart_products/openmv/C03-EE/03_output/Design_Definition.md` and
`thesmart_products/openmv/N6_board/C03_EE/{EE_Design_Specification,Architecture,Power_Tree,Interface_Definitions}.md`.

Mark the document `draft` with a reason until an EE owner signs off ("未核可;佈局凍結前需 EE
設計審查 gate"). An unsigned spec is `draft`, not silently "done" (honesty rule 3).

If this is a reverse-engineered baseline, write a `Reverse_Engineering_Report.md` first: state
your **method**, what was **reliably extracted** vs what **needs original CAD**, the whole-board
inventory (component/net/pin counts), and the block architecture. Label it reverse-engineered
throughout. See `thesmart_products/openmv/C03-EE/03_output/Reverse_Engineering_Report.md`.

### 2. Capture the schematic — generate via the MCP, or author in KiCad

Produce `.kicad_sch` sheets (one per block for a large design — e.g. `generated/sch_memory/`,
`sch_rgmii/`, `sch_sensors/` in the aiguard example) plus a `symbols/` library for non-standard
parts. Put MPNs and `Datasheet` URLs on the symbol properties as you go — the analyzer's
sourcing gate (SS-001/002/003) and the datasheet sync both key off MPN coverage.

**Primary path — bodesign MCP (when reachable; see `../../SKILL.md` § "Relationship to the
bodesign MCP server"):** generate rather than hand-draw.
- `bodesign_emit_symbol` for each non-standard part (pins + footprint filter + datasheet).
- `bodesign_compose_schematic` (`out_dir`, `project_name`, `spec`, `symbol_dirs`, `validate=true`)
  to place + net a schematic from the structured design spec; it returns `placed`, `nets`,
  `unresolved_pins`, and a `kicad-cli` validation block. Resolve `unresolved_pins` before moving on.
- `bodesign_pin_allocation` (`nets`, `mcu_refs`) to derive the GPIO/peripheral map for step 7/FW.

**Fallback — manual KiCad capture** (MCP absent, or a reverse-engineered baseline with no spec to
generate from): author the `.kicad_sch` by hand as above.

Either way, the generated/authored schematic is **unverified** until step 4–5. Generation ≠
correctness — do not skip the analyzer because a tool produced the file.

If a full CAD capture is out of scope (reverse-engineered baseline, no original CAD), say so and
deliver the *interface + major-IC* connectivity instead, with a documented gap — see step 6 and
`Netlist_Status.md`. Do not invent a schematic to look complete.

### 3. Sync datasheets (verification prerequisite)

Datasheets are what turn a *consistency* check into a *correctness* check. Without them the
engine can only confirm the design agrees with itself. Sync before reading any analyzer output:

```bash
python3 ../../engines/datasheets/../digikey/scripts/sync_datasheets_digikey.py <file.kicad_sch>
# DigiKey best (direct PDF URLs); element14 reliable; lcsc for LCSC-only; mouser last resort.
```

The engine exposes the `datasheets` and `emc` bridges via `../../engines/datasheets` and
`../../engines/emc` symlinks. If sync fails or no API keys exist, fall back to the `Datasheet`
property URLs, the `digikey` skill for individual parts, or **ask the user** — do not silently
skip verification. Datasheets cache into `datasheets/` with a `manifest.json`; extractions land
in `datasheets/extracted/<MPN>.json` and are reused across runs.

### 4. Run the schematic analyzer

```bash
python3 $ENG/analyze_schematic.py <file.kicad_sch> --analysis-dir analysis/
# Stage/audience filtered views:
python3 $ENG/analyze_schematic.py <file.kicad_sch> --stage schematic --audience reviewer --text
# Network + MPNs available → fold in obsolescence/EOL audit:
python3 $ENG/analyze_schematic.py <file.kicad_sch> --lifecycle --analysis-dir analysis/
```

This emits ~60–220 KB JSON: components/BOM, full nets (pin→net), detected subcircuits
(regulators with Vout + `vref_source`, dividers, RC/LC filters, crystals, ESD, decoupling, buses,
diff pairs, power-sequencing…), IC pinout analysis, power analysis (PDN impedance, budget, EN/PG
chains), and ERC. Read the JSON directly — don't write ad-hoc extractors. If the shape surprises
you, run `python3 $ENG/analyze_schematic.py --schema` first.

**The output envelope carries the honesty model for you.** Every finding has `rule_id`,
`detector`, `severity`, `confidence` (`deterministic` / `heuristic` / `datasheet-backed`), and
`evidence_source`; the `trust_summary` rolls up `trust_level`, `by_confidence`, and
`provenance_coverage_pct`. When you quote a finding in a deliverable, keep that label — do not
launder a `heuristic` Vout estimate into a bare assertion (honesty rule 2).

Watch these gate findings:
- **DS-001** (datasheet coverage, `high`): no verified claim is possible. Either sync datasheets,
  populate MPNs, or state explicitly that every pin/electrical/regulator finding is *consistency
  only* — and never write "verified"/"confirmed"/"per datasheet" anywhere.
- **SS-001** (MPN < 50 %, `high`): a pre-fab blocker; resolve before any handoff to sourcing.
- **PP-001** (`high`): an IC power pin reaches its rail only through a capacitor (no DC path).
- **RS-002** (`high`): a rail depends on the user closing an open jumper.
- **NT-001**: single-pin/floating net.

### 5. Verify analyzer output against the raw schematic + datasheets

The analyzer can produce plausible-but-wrong results (wrong Vout, wrong pin→net, missing MPN)
without erroring. These flow into your report unless you check. Verify, don't trust:

- **Component count** vs raw `(symbol (lib_id` blocks (minus power symbols) — must match exactly.
- **Pin-to-net** for every IC against the datasheet pin table — the highest-value check; a wrong
  pin map is invisible to ERC and kills the board. Cite the datasheet page/figure in your notes.
- **Transistor/regulator pinout assumptions:** a SOT-23 `lib_id` suffix (`Q_NPN_BEC`…) encodes a
  pinout that may not match the real part. With an MPN, verify against the datasheet; without one,
  assess *plausibility* against the common convention and report the confidence level — "matches
  the most common SOT-23 BCE convention" vs "could go either way" (honesty: show, don't assert).
- **Regulator Vout:** check `vref_source` — `lookup` = datasheet-verified; `heuristic` = a guess
  needing manual confirmation. `vout_net_mismatch` flags >15 % disagreement with the rail name.

Deep checklist: `../../engines/kicad/references/schematic-analysis.md`.

### 6. Cross-check, simulate, and document the connectivity boundary

- **Reference cross-check (do this when a control group exists):** if you have a known-good
  reference netlist (e.g. the source board you derived from), compare net-by-net and report the
  delta honestly — what matched, what is an *extra*, what is *missing*. "269/269 nets matched the
  reference" is a *shown* claim (honesty rule 5). `diff_analysis.py base.json head.json --text`
  compares two analyzer runs.
- **What-if** any value you are unsure of before committing it:
  `python3 $ENG/what_if.py analysis/<run>/schematic.json R5=4.7k --text` (recalculates divider
  ratios, filter cutoffs, regulator Vout; `--fix voltage_dividers[0] --target 3.3` solves
  inverse with E-series snapping).
- **SPICE (analog front-ends):** if `which ngspice ltspice xyce` finds a simulator, hand the
  schematic JSON to the `spice` skill to verify filter/divider/gain math. This is a *plan* item
  for C06's verdict — at C03 it is a sanity check, marked `not-run` in the spec until C06 runs it.
- **Document the honest connectivity boundary.** When source data cannot yield a full netlist
  (no original CAD; a bus configured by boot-ROM and absent from public firmware; ~600 passives
  with no shared identifier between a glb and a lossy schematic PDF), write `Netlist_Status.md`:
  what is *required*, what is *recoverable* and from where, what *is* derivable (named ICs,
  header I/O, power-rail membership), and the **conclusion** that the gap is a *source-data
  limit, not a process failure*. This is the canonical pattern — model it exactly on
  `thesmart_products/openmv/N6_board/C03_EE/Netlist_Status.md`. A documented gap is a finding; a
  back-filled guess is a lie (honesty rule 6).

### 7. Export the deliverable tables

From the verified analyzer JSON (not by hand), export:
- **Complete BOM** — `BOM.csv` (or `..._完整BOM.xlsx`): reference / value / footprint / MPN /
  manufacturer / qty / block. Hand to the `bom` skill for enrichment, pricing, stock, lifecycle,
  and fab BOM/CPL — do not reimplement sourcing here.
- **Netlist** — `..._網路表.xlsx` or `.net`: net → pins (or the honest interface subset per
  step 6).
- **GPIO + interface pinmap** — `..._GPIO_pinout.xlsx`, `..._介面pinmap.xlsx`,
  `Pin_Allocation.csv`: MCU ball → GPIO → peripheral function. Drives FW (C05) and headers.
- **Power-frontend diagram** — `..._power_frontend.svg` (+ `.png`): the input-protection →
  charger → OR-ing → regulators → rails chain. Generate via the `kidoc` engine's power-tree
  diagram or the `drawmiat` skill; keep `Power_Tree.md` as the markdown source of truth.

### 8. Produce the Mechanical_Constraint_Export.json (C03→C02/C04 bridge)

This is the structured handoff that lets ME finalise the enclosure and Layout place connectors.
Export **only explicit C03 values** — component heights, connector openings (with preferred edge
and owner), heat sources (W), antenna keepouts, ESD/EMC notes, and a battery envelope marked
`TBC` if ME has not confirmed it. Board outline, mounting holes, placement coordinates, and final
dimensions stay C04/C02 responsibilities — say so in the `source.notes`. Set
`approval.mechanical_approval` / `layout_approval` to `false`: this export is a handoff, not an
approval (honesty rule 4). Model it exactly on
`thesmart_products/openmv/C03-EE/03_output/Mechanical_Constraint_Export.json`.

Optionally generate an engineering doc package (HDD / power-analysis / schematic-review) via the
`kidoc` engine: `python3 ../../engines/kidoc/scripts/kidoc_scaffold.py --type power_analysis
--analyze --output <md>` then `kidoc_generate.py` for PDF. See `../../engines/kidoc/ENGINE.md`.

## Deliverables

Source-of-truth = markdown/CSV/JSON you author or export; generated = engine/diagram outputs.

| Artifact | File | Kind | Notes |
|---|---|---|---|
| Design definition | `Design_Definition.md` / `EE_Design_Specification.md` | source | intent, blocks, power, interfaces; `draft` until signed |
| Reverse-eng report | `Reverse_Engineering_Report.md` | source | only for derived baselines; method + reliable-vs-needs-CAD |
| Architecture | `Architecture.md` | source | block diagram + component evidence |
| Power tree | `Power_Tree.md` (+ `..._power_frontend.svg/.png`) | source + generated | rails, decoupling, budget (to-confirm) |
| Interfaces | `Interface_Definitions.md` | source | connector → electrical → SI requirement |
| Schematic | `generated/sch*/*.kicad_sch` + `symbols/` | source | KiCad; MPNs on properties |
| Complete BOM | `BOM.csv` / `..._完整BOM.xlsx` | exported | ref/value/fp/MPN/qty/block |
| Netlist | `..._網路表.xlsx` / `.net` | exported | full, or honest interface subset |
| Pinmap | `..._GPIO_pinout.xlsx`, `..._介面pinmap.xlsx`, `Pin_Allocation.csv` | exported | ball→GPIO→function |
| Netlist status | `Netlist_Status.md` | source | the honest connectivity boundary (when full netlist is blocked) |
| Mechanical bridge | `Mechanical_Constraint_Export.json` | exported | C03→C02/C04; `approval=false` |
| Analyzer runs | `analysis/<run>/*.json` + `manifest.json` | generated | keep; gitignored, manifest tracked |

## Gate / done-criteria

C03 is genuinely complete when:
- Design definition is reviewed and signed by a named EE owner (else it is `draft`).
- Schematic analyzer runs clean of **`high`** findings, or each is explicitly justified:
  **no open DS-001** (datasheets synced or the consistency-only caveat stated), **no SS-001**
  (MPN coverage adequate for sourcing), **no unresolved PP-001 / RS-002**.
- Every IC pin-to-net is verified against its datasheet (or the unverifiable ones are flagged
  with a plausibility assessment).
- BOM, netlist, pinmap, and power-frontend are exported from the *verified* JSON.
- `Mechanical_Constraint_Export.json` is produced with `approval=false`.
- If a full netlist is not recoverable, `Netlist_Status.md` documents the source-data limit.

Still `draft` if any `high` finding is unexplained, datasheets are unsynced with claims made
anyway, or a connectivity gap is silently back-filled. SPICE/EMC/thermal *verdicts* are **not**
a C03 gate — they are `not-run` here and owned by C06.

## Honesty notes for this stage

Anchored in `../../references/honesty-model.md`:
- **Every value/net carries provenance** (rule 2). The analyzer's `confidence` + `evidence_source`
  exist precisely so you don't have to launder findings into bare assertions — preserve them.
- **Missing connectivity is a documented limit, not an invented net** (rule 6). `Netlist_Status.md`
  is the canonical artifact: state required / recoverable / derivable / conclusion. Exclude rather
  than guess.
- **Reverse-engineered baselines are labelled as such** — and `refs/` source material is cited by
  path/role, never copied into the deliverable (rule 7).
- **External gates stay external** (rule 4): FCC Part 15 / CE RED / EN 55032 / IEC 62368-1 /
  RoHS-REACH and ESD-lab results are *targets + plans* here. `Mechanical_Constraint_Export.json`
  carries `approval=false`.
- **Show reliability, don't assert it** (rule 5): "269/269 nets matched the reference (control
  group)" beats "robust design". Report extras and misses both.
- Litmus test before upgrading any status: *if the reader fabricated the board tomorrow and
  checked this claim, would it hold?* If not, downgrade and name what is missing.

## Handoff to C04 (Layout) and C06 (Verify)

To **C04 (`../c04-layout/GUIDE.md`)** export:
- the verified **netlist** (the connectivity C04 routes — full or the honest subset),
- the **SI requirements as targets** (USB 90 Ω diff; MIPI CSI-2 100 Ω diff length-matched; XSPI
  50 Ω SE DQS-matched; SDMMC 50 Ω) — C04 makes copper meet these; you do not pre-route,
- the **`Mechanical_Constraint_Export.json`** (heights, connector edges/openings, heat sources,
  antenna keepouts) so C04 can place and C02 can finalise the enclosure.

To **C06 (`../c06-verify/GUIDE.md`)** export the same analyzer run as the **reference cross-check
baseline** and the design/verification notes (which checks to run: ERC/DRC, SPICE on analog
front-ends, EMC pre-compliance, thermal on the linear charger, reference netlist crosscheck).
C06 produces the verdicts; C03 names the plan.

## Tools & companion skills

- **KiCad analysis engine** — `../../engines/kicad/` (`ENGINE.md`). Scripts in
  `engines/kicad/scripts/`: `analyze_schematic.py` (with `--lifecycle`, `--schema`,
  `--stage/--audience`), `what_if.py`, `diff_analysis.py`, `summarize_findings.py`,
  `cross_analysis.py`/`cross_verify.py` (when a PCB exists), `export_issues.py`. Bridges:
  `../../engines/datasheets`, `../../engines/emc`.
- **Documentation engine** — `../../engines/kidoc/` (`ENGINE.md`): HDD / power-analysis /
  schematic-review / ICD packages, rendered SVGs, styled PDF.
- **`datasheets` skill** — IC pin/electrical/topology extraction; consumed by the analyzer for
  datasheet-backed findings.
- **`bom` skill** (+ `digikey` / `mouser` / `lcsc` / `element14`) — hand off the BOM for
  enrichment, pricing, stock, lifecycle, and fab BOM/CPL. Don't reimplement sourcing in C03.
- **`spice` / `emc`** — analog front-end and EMC pre-compliance *plans* here; *verdicts* in C06.
- **`drawmiat` / `kidoc`** — power-frontend, block, and bus diagrams.
- **`docx` / `xlsx` / `pdf` / `pptx` + `docxmcp` MCP** — for the BOM/netlist/pinmap spreadsheets
  and the design-definition document artifacts.
