# Implementation Spec: C00 PRD consultant completion

## Objective

Complete C00/C07 as a PRD expert-consultant workflow. The runtime implementation should not pretend every expert action is a tool. Tools provide deterministic state and evidence; the AI workflow skill guides the human to decisions; humans and external professionals approve claims and downstream handoffs.

## Runtime Components

### Template Loader

- Loads `c00_prd.template.json` and `c00_prd.rubric.json`.
- Validates that every PRD section has `required_fields`, `ai_can_draft`, `human_decisions`, `consultant_prompts`, and `handoff_targets`.
- Exposes the C00 question and handoff model to `requirement_planning` without duplicating hard-coded fields.

### Scaffold Tool

- Creates `C00-PRD/Project_Requirements.md` and conditional `C00-PRD/RF_Requirements.md` stubs inside the token/project folder.
- Creates a hidden answer-state file under the project state/cache area.
- Writes headings, open questions, and field-state placeholders only; it must not fabricate approved content.

### Readiness Tool

- Computes field, section, document-gate, and downstream-handoff readiness from the PRD source state.
- Reports `missing`, `drafted`, `answered`, `external-needed`, `blocked`, and `accepted-risk` separately.
- Returns the single highest-value next question plus the responsible party: `ai`, `human`, or `external`.

### Emit Tool

- Renders Markdown-first PRD content from approved and clearly labeled draft state.
- Keeps assumptions, open issues, accepted risks, and external-needed fields visible in the output.
- Can later call `bodesign_emit_doc` / kidoc for docx/pdf, but Markdown is the source of truth.

## AI Workflow Skill Contract

- Load or embed `c00_consultant.system-prompt.md` as the C00 agent's system behavior.
- Read the C00 readiness result before asking questions.
- Ask one focused next question unless the user explicitly requests a full questionnaire.
- Label each response target as MCP-supported, AI-draftable, human decision, or external expert input.
- Never convert AI-drafted content to `answered` without user approval.
- Keep PRD §5/§6/§7 implications visible for C01/C02, C03, and C05.
- Treat unresolved compliance, legal, certification, safety, schedule, and business claims as human/external gates.

## Verification Plan

- **Template completeness test**: every Project Requirements section has required fields, prompts, AI/human/external boundaries, and handoff targets.
- **RF conditional test**: RF appendix is required only when RF/wireless keywords or certification requirements are present.
- **Readiness scoring test**: missing fields block gates; drafted fields are partial; answered and accepted-risk complete only with visible evidence.
- **Next-question test**: readiness chooses one highest-value next question and identifies the responsible party.
- **Handoff test**: PRD §5 blocks C01/C02, §6 blocks C03, §7 blocks C05, and verification/project sections block C06 when required content is missing.
- **No-fallback test**: incomplete fields must remain explicit gaps; no default values may silently pass readiness.

## First Implementation Order

1. Move template/rubric loading into `packages/workflow-core`.
2. Replace C00 `REQUIREMENT_FIELDS` duplication with template-derived fields while preserving existing API shape.
3. Add PRD scaffold/readiness functions and unit fixtures.
4. Add MCP tool entries only for deterministic surfaces: scaffold, readiness, emit.
5. Keep consultant behavior as AI workflow guidance, not as a brittle deterministic tool.
6. Package the C00 consultant prompt into the runtime agent/skill registry before exposing the workflow to users.
7. Define C00→C01-C06 work-packet and blocker-return schemas before implementing downstream dispatch.

## C01 Implementation Plan

### Objective

Implement C01 as the Rockbox-style document package completer with an industrial-design consultant role. C01 consumes C00; it does not re-ask product requirements. It diagnoses missing C01 material, collects user preferences, applies basic ID knowledge for options and risk warnings, and outputs machine-editable first-pass ID scripts and constraints that human ID designers and downstream engineering layers can consume.

### Runtime Components

- **C01 Template Loader**: loads `c01_id.template.json` and `c01_id.rubric.json`, validates all target outputs and gates.
- **Visual Requirement Extractor**: reads C00 PRD state and extracts visual form, exposed components, user-facing interface, display/status behavior, CMF direction, and unresolved visual decisions.
- **Reference Image Intake**: accepts user-provided reference images as preference evidence, extracts visible form/CMF/UI cues through the C01 skill or available vision model, stores only traceable cue summaries and file references, and requires user confirmation before treating cues as product preferences.
- **C01 Scaffold Tool**: creates Rockbox canonical slots `C01-ID/Ai file/`, `C01-ID/CMF/`, `C01-ID/Display UIUX/`, plus `Interface_Constraints.json` and `Handoff_to_ID_Designer.md` as support artifacts.
- **C01 Emit Tool**: generates deterministic Rockbox-like first-pass scripts: `Ai file/Design_Direction.md`, `CMF/CMF_Direction.md`, `Display UIUX/UIUX_Requirements.md`, `Interface_Constraints.json`, and `Handoff_to_ID_Designer.md`. Optional SVG/Figma/Illustrator carriers may come later, but MVP readiness depends on non-empty structured scripts with draft/decision/owner markers.
- **C01 Readiness Tool**: scores artifact gates and downstream gates for C02, C03, C04, and C05.
- **Concept Image Prompt Support**: the C01 skill may generate concept-image prompts from accumulated C00/C01 visual requirements whenever enough appearance intent exists. External image generation is an optional add-on and, when explicitly configured with an image provider/API key, may produce reference images for communication. Generated images are not required for C01 readiness and must fail fast if the configured API key/provider is unavailable.

