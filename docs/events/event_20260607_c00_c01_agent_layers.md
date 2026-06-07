# Event: C00/C01 Agent Layer Planning

## 需求

- Clarify C00/C01 roles for the document package scaffold.
- Treat C00 as the user-facing consultant agent and C01 as an industrial-design requirement deepening mode/layer.
- Decide whether C01 should rely on existing skills, external GitHub resources, MCP tools, or a self-built specialist skill.

## 範圍(IN)

- C00/C01 role boundaries and agent responsibilities.
- C01 Rockbox target outputs: `Ai file`, `CMF`, `Display UI/UX`.
- C01 MCP/tool vs AI skill vs human industrial designer boundary.
- C01 skill discovery and self-build strategy.

## 範圍(OUT)

- Final industrial design, CAD, Illustrator `.ai`, CMF sample, or human ID approval.

## 任務清單

- [x] Define C00 as consultant agent / C00 user workspace.
- [x] Define C01 as C00-derived external appearance and human-interface requirement deepening layer.
- [x] Preserve Rockbox C01 canonical targets while downgrading AI-only output to structured scripts/draft carriers.
- [x] Search public GitHub for reusable industrial-design / CMF / design-brief skill candidates.
- [x] Decide to self-build `c01-industrial-design-requirements` from known sources and future project experience.
- [x] Promote Rockbox-like C01 output to the MVP readiness gate.
- [x] Implement C01 Rockbox-like MVP in workflow-core and MCP tools.
- [x] Add initial C01 skill package source under the plan package.
- [x] Refine C01 role to industrial-design consultant plus Rockbox C01 document completer.

## Key Decisions

- C00 is the user-facing product development consultant. Users primarily work in C00.
- C01 is entered by user request or C00/readiness trigger as a specialist mode, not a replacement for C00.
- C01 is not a final design production layer. It produces structured requirement scripts and constraints for ID/ME/EE/FW/Layout.
- Public GitHub discovery did not reveal a ready-to-adopt C01 opencode skill.
- The project should self-build a conservative C01 specialist skill and improve it with real project sessions.
- The first usable C01 capability must generate non-empty structured scripts for `Ai file`, `CMF`, and `Display UI/UX`, plus `Interface_Constraints.json` and `Handoff_to_ID_Designer.md`.
- C01 MVP implementation is script-first: Markdown/JSON now; SVG/Figma/Illustrator are future optional carriers.
- C01's next product step is interactive preference collection: diagnose missing C01 fields, ask user-answerable questions, update answer state, regenerate documents, and recompute readiness.
- C01 can generate concept-image prompts from accumulated appearance requirements as a skill behavior when the user asks for visual references; only external image generation is an optional API-key-backed add-on.
- C01 should support uploaded/reference images as preference evidence: understand what the user likes or rejects, generalize the visual cues, and turn confirmed cues into C01 deliverables without copying a reference design.
- C01 image generation add-on is now wired to Google AI Studio through an explicit MCP tool; API keys are execution-environment configuration, not project artifacts.
- For this phase, the C01 Google credential resolver is server-side: explicit env vars first, then the active `gemini-cli` API account in opencode `accounts.json`; subscription accounts fail fast because the current image endpoint requires an API key.

## Issues Found

- Generic LLM knowledge has C01 common sense but lacks reliable professional industrial-design workflow depth.
- Generic visual/brand/frontend skills are useful support but insufficient as C01 authority.
- C01 must avoid silent defaults for style, placement, CMF, UI/status behavior, and approval status.

## Verification

