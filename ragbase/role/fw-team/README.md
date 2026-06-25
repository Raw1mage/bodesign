---
slug: role/fw-team
title: Firmware team (owns the code)
layer: ragbase
type: role
confidence: verified
---
# Firmware team (owns the code)

The firmware team that owns the CODE: drivers, ISRs, init sequences, the RTOS-vs-bare-metal decision, the HAL, module APIs, scheduler model, inter-module messaging, memory map. bodesign owns the firmware SPEC only — it never writes source or claims a behaviour is implemented. The C05 package (`Functional_Spec.md`, `Module_Architecture.md`, `State_Machine.md`, `Task_Breakdown.md`, `Pin_Map_Bridge.json`) is the contract they implement against; every pin-map signal carries `responsibility: 'TBD by FW team'`.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c05/fw/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c05.fw.guide.md]] @ c05-fw/GUIDE.md — source_weight 4

## Related

- → `performs` [[workflow/c05-fw|C05 FW — firmware spec (not code)]]