### AI Workflow Skill Contract

- Build and load a dedicated `c01-industrial-design-requirements` skill before treating C01 as ready for users.
- Use C00 as the source of product intent; do not duplicate C00 PRD questioning.
- Ask only visual/source questions: form archetype, primary face, visible sensor treatment, CMF direction, UI/status expression, antenna/connector treatment.
- When the user uploads or references images, analyze them as preference evidence: identify reusable cues, ask what the user likes/dislikes, and generalize into design intent instead of copying the reference.
- Treat user preference collection as a first-class workflow, not a side note: unanswered preferences remain `missing`; AI suggestions remain `drafted`; explicit no-preference is recorded as `no-preference`.
- Keep final aesthetics, brand approval, CMF samples, and production ID sign-off as human/ID gates.
- Preserve electrical/RF/mechanical conflicts as explicit blockers or accepted risks, never as silent design choices.
- Keep an explicit `known_gaps` / learned-patterns section in the skill so real C01 sessions can improve the framework over time without pretending the LLM already has full industrial-design expertise.

### Skill Build Order

1. Create the `c01-industrial-design-requirements` skill package from `c01_skill_build_plan.md`.
2. Seed the skill with Rockbox C01 targets, C00 input mapping, CMF framework, Display/UIUX script rules, exposed-interface checklist, downstream constraint map, and risk map.
3. Add C01 mode/session contract: C00 may trigger C01 mode; C01 may ask C01-scoped follow-ups; unresolved product decisions return to C00.
4. Make Rockbox-like script output the first acceptance target: all three canonical C01 targets must have non-empty scripts before C01 is considered usable.
5. Add examples only from known sources or real project sessions; do not import arbitrary GitHub app behavior as authority.
6. After the skill exists, implement deterministic MCP tools for template loading, extraction, scaffold, emit, and readiness.

### Next Interaction Implementation

1. Add a C01 answer-state schema with field states: `missing`, `answered`, `drafted`, `no-preference`, `external-needed`, `blocked`, and `accepted-risk`.
2. Add a preference question bank for user-answerable decisions: form archetype, visual style, CMF, exposed component treatment, UI/status behavior, POC fidelity, and approval owner.
3. Add `bodesign_c01_next_question` to return the single highest-value missing question and the artifact/downstream gate it unblocks.
4. Add `bodesign_c01_update_answers` to merge a user answer, regenerate the Rockbox-like package, and recompute readiness.
5. Upgrade `bodesign_c01_readiness` to inspect field states and blocker ownership, not only file existence/non-empty checks.
6. Harden `Interface_Constraints.json` so every exposed component carries owner, status, downstream targets, and risk notes.

### Reference Image Intake Implementation

1. Allow C01 sessions to accept image file paths or uploaded image attachments as reference evidence for form, CMF, UI/status, component treatment, or general mood.
2. Extract `reference_cues` with fields such as `source_image`, `cue_type`, `observed_cue`, `user_confirmation`, `target_artifact`, and `notes`.
3. Keep unconfirmed cues as `reference-derived`; only user-confirmed cues may become `answered` preferences.
4. Persist reference summaries and source paths in C01 handoff artifacts when useful; do not store API keys or private provider metadata.
5. Add copyright/style-safety guidance: do not copy a specific product or brand design; translate references into generalized intent language.

### Optional Concept Image Implementation

1. Let the C01 skill produce concept, moodboard, and UI concept prompts directly from the current C01 scripts when the user requests a visual reference.
2. Add deterministic prompt artifacts for `Concept_Image_Prompts.md`, `Moodboard_Prompts.md`, and `UI_Concept_Prompts.md` if prompt persistence becomes useful for handoff.
3. If image generation is implemented, expose it as an explicit add-on tool such as `bodesign_c01_generate_concept_image`, not as part of core readiness.
4. Read provider credentials only from explicit environment/config entries; never store API keys in repo artifacts.
5. Fail fast when the selected provider/API key is missing; do not silently fallback to another provider or generic image path.
6. Record output image path, provider/model, prompt, timestamp, and limitation statement in `Concept_Reference.md`.

## C02/C03/C04 Engineering Loop Implementation

Rockbox document numbering is authoritative for deliverables and vendor handoff: C02 remains ME and C03 remains EE/circuit. Execution order is not encoded by the `Cxx` number; execution loops may let C03 circuit constraints lead C02/C04 convergence without renumbering the documents.

### C03 Circuit Lead Responsibilities

- C03 is the first hard engineering constraint source after C01 because it identifies real components, connectors, heat sources, RF/antenna choices, battery/charger constraints, ESD/EMC needs, and component height envelopes.
- C03 outputs must provide C02/C04 with mechanical-relevant constraints: component footprints/heights, external connector requirements, heat-source map, battery envelope, antenna keepouts, cable openings, and ESD/EMC protection notes.
- C03 does not wait for C02 CAD; it provides the first hard engineering entities that make C02 and C04 non-speculative.

