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
1a. **Know the container boundary** — `references/container-boundary.md`. bodesign MCP runs in
   Docker and only sees `.run`/sessions/vault; a host path outside those mounts is invisible.
   Readiness tools report `root_visible: false` for it — never read a `readiness_pct: 0` as
   "deliverables missing" without checking `root_visible` first. Unmounted trees go through the
   file model (tar → token → doc_dir).
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

Required deliverables are filed under the canonical stage layout — split by **AUDIENCE** (owner rule,
2026-07-17): **human-facing deliverables flat at the stage root** — document deliverables as `.docx` in
繁體中文 (their editable `.md` source — any working language — is an intermediate in `02_build/`;
translate to Traditional Chinese when assembling the `.docx`), the engineering files a human opens, and
a viewable PNG; **AI/machine-facing deliverables in `03_output/`** — generated `.md` reports and `.json`
bridges that downstream tools/agents consume (humans don't read raw md/json); `01_refs/` holds external
inputs; `02_build/` holds garbage-collectable intermediates (incl. the `.md` document sources); the
stage root otherwise holds only `README.md`/`CHANGELOG.md` (meta, not deliverables, not translated). No
ad-hoc subfolders. See `references/stage-structure.md`. The **deliverables in their sanctioned
locations** *are* the Definition of Done; the readiness tools score it. Each shared artifact (mechanical
constraints, pin map, PRD targets) has one owning stage and is consumed by reference downstream (its
bridge lives in the owner's `03_output/`), never re-copied.

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
`package_readiness` roll-up (landing verb, via `gate.py`) also surfaces these open blockers so the gate is machine-checked,
not memory-dependent.

**Self-verify before you report.** Run the stage's readiness check and state its result (which
required items are present / partial / missing) in your completion report. **Readiness checks are
landing verbs, NOT MCP tools** (§ "Landing / compute routing contract") — run them locally:

```bash
python3 <skill>/scripts/gate.py <verb> --repo <abs-project> [--arg folder=<stage-dir>]
```

- C00 / C01 / C02 / C05 / C06 → landing verbs `c00_readiness` … `c06_readiness` (`folder` defaults
  to `--repo`; a relative `folder` resolves against it).
- C04 → the gate: the MCP tool `bodesign_layout_drc_gate` (`board_path`) + the landing verb
  `c04_readiness` (`folder`).
- C03 → the schematic analyzer's gate (`analyze_schematic.py`: no open `high` findings) plus the
  PRD-fulfilment gate: the MCP tool `bodesign_prd_bom_crosscheck` (`manifest_path` + netlist) must
  report `gate: PASS` before C04 entry (`stages/c03-ee/GUIDE.md` § 3b) — there is no
  `c03_readiness` verb.
- C07 → the C04 fab-release gate (`fab_release_gate.py`) — there is no `c07_readiness` verb.
- Any milestone → landing verb `package_readiness` (`folder`) for the cross-stage roll-up.

> **Legacy-name correction table.** Older docs / model memory may still advertise these as
> `bodesign_<verb>` MCP tools; they were landed in R13 and calling them as tools fails
> (`TOOL_LANDED` / unknown-tool). Self-correct as follows — `bodesign_c00_readiness` → `gate.py
> c00_readiness` · `bodesign_c01_readiness` → `gate.py c01_readiness` · `bodesign_c02_readiness` →
> `gate.py c02_readiness` · `bodesign_c04_readiness` → `gate.py c04_readiness` ·
> `bodesign_c05_readiness` → `gate.py c05_readiness` · `bodesign_c06_readiness` → `gate.py
> c06_readiness` · `bodesign_package_readiness` → `gate.py package_readiness` · and likewise every
> scaffold / emit / orchestration verb listed by `gate.py --list` (e.g. `bodesign_c00_scaffold_prd`,
> `bodesign_c00_update_answers`, `bodesign_pin_allocation`, `bodesign_impedance_solve`,
> `bodesign_c03_emit_host_block_diagram`).

If the check says a required item is missing and you have not marked it honestly blocked, you are not
done — go produce it. Only after it passes do you announce completion or cross the handoff.

> **`readiness_pct: 100` is NOT "done". Read `dod_ok` + `guide_compliance`.** The readiness
> tools now enforce each stage's GUIDE.md "Required deliverables — Definition of Done" as a
> machine-checkable manifest. The real done-gate is **`dod_ok: true`** — it is true only when every
> GUIDE Required-deliverable is `present` (or honestly deferred via a `dod_status.json` entry) AND no
> `answered` field is *fake-complete* (state `answered` but value is a placeholder like `TBC`/`待補`).
> A required deliverable that is silently absent, a flipped `include_rf=false` while a radio part is in
> the BOM, or a `TBC` hiding under `answered` each flip `dod_ok` to **false** and are named in
> `guide_compliance` with their GUIDE row. So: **self-verify against the guide's DoD manifest** (the
> `guide_compliance` block), not the bare `readiness_pct`. A high percentage with `dod_ok: false` means
> the deliverables do not yet meet the GUIDE — fix what `guide_compliance.missing_blocking` / the
> `fake_complete_fields` list names, or record an honest status; never report done on a fake green.

