# Tasks: C00 PRD consultant completion

## Re-baseline 2026-06-07 (handoff) — status truth & next-batch ordering

**Lifecycle:** `.state.json` synced `proposed → implementing` (forced via `mode:sync`; see RB-1).
**Runtime reality:** C00/C01/C02 draft-grade runtime LANDED (15 Cxx MCP tools, 144 tests green). C03 = full chain.
The stale all-gap snapshots in `c00_c01_gap-audit.md` and `doc_architecture.template.json` are now corrected;
`doc_architecture.template.json → gap_summary` is the authoritative coverage/gap map.

**Diagnosis (why a re-baseline was needed):** per-layer emitters were built bottom-up and outran their own
declared prerequisites; the orchestration **spine** the implementation-spec calls the real dependency was deferred.
Symptoms: C01-I1 (template loader) and C01-I3 (mode contract) sit undone *beneath* their already-`[x]` dependents.

**Chosen next-batch ordering (A→B→C):**
1. **A — DONE:** reconcile status docs, sync lifecycle, amend proposal scope, record debts.
2. **B — DONE (this pass):** orchestration spine LANDED — `agent_registry.py` (C00–C06 derived from the
   document architecture), `orchestration.py` (`work_packet.v1`/`blocker_return.v1` persisted under
   `<folder>/_orchestration/` + dispatch/return/ingest, fail-fast), 7 new MCP tools, and the C00→C01
   mode contract `mode_contracts.enter_c01_mode` (C01-I3). RB-2 folded in. +29 tests (173 total green).
3. **C — DONE:** all 7 layers now have runtime — C04 `bodesign_c04_emit_layout_package` (constraint-first),
   C05 `bodesign_c05_scaffold_fw_spec` (plan-builder-like SW-dev spec), C06 `bodesign_c06_assemble_test_plan`
   (verdict assembler). Each constraint-first/draft-only, fail-fast, no fabricated pass/approval. +15 tests.

**After A→B→C:** remaining is depth, not breadth — cross-section consistency checks, the autonomous
C00-driven dispatch loop, RB-1 (canonical-artifact conformance), and C00 docx/pdf render + PRD verifier.

**Re-baseline debts:**
- **RB-1** (OPEN) custom artifact set ≠ plan-builder canonical (spec.md/idef0/grafcet/sequence/data-schema); lifecycle gates bypassed — conform or document deviation.
- **RB-2** (DONE, Batch B) runtime templates moved to `packages/workflow-core/.../templates/`; see `TEMPLATES.md`. C01 templates move when C01-I1 lands.
- **RB-3** (DONE) = C01-I1: `c01_id_template.py` loads the template/rubric and binds the emitter to it (`validate_c01_outputs_binding`); C01 templates moved to `packages/.../templates/`.

## Goal

Make C00/C07 a consultant-led PRD layer: AI guides the user through product, business, engineering, project, and handoff decisions until the PRD is sufficient for C01-C06 teams to start work.

## C00 Scope Split

| Capability | MCP tool responsibility | AI workflow skill responsibility | Human / external responsibility |
|---|---|---|---|
| PRD structure | Store section template, scaffold files, persist answers | Explain why each section matters and sequence the work | Approve that the structure matches the business context |
| Requirements intake | Extract stated/missing fields, update answer state | Ask focused follow-ups, infer safe draft text, flag assumptions | Decide product positioning, market, budget, schedule, tradeoffs |
| PRD drafting | Render Markdown/docx/pdf from template + answers | Write coherent section prose, normalize terminology, preserve open issues | Confirm final wording and business claims |
| Handoff readiness | Score section completeness and downstream readiness | Interpret risk, choose next best question, explain blockers | Accept unresolved risks or provide missing decisions |
| Cross-layer sync | Map PRD §5/§6/§7 to C01/C02/C03/C05 gates | Keep downstream implications visible during conversation | Downstream teams validate their own deliverables |

## Implementation Slices

