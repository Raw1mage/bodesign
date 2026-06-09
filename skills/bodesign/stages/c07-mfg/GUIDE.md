# C07 MFG — Manufacturing Transfer (fab/assembly handoff readiness)

## Purpose & scope

C07 produces the **manufacturing-transfer package**: the record a fab house and an assembly
house need to build the board, plus the cost/quantity/certification targets that gate whether a
build is worth ordering. For a real fabricated board it is the *handoff inventory*; for a
derived/in-progress product it is a **readiness record** — a structured statement of what fab
outputs *will* exist and what gate currently blocks them.

The central honesty fact for this stage (read `../../references/honesty-model.md` first):
**a manufacturing-transfer record is not a record of a built board.** aiguard-style derived
products are **pre-fabrication** — C04 is still a layout *draft*, so there are no released
Gerber/drill/IPC binaries, every fab deliverable is `pending` against the C04-freeze gate, and
**no build is claimed**. A *design* BOM (from C03) only becomes a *manufacturing* BOM/CPL after
C04 places parts and exports fab outputs.

This stage **owns**:
- the fab-output inventory (Gerber, NC drill+route, IPC-D-356 netlist, stackup, panelization,
  pick-and-place/CPL+centroid, assembly BOM, aperture/fab parameters) — tracked by status;
- cost & quantity targets (read from C00 PRD, not invented here);
- certification targets (external-lab gates — recorded, never marked passed);
- the DFM / handoff checklist that gates release to the fab house.

This stage does **not** own: routing or DRC (that is C04 — C07 only *consumes* its frozen
outputs); the design BOM authoring (C03); verification verdicts (C06); the fabrication itself or
any certification verdict (external houses/labs). C07 never relaxes a C04 gate to make outputs
"exist" — if C04 is not frozen, the outputs stay `pending`.

## Required deliverables — Definition of Done

