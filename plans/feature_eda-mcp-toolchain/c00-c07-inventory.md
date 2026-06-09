# C00-C07 Intermediate Artifact Inventory

Source project: `thesmart_products/openmv/`

Purpose: classify the real OpenMV/STM32N657/aiguard run artifacts before promoting anything else into bodesign MCP. This prevents overfitting to C04 scripts while also avoiding duplicate work for capabilities already landed in workflow-core/MCP.

## Classification Legend

- `already-integrated`: Equivalent bodesign workflow/MCP capability already exists.
- `promote-to-mcp`: Should become a callable MCP tool.
- `promote-to-workflow-core`: Should become deterministic package/workflow logic, not a low-level tool.
- `template/package-output`: Generated deliverable shape; useful as output/template, not a tool by itself.
- `fixture/evidence-only`: Useful regression fixture or validation evidence.
- `discard-one-off`: Execution scratch or one-off script not worth productizing directly.
- `blocked-needs-decision`: Needs dependency, architecture, or product decision.

## Summary

| Stage | Artifact families found | Classification | Decision |
|---|---|---|---|
| C00 | `Project_Requirements.md/.docx` | already-integrated + template/package-output | Covered by `bodesign_c00_scaffold_prd`, `bodesign_c00_update_answers`, `bodesign_c00_emit_prd`, `bodesign_c00_readiness`; keep this project output as fixture/evidence. |
| C01 | `Interface_Constraints.json`, `CMF_Direction.md`, `Design_Direction.md`, `UIUX_Requirements.md`, `Handoff_to_ID_Designer.md` | already-integrated + template/package-output | Covered by C01 package/readiness/question/reference-image tools; no new MCP needed. |
| C02 | `Mechanical_Constraints.json`, `Enclosure.scad`, `Enclosure.step`, print/vendor/SketchUp handoff docs | already-integrated + template/package-output | Covered by C02 readiness/package/OpenSCAD/STL/SKP/STEP tools; `Enclosure.step` remains generated output evidence, not proof of final ME approval. |
| C03 | design docs, BOM/pinmap spreadsheets, KiCad schematic/netlist/ ERC/BOM outputs, `Mechanical_Constraint_Export.json` | partially integrated | Mechanical constraint export exists; schematic/netlist/BOM bridge tools also exist. Remaining reusable gap is a C03 pin-map normalization/export primitive feeding C05. |
| C04 | `Layout_Constraints.json`, KiCad PCB/pro/routed outputs, routing shell scripts, EDA Python tools, DRC/SI/length/map reports, Gerber/drill/render/assembly outputs | partially integrated + promote-to-mcp | Layout package/readiness and first routing MCP tools exist. Remaining promoted tools: impedance solve, widen bus tracks, length-match bus, Gerber preview, and possibly C04 build/finish orchestration. |
| C05 | `Pin_Map_Bridge.json`, FW spec/state/module/task docs | already-integrated + workflow gap | Covered by `bodesign_c05_scaffold_fw_spec` and readiness. Reusable gap is upstream C03→C05 pin-map normalization so agents do not hand-author bridge JSON. |
| C06 | `Verification_Summary.json`, `Test_Plan.md`, `Bring_Up_Checklist.md` | already-integrated | Covered by `bodesign_c06_assemble_test_plan` and readiness. Need future linkage from C04 DRC/SI + simulation/EMC/thermal tools into C06 verdict ingestion. |
| C07 | `Manufacturing_Transfer.md` | promote-to-workflow-core | No dedicated C07 MCP/workflow tool found. Add C07 manufacturing-transfer assembler/readiness once C04/C06 outputs stabilize. |

## Stage Details

### C00 — Product Requirements

Representative artifact:

- `openmv/C00-PRD/Project_Requirements.md`

Existing bodesign coverage:

- `bodesign_c00_scaffold_prd`
- `bodesign_c00_update_answers`
- `bodesign_c00_emit_prd`
- `bodesign_c00_readiness`
- C00 orchestration status/tick tools