- [x] **C00-T1 PRD template source** — add `c00_prd.template.json` with Rockbox-derived 12-section PRD structure, RF conditional appendix, per-section purpose, fields, prompts, human decisions, AI draftability, and downstream handoff targets.
- [x] **C00-T2 Readiness rubric** — add machine-readable completeness gates for PRD document quality and downstream C01-C06 handoff sufficiency.
- [x] **C00-T3 Consultant workflow spec** — define the turn loop: diagnose → ask one highest-value question → update draft state → recompute readiness → produce next handoff.
- [x] **C00-T4 Template binding** — link the C00 section in `doc_architecture.template.json` to the dedicated PRD template and rubric so C00 is no longer only a shallow question bank.
- [x] **C00-T5 Tool boundary plan** — specify which pieces become MCP tools now (`scaffold`, `readiness`, `emit`) versus which remain AI workflow skill behavior.
- [x] **C00-T6 Verification plan** — define fixture tests for template completeness, question ordering, readiness scoring, and PRD handoff gates before implementation.
- [x] **C00-T7 Consultant system prompt** — define C00 as the user-facing product development consultant agent and coordinator for downstream specialist agents.

## Acceptance Criteria

- C00 can be evaluated without confusing MCP tools, AI judgement, and human decisions.
- The PRD template covers all Rockbox-derived 12 sections plus conditional RF requirements.
- Every PRD section declares required fields, prompts, AI-draftable content, human-only decisions, and downstream handoff mapping.
- Readiness can answer: `What is missing?`, `Who must answer it?`, and `Which downstream layer is blocked?`.
- C00 implementation can start without inventing new fallback behavior or treating incomplete PRD content as complete.

## Next Implementation Backlog

- [x] **C00-I1 Template loader** — load and validate `c00_prd.template.json` / `c00_prd.rubric.json` in `packages/workflow-core`.
- [x] **C00-I2 Scaffold function/tool** — create blank C00 PRD source files and answer-state records inside a token/project folder.
- [x] **C00-I3 Readiness function/tool** — compute field/section/gate/handoff readiness and return one highest-value next question.
- [x] **C00-I4 Emit function/tool** — render Markdown-first PRD and handoff report while preserving assumptions/open issues.
- [x] **C00-I5 Requirement planning binding** — replace duplicated C00 hard-coded fields with template-derived fields without breaking existing API shape.
- [x] **C00-I6 Tests** — add unit fixtures for template completeness, scoring, next-question selection, RF conditional gating, and no-fallback behavior.
- [x] **C00-I7 Agent prompt packaging** — decide where `c00_consultant.system-prompt.md` lives at runtime and how it is loaded.
- [x] **C00-I8 Downstream dispatch contract** — define C00 work-packet and blocker-return schemas for C01-C06 agents.

## C01 Visual Source Plan

### Goal

Make C01 an industrial-design consultant and Rockbox C01 document completer: diagnose missing C01 data, interactively collect user preferences, apply basic ID knowledge, and generate the target package (`Ai file`, `CMF`, `Display UI/UX`) plus downstream constraints.

### Completed Plan Slices

- [x] **C01-T1 Target package definition** — preserve Rockbox C01 canonical outputs (`Ai file`, `CMF`, `Display UI/UX`) and define AI draft carriers plus support artifacts under those slots.
- [x] **C01-T2 Boundary split** — separate MCP extraction/emission/readiness, AI visual-source workflow skill, and human/ID final authority.
- [x] **C01-T3 Readiness rubric** — define artifact gates and downstream gates for C02/C03/C04/C05.
- [x] **C01-T4 Workflow spec** — define C00→C01 extraction, visual prompt loop, AI-draft labeling, and ID designer handoff.
- [x] **C01-T5 Template binding** — update the C01 section in `doc_architecture.template.json` from track-only to visual-source package.
- [x] **C01-T6 Skill build strategy** — decide to self-build `c01-industrial-design-requirements` and seed it from Rockbox C01, C00 handoff inputs, generic ID/CMF/UIUX practice, and observed project experience.
- [x] **C01-T7 Rockbox-like MVP gate** — require the first usable C01 capability to produce non-empty structured scripts for `Ai file`, `CMF`, and `Display UI/UX`, plus constraints and ID handoff.

