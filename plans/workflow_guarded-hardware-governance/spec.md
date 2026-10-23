# Specification: Governed Hardware Design Workflow under IDEF0 A2A Institutional Regime (C03-C04)

## Purpose

This specification establishes an institutional multi-agent governance system (IDEF0 A2A 制度) for autonomous hardware engineering agents operating across bodesign's C03 (Schematic Synthesis) and C04 (PCB Layout & Routing) stages. It mandates strict separation of concerns across 6 specialized roles, enforces upstream deliverables as immutable `:control` constraints, governs state transitions via cryptographic receipts, and routes all exceptions through a centralized Blocker Hub.

## Requirements

### Requirement: Institutional Multi-Agent Role Stratification (A2A Roles)

The system SHALL divide execution responsibilities among 6 discrete agent roles across 5 IDEF0 activities:
1. `Systems Architect`: Ingests PRD requirements, defines interface boundaries, and certifies state locks.
2. `EE Designer`: Authorizes schematic wiring, component selection, and circuit block expansion.
3. `Layout Specialist`: Authors physical placement, geometric alignment (`grid_snap`), and routing.
4. `Verification Adversary`: Independently executes deterministic validation gates (`check_c03`, `placement_preflight`, `layout_drc_gate`). Self-approval by authoring agents is strictly prohibited.
5. `Release Engineer`: Assembles manufacturing deliverables and signs release manifests.
6. `Orchestrator Duty Officer`: Manages the Blocker Hub (A5), triaging exceptions and routing repairs.

#### Scenario: Authoring agent attempts to self-approve layout DRC
- Given a `Layout Specialist` session that has completed routing.
- When the `Layout Specialist` attempts to mint an approval receipt without delegating to `Verification Adversary`.
- Then the governance engine rejects the receipt with `GOV_SELF_APPROVAL_PROHIBITED: verification must be executed by verification-adversary`.

### Requirement: Immutable Upstream Controls (ICOM Topology)

Downstream activities SHALL consume upstream deliverables strictly as `:control` ports:
- The output of A1 (Pin Allocations, Mandated Passives) controls A2 schematic synthesis.
- The output of A2 (Signed C03 Lock Receipt, Netlist SSOT) controls A3 physical placement.
- The output of A3 (Signed P3 Preflight Receipt, Placement Bounds) controls A4 routing and DRC.
Downstream agents are strictly forbidden from modifying upstream control artifacts.

#### Scenario: Layout agent attempts to alter netlist to ease routing congestion
- Given a `Layout Specialist` encountering routing congestion around an MCU.
- When the layout agent attempts to swap pins in the netlist to untangle trace crossings.
- Then the engine halts execution with `GOV_CONTROL_VIOLATION: netlist is immutable control from A2; request pin reallocation via Blocker Hub`.

### Requirement: Centralized Blocker-Hub Exception Routing (Activity A5)

When any deterministic gate or preflight check fails, the executing agent SHALL NOT attempt ad-hoc workarounds. Instead, the agent SHALL:
1. Log a structured `BLK-nnn.json` record containing `error_code`, `owning_activity`, and `evidence`.
2. Diverge execution to Activity A5 (Blocker Hub).
3. The Orchestrator Duty Officer reviews the blocker and dispatches a directed repair work order back to the designated owning activity.

#### Scenario: DRC clearance violation triggers blocker routing
- Given a trace-to-pad clearance violation during `P6_DRC_AND_VISUAL_CLOSED`.
- When `layout_drc_gate` fails.
- Then the agent emits `BLK-004.json` with visual crop attachments; the Blocker Hub assigns repair directly to `Layout Specialist` with exact coordinate targets.

### Requirement: C03 Schematic Micro-State Transitions (S0-S5)