Decision: no new MCP tool. Treat the aiguard PRD as fixture/evidence for C00 emitter quality and cross-stage traceability.

### C01 — Industrial Design / Interface Intent

Representative artifacts:

- `openmv/C01-ID/Interface_Constraints.json`
- `openmv/C01-ID/CMF/CMF_Direction.md`
- `openmv/C01-ID/Ai file/Design_Direction.md`
- `openmv/C01-ID/Display UIUX/UIUX_Requirements.md`
- `openmv/C01-ID/Handoff_to_ID_Designer.md`

Existing bodesign coverage:

- C01 package emitter/readiness/question/update tools.
- C01 concept prompt/reference image tools.

Decision: no new low-level MCP tool. Preserve these as template/package-output examples and fixtures.

### C02 — Mechanical / Enclosure

Representative artifacts:

- `openmv/C02-ME/Mechanical_Constraints.json`
- `openmv/C02-ME/Enclosure.scad`
- `openmv/C02-ME/Enclosure.step`
- `openmv/C02-ME/Print_Settings.md`
- `openmv/C02-ME/Vendor_Handoff.md`
- `openmv/C02-ME/SketchUp_Import_Guide.md`
- `openmv/C02-ME/STEP_Draft_Handoff.md`

Existing bodesign coverage:

- C02 readiness/package/OpenSCAD/STL/SKP/STEP tools.

Decision: no new MCP tool from these artifacts. Keep generated outputs as fixtures for fail-fast export semantics and package content regression.

### C03 — Electrical Engineering

Representative artifacts:

- `openmv/C03-EE/Mechanical_Constraint_Export.json`
- `openmv/C03-EE/generated/sch/*.net`
- `openmv/C03-EE/generated/sch/*.erc.rpt`
- `openmv/C03-EE/generated/sch/*-bom.csv`
- `openmv/C03-EE/generated/symbols/*.kicad_sym`
- C03 spreadsheets for BOM/netlist/pin allocation.

Existing bodesign coverage:

- `bodesign_c03_export_mechanical_constraints`
- schematic/netlist/BOM/KiCad bridge tools in `bodesign_eda_bridge`

Gaps:

- Add/extend a deterministic C03 pin-map normalization/export capability that turns C03 pin allocation sources into the C05 `Pin_Map_Bridge.json` contract.
- Preserve generated KiCad schematic/netlist/ERC outputs as fixtures for EE bridge regression.

Decision: `promote-to-workflow-core` for C03→C05 pin-map bridge normalization; not a shell-script MCP tool.

### C04 — Layout / EDA Runtime

Representative artifacts:

- `openmv/C04-Layout/Layout_Constraints.json`
- `openmv/C04-Layout/generated/tools/net2pcb.py`
- `openmv/C04-Layout/generated/tools/viainpad.py`
- `openmv/C04-Layout/generated/tools/pour.py`
- `openmv/C04-Layout/generated/tools/impedance.py`
- `openmv/C04-Layout/generated/tools/widen.py`
- `openmv/C04-Layout/generated/tools/length_match.py`
- `openmv/C04-Layout/generated/tools/si_check.py`
- `openmv/C04-Layout/generated/tools/gerber_view.py`
- `openmv/C04-Layout/generated/tools/gerber_layer.py`
- `openmv/C04-Layout/generated/tools/gerber_stack.py`
- `openmv/C04-Layout/generated/tools/build_c04.sh`
- `openmv/C04-Layout/generated/tools/finish_c04.sh`
- routed board outputs, DRC/SI/length/map JSON, Gerbers, drill, assembly files, PNG renders.

Existing bodesign coverage:

- C04 layout package/readiness.
- `bodesign_route_net2pcb`
- `bodesign_via_in_pad`
- `bodesign_pour_planes`
- `bodesign_layout_drc_gate`
- `bodesign_si_check`
- `bodesign_autoroute`