### Next Implementation Backlog

- [x] **C01-I1 Template loader** — `c01_id_template.py`: `load_c01_id_template` / `load_c01_id_rubric` (fail-fast) + `validate_c01_outputs_binding`, which asserts the emitter's `C01_OUTPUTS` Rockbox carriers match the template's `target_package.outputs` (drift fails fast). Resolves RB-3: C01 is now template-bound like C00.
- [x] **C01-I2 Skill package** — create `c01-industrial-design-requirements` with role prompt, question strategy, CMF framework, UI/status script, exposed-interface checklist, downstream constraint map, risk map, and `known_gaps` section.
- [x] **C01-I3 Mode contract** — `mode_contracts.enter_c01_mode` (Batch B): C00 dispatches a C01 work packet scoped to the PRD sections whose `handoff_targets` include C01 (derived from the template), emits the Rockbox C01 package, and returns the next C01 preference question. C01 asks preference questions directly; product-level decisions return to C00 via `return_blocker`; C01 never mutates the PRD. MCP tool `bodesign_enter_c01_mode`.
- [x] **C01-I4 Visual extractor** — extract C00 §1/§2/§5/§6/§7 content into normalized visual/interface requirements.
- [x] **C01-I5 Scaffold function/tool** — create the C01-ID package using Rockbox deliverable names: `Ai file/`, `CMF/`, `Display UIUX/`, plus support artifacts.
- [x] **C01-I6 Rockbox-like script emitters** — generate `Design_Direction.md`, `CMF_Direction.md`, `UIUX_Requirements.md`, `Interface_Constraints.json`, and `Handoff_to_ID_Designer.md` with explicit draft/decision/owner markers.
- [x] **C01-I7 Readiness function/tool** — score C01 artifact completeness and C02/C03/C04/C05 downstream gates.
- [x] **C01-I8 Tests** — add fixtures for C00→C01 extraction, Rockbox-like script generation, artifact scaffold, constraint JSON, readiness gates, and no silent visual defaults.

### Next Interaction Backlog

- [x] **C01-N1 Answer state** — persist C01 fields as `missing`, `answered`, `drafted`, `no-preference`, `external-needed`, `blocked`, or `accepted-risk`.
- [x] **C01-N2 Preference question bank** — define user-answerable questions for form archetype, style, CMF, visible components, UI/status, POC fidelity, and approval owner.
- [x] **C01-N3 Next question tool** — add `bodesign_c01_next_question` to diagnose the highest-value missing preference.
- [x] **C01-N4 Update answers tool** — add `bodesign_c01_update_answers` to merge user answers, regenerate the package, and recompute readiness.
- [x] **C01-N5 Field-level readiness** — upgrade `bodesign_c01_readiness` from file existence checks to field-state and downstream blocker checks.
- [ ] **C01-N6 Constraint hardening** — require each exposed component constraint to include owner, status, downstream targets, and risk notes.
- [ ] **C01-N7 Reference image intake** — accept user-uploaded/reference images, extract form/CMF/UI cues, ask what should be borrowed or avoided, and keep cues `reference-derived` until user confirmation.
- [ ] **C01-N8 Reference traceability** — persist source image paths, cue summaries, confirmation status, and target artifact mapping in C01 handoff output.

### C01 Concept Image Support

