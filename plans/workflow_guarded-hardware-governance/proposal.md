# Proposal: workflow_guarded-hardware-governance

## Why

Current AI hardware agents (including bodesign C03–C04 pipelines) frequently suffer from **state drift, coordinate hallucination, role conflation, and unconstrained action spaces** when conducting schematic capture and PCB layout. In complex board designs, without strict institutional guardrails:
1. LLM agents jump directly to routing before component placements or netlists are reconciled.
2. Authoring agents self-approve substandard designs due to lack of adversarial verification separation.
3. Minor pin-polarity or missing passive errors (e.g. absent feedforward capacitors, inverted common-anode LEDs) compound silently into unrecoverable routing failures.
4. When errors occur, agents engage in unauthorized, ad-hoc workarounds rather than structured exception escalation.

The open-source `zhoushoujianwork/easyeda-agent` demonstrates the power of Typed Actions, Micro-State Machines, and Circuit Blocks. This proposal elevates those technical primitives into a formal **IDEF0 A2A Institutional Regime (多 Agent 責任分層與制度治理體系)**:
- Establishing clean multi-agent labor division across 6 specialized roles.
- Enforcing upstream deliverables strictly as immutable `:control` constraints.
- Isolating adversarial verification into a dedicated `Verification Adversary`.
- Funneling all failures through a centralized `Blocker Hub (A5)` for directed repair.
- Mandatory cryptographic receipt handoffs disclosing unmeasured axes (`not_checked`).

## Original Requirement Wording (Baseline)

"看來它的治理層確實值得參考。很好奇他的做法是否真能讓agent變得更聰明的工作。用a2a idef0 plan-builder拆解他的原理，重建為自己的plan，與現有系統C03-C04調和。"
"務必把工作流設計成idef0 a2a制度"

## Requirement Revision History

- 2026-10-22: Initial proposal formulated based on architectural deconstruction of `zhoushoujianwork/easyeda-agent`.
- 2026-10-22: Institutional upgrade to formal IDEF0 A2A regime, establishing 5-activity ICOM decomposition, 6-role authority boundaries, and Blocker-Hub exception arbitration.

## Effective Requirement Description

1. **IDEF0 A2A Institutional Stratification**: Define a rigorous multi-agent governance system specifying 6 specialized roles (`Systems Architect`, `EE Designer`, `Layout Specialist`, `Verification Adversary`, `Release Engineer`, `Orchestrator Duty Officer`) across 5 IDEF0 activities (A1–A5).
2. **Immutable Upstream Controls**: Treat upstream deliverables (PRD requirements, netlist SSOT, placement boundaries) as non-negotiable `:control` inputs to downstream agents.
3. **Blocker-Hub Centralized Arbitration (A5)**: Mandate that all exceptions produce structured `BLK-nnn.json` records and route through Activity A5, eliminating autonomous uncoordinated workarounds.
4. **Mechanical Pass & Unmeasured Disclosure**: Separate mechanical validation from deliverable acceptance; mandate explicit enumeration of `not_checked` verification axes.
5. **Harmonized Micro-State Transitions**: Govern C03 (`S0–S5`) and C04 (`P0–P7`) via signed cryptographic receipts.

## Scope

### IN
- Formal definition of IDEF0 A2A activities (A1–A5), ICOM arrow topologies, and role bindings.
- Centralized Blocker-Hub (A5) exception logging and directed repair routing protocol.
- C03 micro-states (`S0_SPEC_FROZEN` to `S5_C03_LOCKED`) and C04 micro-states (`P0_BOARD_BOUNDED` to `P7_FAB_RELEASED`).
- Schema and verification contract for Verified Circuit Blocks (`packages/workflow-core/circuit_blocks/`).
- Deterministic layout tidy algorithms (`grid_snap`, `distribute_passives`, `silk_tidy`) in `workflow-core`.
- Visual DRC crop generation specification using `pygerber` / `gerber-core`.

### OUT
- Re-implementing EasyEDA's `.eext` browser extension (bodesign targets headless, deterministic EDA toolchains).
- Eliminating human-in-the-loop sign-off for final physical fab release.

## Non-Goals

- Allowing authoring agents to self-approve or bypass gates.
- Replacing KiCad/pcbnew with external proprietary cloud EDAs.

## Constraints

- Zero silent fallbacks: every sub-state transition requires explicit, non-empty validation receipts.
- Pure Python execution for landing plane checkers (`gate.py`), avoiding token roundtrips for deterministic math.
- Institutional separation: no agent session may approve its own structural deliverables.

## What Changes

- `packages/workflow-core`: Gains `substate_machine.py`, `blocker_hub.py`, `circuit_blocks/`, and `tidy/`.
- `skills/bodesign/`: Updated stage guides (C03 and C04) enforcing IDEF0 A2A roles, micro-step transitions, and receipt checks.
- `services/mcp/`: Exposes `bodesign_apply_circuit_block`, `bodesign_layout_tidy`, and visual DRC crop metadata in `bodesign_layout_drc_gate`.

## Capabilities

### New Capabilities
- `a2a_institutional_governance`: Enforces role stratification, upstream control immutability, and blocker-hub routing.
- `governed_microstate_engine`: Enforces step-by-step state transitions with signed receipt tokens across C03 and C04.
- `verified_circuit_blocks`: Reusable sub-circuit blocks pre-packaged with DRC/DFM and placement topology constraints.
- `layout_tidy_primitives`: Deterministic silkscreen orientation/clearance repair and passive array alignment.
- `visual_drc_crop`: Deterministic sub-image rasterizer centered on DRC violation coordinates for agent multimodal verification.

### Modified Capabilities
- `check_c03`: Integrated as the mandatory gatekeeper for transition `S4 -> S5`.
- `layout_drc_gate`: Enriched with visual crop artifacts when violations are found.

## Impact

- Eliminates role conflation and self-approval defects across multi-agent hardware engineering rounds.
- Prevents conversational agents from skipping placement preflight or netlist reconciliation.
- Standardizes exception recovery through structured blocker records (`BLK-nnn.json`).