### Handing over a *document*? Read the content criteria.

The Definition of Done above is an **existence + placeholder** check (`dod_ok` / `guide_compliance`
below). It cannot tell a generated document that says something from one that says nothing. Before a
**document deliverable** leaves the building — HDD · CE technical file · ICD · design-review package ·
manufacturing-transfer package (PRD too) — apply
**`references/deliverable-content-criteria.md`**: per-document content rows in auditable form, the
inference-leap patterns that turn a sound source into an unsound claim, and the index of human DECIDE
nodes an AI may never mark satisfied. It borrows the review machinery (forced-find, finding schema,
severity, verdict) from `stages/c04-layout/references/layout-review-method.md` — that file reviews *a
board*, this one reviews *a finished document*.

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

## Concept-diagram router — "which diagram do I emit?"

When the task is to *draw a concept/structure diagram* (not analyse a real board), route by what the
diagram depicts. Each is a distinct deterministic emitter — do not hand-author the SVG:

| If the diagram depicts… | Emit via | Notes |
|---|---|---|
| **board-level partition / fan-out** (core↔carrier split, board-to-board pin classes, breakout) | `c03_emit_partition_diagram` (landing verb, via `gate.py`) | MODEL = {boards, interconnect}; layered SVG (boards/modules/interconnect/legend/annotations); honest-boundary footer always on (design partition, **not** fab pinout). |
| **host / MCU-centric functional block diagram** (center SoC/MCU + peripherals radiating to the four sides; buses on the connecting lines) | `c03_emit_host_block_diagram` (landing verb, via `gate.py`) | MODEL = {center_part, peripherals[{name, side, bus?, type?}], reference_baseline?}; layered SVG (center/peripherals/buses/legend/annotations); unknown type → named placeholder (never dropped); optional `reference_baseline` renders a derived-from / diffs / sourcing-gates block (honesty model for derived products); honest-boundary footer always on (functional block diagram, **not** a netlist). |
| **mechanical look & feel** (ID skeleton, CMF, exposed-component faces) | `c01_emit_id_visual_package` (landing verb, via `gate.py`) | Layered, designer-editable ID skeleton SVG; not final industrial design. |
| **physical placement** (real board outline, where parts land on copper) | `emit_layout` (C04 path) | Constraint-first; placement coordinates/stackup never fabricated. |
| **software containers / processes** (C4, IDEF0, Grafcet) | `drawmiat` companion skill | C00/C01/C05 architecture diagrams. |

All four are *concept/intent* projections, honestly gated — never a fab pinout, DRC, or SI claim.

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
  `bodesign_analyze_thermal` *call these very engines* (`engines/kicad` + `spice`/`emc`, via
  `BODESIGN_KICAD_SKILL` / `BODESIGN_SPICE_SKILL` / `BODESIGN_EMC_SKILL`). So the analyzer logic
  lives here, once. The **container image self-bundles** these engines under `/opt/bodesign-engines`
  and sets those env vars (so C06 runs without a host install); on a non-containerized host they
  resolve to `~/.claude/skills/bodesign/engines/kicad` (+ `~/.claude/skills/{spice,emc}`).