- [x] **C01-A1 Skill prompt generation** — the strengthened `c01-industrial-design-requirements` skill now carries a Moodboard & Concept-Prompt framework (archetype + CMF route + brand tone → reference-only prompts, copyright-safe) feeding `bodesign_c01_generate_concept_image`.
- [ ] **C01-A2 Prompt artifacts** — optionally persist `Concept_Image_Prompts.md`, `Moodboard_Prompts.md`, and `UI_Concept_Prompts.md` for ID handoff.
- [x] **C01-A3 Image generation tool** — add `bodesign_c01_generate_concept_image` behind explicit Google AI Studio provider/API key config; fail fast when unavailable and never fallback silently.
- [x] **C01-A4 Reference metadata** — write `Concept_Reference.md` with image path, prompt, provider/model, timestamp, and reference-only limitation statement.
- [x] **C01-A5 Add-on tests** — verify generated images do not affect C01 MVP readiness and missing API credentials produce explicit errors.

## C02 Parametric Enclosure Draft

- [x] **C02-P1 Responsibility split** — define C02 as an AI-assisted constraint-first parametric enclosure draft layer with explicit MCP tool / agent skill / human-vendor boundaries in `c02_me_enclosure_plan.md`.
- [x] **C02-P2 Three MVP gates** — require outputs that the boss can view, the user can 3D print, and an ME/ID vendor can take over.
- [x] **C02-P3 Workflow phases** — split ME work into C02-pre constraints, C02-check after C04 layout, and C02-final enclosure draft.
- [x] **C02-P4 Restore Rockbox code** — keep C02 as ME by deliverable/vendor boundary; express C03-led component constraints through execution-loop metadata instead of renumbering.
- [x] **C02-S1 Mechanical consultant skill** — create `c02-mechanical-enclosure-consultant` skill for user-answerable mechanical questions, assumptions, printability tradeoffs, compliance risks, and vendor handoff guidance.
- [x] **C02-P5 Implementation stages** — split the remaining C02 work into package emitter, OpenSCAD source, STL export, optional SKP/STEP handoff, and validation gates.
- [x] **C02-T1 Enclosure package tool** — implement `bodesign_c02_emit_enclosure_package` to emit `Mechanical_Constraints.json`, `Mechanical_Assumptions.md`, `Assembly_Notes.md`, `Print_Settings.md`, `Vendor_Handoff.md`, and SketchUp fallback guidance without claiming CAD readiness.
- [x] **C02-T2 Parametric source generator** — implement `bodesign_c02_generate_openscad` from explicit board outline, mounting strategy, wall/clearance parameters, openings, component heights, battery, heat, RF, and keepout data.
- [x] **C02-T3 STL export** — implement `bodesign_c02_export_stl` with local OpenSCAD/CAD tool detection, real `Enclosure.stl` output when available, and explicit `export_unavailable` when not.
- [x] **C02-T4 Readiness checker** — report constraint readiness before CAD generation, including blockers for board outline, heights, openings, thermal/RF, battery, and environment targets.
- [x] **C02-T5 SketchUp import fallback** — emit `SketchUp_Import_Guide.md` and explicit `skp_export_unavailable` status when native SKP cannot be generated; native `bodesign_c02_export_skp` remains optional and toolchain-gated.
- [x] **C02-T6 STEP draft export** — implement `bodesign_c02_export_step` as a toolchain-gated handoff path: it writes `STEP_Draft_Handoff.md` and returns explicit `step_export_unavailable` when FreeCAD/CadQuery/OCP is unavailable, without fabricating `Enclosure.step`.
- [x] **C02-T6b Real STEP backend (build123d/OCP)** — `export_c02_step` now builds a real `Enclosure.step` via the build123d/OCP kernel from the SAME constraints as the OpenSCAD path (`_build_enclosure_part`: open-top shell + wall floor + mounting bosses) when the kernel is present AND explicit wall/clearance/lid_clearance are given; otherwise keeps `step_export_unavailable` (no kernel) and never guesses dimensions (no dims → unavailable). Output marked `draft_unapproved`, never `me_approved`. Tests: kernel-present → real ISO-10303 STEP (skip-guarded), kernel-absent (patched) → unavailable + non-destructive, no-dims → unavailable. **build123d is dev-installed only; deliberately NOT in the monolith image. Decision (Batch E): it lands in the responsibility-grouped `bodesign-me` worker container, not the core image — see `toolchain_workers.md`. Runtime stays gated until that worker exists.**
- [ ] **C02-T7 Real STL toolchain validation** — when OpenSCAD is installed/configured, run an end-to-end sample that produces a real `Enclosure.stl` and records toolchain/version metadata; until then, keep `export_unavailable` explicit.
- [x] **C02-V1 Readiness validation** — add tests for no guessed dimensions, CAD-source blockers, missing constraint ownership, and no printable/CAD export claim at readiness stage.
- [x] **C02-V2 Package validation** — test package emitter files, owner-tagged pending constraints, vendor handoff wording, and no production ME approval.
- [x] **C02-V3 Source/STL validation** — test OpenSCAD generation, explicit dimension requirements, STL export unavailable behavior, and no fake STL output.
- [x] **C02-V4 Optional handoff validation** — test SketchUp fallback, optional native SKP gating, and optional STEP gating.
- [ ] **C02-V5 Toolchain validation** — test real STL export only in an environment with OpenSCAD available; otherwise assert the unavailable path remains explicit and non-destructive.

