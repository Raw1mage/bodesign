# C00/C01 Gap Audit

## Current Status

- **C00 function model**: planned. It has PRD template, readiness rubric, implementation spec, and now a consultant-agent system prompt.
- **C01 function model**: planned. It has Rockbox canonical target outputs, readiness rubric, workflow spec, and C00-derived visual source boundary.
- **Runtime status**: not implemented. Current artifacts are plan/spec/template files only.

## C00 Remaining Gaps

### Prompt / Agent Packaging

- [x] Draft C00 consultant system prompt.
- [ ] Decide where C00 prompt lives at runtime: agent profile, skill, MCP workflow config, or template-driven prompt registry.
- [ ] Define how C00 dispatches C01-C06 work packets without letting downstream agents mutate the PRD contract directly.

### MCP / Runtime Tools

- [ ] Template loader for `c00_prd.template.json` and `c00_prd.rubric.json`.
- [ ] C00 scaffold function/tool for `Project Requirements` and conditional `RF Requirements`.
- [ ] C00 answer-state file format.
- [ ] C00 readiness function/tool with one next-best question.
- [ ] C00 PRD emitter that preserves missing/drafted/external-needed/accepted-risk fields.
- [ ] C00 handoff packet generator for C01-C06.

### Integration

- [ ] Replace or bind `requirement_planning.REQUIREMENT_FIELDS` to the C00 template instead of hard-coded fields.
- [ ] Feed C00 readiness into `package_readiness` instead of treating PRD as merely present/missing.
- [ ] Add C00 dispatch contract for downstream agents: input scope, output packet, blocker return format.
- [ ] Add event/history state so C00 can resume an interview without losing decisions.

### Verification

- [ ] Template completeness tests for all 12 PRD sections and RF appendix.
- [ ] Readiness scoring tests for missing/drafted/answered/external-needed/blocked/accepted-risk.
- [ ] Next-best-question selection tests.
- [ ] Downstream gate tests for C01/C02/C03/C04/C05/C06.
- [ ] No-fallback tests: incomplete business/product/compliance decisions must not silently pass.

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

- [ ] Template loader for `c01_id.template.json` and `c01_id.rubric.json`.
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

## Cross-Cutting Gaps

- [ ] Agent registry: define C00/C01/C02/C03/C04/C05/C06 roles, prompts, inputs, outputs, authority boundaries, and human gates.
- [ ] Work packet schema: C00 dispatch → downstream agent output → blocker backflow to C00.
- [ ] Human approval model: distinguish AI draft, human-approved, external-confirmed, and accepted-risk across all layers.
- [ ] Folder/package state model: decide where answer state, draft carriers, readiness reports, and handoff packets live in the client-owned project folder.
- [ ] Runtime UX: user stays in C00; downstream agents work in background and return questions to C00.
