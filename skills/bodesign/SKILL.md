---
name: bodesign
description: L0 entry router for the hardware product-design lifecycle across C00-C07.
---

# Bodesign Router

This skill routes hardware engineering tasks to specialized skills. It executes no direct actions.

## 1. Primary Workflow Router

Identify the active stage and load the dedicated skill.

| Target Domain | Active Stage | Delegated Skill |
|---|---|---|
| Product Requirements and Architecture | C00 | `bodesign-architect` |
| Industrial Design and CMF | C01 | `stages/c01-id/GUIDE.md` |
| Mechanical Design and Enclosure | C02 | `stages/c02-me/GUIDE.md` |
| Electrical Schematic, BOM and Netlist | C03 | `bodesign-ee` |
| PCB Placement, Routing and DRC | C04 | `bodesign-layout` |
| Firmware Specification | C05 | `stages/c05-fw/GUIDE.md` |
| Hardware Verification and SI | C06 | `bodesign-verify` |
| Manufacturing Transfer and Fab | C07 | `bodesign-release` |

## 2. Supporting Discipline and Tool Skills

Load supporting skills for quality gates and tool execution.

- Quality gates, honesty rules, and Definition of Done standards: load `bodesign-discipline`.
- Reference-derived design contracts and SSOT traceability: load `bodesign-kb`.
- Command-line runner syntax, landing verbs, and tool error codes: load `bodesign-tools`.
- Architecture and diagram emitter references: read `references/concept-diagrams.md`.

## 3. Operating Invariant

Do not load all stage guides at once. Load only the skill mapped to your active step.
