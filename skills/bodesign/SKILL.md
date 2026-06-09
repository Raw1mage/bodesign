---
name: bodesign
description: >-
  End-to-end hardware product-design lifecycle skill (bodesign C00–C07: PRD → ID →
  ME → EE → Layout → FW → Verify → MFG). Owns the workflow that turns a product idea
  or a reference board into a documented, honestly-gated design package, and carries
  two execution engines underneath: a KiCad analysis engine (schematics, PCB, Gerbers,
  netlists, DRC/ERC, net tracing, BOM extraction, power tree, DFM, cross-check, fab-release
  gate — every finding carries a confidence label + evidence source) and a documentation
  engine (HDD, CE technical file, ICD, design-review and manufacturing-transfer packages,
  rendered schematic/PCB SVGs, block/power-tree/bus diagrams, styled PDF). Use this skill
  whenever the work touches a hardware design at ANY stage — writing or reviewing a PRD,
  industrial/CMF/UX direction, enclosure/mechanical constraints, schematic or PCB design,
  layout/routing/stackup/impedance, firmware spec, verification/bring-up/test plans, or
  manufacturing transfer — AND for every legacy kicad/kidoc trigger: .kicad_sch / .kicad_pcb
  / .kicad_pro, "review my board", "check my schematic", "trace this net", "is this ready
  to fab", "DRC/ERC", "BOM extraction", "power budget", PDF schematics, reference designs,
  Gerbers, "generate documentation", "HDD", "CE technical file", "ICD", "design review
  package", "manufacturing package", "render schematic/layout", "generate block diagram",
  or "generate PDF". This skill replaces the standalone kicad and kidoc skills — route ALL
  of their work through here. Strongly prefer this skill over answering hardware-design or
  documentation questions from memory.
---

# bodesign — C00–C07 hardware product-design lifecycle

This skill teaches the **bodesign C00–C07 lifecycle** and carries the execution engines that
do the heavy lifting. The whole point is that bodesign (the tooling) is *just an executor* —
**doing good work requires knowing the workflow**: what each stage consumes and produces, which
gate it must pass, and the honesty rules that forbid faking any of it. That knowledge lives here.

## How to use this skill (read this first)

**Do not read all eight stage guides up front.** This file is the spine: the lifecycle map, the
honesty contract, and a router. Identify the stage the current task is in, then open **only that
stage's guide** (`stages/cXX-*/GUIDE.md`). Each guide is self-contained. Pull in a neighbouring
stage's guide only when you are actually crossing a handoff.

1. **Read the honesty model** — `references/honesty-model.md`. It is non-negotiable and applies
   to every stage. If you internalise nothing else, internalise this.
2. **Locate the stage** using the router below.
3. **Open that stage's `GUIDE.md`** and follow its SOP.
4. **Respect the handoff** — produce the artifacts the next stage needs, in the agreed format.

The guides cite **worked examples** by path (`thesmart_products/…`, `openmv/…`). Those are the
maintainer's private reference boards, resolved locally by two gitignored root symlinks and **not
bundled** with a distributed skill — see `references/worked-examples.md`. Treat every such citation
as **illustrative**: a concrete model to imitate when present, never a dependency the workflow needs.

## The lifecycle

| Stage | Name | Owns | Guide |
|---|---|---|---|
| **C00** | PRD | Product requirements: vision, system architecture, constraints, targets, roles, timeline | `stages/c00-prd/GUIDE.md` |
| **C01** | ID | Industrial design: design direction, CMF, display UI/UX, interface constraints | `stages/c01-id/GUIDE.md` |
| **C02** | ME | Mechanical: enclosure constraints/assumptions, OpenSCAD + STEP draft, assembly/print/vendor handoff | `stages/c02-me/GUIDE.md` |
| **C03** | EE | Electrical: design definition, schematic, BOM, netlist, GPIO/interface pinmap, power frontend | `stages/c03-ee/GUIDE.md` |
| **C04** | Layout | PCB: placement/routing/stackup/impedance constraints, routed board, gated fab outputs | `stages/c04-layout/GUIDE.md` |
| **C05** | FW | Firmware **spec** (not code): functional spec, module architecture, state machine, task breakdown, pin-map bridge | `stages/c05-fw/GUIDE.md` |
| **C06** | Verify | Verification summary, test plan, bring-up checklist, reference cross-check | `stages/c06-verify/GUIDE.md` |
| **C07** | MFG | Manufacturing-transfer readiness: fab-output inventory, cost/qty/cert targets, DFM handoff | `stages/c07-mfg/GUIDE.md` |

The chain is **directional but iterative**: later stages feed constraints back (C03 exports a
mechanical-constraint JSON for C02/C04; C04 freeze unblocks C07). Each stage's guide names exactly
what it receives from upstream and what it must hand downstream.

## Definition of Done — produce the deliverables, don't wait to be asked

