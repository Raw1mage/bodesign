# C00/C01 Gap Audit

> **RE-BASELINED 2026-06-07 (handoff).** This audit predated the runtime commits and was stale.
> The authoritative coverage/gap map is now `doc_architecture.template.json → gap_summary`.
> Boxes below are flipped to `[x]` only where code + passing tests exist (193 green after Batch C).

## Current Status

- **C00 function model**: runtime LANDED (draft-grade). Template+rubric loaded by `c00_prd_template.py`; `bodesign_c00_scaffold_prd` / `_readiness` / `_emit_prd` live with answer-state field readiness, next-best question, downstream-gate assessment, and a Markdown handoff *report*. Consultant prompt packaged as a skill. `requirement_planning` fields bound+validated against the template.
- **C01 function model**: runtime LANDED (draft-grade). `bodesign_c01_emit_package` / `_next_question` / `_update_answers` / `_readiness` (+ optional concept-image) live over Rockbox canonical slots. NOTE: emitters hardcode structure — `c01_id.template.json`/rubric are NOT yet loaded at runtime (C01-I1 genuinely undone).
- **C02 function model**: runtime LANDED (draft-grade). package/openscad/export(stl·skp·step, toolchain-gated)/readiness live. Real STL export validation pending OpenSCAD-in-container.
- **C03**: full chain (pre-existing EE pipeline) + `bodesign_c03_export_mechanical_constraints`.
- **C04/C05/C06** (Batch C): `bodesign_c04_emit_layout_package` (constraint-first layout), `bodesign_c05_scaffold_fw_spec` (plan-builder-like FW SW-dev spec, not code), `bodesign_c06_assemble_test_plan` (verdict assembler). **All 7 layers now have runtime.**
- **SPINE wired** (Batch B): `work_packet.v1`/`blocker_return.v1` runtime + agent registry + C00→C01 mode contract. Remaining is depth: cross-section consistency, the autonomous C00 dispatch loop, RB-1, and C00 docx/pdf + PRD verifier.

## C00 Remaining Gaps

### Prompt / Agent Packaging

- [x] Draft C00 consultant system prompt.
- [x] Decide where C00 prompt lives at runtime: packaged as a skill source (`skills/c00-product-development-consultant/SKILL.md`).
- [~] Define how C00 dispatches C01-C06 work packets without letting downstream agents mutate the PRD contract directly. — SCHEMA DRAFTED in `c00_downstream_contract.md` (`work_packet.v1`/`blocker_return.v1`); NOT wired to runtime. → Cross-Cutting.

### MCP / Runtime Tools

- [x] Template loader for `c00_prd.template.json` and `c00_prd.rubric.json`.
- [x] C00 scaffold function/tool for `Project Requirements` and conditional `RF Requirements`.
- [x] C00 answer-state file format.
- [x] C00 readiness function/tool with one next-best question.
- [x] C00 PRD emitter that preserves missing/drafted/external-needed/accepted-risk fields.
- [~] C00 handoff packet generator for C01-C06. — Markdown handoff *report* exists in `_emit_prd`; a structured `work_packet.v1` *emitter* does not. → Cross-Cutting.

### Integration

- [x] Bind `requirement_planning` fields to the C00 template (validated against section/field bindings; fail-fast on missing field). Full hard-coded-field *removal* not required — API shape preserved.
- [ ] Feed C00 readiness into `package_readiness` instead of treating PRD as merely present/missing.
- [~] Add C00 dispatch contract for downstream agents: input scope, output packet, blocker return format. — drafted in doc, not wired.
- [ ] Add event/history state so C00 can resume an interview without losing decisions.

### Verification

- [x] Template completeness tests for all 12 PRD sections and RF appendix.
- [x] Readiness scoring tests for missing/drafted/answered/external-needed/blocked/accepted-risk.
- [x] Next-best-question selection tests.
- [~] Downstream gate tests for C01/C02/C03/C04/C05/C06. — `_assess_downstream_gates` exists + readiness tests cover it; explicit per-downstream-layer gate assertions still thin.
- [x] No-fallback tests: incomplete business/product/compliance decisions must not silently pass (missing answer_state fails fast).

## C01 Remaining Gaps

### Skill Discovery Result

- [x] Loaded `skill-finder` after restoring the runtime `skill` loader.
- [x] Searched external/public sources for industrial-design / CMF / product-design-brief / hardware UIUX skill candidates.
- [x] Found no ready-to-adopt C01 specialist skill. One rough repository candidate appeared (`TheFrenchPixel/designfuse`, an industrial design brief app), but it is not an opencode skill and does not provide the C01 agent prompt, CMF framework, downstream constraint map, or blocker-return contract needed here.
- [x] Decide to create a dedicated `c01-industrial-design-requirements` skill instead of relying on generic visual-design skills. Initial build plan lives in `c01_skill_build_plan.md`.
- [ ] Optionally borrow supporting concepts from generic `canvas-design`, `brand-guidelines`, and `frontend-design`, but do not treat them as sufficient C01 authority.
- [x] Create the initial skill package source and keep a `known_gaps` / learned-patterns section so real project experience can improve the skill over time.