Produce **all** of these before you report C07 done or hand off (see SKILL.md § "Definition of
Done"). Each exists **or** carries an explicit `pending`/`available` status against its owning gate
with a reason — every fab deliverable stays `pending` until C04 is frozen, which is honest, not
missing.

| # | Required artifact | File | Bucket |
|---|---|---|---|
| 1 | Manufacturing-transfer record | `Manufacturing_Transfer.md` | `03_output/` |
| 2 | Fab-output package (when C04 frozen) | `gerber/` (Gerber · drill · IPC · route · params), panelization, stackup | `03_output/` |
| 3 | Manufacturing BOM / CPL | `mfg_bom.csv` + CPL | `03_output/` (only after C04 fab export) |
| 4 | Cost / qty / cert targets + DFM checklist | within `Manufacturing_Transfer.md`, cited to C00 | `03_output/` |

**Self-verify:** confirm the C04 freeze via `fab_release_gate.py` (there is no `c07_readiness` tool)
and `bodesign_package_readiness` for the roll-up; every fab item must list its owning gate + honest
status. PRD cost/qty/cert targets are **consumed from C00**, never restated as achieved. Model:
`thesmart_products/rockbox/c07-mfg/`.

## Inputs (from upstream)

| From | Artifact | What C07 relies on |
|---|---|---|
| **C04 Layout** | frozen `.kicad_pcb` + `generated/routed/<board>/{gerbers,drill,assembly}/`, per-layer copper PNGs, fab-view PNG, length-match/SI reports | **The gate that unblocks everything.** Fab outputs are real only once C04 passes its own gate (`bodesign_layout_drc_gate` + `c04_readiness`). Until then, every fab deliverable is `pending`. |
| **C03 EE** | design BOM (`*_完整BOM.xlsx` / `*-bom.csv`), netlist | The *design* BOM — becomes a *manufacturing* BOM/CPL only after C04 placement+export. |
| **C00 PRD** | cost target, quantity ramp, certification list (PRD §2–§3) | Cost/qty/cert **targets are read from C00**, never authored fresh here. |
| **C06 Verify** | verification evidence (cross-check coverage, bring-up/EVT findings) | Establishes the electrical baseline's trust posture; EVT findings feed re-spin ECOs. |

Determine your mode before doing anything else:
- **(a) Derived / in-progress** (aiguard): C04 is a draft → produce a **readiness record**,
  everything `pending`. This is the default for any derived product.
- **(b) Archive of a real fabricated board** (rockbox): real fab outputs exist → **preserve them
  verbatim** under `source/` and write an inventory that indexes/explains them. Never mutate
  originals. Proprietary binaries stay in the gitignored vault (`refs/`); rendered, shareable
  copper previews live under the C04 stage.

## SOP

### 1 — Confirm the C04 freeze status (the gate that owns fab outputs)

Run the layout gate against the C04 outputs. If C04 is a draft, this is *expected* to be
incomplete — that is the honest signal that fab outputs are `pending`, not a failure to fix here.

```bash
python3 ../../engines/kicad/scripts/fab_release_gate.py \
  --schematic <C03/analysis>/schematic.json \
  --pcb       <C04/analysis>/pcb.json \
  --gerbers   <C04/analysis>/gerbers.json \
  --text
```

Read the overall verdict honestly:
- `PASS — Ready for fabrication` → C04 is genuinely frozen; fab outputs are real → you may move
  deliverables from `pending` to `available`.
- `WARN` / `FAIL` / `INCOMPLETE` → C04 is not release-ready. Record the gate verdict and keep the
  fab inventory `pending`. Do **not** relax `--strict` or hand-edit the JSON to force a pass.

If there is no `.kicad_pcb` at all (pure draft), there is nothing to gate — record the inventory
as `pending — no .kicad_pcb released` and proceed to build the readiness record.

### 2 — Generate the manufacturing-transfer scaffold (doc engine)

Use the documentation engine's `manufacturing` report type. It auto-runs the available analyses
and emits a structured scaffold with the assembly/fab/test sections pre-filled from real data:

```bash
python3 ../../engines/kidoc/scripts/kidoc_scaffold.py \
  --project-dir <C04 board dir> \
  --type manufacturing \
  --analyze \
  --output Manufacturing_Transfer.md
```

`--analyze` is required on a first run (it runs the analyzers that feed the scaffold). If C04 has
no board file, skip the engine and hand-author the readiness record from the template in
`assets/manufacturing_transfer_template.md` — the engine has nothing to analyze on a pure draft,
and a hand-authored `pending` record is the correct, honest output.

Render a shareable PDF only once the record is real (not while everything is `pending`, unless a
reviewer specifically wants the readiness snapshot):

```bash
python3 ../../engines/kidoc/scripts/kidoc_generate.py \
  --project-dir <C04 board dir> --doc Manufacturing_Transfer.md --format pdf
```

### 3 — Build the fab-output inventory (status-tracked)

List every fab deliverable with the **gate/owner that produces it** and its honest status. Model
the table on the aiguard example (`openmv/C07-MFG/03_output/Manufacturing_Transfer.md`). In derived mode,
status is `pending — <reason>` for each output not yet exported by a frozen C04:

| Deliverable | Owner / Gate | Typical status (derived) |
|---|---|---|
| Gerber (copper, mask, paste, silk) | C04 layout | `pending — no .kicad_pcb released` |
| NC drill + route | C04 layout | `pending` |
| IPC-D-356 netlist (bare-board ET) | C04 layout | `pending` |
| Stackup definition | C04 layout / fab | `pending — layer count TBC` |
| Panelization (連板) drawing | C04 layout / assembly house | `pending` |
| Pick-and-place (CPL) + centroid | C04 layout | `pending` |
| Assembly BOM (placement) | C03 EE | `available` (design BOM); CPL pairing `pending` |
| Fabrication / aperture parameters | C04 layout / fab | `pending` |

In **archive mode**, replace the status column with the real filename and purpose (see the
rockbox example: `L1_top.art … L6_bot.art`, `*.drl`/`*.rou`, `*.ipc`, `panel_router.art`,
`連板.pdf`, `art_param.txt`) and keep the binaries under `source/` (or in the gitignored vault).

### 4 — Pair the manufacturing BOM + CPL (only after C04 export)

The C03 design BOM becomes a *manufacturing* BOM/CPL only once C04 has placed parts. When that
export exists, use the `bom` companion to produce the manufacturing BOM and reconcile it; the
fab-specific format (basic vs extended parts, CPL/centroid) comes from the `jlcpcb` / `pcbway`
companions.

```bash
# Manufacturing BOM from the placed design (companion: bom)
python3 ../../../bom/scripts/bom_manager.py export --schematic <board>.kicad_sch -o mfg_bom.csv
```

Until that export exists, record the manufacturing BOM/CPL as `pending` and keep the **design**
BOM clearly labelled as design-only. Do not synthesize a CPL from a schematic — placement
coordinates come from the board, which does not yet exist in draft mode.

### 5 — Read cost, quantity & certification targets from C00

These are **targets**, copied from the PRD — never authored or estimated fresh in C07:

- **Cost**: PCBA BOM cost target and finished-good target (e.g. aiguard: PCBA BOM ≤ USD 38,
  finished good ≤ USD 55, excl. tooling) — from C00 PRD §2–§3.
- **Quantity ramp**: EVT → 試產 → DVT / pre-MP build counts (e.g. aiguard: EVT 50 套 → 試產 500
  台 → DVT). Enclosure tooling note (soft tooling for EVT/DVT).
- **Certification targets** (external-lab gates): FCC Part 15, CE RED 2014/53/EU, EN 55032 /
  CISPR 32, IEC 62368-1, RoHS / REACH, ESD levels. **Record the target and the plan; never mark
  any of these passed** — they are decided by an external lab on a physical build.

### 6 — Write the DFM / handoff checklist

A checklist of unchecked boxes that gates release to the fab house. Every box stays unchecked in
derived mode because each depends on C04 freeze. Model on the aiguard checklist:

- [ ] C04 layout frozen; outline + stackup confirmed by ME + fab.
- [ ] Gerber / drill / IPC / panel released and DFM-reviewed by the fab house.
- [ ] CPL generated and reconciled with the C03 BOM.
- [ ] Manufacturing BOM costed against the C00 PCBA target; sourcing confirmed.
- [ ] Stencil / paste design for the EVT build quantity.
- [ ] Enclosure soft-tooling drawings (C02 STEP draft → ME production release).
- [ ] First-article inspection + C06 bring-up plan handed to the EVT line.
- [ ] Certification samples reserved for the external FCC / CE lab.

### 7 — Write the status conclusion

State plainly what this record is and what the next gate is. For derived products: "This is a
pre-fabrication manufacturing-**readiness** record. It reuses the verified [baseline] (control
group, C06 cross-check) and adds the product-specific deltas; it is **not** a record of a
fabricated board. The next gate is **C04 layout freeze**, which unblocks the fab-output
inventory." For archives: state it is the preserved transfer record of a board that was built
(control group), and that next-revision ECOs from EVT must merge into a re-spin before MP.

## Deliverables

Source-of-truth markdown, modelled on the real repo examples:

| Artifact | Path | Source-of-truth / generated | Notes |
|---|---|---|---|
| `Manufacturing_Transfer.md` | stage root | **source-of-truth** (markdown) | The readiness record / transfer inventory. Hand-authored or doc-engine scaffolded. |
| `Manufacturing_Transfer.pdf` | stage root | generated (kidoc) | Optional; render once the record is real. |
| `mfg_bom.csv` / CPL | stage root | generated (`bom` + fab companion) | **Only after C04 export.** `pending` otherwise. |
| `source/` (archive mode only) | stage root | preserved verbatim | Real Gerber/drill/IPC/stackup/panel binaries of a fabricated board; never mutated. |

The `Manufacturing_Transfer.md` is the load-bearing deliverable. Keep its structure: provenance &
status block → fab-output inventory (status-tracked) → cost & quantity targets (from C00) →
certification targets (external gate) → DFM/handoff checklist → status conclusion. A copyable
skeleton is in `assets/manufacturing_transfer_template.md`.

## Gate / done-criteria

**Derived / in-progress mode** — C07 is *complete as a readiness record* when:
- every fab deliverable is listed with its owning gate and an honest `pending`/`available` status
  (with a reason);
- cost/quantity/certification targets are present and cited to C00;
- the DFM checklist exists with every C04-dependent box honestly unchecked;
- the status conclusion names the C04-freeze gate as the next unblocker.

It is **not** complete as a *transferable fab package* until C04 is frozen, the fab outputs are
genuinely released (gate `PASS`), the manufacturing BOM is costed and sourced, and a fab house has
DFM-reviewed the package. That transition is gated on C04, not achievable within C07.

**Archive mode** — complete when every real fab output is preserved verbatim under `source/` (or
the vault) and the inventory faithfully indexes them, with no mutation of originals.

Certification is **never** part of the done-criteria as "passed" — it is an external-lab gate.

## Honesty notes for this stage

Stage-specific application of `../../references/honesty-model.md`:

- **Pre-fabrication means pending, not done.** No build is claimed for a derived product. "Build
  performed: none yet" is the honest line; fab outputs are `pending` against C04 freeze (rule 1, 3).
- **Targets vs results.** Cost/quantity/certification entries are *targets read from C00*, not
  achieved results. Label them as targets; never write a cost as if it were a quoted/sourced
  number until the manufacturing BOM is actually costed (rule 1, 5).
- **External gates stay external.** FCC, CE RED, CISPR/EN 55032, IEC 62368-1, RoHS/REACH, ESD are
  recorded as targets with a plan and **never marked passed** here — they belong to an external
  lab on a physical build (rule 4).
- **Design BOM ≠ manufacturing BOM.** The C03 BOM is `available` as a *design* BOM; it does not
  become a manufacturing BOM/CPL until C04 places parts and exports. Do not relabel it (rule 1).
- **Don't relax the C04 gate.** If `fab_release_gate.py` reports WARN/FAIL/INCOMPLETE, report it
  and keep outputs pending — do not use `--strict` inversely, hand-edit JSON, or claim release
  (C04 gate contract; rule 6).
- **Show the baseline's reliability, don't assert it.** Reference the C06 cross-check (e.g.
  "269/269 nets matched a known-good reference, control group") rather than calling the design
  "production-ready" (rule 5).
- **Preserve archives verbatim.** In archive mode, copy real fab outputs into `source/` unmodified
  and keep proprietary binaries in the gitignored vault — never commit `refs/` content (rule 7).

## Handoff to external fab house + certification labs

C07 is the last bodesign stage; its handoff is **out of the lifecycle**:

- **To the fab/assembly house**: the released Gerber/drill/IPC/stackup/panel + CPL + manufacturing
  BOM + assembly drawing — only once C04 is frozen and the DFM checklist clears. Companions
  `jlcpcb` / `pcbway` carry the house-specific format and DFM rules.
- **To external certification labs**: certification *samples* and the target/plan. The lab returns
  the verdict; bodesign records the plan, never the pass.
- **EVT feedback loop**: bring-up/EVT findings (C06, `../c06-verify/GUIDE.md`) become re-spin ECOs
  that must merge back into C04 (`../c04-layout/GUIDE.md`) before MP — C07 does not absorb them.

## Tools & companion skills

| Tool / skill | When to use |
|---|---|
| `../../engines/kidoc/scripts/kidoc_scaffold.py --type manufacturing --analyze` | Generate the manufacturing-transfer scaffold from a frozen C04 board; then `kidoc_generate.py` for PDF. |
| `../../engines/kicad/scripts/fab_release_gate.py` | Gate whether the C04 fab outputs are genuinely release-ready (routing, BOM, DFM, gerbers, consistency). The honest source of `pending` vs `available`. |
| `bom` (+ `digikey`/`mouser`/`lcsc`/`element14`) | Produce + cost the manufacturing BOM once C04 has placed parts; reconcile against the C00 cost target. |
| `jlcpcb` / `pcbway` | Fab/assembly handoff format: basic vs extended parts, CPL/centroid, house DFM rules, ordering workflow. |
| `docx` / `pptx` / `pdf` / `xlsx` + `docxmcp` MCP | Package the transfer record into shareable document artifacts when a reviewer needs them. |