Every stage has a fixed set of **required deliverables** (its "Required deliverables — Definition of
Done" block, at the top of that stage's guide). This is a contract, not a menu. When you enter a
stage, **commit to producing its entire required set in that one pass** — author/generate every
required file, then report. The default failure mode this rule exists to kill: doing one or two
artifacts, narrating what *could* be produced, and stopping until the user asks again. Don't. If the
user named the stage (or the work is clearly in it), produce the whole set.

Required deliverables are filed under the canonical stage layout — every deliverable (the spec/handoff
`.md` docs, the `.json` bridges, the engineering files, a viewable PNG) goes in **`03_output/`**;
`01_refs/` holds external inputs; `02_build/` holds garbage-collectable intermediates; the stage
**root holds only `README.md`/`CHANGELOG.md`** (an execution record, not a deliverable). See
`references/stage-structure.md`. `03_output/` *is* the Definition of Done; the readiness tools score
it. Each shared artifact (mechanical constraints, pin map, PRD targets) has one owning stage and is
consumed by reference downstream, never re-copied.

A stage is **NOT done** — and you must not say it is done, advance to the next stage, or hand off —
until **every required deliverable either exists on disk or carries an explicit `blocked`/`not-run`
status with a reason and an owner.** Silent absence is forbidden; an honest blocked artifact is
allowed (this is how the honesty model and the Definition of Done coexist — see
`references/honesty-model.md`). "I can produce X if you'd like" is the anti-pattern: produce X, or
mark it blocked and say why.

**…and not done while you own an open cross-stage reconciliation.** A stage is also NOT done while
`list_blockers(folder, unresolved_only=True)` returns a record naming this stage in
`affected_downstream_layers` (`references/cross-stage-reconciliation.md`). This is the recursive loop: a
downstream area/thermal/height overflow or a C06 verdict-fail routes *back* here as a `BlockerReturn`;
you re-enter, **fix the design** (never relax the threshold — the C04 floating-PSRAM lesson), then
`ingest_blocker` to resolve it, or escalate to the next lever's stage. You — the agent running
bodesign — are the orchestrator that runs this scan each time you would advance or report done. The
`bodesign_package_readiness` roll-up also surfaces these open blockers so the gate is machine-checked,
not memory-dependent.

**Self-verify before you report.** Run the stage's readiness check and state its result (which
required items are present / partial / missing) in your completion report:
- C00 / C01 / C02 / C05 / C06 → `bodesign_c00_readiness` … `bodesign_c06_readiness` (`folder`).
- C04 → the gate: `bodesign_layout_drc_gate` (`board_path`) + `bodesign_c04_readiness` (`folder`).
- C03 → the schematic analyzer's gate (`analyze_schematic.py`: no open `high` findings) — there is no
  `c03_readiness` tool.
- C07 → the C04 fab-release gate (`fab_release_gate.py`) — there is no `c07_readiness` tool.
- Any milestone → `bodesign_package_readiness` (`folder`) for the cross-stage roll-up.

If the check says a required item is missing and you have not marked it honestly blocked, you are not
done — go produce it. Only after it passes do you announce completion or cross the handoff.

## Router — "which stage am I in?"

| If the task is about… | Go to |
|---|---|
| requirements, vision, scope, targets, "what are we building / why" | **C00** |
| look & feel, CMF, colours/materials/finish, screen UX, bezel/button layout | **C01** |
| enclosure, fit, tolerances, STEP/SCAD, assembly, injection moulding, vendor | **C02** |
| schematic, nets, BOM, power tree, GPIO/pin assignment, regulator/charger, ERC | **C03** |
| placement, routing, stackup, impedance, length-match, Gerbers, drill, DRC, fab outputs | **C04** |
| firmware behaviour spec, drivers↔pins, state machine, task list (the *spec*, not the code) | **C05** |
| does it work, test plan, bring-up, cross-check vs a known-good reference, SPICE/EMC/thermal | **C06** |
| sending to fab, CPL/IPC, panelization, cost target, certification gates, DFM review | **C07** |
| "review/debug/understand an existing board or schematic" (no stage named) | **C03** (sch) and/or **C04** (PCB) |
| "generate a report / HDD / CE file / ICD / manufacturing package / PDF" | the stage that owns the content, then its guide points at the **doc engine** |

## Engines (under `engines/`, invoked by stage guides — not read top-down)

These are the migrated, fully-functional `kicad` and `kidoc` engines. **Do not invoke them
blindly** — the stage guide tells you when and how. They are documented by their own `ENGINE.md`.

| Engine | Path | Driver doc | Used by |
|---|---|---|---|
| **KiCad analysis** | `engines/kicad/scripts/` | `engines/kicad/ENGINE.md` | C03, C04, C06 |
| **Documentation** | `engines/kidoc/scripts/` | `engines/kidoc/ENGINE.md` | C03, C04, C06, C07 (any stage emitting a formal doc/PDF) |