### Prompt / Agent Packaging

- [x] Draft C01 ID agent system prompt.
- [ ] Define C01 as a downstream worker agent that consumes C00 work packets, not as a user-facing requirement interviewer.
- [ ] Define C01 blocker return format to C00.
- [ ] Add C01 mode/session contract: how C00 enters C01 mode, how C01 asks user-facing follow-ups, and how unresolved decisions return to C00.

### MCP / Runtime Tools

- [x] Template loader for `c01_id.template.json` and `c01_id.rubric.json`. — RB-3 RESOLVED: `c01_id_template.py` loads both (fail-fast) and `validate_c01_outputs_binding` ties the emitter's carriers to the template; templates moved into the package.
- [x] C00→C01 visual/interface extractor.
- [x] C01 scaffold function/tool that creates Rockbox canonical slots: `Ai file/`, `CMF/`, `Display UIUX/`.
- [x] C01 source emitters for AI draft carriers under the canonical slots.
- [x] `Interface_Constraints.json` schema for C02/C03/C04/C05 consumption.
- [x] C01 readiness function/tool that scores canonical outputs separately from support artifacts.

### Design Output Quality

- [x] Decide minimum viable visual source format for `Ai file` draft carrier: Markdown `Design_Direction.md` first; SVG/AI later.
- [x] Decide minimum viable CMF representation: Markdown `CMF_Direction.md` first; images/sample-board references later.
- [x] Decide minimum viable Display UI/UX representation: Markdown `UIUX_Requirements.md` first; SVG/Figma later.
- [x] Define how C01 handles products with no display: map `Display UI/UX` to LED/status/button interaction instead of omitting it silently.

### Verification

- [x] Extraction tests from C00 §1/§2/§5/§6/§7 into visual/interface requirements.
- [x] Scaffold tests for Rockbox canonical folders and support artifacts.
- [x] Markdown/JSON emitter tests with draft markers.
- [ ] Downstream gate tests for C02/C03/C04/C05 constraints.
- [ ] No-fallback tests: no arbitrary style, placement, CMF, or UI decision may pass as approved.

## Cross-Cutting Gaps — SPINE (LANDED in Batch B 2026-06-07)

These tie the 15 Cxx tools into a driven workflow. Runtime in `packages/workflow-core`:
`agent_registry.py`, `orchestration.py`, `mode_contracts.py`; MCP tools in `services/mcp/server.py`.

- [x] Agent registry: `agent_registry.load_agent_registry` derives C00–C06 roles, target_role, owning team, skills, human gates, and allowed/forbidden actions from the document architecture. C00 is the contract owner; C01–C06 are downstream workers. MCP `bodesign_agent_registry`.
- [x] Work packet schema wired: `orchestration.py` implements `bodesign.c00.work_packet.v1` + `bodesign.c00.blocker_return.v1` as persisted state with `dispatch_work_packet` / `return_blocker` / `ingest_blocker` and fail-fast validation. MCP `bodesign_dispatch_work_packet` / `_return_blocker` / `_ingest_blocker` / `_list_work_packets` / `_list_blockers`.
- [x] Folder/package state model: `<folder>/_orchestration/{work_packets,blockers}/*.json` + append-only `log.jsonl`; deterministic count-based IDs.
- [x] C00→C01 mode contract (C01-I3): `mode_contracts.enter_c01_mode` + MCP `bodesign_enter_c01_mode`.
- [~] Human approval model: blocker `recommended_owner`/`proposed_state` + ingest `decided_by` give a per-decision owner model; a unified cross-layer approval state is still not consolidated. → Batch C / later.
- [x] Runtime UX: user stays in C00; downstream agents work in background and return questions to C00. **LANDED (Batch D)**: `c00_orchestration.py` — `c00_orchestration_tick` (deterministic conductor: resolve_blocker → ask_c00 → dispatch → done → ask_c00 → waiting; auto-dispatches ready layers, never auto-answers) + `c00_orchestration_status` (read-only board). MCP `bodesign_c00_orchestration_tick` / `_status`. 10 tests. The spine now has a conductor.

## Re-baseline Debts (introduced/exposed by 2026-06-07 reconciliation)

- [ ] **RB-1** (OPEN) Plan uses a custom artifact set, not plan-builder canonical artifacts (spec.md/idef0/grafcet/sequence/data-schema). `.state.json` was force-set to `implementing` via `mode:sync` because forward gates validate the canonical set. Decision needed: conform to the canonical schema, or formally document the deviation in design.md.
- [x] **RB-2** (DONE, Batch B) Runtime-depended templates moved to `packages/workflow-core/bodesign_workflow_core/templates/` (`c00_prd.template.json`, `c00_prd.rubric.json`, `doc_architecture.template.json`); loaders updated; `plans/.../TEMPLATES.md` records the move. C01 templates relocate when C01-I1 lands.
- [x] **RB-3** (DONE) = C01-I1 above: `c01_id_template.py` loads the template/rubric and binds the emitter via `validate_c01_outputs_binding`; templates relocated into the package.
