# C02 ME Enclosure Draft Plan

## Positioning

C02 is the mechanical engineering layer for turning C00 product intent, C01 ID/human-interface direction, C03 circuit constraints, and C04 layout geometry into a physical enclosure draft. Unlike C01, C02 must produce something spatially inspectable: a 3D object that the user can view, prototype, and hand off to a mechanical vendor.

C02 does not claim production mechanical sign-off. It targets a constraint-first POC/prototype enclosure that is good enough to visualize, 3D print, and hand to an ME/ID vendor for strengthening after C03/C04 constraints are sufficient.

## MVP Success Criteria

1. **The boss can see it** — produce a 360-degree inspectable enclosure draft such as `Enclosure.skp` when a SketchUp-capable toolchain is configured, or `Enclosure.stl` / optional renders as the baseline viewable artifact.
2. **The user can print it** — produce a home-3D-printer-oriented `Enclosure.stl` plus `Print_Settings.md` with material, wall thickness, clearance, orientation, and support assumptions.
3. **A vendor can take over** — produce parametric source and handoff notes so an ME/ID vendor can turn the draft into a proper `3D File (.step)` and `Introduction of Assembly`.

## Target Output Package

```text
C02-ME/
├─ Enclosure.scad                # OpenSCAD parametric source, MVP-friendly
├─ Enclosure.stl                 # 360-degree inspectable / printable draft
├─ Enclosure.skp                 # Optional preferred SketchUp review artifact when export/import tooling exists
├─ Enclosure.step                # Optional engineering handoff target when toolchain supports it
├─ SketchUp_Import_Guide.md      # How to open/import the draft in SketchUp when native SKP is unavailable
├─ Mechanical_Assumptions.md     # Board, hole, battery, clearance, material, and pending assumptions
├─ Assembly_Notes.md             # PCB mounting, lid/base, screws, battery, cable, and access notes
├─ Print_Settings.md             # Prototype printing guidance and tolerance assumptions
├─ Mechanical_Constraints.json   # Machine-readable geometry, hole, opening, keepout, and status data
└─ Vendor_Handoff.md             # What the ME/ID vendor must refine, verify, quote, and return
```

Rockbox C02 canonical targets remain `3D File (.step)` and `Introduction of Assembly`. In bodesign MVP, `Enclosure.stl`, optional `Enclosure.skp`, and `Enclosure.scad` are AI/tool-generated prototype drafts; final STEP and assembly documents remain vendor/human-ME authority unless the CAD toolchain can generate a draft STEP explicitly marked as unapproved.

SketchUp is the preferred review format for this user. Because `.skp` is not as broadly CLI-generatable as STL/STEP, native `Enclosure.skp` is an optional tool-assisted output. If SketchUp export is unavailable, bodesign must still provide an STL/DAE/OBJ-compatible import path and a `SketchUp_Import_Guide.md` rather than pretending SKP was generated.

## Workflow Phases

- **C02-pre**: after C01/C03, collect mechanical/layout constraints, environmental targets, thermal/RF/EMC/compliance risks, and layout requests for C04. Do not generate final enclosure CAD here.
- **C02-check**: after C04 layout, inspect board outline, mounting holes, connector coordinates, component heights, heat sources, antenna keepouts, openings, and assembly feasibility.
- **C02-final**: only after constraint readiness passes, generate parametric enclosure source and viewable/printable draft artifacts.

## Implementation Stages

### Stage 1 — Package Emitter

Goal: make C02 useful before CAD generation is possible.

- Tool: `bodesign_c02_emit_enclosure_package`.
- Inputs: `out_dir`, optional C00/C01/C03/C04 summaries, explicit `constraints`, optional `prototype_intent`, optional `printer_profile`.
- Outputs: `Mechanical_Constraints.json`, `Mechanical_Assumptions.md`, `Assembly_Notes.md`, `Print_Settings.md`, `Vendor_Handoff.md`, and `SketchUp_Import_Guide.md` when SKP is not available.
- Behavior: all missing board, hole, connector, battery, heat, RF, and material data remain `engineering_pending` with owner and reason.
- Acceptance: creates a vendor-readable package and readiness result, but does not claim `source_ready`, `viewable_draft_ready`, or `printable_draft_ready`.

### Stage 2 — OpenSCAD Source Generator

Goal: produce a deterministic parametric source only from explicit geometry.

- Tool: `bodesign_c02_generate_openscad`.
- Required inputs: board outline, wall thickness, lid/base style, clearance, at least one mounting strategy, and explicit openings or a declaration that no openings are currently known.
- Optional inputs: mounting holes, connector openings, camera/mic/LED/button openings, battery pocket, antenna keepout, heat vent zones, screw size, printer tolerance.
- Outputs: `Enclosure.scad` and updated `Mechanical_Assumptions.md` / `Mechanical_Constraints.json`.
- Behavior: missing dimensions become named OpenSCAD parameters only when safe; unsafe missing dimensions block source generation.
- Acceptance: `source_ready` can become true only when the source file and assumption ledger exist.

### Stage 3 — STL Export

Goal: make the draft visible and printable when local tooling exists.

- Tool: `bodesign_c02_export_stl`.
- Toolchain: OpenSCAD CLI preferred for `.scad`; CadQuery/FreeCAD may be later alternatives.
- Outputs: `Enclosure.stl`, export metadata, and updated `Print_Settings.md`.
- Behavior: if the local exporter is missing, return `export_unavailable` and keep the source/support docs intact.
- Acceptance: `viewable_draft_ready` and `printable_draft_ready` require a real STL file plus print assumptions.