Entry points you will use most (full detail in each `ENGINE.md`):
- Analyse a schematic: `python3 engines/kicad/scripts/analyze_schematic.py --project-root <dir> [--lifecycle]`
- Analyse a PCB: `python3 engines/kicad/scripts/analyze_pcb.py <board.kicad_pcb>`
- Cross-check against a reference (control group): `python3 engines/kicad/scripts/cross_verify.py …`
- Fab-release gate: `python3 engines/kicad/scripts/fab_release_gate.py …`
- Lifecycle audit (which C-stages are actually complete): `python3 engines/kicad/scripts/lifecycle_audit.py …`
- Generate a doc scaffold + analyses: `python3 engines/kidoc/scripts/kidoc_scaffold.py --project-dir <dir> --type <hdd|ce_technical_file|icd|design_review|manufacturing|…> --analyze --output <md>`
- Render the styled PDF: `python3 engines/kidoc/scripts/kidoc_generate.py …`

The engines also bridge to sibling skills (`datasheets`, `emc`) via `engines/datasheets` and
`engines/emc` symlinks — keep those intact.

## Relationship to the bodesign MCP server (the generation half)

This skill is the **workflow brain + analysis/doc engines**. The optional **bodesign MCP
server** (a separate Docker/stdio service, repo `bodesign/`) is the **generation half**: it
turns the SOPs below into *executable* tools that emit KiCad artifacts. The split is
deliberate and bidirectional:

- **skill → MCP** for **generation**: when the MCP is reachable (you will see tools prefixed
  `bodesign_`), use it to *create* artifacts instead of hand-authoring them.
- **MCP → skill** for **analysis**: the MCP's `bodesign_simulate` / `bodesign_analyze_emc` /
  `bodesign_analyze_thermal` *call these very engines* (`engines/kicad`, via `BODESIGN_KICAD_SKILL`
  → it resolves `~/.claude/skills/bodesign/engines/kicad`). So the analyzer logic lives here, once.

**Generation is not validation.** Whatever the MCP emits is still `draft`/`pending` until you run
the local analyzers (`analyze_schematic.py` / `analyze_pcb.py`) and the gates over it, exactly as
the stage guides require. The MCP refuses send-to-fab output without deterministic validation + an
explicit approval — mirror that here.

**Stage → MCP tool family** (use when the MCP is present; otherwise fall back to the manual/KiCad
path each guide documents):

| Stage | MCP generation tools (prefix `bodesign_`) |
|---|---|
| C00 | `c00_scaffold_prd` · `c00_emit_prd` · `c00_readiness` · `plan_design_intent` · `evidence_manifest` |
| C01 | `c01_emit_package` · `c01_emit_concept_prompts` · `c01_generate_concept_image` · `c01_readiness` |
| C02 | `c02_emit_enclosure_package` · `c02_generate_openscad` · `c02_export_{stl,step,skp}` · `c02_readiness` |
| C03 | `emit_symbol` · `compose_schematic` · `pin_allocation` · `export_bom` · `export_netlist` · `c03_export_mechanical_constraints` |
| C04 | `c04_emit_layout_package` (one-shot) **or** `impedance_solve` · `route_net2pcb`/`autoroute` · `pour_planes` · `widen_bus_tracks` · `length_match_bus` · `via_in_pad` · `si_check` · `layout_drc_gate` · `emit_fab` · `c04_readiness` |
| C05 | `c05_scaffold_fw_spec` · `c05_readiness` |
| C06 | `c06_assemble_test_plan` · `reference_crosscheck` · `simulate` · `analyze_emc` · `analyze_thermal` · `c06_readiness` |
| C07 | `package_readiness` · `render_companion` · `emit_doc` |
| files/orchestration | `stage_dir` · `ingest_project` · `datasheet_lookup`/`register`/`spec_check` · `dispatch_work_packet` · `mcp_call` |

**Do not hardcode tool schemas from this table** — it is a router, not a contract. The server is
self-describing: open `/tools` and `/tools/{name}` (or the `/` landing page) on the running
service for the authoritative, current argument schemas. This keeps the skill light and prevents
it drifting out of sync as the MCP's tool surface evolves.

## Companion skills (hand off, don't reimplement)

`bom` (BOM enrichment/pricing/order/export) · `digikey`/`mouser`/`lcsc`/`element14` (part search +
datasheets) · `jlcpcb`/`pcbway` (fab/assembly ordering, DFM rules) · `spice` (analog sim) ·
`emc` (EMI pre-compliance) · `drawmiat` (IDEF0/Grafcet/C4 diagrams for C00/C01/C05) ·
`docx`/`pptx`/`pdf`/`xlsx` + the `docxmcp` MCP (document artifacts). Stage guides call these out
where they fit; never hand-roll what a companion skill already does well.

## The one rule that overrides convenience

Everything here serves a single discipline: **a bodesign package is trustworthy because it never
claims more than it can show.** Mark unproven things `draft`/`pending`/`not-run` and say why.
External gates (EVT/DVT, FCC/CE, EMC lab, safety) are *never* marked passed. See
`references/honesty-model.md` before you write a single deliverable.