### Post-Commit Execution Queue

1. **C02-T7 / C02-V5** — validate real STL export after OpenSCAD is installed or configured on the MCP host/container.
2. **C00-I1–I4** — implement the C00 SSOT/PRD runtime scaffold, readiness, and emitter after the C02 prototype gates are explicit.
3. **C01-N1–N5** — add field-state interaction support after the C00 SSOT model exists.

## C03 Circuit Engineering Lead

- [x] **C03-P1 Preserve Rockbox EE code** — keep C03 as circuit design by EE/vendor deliverable boundary while allowing C03 component constraints to lead C02/C04 execution loops.
- [x] **C03-P2 Mechanical constraint export** — ensure C03 circuit outputs include component heights, connector locations/types, heat sources, antenna/RF keepouts, battery envelope, and ESD/EMC notes for C02/C04.

## Batch D — Autonomous C00 orchestration loop

Design: `c00_orchestration_loop.md` (the conductor over the Batch B spine — the last
open Runtime-UX gap). Deterministic selector; auto-dispatch only, never auto-answer.

- [x] **D-1 Selector core** — `c00_orchestration.py`: `c00_orchestration_tick(folder)` returns one `NextAction` per the priority (resolve_blocker → ask_c00(unblock) → dispatch → done-when-all-dispatched → ask_c00(advance) → waiting) over `assess_c00_prd_readiness` + `list_work_packets` + `list_blockers` + `load_agent_registry`. Fail-fast, deterministic. Handles combined gate targets (`C01/C02`) and the ungated C04 via an upstream-dependency rule (`C04` after C01+C03).
- [x] **D-2 Board status** — `c00_orchestration_status(folder)` returns the read-only per-layer board (gate status, dispatched?, packet status, open blockers) + C00 overall status. Mutates nothing.
- [x] **D-3 Dispatch binding** — tick dispatches a dispatchable layer once; `enter_c01_mode` for C01, `dispatch_work_packet` for C02–C06; idempotent. `auto_dispatch=False` dry-run recommends without dispatching.
- [x] **D-4 MCP tools** — `bodesign_c00_orchestration_status` (read-only) and `bodesign_c00_orchestration_tick` (advance one step; returns next action + any new packet).
- [x] **D-5 Tests** — 9 tests: scaffold-first, never dispatch a blocked-gate layer, dispatch each layer once (C01→C06, C04 after C01+C03), no re-dispatch, blocker preempts, all-dispatched → `done`, no tick writes PRD/blocker/approval, determinism, dry-run. +1 MCP server test. (203 total green.)

### Acceptance (Batch D)

- C00 can drive the whole C00→C06 chain by repeated `tick` without manual tool choice.
- Human stays in control: every PRD answer, blocker resolution, and approval still requires the user; the loop only selects and (safely) dispatches.