Gaps to promote to MCP:

- `bodesign_impedance_solve`
- `bodesign_widen_bus_tracks`
- `bodesign_length_match_bus`
- `bodesign_render_gerber_preview`

Gaps to consider as workflow orchestration:

- `build_c04.sh` and `finish_c04.sh` encode a valuable C04 chain: route if needed, finish, export Gerbers/drill, run DRC, render PNGs, export assembly package, verify manifest. Do not port these as shell wrappers; convert into a typed `bodesign_c04_build_manifest` or workflow-core orchestration that calls MCP primitives and returns explicit gates.

Decision: promote low-level PCB operations to MCP; promote the build/finish shell sequence to workflow-core/MCP orchestration after low-level tools are stable.

### C05 — Firmware / Software Spec

Representative artifacts:

- `openmv/C05-FW/Pin_Map_Bridge.json`
- `openmv/C05-FW/Functional_Spec.md`
- `openmv/C05-FW/State_Machine.md`
- `openmv/C05-FW/Module_Architecture.md`
- `openmv/C05-FW/Task_Breakdown.md`

Existing bodesign coverage:

- `bodesign_c05_scaffold_fw_spec`
- `bodesign_c05_readiness`

Gap:

- Upstream C03 pin-map inputs should be normalized deterministically instead of manually becoming `Pin_Map_Bridge.json`.

Decision: no new C05 output tool; add C03→C05 pin-map bridge normalization as workflow-core capability.

### C06 — Verification

Representative artifacts:

- `openmv/C06-Verification/Verification_Summary.json`
- `openmv/C06-Verification/Test_Plan.md`
- `openmv/C06-Verification/Bring_Up_Checklist.md`

Existing bodesign coverage:

- `bodesign_c06_assemble_test_plan`
- `bodesign_c06_readiness`

Gap:

- C04 DRC/SI/length reports and existing simulation/EMC/thermal tools should feed C06 verdicts without hand-transcription.

Decision: promote report ingestion/rollup to workflow-core later; current package emitter is sufficient for documents.

### C07 — Manufacturing Transfer

Representative artifact:

- `openmv/C07-MFG/Manufacturing_Transfer.md`

Existing bodesign coverage:

- No dedicated C07 workflow/MCP tool found.

Gap:

- Need `bodesign_c07_assemble_manufacturing_transfer` and `bodesign_c07_readiness` once C04 fab outputs and C06 verification summaries are available.

Decision: `promote-to-workflow-core`, not part of the immediate EDA low-level MCP slice unless requested.

## Resulting Backlog

### Immediate C04 MCP Slice

1. `bodesign_impedance_solve`
2. `bodesign_widen_bus_tracks`
3. `bodesign_length_match_bus`
4. `bodesign_render_gerber_preview`

### Workflow-Core Follow-Up Slice

1. C03→C05 pin-map normalization/export.
2. C04 build/finish manifest orchestration over MCP primitives.
3. C06 verdict ingestion from C04 DRC/SI/length and verify-tool outputs.
4. C07 manufacturing-transfer assembler/readiness.

## Evidence Reads

- `openmv/C00-PRD/Project_Requirements.md`
- `openmv/C01-ID/Interface_Constraints.json`
- `openmv/C02-ME/Mechanical_Constraints.json`
- `openmv/C03-EE/Mechanical_Constraint_Export.json`
- `openmv/C04-Layout/Layout_Constraints.json`
- `openmv/C04-Layout/generated/tools/build_c04.sh`
- `openmv/C04-Layout/generated/tools/finish_c04.sh`
- `openmv/C05-FW/Pin_Map_Bridge.json`
- `openmv/C06-Verification/Verification_Summary.json`
- `openmv/C07-MFG/Manufacturing_Transfer.md`
- `services/mcp/server.py`
- `packages/workflow-core/bodesign_workflow_core/c0*.py`
