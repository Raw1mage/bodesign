# Tasks: Governed Hardware Design Workflow under IDEF0 A2A Institutional Regime (C03-C04)

## Phase 1: Institutional A2A & Micro-State Governance Foundation
- [x] 1.1 Implement `substate_machine.py` in `packages/workflow-core/` with `C03State` (`S0-S5`) and `C04State` (`P0-P7`). artifact: packages/workflow-core/bodesign_workflow_core/substate_machine.py
- [x] 1.2 Implement `blocker_hub.py` for structured exception logging (`BLK-nnn.json`) and directed repair routing. artifact: packages/workflow-core/bodesign_workflow_core/blocker_hub.py
- [x] 1.3 Implement cryptographic receipt generator with mandatory `not_checked` unmeasured axis disclosure. artifact: packages/workflow-core/bodesign_workflow_core/substate_machine.py
- [x] 1.4 Add unit tests verifying role separation, transition blocking, and invalid state jump prevention. artifact: tests/test_substate_machine_and_blocker_hub.py

## Phase 2: Verified Circuit Blocks System
- [x] 2.1 Define JSON/Python schema for `CircuitBlockDefinition` (schematic nets, BOM rows, layout constraints). artifact: packages/workflow-core/bodesign_workflow_core/circuit_blocks/schema.py
- [x] 2.2 Create core block library: `usb_c_sink`, `power_ldo_3v3`, `power_dcdc_buck`, `esd_protection_array`. artifact: packages/workflow-core/bodesign_workflow_core/circuit_blocks/library.py
- [x] 2.3 Implement block instantiation and netlist merge logic in `workflow-core`. artifact: packages/workflow-core/bodesign_workflow_core/circuit_blocks/manager.py
- [x] 2.4 Add unit tests for circuit block expansion and pin reconcile checks. artifact: tests/test_circuit_blocks.py

## Phase 3: Layout Tidy Primitives
- [x] 3.1 Implement `grid_snap` utility snapping footprints and vias to user-specified grids. artifact: packages/workflow-core/bodesign_workflow_core/tidy/grid.py
- [x] 3.2 Implement `distribute_passives` for uniform linear passive component alignment. artifact: packages/workflow-core/bodesign_workflow_core/tidy/distribute.py
- [x] 3.3 Implement `silk_tidy` for detecting and repairing silkscreen overlaps with component copper pads. artifact: packages/workflow-core/bodesign_workflow_core/tidy/silk_tidy.py
- [x] 3.4 Wire tidy actions into KiCad PCB adapter and verify against test boards. artifact: packages/workflow-core/bodesign_workflow_core/tidy/kicad_adapter.py

## Phase 4: Visual DRC Cropping Pipeline
- [x] 4.1 Implement coordinate parsing from KiCad / DRC violation reports. artifact: packages/workflow-core/bodesign_workflow_core/drc_crop.py
- [x] 4.2 Build PyGerber / KiCad render bounding-box cropping utility (5mm x 5mm window with red highlight). artifact: packages/workflow-core/bodesign_workflow_core/drc_crop.py
- [x] 4.3 Integrate visual crops into `layout_drc_gate` response envelope. artifact: packages/eda-bridge/bodesign_eda_bridge/routing.py
- [x] 4.4 Add fixture-based integration test asserting crop generation on DRC clearance failure. artifact: tests/test_drc_crop.py

## Phase 5: Landing Plane & Multi-Agent Skill Integration
- [x] 5.1 Expose micro-state transition and blocker hub checks in `skills/bodesign/scripts/gate.py`. artifact: skills/bodesign/scripts/gate.py
- [x] 5.2 Update C03 and C04 stage guides in `skills/bodesign/` documenting the 6-role A2A protocol and handoffs. artifact: skills/bodesign/stages/c03-ee/GUIDE.md, skills/bodesign/stages/c04-layout/GUIDE.md
- [x] 5.3 Conduct end-to-end dry run validating multi-agent behavior across full S0->P7 lifecycle. artifact: tests/test_a2a_lifecycle_dryrun.py