## Batch E — Toolchain worker containers (responsibility-grouped)

Design: `toolchain_workers.md`. One external MCP (`bodesign-core`) + a few worker
containers grouped by C0x responsibility (`ee`, `me`, optional `docs`); heavy deps
isolated per worker; absent worker → tool `*_unavailable` (gate generalized). Grouped
by function/responsibility, NOT by weight. Already-MCP toolchains (docxmcp/drawmiat)
mounted via MCP-of-MCPs. Incremental, non-breaking; monolith keeps working.

- [x] **E-1 Tool→group routing** — each tool carries a `group` (me tagged; rest core); `--tools <group>` selector sets `SERVED_GROUPS`; `run_tool` routes via `_route_tool` → local / forward (`_forward_to_worker` httpx POST `/invoke`) / `worker_unavailable`. Monolith default `--tools all` = every tool local, zero behaviour change.
- [x] **E-2 Shared session volume model** — `/invoke` worker entrypoint runs the tool against the shared `bodesign-sessions` tree (worker resolves the token itself); compose mounts the same named volume into core + worker; wire payload = args+token only.
- [x] **E-3 Phase 1: `bodesign-me` worker (reference)** — lean `Dockerfile.me` (build123d/OCP + GL libs + OpenSCAD, NO KiCad/LibreOffice) + `docker-compose.workers.yml` overlay routing `bodesign_c02_*` to it. Proven in-process: `--tools me` → `/healthz` served_groups=[me]; `/invoke` c02_export_step → real ISO-10303 STEP.
- [x] **E-3b Starting vs unavailable semantics** — a configured-but-unreachable worker (booting/warming) returns retryable `worker_starting` + `retry_after_seconds`; an unconfigured worker (slim deployment) returns permanent `worker_unavailable`. Keeps workers always-on (cheap idle) while giving agents a clean "warming up, retry" signal. +2 tests.
- [x] **E-4 Phase 2: `bodesign-ee` worker** — tagged the KiCad/ngspice tools `ee` (emit_symbol, compose_schematic, emit_layout, emit_fab, simulate, analyze_emc, analyze_thermal, export_bom, export_netlist, render_companion); pure-python EE-adjacent tools (pin_allocation, ingest, crosscheck, cNN emitters) stay core. Lean `Dockerfile.ee` (KiCad 9 + ngspice, no LibreOffice/OpenSCAD/build123d); `docker-compose.workers.yml` adds `bodesign-ee` and runs core as `--tools core`, forwarding me+ee. +1 routing test. NOTE: the core **process** no longer executes EE tools (isolation achieved), but the core **image** (main Dockerfile) still physically carries KiCad/LibreOffice — a dedicated lean `Dockerfile.core` waits until E-5 moves LibreOffice (emit_doc) to a docs worker, after which every heavy dep lives only in its worker.
- [ ] **E-7 (future) scale-to-zero** — only when there are many heavy, rarely-used workers: hand worker lifecycle to the platform (K8s/KEDA), MCP stays unprivileged (no Docker socket); `worker_starting` is already the contract. Not needed while idle cost is low.
- [ ] **E-5 Phase 3: optional `bodesign-docs`** + mount docxmcp/drawmiat via MCP-of-MCPs.
- [x] **E-6 Tests/validation** — routing unit tests (monolith all-local; core+url→forward; core+no-url→`worker_unavailable`, no fabrication/crash; worker serves its group) + an in-process `/invoke` real-STEP smoke. Full image e2e (build123d-in-Dockerfile.me) validated at deploy. +5 tests (211 total green).

### Acceptance (Batch E)

- Clients see ONE MCP endpoint; worker topology is invisible. A heavy dependency lives in exactly one worker. Stopping a worker degrades only its tools (to `*_unavailable`), never the server.

## Open Gap Audit

- [x] **GAP-T1 C00/C01 gap audit** — document remaining prompt, runtime, tool, integration, verification, and cross-agent gaps in `c00_c01_gap-audit.md`.