### Stage 4 — SketchUp / STEP Handoff

Goal: support the user's SketchUp review preference and vendor handoff without pretending native SKP is always possible.

- Tool: `bodesign_c02_export_skp` is optional and must require an explicitly configured SketchUp-capable toolchain.
- Fallback: always emit `SketchUp_Import_Guide.md` explaining how to import STL/DAE/OBJ into SketchUp when native SKP is unavailable.
- STEP: `Enclosure.step` is optional and may be produced only by a capable CAD toolchain; it must be marked `draft_unapproved`.
- Acceptance: `vendor_handoff_ready` requires source, assumptions, constraints, assembly notes, print/view artifact, and vendor handoff; it does not require native SKP.

## Responsibility Split

### MCP Tool Responsibilities

- Generate deterministic parametric enclosure drafts from explicit geometry inputs.
- Emit `Enclosure.scad` or another parameterized CAD source without inventing hidden dimensions.
- Run available local CAD/export tools such as OpenSCAD or CadQuery when installed.
- Export `Enclosure.stl` for 360-degree viewing and home 3D printing.
- Export `Enclosure.skp` only when a SketchUp-capable converter, SketchUp Ruby automation, or supported vendor toolchain is explicitly configured.
- Generate a `SketchUp_Import_Guide.md` for importing STL/DAE/OBJ into SketchUp when native SKP export is unavailable.
- Export draft `Enclosure.step` only when the configured toolchain supports it; otherwise fail fast or mark `not_generated`.
- Generate deterministic support files: `Mechanical_Assumptions.md`, `Assembly_Notes.md`, `Print_Settings.md`, `Mechanical_Constraints.json`, and `Vendor_Handoff.md`.
- Mark missing PCB outline, mounting holes, connector positions, component heights, battery dimensions, antenna keepouts, and material choices as `engineering_pending`, not guessed defaults.

Candidate tools:

- `bodesign_c02_emit_enclosure_package`
- `bodesign_c02_generate_openscad`
- `bodesign_c02_export_stl`
- `bodesign_c02_export_skp` — optional, requires explicit SketchUp-capable toolchain
- `bodesign_c02_export_step` — optional, draft-only when supported
- `bodesign_c02_readiness`

### C02 Agent / Skill Responsibilities

- Act as a mechanical design consultant, not a production ME sign-off authority.
- Translate C00/C01 intent into user-answerable mechanical questions: use posture, size class, access needs, print material, lid style, serviceability, and prototype fidelity.
- Explain tradeoffs in plain language: wall thickness, clearance, screw posts, snap fits, printer tolerance, support material, and assembly order.
- Decide when a missing datum blocks CAD generation versus when it can be recorded as an adjustable parameter.
- Read C01 `Interface_Constraints.json`, C03 circuit component/thermal/RF constraints, and C04 board/connector/height data when available.
- Produce vendor-facing context: what is AI-generated, what is assumed, what must be checked by ME, and what the vendor should return.
- Never silently turn C01 visual preference into fixed mechanical dimensions when C03/C04 data is pending.

### Human / Vendor Responsibilities

- User/boss decides prototype intent: visual review, hand-fit, electronics fit check, demo enclosure, or vendor RFQ package.
- User or EE/Layout provides real PCB dimensions, mounting holes, connector locations, component heights, battery dimensions, and antenna/RF constraints.
- ME/ID vendor owns final STEP, assembly design, tolerance stackup, structural strength, manufacturability, waterproofing, thermal design, and production sign-off.
- Home 3D printer operator owns slicing, material behavior, support removal, and fit iteration.

## Input Dependency Model

- **C00**: product intent, use case, environment, budget/fidelity expectations.
- **C01**: visible surfaces, preferred form class, exposed component intent, UI/status constraints.
- **C03**: connector types, component heights, battery, heat sources, RF/ESD/EMC constraints, and electrical modules.
- **C04**: board outline, mounting holes, connector coordinates, keepouts, antenna areas.
- **C06**: prototype validation goals such as fit check, drop/handling, thermal smoke test, or demo readiness.

## Fail-Fast Rules

- If no board outline is available, generate only a mechanical brief and parameter template; do not fabricate board dimensions.
- If no mounting-hole data is available, omit screw posts or mark them as placeholder parameters.
- If OpenSCAD/CadQuery/export tools are unavailable, still emit source and handoff docs, but return explicit `export_unavailable` status for STL/STEP.
- If native SKP export is requested but no SketchUp-capable toolchain is configured, return explicit `skp_export_unavailable` and emit `SketchUp_Import_Guide.md` for the available 3D artifact.
- If requested output implies production sign-off, stop and require human/ME approval.

## Readiness Levels

- `brief_ready`: C02 vendor brief exists, but CAD inputs are incomplete.
- `source_ready`: parametric CAD source exists with explicit assumptions.
- `viewable_draft_ready`: SKP or STL/DAE/OBJ importable preview artifact exists and review assumptions are recorded.
- `printable_draft_ready`: STL exists and print assumptions are recorded.
- `vendor_handoff_ready`: source, draft 3D output, assumptions, constraints, assembly notes, and vendor requests are present.
- `me_approved`: only after human/ME vendor review; never set by AI alone.