## C02 Parametric Enclosure Draft Implementation

### Scope

C02 runtime work should target prototype enclosure drafts, not final production mechanical design. The measurable MVP is: visible to the boss, printable on a home 3D printer, and structured enough for an ME/ID vendor to take over. C02 final CAD generation only runs after C03 circuit constraints and C04 layout geometry are sufficient.

### Tool / Skill / Human Boundary

- **MCP tools** generate deterministic geometry/source/export artifacts from explicit inputs: `Enclosure.scad`, `Enclosure.stl`, optional preferred `Enclosure.skp`, optional unapproved `Enclosure.step`, `SketchUp_Import_Guide.md`, `Mechanical_Constraints.json`, `Mechanical_Assumptions.md`, `Assembly_Notes.md`, `Print_Settings.md`, and `Vendor_Handoff.md`.
- **C02 skill** acts as a mechanical design consultant: asks user-answerable questions, explains printability, thermal, RF, compliance, and assembly tradeoffs, maps C01/C03/C04 dependencies, and decides whether missing data blocks CAD generation or remains an adjustable parameter.
- **Human/vendor** owns final PCB/mechanical dimensions, slicing/printing fit iteration, STEP/assembly approval, tolerance stackup, DFM, waterproofing, strength, thermal, and production sign-off.

### Implementation Stage Order

1. `bodesign_c02_readiness` — already implemented as constraint readiness before CAD generation. It reports `brief_ready` / `source_ready`, owner-tagged blockers, and whether CAD source/openings can be attempted. It deliberately does not claim printable/STL/SKP/STEP readiness.
2. `bodesign_c02_emit_enclosure_package` — next implementation slice. Scaffold C02-ME and deterministic support docs even when CAD export is blocked: `Mechanical_Constraints.json`, `Mechanical_Assumptions.md`, `Assembly_Notes.md`, `Print_Settings.md`, `Vendor_Handoff.md`, and SketchUp fallback guidance.
3. `bodesign_c02_generate_openscad` — generate OpenSCAD source for a simple enclosure from explicit board outline, mounting strategy, wall/clearance parameters, openings, component heights, battery, heat, RF, and keepout data.
4. `bodesign_c02_export_stl` — call local OpenSCAD/CadQuery export when available; return `export_unavailable` when missing. `viewable_draft_ready` and `printable_draft_ready` require a real STL and print assumptions.
5. `bodesign_c02_export_skp` — optional preferred SketchUp output; require an explicit SketchUp-capable converter/Ruby/vendor toolchain and return `skp_export_unavailable` otherwise. Native SKP is not required for vendor handoff if STL/DAE/OBJ import guidance exists.
6. `bodesign_c02_export_step` — optional draft-only engineering handoff when a capable CAD toolchain exists; output must be marked `draft_unapproved` and cannot imply ME approval.

### C02 Verification Plan

- **No-guess test**: missing board outline or mounting holes remain `engineering_pending`; tools do not fabricate hidden dimensions.
- **Package test**: C02 package emitter creates every support artifact and preserves owner-tagged pending constraints.
- **Source test**: generated parametric source includes board size, wall thickness, clearances, openings, and assumptions.
- **Export test**: unavailable CAD/export toolchain returns explicit status and still keeps source/support docs.
- **SketchUp test**: if native SKP export is unavailable, tools emit `SketchUp_Import_Guide.md` and do not claim `Enclosure.skp` exists.
- **STEP test**: optional STEP output is marked `draft_unapproved`; missing STEP toolchain returns explicit unavailable status.
- **Handoff test**: vendor handoff states what is AI-generated, what is assumed, what the vendor must refine, and which Rockbox C02 targets remain vendor-owned.
- **Approval test**: AI cannot mark `me_approved` without explicit external/human evidence.

### Verification Plan

- **Template completeness test**: the three Rockbox canonical outputs (`Ai file`, `CMF`, `Display UI/UX`) are declared separately from support artifacts, with human/AI/tool boundaries.
- **Skill behavior test**: C01 skill stays inside external appearance/human-interface scope and does not redo C00 product discovery or claim final ID approval.
- **Extraction test**: C00 visual/interface fields produce normalized exposed-component and placement-zone constraints.
- **Reference image test**: uploaded/reference images produce traceable cue summaries that remain `reference-derived` until user confirmation.
- **Scaffold test**: C01-ID folder contains all target files with no fabricated approved content.
- **Emitter test**: Rockbox-like script outputs are created for `Ai file`, `CMF`, and `Display UI/UX`; each includes visible draft/assumption/decision/owner markers.
- **Readiness test**: missing primary face, exposed component list, or UI/status model blocks relevant downstream gates.
- **No-fallback test**: absent visual decisions remain `missing`/`drafted`; no arbitrary product style or placement silently passes.
- **Optional image test**: concept image generation does not affect C01 readiness; missing API key/provider returns an explicit error while prompt-only output remains available.