**Generation is not validation.** Whatever the MCP emits is still `draft`/`pending` until you run
the local analyzers (`analyze_schematic.py` / `analyze_pcb.py`) and the gates over it, exactly as
the stage guides require. The MCP refuses send-to-fab output without deterministic validation + an
explicit approval — mirror that here.

## Landing / compute routing contract (MCP server ≥ 0.2.0)

The tool surface is split into two planes. Route by plane, not by habit:

- **Landing plane — run locally via `gate.py`.** The deterministic, repo-local verbs (C00 + C01
  full families, C02 analysis-only, C03 emitters, C04–C06 scaffold/readiness, the orchestration
  spine, read/gate verbs — `ingest_project` / `package_readiness` / `datasheet_lookup` /
  `spec_check` / `rca_spec_audit` — and pure functions — `plan_design_intent` /
  `evidence_manifest` / `pin_allocation` / `reference_crosscheck` / `impedance_solve`) are **no
  longer MCP tools**. `gate.py --list` is the authoritative count and roster; this document
  deliberately does not restate a number, because a hand-copied count is exactly the kind of
  second declaration that drifts (BR_20260730). Run them agent-local against the client project
  folder:

  ```bash
  python3 <skill>/scripts/gate.py --list                 # authoritative verb list + summaries
  python3 <skill>/scripts/gate.py <verb> --repo <abs> [--json '{…}' | --arg k=v]
  ```

  Output is one JSON envelope on stdout (`{ok, verb, result}`; errors carry a typed code —
  `VERB_UNKNOWN` / `VERB_NOT_LANDING` / `LANDING_PYTHON_TOO_OLD` / `LANDING_PACKAGES_NOT_FOUND` —
  and exit≠0). When the skill is projected outside the bodesign checkout (XDG install), set
  `BODESIGN_SRC=<bodesign repo>` explicitly. Heavy names are hard-guarded: a blacklisted verb
  returns `VERB_NOT_LANDING` naming the container tool to use instead.

- **Compute plane — container MCP tools (`/tools` and `/health.tools` are authoritative).** Heavy toolchain
  work stays server-side: the C04 layout/routing family, `emit_symbol` / `compose_schematic` /
  `emit_layout` / `emit_fab`, `simulate` / `analyze_emc` / `analyze_thermal` /
  `spice_model_card`, the render family, C02 exports (STL/STEP/SKP) / render / `voice_to_design` /
  `project_svg`, DXF↔DWG, `export_bom` / `export_netlist`, `emit_doc` / `render_companion`,
  `c00_emit_prd_docx` (docxmcp assemble path), `c01_generate_concept_image`, the `vault_*` family,
  `stage_dir`, `mcp_call`, and the three cache-lifecycle tools.

- **`TOOL_LANDED` interception**: calling a landed name as an MCP tool returns a typed error
  `TOOL_LANDED` carrying the equivalent `landing_command`. Follow the command; do not retry the
  tool.

**Cache 三層心智模型** — where files live and how they move:

| Tier | What it is | How you touch it |
|---|---|---|
| **truth store** | client-owned project tree (durable inputs + deliverables) | landing verbs read/write it directly on the host; the container ingests it read-only |
| **working cache** | per-deliverable WebDAV workspace (`deliverable-cache` kind) on the server | `bodesign_cache_provision` → mount `/dav/{token}` (rclone/davfs2, per-owner Basic credential) or let heavy tools emit into it → `bodesign_cache_export` back to a host target → `bodesign_cache_close` (dirty-gate: un-exported changes 409 unless forced) |
| **vault** | cross-project component knowledge (server SQLite) | `vault_*` tools only |

**Stage → MCP tool family** (use when the MCP is present; otherwise fall back to the manual/KiCad
path each guide documents). **Routing note (≥ 0.2.0):** most lightweight entries below are now
*landing verbs* — same name, run via `gate.py`, and the MCP answers `TOOL_LANDED` if called as a
tool. This table remains a *family* router; `--list` / `/tools` decide which plane a name lives on:

