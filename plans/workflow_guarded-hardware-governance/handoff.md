# Handoff: workflow_guarded-hardware-governance

## Execution Contract

The executing agent must deliver a complete, zero-silent-fallback implementation of the IDEF0 A2A institutional regime, C03-C04 micro-state machine, Blocker Hub, verified circuit blocks registry, layout tidy operations, and visual DRC cropper. "Done" is defined as:
1. `substate_machine.py` and `blocker_hub.py` pass all unit tests enforcing monotonic state advancement, role separation, and directed repair routing.
2. Verified circuit block definitions for USB-C, LDO, and ESD load cleanly and inject validated footprints/nets into `BoardDesign IR`.
3. `silk_tidy` successfully eliminates test-case silkscreen overlaps without mutating pad coordinates.
4. `layout_drc_gate` generates visual PNG crops upon simulated DRC violations.
5. All generated receipts carry `verdict: "MECHANICAL_PASS"` and explicitly enumerate unmeasured axes (`not_checked`).

## Required Reads

- `specs/architecture.md`: Modules, C00-C07 lifecycle, core vs worker separation, R13/R15 standards.
- `plans/workflow_a2a-production-pipeline/design.md`: IDEF0 A2A architectural precedent and Blocker Hub topology.
- `skills/bodesign/references/c03_workflow.md` & `c04_workflow.md`: Existing stage guides and gate integration points.
- `packages/workflow-core/bodesign_workflow_core/checkers/check_c03.py`: R1-R8 rules and `not_checked` contract.

## Stop Gates In Force

- **Institutional Role Separation Gate**: No authoring agent may verify or sign off on its own work.
- **Circuit Block Approval Gate**: Any new circuit block added to the repository library must be reviewed against verified manufacturer datasheets.
- **Fab Release Approval Gate**: Transitioning to `P7_FAB_RELEASED` requires clean mechanical DRC (`violations=0`) and explicit human sign-off (天條 3).

## Execution-Ready Checklist

- [x] IDEF0 5-activity functional decomposition and GRAFCET blocker-hub models verified.
- [x] Data schema, error codomain catalogs, and 6-role session bindings authored.
- [x] Compatibility with existing C03-C04 platform gates and A2A precedent confirmed.
