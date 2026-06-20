# BR: C01 Rockbox-Style ID Deliverable Package

Status: fixed

## Summary

bodesign C01 should be able to emit a from-zero ID deliverable structure that mirrors the Rockbox C01 package shape: ID-native source bucket, CMF package bucket, Display UI/UX package bucket, plus the five bodesign companion artifacts. When native ID tools are unavailable, bodesign should produce clearly labelled draft substitutes rather than leaving C01 with only loose supplemental diagrams.

## Reference Pattern

Rockbox C01 demonstrates the expected deliverable layout:

- `02.rockbox/c01-id/Ai file/Rockbox II_ID design_20241027.ai`
- `02.rockbox/c01-id/CMF/ROCKBOX II_CMF.pdf`
- `02.rockbox/c01-id/Display UI_UX/Rockbox 2nd gen_UI_UX_20240719.pdf`
- `02.rockbox/c01-id/Design_Direction.md`
- `02.rockbox/c01-id/CMF_Direction.md`
- `02.rockbox/c01-id/UIUX_Requirements.md`
- `02.rockbox/c01-id/Interface_Constraints.json`
- `02.rockbox/c01-id/Handoff_to_ID_Designer.md`

For from-zero products, bodesign should generate equivalent draft-native outputs and keep them explicitly non-final.

## Problem

The current C01 workflow emits the five core companion artifacts, but it has no formal generator for the ID-native buckets that make Rockbox C01 demo-complete:

- `Ai file/`
- `CMF/`
- `Display UI_UX/`

As seen in the `thesmart_products/03.aiguard` workflow, this pushes agents toward manually maintained diagrams such as `face_map.png`. Those diagrams can drift from `Interface_Constraints.json`, C02 envelope evidence, and C03/C04 constraints, and they are not owned by a bodesign C01 emitter.

## Requirements

### 1. Emit an ID visual/source package

Add a C01 tool such as:

```text
bodesign_c01_emit_id_visual_package(folder, envelope, constraints, out_dir)
```

Expected outputs:

- `C01-ID/Ai file/<product>_ID_skeleton.svg`
- `C01-ID/Ai file/<product>_ID_skeleton.figma.json` or `figma_import_spec.json`
- `C01-ID/Ai file/README.md`

Rules:

- SVG/Figma spec must be generated from structured inputs: `Interface_Constraints.json`, C02/C03 envelope evidence, exposed components, placement preferences, and risk notes.
- Do not fabricate `.ai`. Emit `.ai` only if a real Illustrator-compatible export path exists.
- Every visual must carry visible `draft / not final industrial design` markings.

### 2. Emit a CMF draft package

Add a C01 tool such as:

```text
bodesign_c01_emit_cmf_package(folder, constraints, out_dir)
```

Expected outputs:

- `C01-ID/CMF/<product>_CMF_Direction.pdf`
- `C01-ID/CMF/cmf_tokens.json`
- `C01-ID/CMF/README.md`

The package should include material family, finish, colour routes, RF-transparent zones, gasket/sealing notes, sample/vendor gates, and explicit `not CMF approval` labels.

### 3. Emit a Display UI/UX draft package

Add a C01 tool such as:

```text
bodesign_c01_emit_uiux_package(folder, uiux_requirements, out_dir)
```

Expected outputs:

- `C01-ID/Display UI_UX/<product>_UIUX_Flow.pdf`
- `C01-ID/Display UI_UX/uiux_frames.svg` or `uiux_wireframes.svg`
- `C01-ID/Display UI_UX/README.md`

The package should cover OLED screens/states, LED state vocabulary, module insert/remove feedback, privacy/local-only state, charging/connectivity/error states, and explicit `not UI sign-off` labels.

### 4. Extend C01 readiness

Extend `bodesign_c01_readiness` to report separate readiness tracks:

- Core companion readiness: the five source-of-truth C01 artifacts.
- Optional/demo ID-native package readiness: `Ai file/`, `CMF/`, `Display UI_UX/` generated or preserved draft outputs.

Generated visuals must not be required for final ID approval and must not promote a C01 package from draft to approved.

## Tool Gaps

- Figma MCP/tool may be unavailable. In that case, emit `figma_import_spec.json` as an intermediate artifact.
- Illustrator `.ai` output must not be faked; use SVG/PDF/Figma JSON unless a legitimate exporter is available.
- PDF assembly should use docxmcp or an approved bodesign document pipeline.
- All visual outputs must be deterministic and re-runnable from C01/C02/C03 data.

## Acceptance Criteria

- A from-zero C01 package can produce `Ai file/`, `CMF/`, and `Display UI_UX/` draft deliverable buckets without manual drawing.
- Generated outputs trace back to `Interface_Constraints.json` and envelope evidence.
- Generated outputs visibly state `draft`, `not final ID`, `not CMF approval`, and/or `not UI sign-off` as appropriate.
- The five core companion artifacts remain the source of truth for downstream stages.
- `bodesign_c01_readiness` reports companion readiness separately from optional visual/demo package readiness.
- No fabricated approvals, final artwork claims, CMF sample approvals, Figma source claims, or `.ai` source claims appear.

## Notes

The current manual C01 face-map correction in `thesmart_products/03.aiguard` should be treated as a temporary draft supplement. Once this capability exists, regenerate or supersede that manual artifact through the formal C01 bodesign emitter.