| Stage | Tool family (landing verbs run via `gate.py`; compute tools carry the `bodesign_` prefix) |
|---|---|
| C00 | `c00_scaffold_prd` · `c00_emit_prd` · `c00_readiness` · `plan_design_intent` · `evidence_manifest` |
| C01 | `c01_emit_package` · `c01_emit_concept_prompts` · `c01_generate_concept_image` · `c01_readiness` |
| C02 | `c02_emit_enclosure_package` · `c02_generate_openscad` · `c02_export_{stl,step,skp}` · `c02_readiness` |
| C03 | `emit_symbol` · `compose_schematic` · `pin_allocation` · `export_bom` · `export_netlist` · `c03_export_mechanical_constraints` |
| C04 | `c04_emit_layout_package` (one-shot) **or** `impedance_solve` · `c04_face_placement` · `route_net2pcb`/`autoroute` · `c04_castellation` · `pour_planes` · `widen_bus_tracks` · `length_match_bus` · `via_in_pad` · `si_check` · `layout_drc_gate` · `emit_fab` · `c04_readiness` · `c04_dod_traceback` |
| C05 | `c05_scaffold_fw_spec` · `c05_readiness` |
| C06 | `c06_assemble_test_plan` · `reference_crosscheck` · `simulate` · `analyze_emc` · `analyze_thermal` · `c06_readiness` |
| C07 | `package_readiness` · `render_companion` · `emit_doc` |
| files/orchestration | `stage_dir` · `ingest_project` · `refs_ingest` · `datasheet_lookup`/`register`/`spec_check` · `dispatch_work_packet` · `mcp_call` |

**Refs-derived design verbs** (EPIC capability-inversion 切面 1/2/3/5; landing verbs via `gate.py`) —
these make the refs-first workflow executable end-to-end; the stage guides wire them into their SOPs:

| Verb | 切面 | One-line purpose |
|---|---|---|
| `refs_ingest` | 1 | Scan a stage's `01_refs/` SSOT into a ranked, read-only source manifest (authority order from the baseline file; rich media flagged unadjudicated; absent root → `root_visible:false`, loud — never a clean empty). Run as **step 0 of every stage** — the refs-gated emitters hard-fail `REFS_SSOT_MISSING` without the SSOT. |
| `c04_face_placement` | 2 | Deterministic placement bands binding each connector to its **frozen** C01 face/edge (DD-4: the face is not a C04 degree of freedom). Output feeds `placement_to_coords` → `route_net2pcb(placement=…)`. |
| `c04_castellation` | 3 | Stamp-module castellated edge pads as segfault-free S-expression injection (DD-5: refuses the known-crash pcbnew mutation paths); provenance-gated (天條 2). |
| `c04_dod_traceback` | 5 | Upgrade DoD from surface-existence to SSOT traceability: every delivered item must trace to an SSOT anchor (`untraceable` = 憑空發明) and every SSOT-required ref must be delivered (`unfulfilled` = 漏做). Either non-empty → **blocking**. |

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

## Pre-implementation design review (G2 — scenario walkthrough before validation)

Between "propose subsystem/layout intent" and "deterministic validation" sits a mandatory
`design-review` stage. The review is walkthrough work — you reason through failure scenarios
against the candidate intent, then record a verdict. The workflow gate
(`record_design_review` / `review_gate_status` in workflow-core) only verifies that a review
happened and produced a verdict; the thinking is yours.

**Minimum scenario set** — walk through every applicable item; skipping an applicable one is a
review defect, not a shortcut:

- **power sequencing** — rail bring-up order, enable dependencies, inrush at first plug-in
- **reset chain** — who resets whom, POR timing vs supervisor, strapping pins sampled at reset
- **I2C address conflict** — every bus member's 7-bit address (including address-select straps)
- **level compatibility** — each interface pair's VIH/VIL/VOH/VOL across voltage domains
- **diff-pair topology** — USB/Ethernet/LVDS pair routing intent, polarity, AC coupling needs

Each scenario gets `{name, walkthrough, conclusion, severity}` (severity: critical/major/minor/info).
Verdict is `APPROVE` / `APPROVE_WITH_CONCERNS` / `REJECT`:

