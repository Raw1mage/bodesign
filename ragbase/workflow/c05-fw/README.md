---
slug: workflow/c05-fw
title: C05 FW — firmware spec (not code)
layer: ragbase
type: workflow
confidence: verified
---
# C05 FW — firmware spec (not code)

C05 turns intended behaviour into a **firmware specification package** the FW team builds against: functions, modules, a top-level state model, a task list, and a `Pin_Map_Bridge.json` carrying C03's pin truth into firmware-consumable signal definitions. **The central boundary — read twice:** bodesign owns the SPEC; the FW team owns the CODE. You never write drivers/ISRs/init/HAL/RTOS-choice/source, and never claim a behaviour is implemented or working. Everything is `draft`/spec-level until the FW team implements and C06 verifies.

Consumes C00 PRD §s07 (software requirements), C01 UI/UX status model (the *Minimum States To Resolve* rows whose `C05 Firmware Dependency` column was written for you), and the C03 GPIO pinmap (the pin truth). Flow: functional spec → module architecture (candidate stubs, open decisions left to FW) → state machine → task breakdown → pin-map bridge → testable-behaviours list for C06.

**Required deliverables (all 6):** `Functional_Spec.md`, `Module_Architecture.md`, `State_Machine.md`, `Task_Breakdown.md`, `Pin_Map_Bridge.json` (**derived from C03's pinmap — zero invented pins**, every signal `responsibility: 'TBD by FW team'`), `Firmware_Build_Notes.md`. Gate: every function traces to PRD §7; every state to PRD §7 + C01; every pin to a C03 row; FW-team decisions honestly marked open. Behaviours are testable, never tested. Self-verify: `bodesign_c05_readiness`.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c05/fw/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c05.fw.guide.md]] @ c05-fw/GUIDE.md — source_weight 6

## Related

- → `output_of` [[concept/artifact-fw-spec|Firmware Spec Package]]
- → `input_to` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- ← `input_to` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]
- ← `input_to` [[workflow/c01-id|C01 ID — industrial-design direction & interface constraints]]
- ← `input_to` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- ← `performs` [[role/fw-team|Firmware team (owns the code)]]
- ← `input_to` [[concept/artifact-prd|PRD Requirements Package]]
- ← `input_to` [[concept/artifact-pin-map|Pin Map Bridge]]

## ICOM

- **Inputs**: PRD Requirements Package, Pin Map Bridge
- **Controls**: _(none)_
- **Outputs**: Firmware Spec Package
- **Mechanisms**: Firmware team (owns the code)