- GitHub discovery was performed using public repository search for industrial design brief, CMF, product design brief, hardware UI/UX, design handoff, and related terms.
- Plan artifacts updated to include C01 self-build strategy and backlog.
- C01 plan artifacts updated so Rockbox-like script output is a hard MVP gate, not an optional future emitter.
- Implemented deterministic C01 package generation and readiness checks in workflow-core.
- Registered `bodesign_c01_emit_package` and `bodesign_c01_readiness` MCP tools.
- Added unit tests for direct workflow-core use and MCP tool calls.
- Updated C01 skill/plan language so the agent is a consultant with basic ID knowledge, but the measurable target remains completing the Rockbox-like C01 document set.
- Clarified concept-image support: prompt generation can happen immediately from C01 context, while generated image files require an optional explicit provider/API key and must remain reference-only.
- Added reference image intake to the C01 plan: image understanding is part of the skill/input workflow, while deterministic tools may persist cue summaries, source paths, and confirmation status.
- Registered `bodesign_c01_generate_concept_image` as an optional Google AI Studio concept-image add-on with fail-fast missing-key behavior, opencode `accounts.json` active API account support, and reference-only metadata output.
- Expanded C02 planning: C02 is now scoped as an AI-assisted parametric enclosure draft layer with three MVP gates: visible 3D object for the boss, printable STL for home prototyping, and parametric/source/handoff artifacts for ME/ID vendor takeover.
- Clarified C02 responsibility split: MCP tools own deterministic CAD source/export/support-file generation; C02 skill owns mechanical consultant interaction and missing-data judgment; humans/vendors own final STEP, assembly, tolerance, DFM, print fit iteration, and production sign-off.
- Added SketchUp preference: C02 should prefer `Enclosure.skp` for user review when a SketchUp-capable export/import toolchain exists, but must fall back to STL/DAE/OBJ import guidance with explicit `skp_export_unavailable` rather than fabricating SKP output.
- Restored Rockbox document numbering as the authoritative deliverable/vendor boundary: C02 remains ME/enclosure and C03 remains EE/circuit. Execution-loop metadata now carries the fact that C03 circuit constraints may lead C02/C04 convergence without renumbering files.
- Implemented C02 constraint-readiness MVP: added `c02-mechanical-enclosure-consultant` skill source, workflow-core readiness assessment, MCP `bodesign_c02_readiness`, and tests. This only decides whether CAD drafting is allowed; it does not generate SCAD/STL/SKP/STEP.
- Expanded C02 implementation plan before further coding: next sequence is package emitter first, then OpenSCAD source generation, then STL export, then optional SketchUp/STEP handoff. Native SKP and STEP remain explicit toolchain-gated add-ons, not baseline readiness requirements.
- Implemented C02 package emitter MVP: added workflow-core `emit_c02_enclosure_package`, MCP `bodesign_c02_emit_enclosure_package`, support-file generation for `Mechanical_Constraints.json`, `Mechanical_Assumptions.md`, `Assembly_Notes.md`, `Print_Settings.md`, `Vendor_Handoff.md`, and `SketchUp_Import_Guide.md`, plus direct/MCP tests. This still does not generate SCAD/STL/SKP/STEP or ME approval.
- Implemented C02 OpenSCAD/STL MVP: added `generate_c02_openscad`, `export_c02_stl`, MCP `bodesign_c02_generate_openscad`, and MCP `bodesign_c02_export_stl`. OpenSCAD source requires explicit board outline, component heights, wall thickness, clearance, and lid clearance; no hidden enclosure dimensions are guessed. Local `openscad` CLI is currently unavailable, so STL export returns `export_unavailable` and does not create a fake STL.
- Updated post-commit plan sequence: implement SketchUp import fallback / explicit native SKP unavailable status first; validate real STL only after OpenSCAD is installed or configured; then add C03 mechanical-relevant constraint export; resume C00 SSOT/PRD runtime after C02 prototype boundaries are stable.
- Implemented C02 SketchUp fallback MVP: added explicit `bodesign_c02_export_skp` unavailable status, refreshed `SketchUp_Import_Guide.md`, and direct/MCP tests proving no native `Enclosure.skp` is fabricated without a configured SketchUp-capable toolchain.
- Implemented C03 mechanical-relevant constraint export: added workflow-core `export_c03_mechanical_constraints`, MCP `bodesign_c03_export_mechanical_constraints`, and direct/MCP tests. The export maps explicit C03 component heights, external connectors/openings, heat sources, antenna/RF keepouts, battery envelope, and ESD/EMC notes for C02/C04 while refusing to infer board outline, mounting holes, placement coordinates, or mechanical approval.
- Architecture Sync: Verified (No doc changes). `specs/architecture.md` already records MCP tool handlers, workflow-core, client-owned package outputs, fail-fast/no-final-output constraints, and external-fetch policy gates; this C01 add-on remains an optional MCP handler and does not change module boundaries.

## Remaining

- Define C01 mode/session contract and blocker return format to C00.
- Implement C01 answer state, preference question bank, `bodesign_c01_next_question`, and `bodesign_c01_update_answers`.
- Upgrade C01 readiness from file-level checks to field-state and blocker-owner checks.
- Package/install the C01 skill source into the distributed skill bundle once skill packaging policy is finalized.
- Add C01 reference image intake and traceability so uploaded examples can become confirmed design-intent evidence for the Rockbox-like documents.
- Validate real STL export after OpenSCAD is installed or configured, then proceed to optional STEP/native SKP toolchain gates and C00 SSOT runtime work.