- `REJECT` **keeps deterministic-validation blocked** until concerns are resolved and re-reviewed.
- A missing review record blocks validation the same way (`REVIEW_MISSING`) — the gate cannot be
  skipped by simply not doing the review.
- `APPROVE_WITH_CONCERNS` passes the gate but the concerns must appear as scenarios with
  severity ≥ major, so they stay visible downstream.

The record persists to the client project folder (`_design_review/design_review.json`) as
evidence — reviews that live only in chat are not reviews.

## Debug cost-ordering discipline (G6 — cheap hypotheses before structural changes)

When a verification gate fails (DRC / ERC / SI / reference crosscheck mismatch), do **not** jump
to structural proposals (re-layout, layer-count change, subsystem rework). Most failures have
cheap causes. The mandatory order:

1. **Enumerate `simple_fix_candidates` first** — attach them to the blocker
   (`return_blocker(..., simple_fix_candidates=[...])`): each candidate is
   `{hypothesis, check_method, ruled_out, evidence_ref}`. Typical cheap hypotheses:
   - DRC rule parameter wrong (rule file / net-class value, not the copper)
   - a single net or pad exception, not a systemic problem
   - footprint pin definition error (symbol↔footprint mapping)
   - stale generated output (re-run the deterministic tool before trusting the failure)
2. **Rule each candidate out with evidence** — `ruled_out: true` requires an `evidence_ref`
   (tool output, file anchor). The schema rejects evidence-free rule-outs.
3. **Only after all candidates are `ruled_out`** may a structural proposal be made.
   `BlockerReturn.structural_proposal_allowed` is the machine gate: while any candidate has
   `ruled_out: false`, structural re-design suggestions are out of bounds.

This is the same principle as "verify the premise before stacking fixes": a structural change
made while a cheap explanation is still alive destroys evidence and multiplies blast radius.

## Delivery contract — hard rules for generate→render deliverables (learned 2026-07-06)

A single "draw a placement/schematic" request once burned ~3.5 h and 15+ relay
subagents into an engine-R&D marathon that shipped nothing. The post-mortem
(`issues/BR_20260706_*`) distilled five rules. They are not advisory:

