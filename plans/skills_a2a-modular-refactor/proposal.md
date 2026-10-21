# Proposal: skills_a2a-modular-refactor

## Why

The current bodesign skill (`skills/bodesign/SKILL.md`) is a 476-line monolith. It bundles routers, discipline rules, stage specifications, CLI syntax, and legacy tables into a single file. This design causes heavy cognitive load on agents (476 lines versus the 120-line budget in `skill-creator`).

Furthermore, the A2A production pipeline (`workflow_a2a-production-pipeline`) defined 6 specialized worker roles, but its bindings continued to point every role to the monolithic `bodesign` skill because modular skills did not exist. Finally, `lint-ste.py` reports 57 hard SCTE violations in `skills/bodesign/SKILL.md`.

Refactoring the skill system into layered, role-aligned skills resolves agent cognitive overload and aligns with the fleet-wide `skill-creator` standard.

## Original Requirement Wording (Baseline)

- "載入新的skill creator skill，檢核bodesign的技能系統是否讓agent認知負載過高。是否有責任分工a2a，是否遵守scte"
- "前幾天不是才重構過，怎麼還這麼亂，找出那個plan"
- "go"

## Requirement Revision History

- 2026-10-21: Initial proposal drafted to decouple bodesign skills into layered, role-specific packages compliant with `skill-creator` and SCTE rules.

## Effective Requirement Description

1. Refactor `skills/bodesign/` into a modular multi-skill architecture following the Five-Layer Model in `skill-creator`.
2. Extract L0 Router into a concise `skills/bodesign/SKILL.md` (capped at 80 lines).
3. Extract L1 Discipline into `skills/bodesign-discipline/SKILL.md` to govern honesty rules, DoD gates, and content criteria.
4. Extract L2/L3 role-specific skills for A2A workers:
   - `skills/bodesign-ee/` for EE Designer (schematic, BOM, netlist, PC-001 decoupling).
   - `skills/bodesign-layout/` for Layout Specialist (placement, routing, DRC, castellation).
   - `skills/bodesign-release/` for Release Engineer (fab package, gerber verification, IPC-D-356).
5. Extract L4 Tool details into `skills/bodesign-tools/SKILL.md` for `gate.py` and analyzer scripts.
6. Clean all SCTE violations across all new and updated skill files (`lint-ste.py` reports 0 hard violations).
7. Update `plans/workflow_a2a-production-pipeline/bindings.json` to bind modular skills to their respective A2A roles.
8. Sync skill capability projections via `opencode skill resync`.

## Scope

### IN
- Restructuring `skills/bodesign/` files and directories.
- Creating `skills/bodesign-discipline/`, `skills/bodesign-ee/`, `skills/bodesign-layout/`, `skills/bodesign-release/`, and `skills/bodesign-tools/`.
- SCTE cleanup with `lint-ste.py`.
- Updating `plans/workflow_a2a-production-pipeline/bindings.json`.
- Projecting skills via OpenCode capability projection.

### OUT
- Changes to backend Python packages under `packages/`.
- Modifications to CT105 Docker deployment or container images.
- Changes to MCP tool schemas in `services/mcp/server.py`.

## Non-Goals

- Rewriting the underlying KiCad or ngspice analysis engines.
- Deprecating existing stage guides under `stages/` (guides remain referenced by specialized skills).
- Introducing speculative fallback mechanisms.

## Constraints

- Every `SKILL.md` must stay below 120 lines.
- No semicolons permitted in skill files (STE Rule 8.1).
- Sentence length capped at 25 words per sentence.
- Strict single-layer assignment per skill.

## What Changes

- `skills/bodesign/SKILL.md`: Replaced by a lightweight L0 router directing tasks to specialized skills.
- `skills/bodesign-discipline/SKILL.md`: New L1 discipline skill holding the Honesty Model and Definition of Done.
- `skills/bodesign-ee/SKILL.md`: New L2/L3 skill for schematic authoring and electrical verification.
- `skills/bodesign-layout/SKILL.md`: New L2/L3 skill for board placement, routing, and DRC gating.
- `skills/bodesign-release/SKILL.md`: New L2/L3 skill for manufacturing package assembly and release gating.
- `skills/bodesign-tools/SKILL.md`: New L4 skill documenting CLI verbs and engine invocations.
- `plans/workflow_a2a-production-pipeline/bindings.json`: Updated role bindings targeting modular skills.

## Capabilities

### New Capabilities
- `bodesign-discipline`: Unified L1 quality and honesty enforcement for hardware deliverables.
- `bodesign-ee`: Granular schematic authoring instructions for EE agents.
- `bodesign-layout`: Granular placement and layout guidance for layout agents.
- `bodesign-release`: Granular fab release package guidance for release agents.
- `bodesign-tools`: Low-level tool invocation reference for landing verbs and analyzer engines.

### Modified Capabilities
- `bodesign`: Replaced monolithic guide with clean L0 router.

## Impact

- All A2A worker sessions in bodesign will load concise, targeted skills, saving over 70% context overhead per session.
- Zero SCTE regressions across all bodesign skill manifests.
