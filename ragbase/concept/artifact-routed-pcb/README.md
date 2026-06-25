---
slug: concept/artifact-routed-pcb
title: Routed PCB + Fab Outputs
layer: ragbase
type: concept
confidence: verified
locator: C04 LAYOUT GUIDE
---
# Routed PCB + Fab Outputs

C04 output: netted+routed .kicad_pcb (placement, pours, length-matched buses, via-in-pad), DRC-gated, plus exported Gerbers/drill/pos/STEP/PDF fab outputs. Input to C06 verification and C07 manufacturing.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c04/layout/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c04.layout.guide.md]] @ c04-layout/GUIDE.md — source_weight 6

## Related

- → `input_to` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- → `input_to` [[workflow/c07-mfg|C07 MFG — manufacturing-transfer readiness]]
- ← `output_of` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]