1. **Capability-triage gate (do at task start).** List *engine capabilities the
   deliverable needs* vs *what exists today*. If a gap plausibly needs **>2 rounds
   of engine change** to close, STOP delegating in the delivery session — open a
   plan in the bodesign repo and run that gap through the real R&D lifecycle. Ship
   the delivery with existing capability + an honest limitations note (e.g. "CCM 5
   pages electrically PASS; known text-overlap list attached") so the user can
   approve *direction* while the engine improves separately. Never braid a delivery
   deadline and engine quality-engineering onto one thread.
2. **Two-round convergence stop-loss.** Same class of defect fails to converge for
   **2 fix rounds → forbidden to try a 3rd at the same layer.** Escalate the root
   cause up a layer (call-site → emit → placement → methodology) and report to the
   user for a ruling. The session's 4-round text-overlap loop is the anti-pattern.
3. **Delivery-layer QA first.** For any generate→render deliverable, the FIRST
   step is to define + implement the *render-layer* machine gate (e.g.
   `render_qa.qa_svg_text` scanning the rendered SVG) and run a baseline — *before*
   any fix iteration. A model-layer QA passing is NEVER grounds to declare the
   presentation done. "A measurable QA that isn't at the delivery layer doesn't
   count when it passes."
4. **Single engine ownership.** Parallel subagents must have disjoint file scopes.
   The engine directory has **at most one writer at a time**; the orchestrator
   states ownership explicitly on dispatch. (Two subagents shared the engine and
   one's rollback pulled the other's environment out from under it.)
5. **Engine-change snapshot + no git rollback.** Before any engine edit:
   `tar -C packages/eda-bridge -cf <cache>/engine_snap_<ts>.tar bodesign_eda_bridge`.
   `git checkout`/`reset`/`stash` on UNCOMMITTED engine files is banned in the
   dispatch template — a frustrated subagent's `git checkout` erased 6 relays of
   uncommitted work (recovered only by luck from a container copy).
6. **Standardized relay handoff.** Every engine-touching relay MUST hand back:
   the `__engine_rev__` stamp after its change, a one-paragraph change summary,
   and the QA baseline numbers (e.g. per-page `qa_svg_text` violations). The next
   relay's FIRST action is verifying that stamp (`scripts/sync_engine.sh`) — no
   re-archaeology of "which copy is live / what did the last relay change".
7. **WebDAV / two-container transfer discipline (doc-render relays).** A
   docx/pdf-producing dispatch crosses TWO separate container namespaces —
   getting them confused is the most-reflexed-wrong area (§4). Every dispatch
   prompt for a doc deliverable MUST state, verbatim:
   - **The two namespaces are distinct and non-interchangeable.** bodesign
     compute tools take a **`token`** arg (tree under `/var/cache/bodesign/sessions/<tok>`);
     docxmcp `assemble` / `add_front_matter` take a **`doc_dir`** arg (ABSOLUTE
     container path `/var/cache/docxmcp/sessions/<tok>/…`). A bodesign `token` is
     NOT a docxmcp `doc_dir`, and vice-versa — never feed one tool the other's
     handle. The docxmcp facade reads `doc_dir` ONLY; a bare `tok_…` or a relative
     path resolves to `/app` and fails (`DOCUMENT_DOC_DIR_NOT_FOUND` / bare
     `--doc-dir` usage error). Pass the **absolute** container `doc_dir`.
   - **Transfer axis, not location axis, decides bytes-crossing** (§4): default
     pass-by-value (`stage_dir` inline OR a WebDAV mount) works on every deployment;
     a file sitting on gdrive/`/tmp` has ZERO bearing on whether WebDAV works. Do
     not "fix" a transfer question by moving the file's location.
   - **Scratch-to-tmp for intermediates.** Preview renders / OOXML dumps / figure
     PNGs staged only to be read back go to `/tmp/<task-slug>/`, never the network
     mount; only the final `C0N_*.docx` lands at the stage root. No `sync; sleep`
     consistency patches — route to `/tmp` instead.
   - **Handle handoff is explicit, never re-derived.** A relay hands the LIVE
     `token` + `doc_dir` (+ cache token / `/dav/{token}/` URL if a working cache is
     mounted) to the next relay verbatim; the next relay does NOT re-provision or
     re-tar to "rediscover" which workspace is live. A cache workspace is closed
     via `bodesign_cache_close` only after `cache_export` to a host target
     (dirty-gated) — an un-exported close loses the work.

Deploy discipline for the engine: there is exactly ONE legitimate in-container
copy — `/app/packages` (a read-only bind mount of the host working tree in dev
mode; host edits are live immediately, deploy = restart + verify). The old
`/tmp/engpatch` overlay is **RETIRED** (2026-07-06, BR2): it was never on the
server process PYTHONPATH and existed only as a session workaround — a pure
drift source. Use `scripts/sync_engine.sh` as the SINGLE deploy/verify action —
it asserts engpatch is absent (fail-loud if recreated) and proves
`__engine_rev__` + live `compose_schematic` signature match the host. Never
hand-roll `docker cp`. `bodesign_compose_schematic` returns `engine_rev` in its
result; if "which copy is live?" is ever in doubt, that stamp answers it.

### Built-in fidelity + render gates (use them, don't reinvent)

- **`compose_schematic(..., fidelity=True)`** runs a post-emit partition-fidelity
  check: the spec's expected net partition vs KiCad's exported partition, compared
  by node-set (NOT net name). Diverge → `FidelityError` (fail-loud). This catches
  collinear-wire net FUSION that ERC is blind to (fewer nets, no dangling). Turn it
  on for every connector-dense board. Standalone: `verify_partition_fidelity`.
- **`render_qa.qa_svg_text(svg)`** is the render-layer text-overlap gate (rule 3).

## The one rule that overrides convenience

Everything here serves a single discipline: **a bodesign package is trustworthy because it never
claims more than it can show.** Mark unproven things `draft`/`pending`/`not-run` and say why.
External gates (EVT/DVT, FCC/CE, EMC lab, safety) are *never* marked passed. See
`references/honesty-model.md` before you write a single deliverable.