The C03 workflow engine SHALL enforce a monotonic micro-state sequence for schematic synthesis:
1. `S0_SPEC_FROZEN`: Baseline PRD and interfaces locked by Systems Architect.
2. `S1_PARTS_RESOLVED`: Components resolved against Component KB / datasheets.
3. `S2_BLOCKS_EXPANDED`: Common peripheral circuits applied via verified circuit blocks.
4. `S3_NETS_WIRED`: Functional interconnections established; net labels assigned.
5. `S4_CHECK_C03_VERIFIED`: `check_c03` rules R1-R8 executed with 0 blocking violations.
6. `S5_C03_LOCKED`: Frozen Netlist, BOM, and Pin Allocation exported with signed receipt.

#### Scenario: Early netlist export without R1-R8 validation
- Given an agent that has wired nets in `S3_NETS_WIRED`.
- When the agent attempts to transition to `S5_C03_LOCKED` without a verified S4 receipt.
- Then the governance engine rejects the request with typed error `GOV_TRANSITION_BLOCKED: missing_prerequisite_state=S4_CHECK_C03_VERIFIED`.

### Requirement: C04 Layout Micro-State Transitions (P0-P7)

The C04 workflow engine SHALL govern PCB layout and routing through the following monotonic stages:
1. `P0_BOARD_BOUNDED`: Board outline and keepouts imported from C02 mechanical spec.
2. `P1_TOPOLOGY_PLACED`: Core ICs, edge connectors, and high-speed paths placed.
3. `P2_PERIPHERAL_TIDIED`: Passives snapped to grid (`grid_snap`) and aligned (`distribute_passives`).
4. `P3_PREFLIGHT_PASSED`: `placement_preflight` and `c04_placement_geometry_gate` clean.
5. `P4_ROUTED`: Escape routing, differential pairs, and auto-routing completed.
6. `P5_PLANES_AND_TIDY`: Ground/power copper poured; silkscreen auto-cleared (`silk_tidy`).
7. `P6_DRC_AND_VISUAL_CLOSED`: `layout_drc_gate` clean with 0 errors; visual crop inspection signed off.
8. `P7_FAB_RELEASED`: Final Gerbers, drill manifests, and SMT files released.

#### Scenario: Agent routes before placement preflight passes
- Given a layout in state `P2_PERIPHERAL_TIDIED`.
- When the agent invokes `bodesign_autoroute`.
- Then the engine halts execution with `GOV_PREFLIGHT_REQUIRED: placement_preflight_unpassed`.

### Requirement: Mechanical PASS vs Deliverable Acceptance & Disclosure

All automated validation receipts SHALL:
1. Explicitly state `verdict: "MECHANICAL_PASS"` (`mechanical_axes_only: true`).
2. Disclose all unmeasured verification axes (`not_checked`: `["functional_circuit_simulation", "high_speed_si_pi_simulation", "thermal_fem_analysis", "rf_tuning_and_emc", "human_visual_inspection"]`).
3. Require explicit human approval prior to manufacturing release (`P7_FAB_RELEASED`).

#### Scenario: Fabricating a board without human sign-off
- Given a board that has achieved `MECHANICAL_PASS` in P6.
- When an agent attempts to release the final fab package without human sign-off.
- Then the release gate blocks execution citing 天條 3 (`NO_SEND_TO_FAB_WITHOUT_HUMAN_APPROVAL`).

## Acceptance Checks

1. **Role Authority Check**: Test that an agent attempting cross-role mutation or self-approval is blocked with a deterministic error code.
2. **Immutable Control Verification**: Test that downstream mutations attempting to alter upstream pin allocation or net connectivity are rejected.
3. **Blocker Hub Loop**: Verify that gate failure produces a valid `BLK-nnn.json` record that routes to Activity A5 and resumes correctly after directed repair.
4. **State Machine Strictness**: Verify monotonic step advancement across S0–S5 and P0–P7 with signed receipts.
5. **Disclosure Audit**: Assert that every generated validation receipt carries a non-empty `not_checked` array.
