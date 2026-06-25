---
slug: concept/artifact-mech-constraints
title: Mechanical Constraint Export
layer: ragbase
type: concept
confidence: verified
locator: C03 EE GUIDE / cross-stage reconciliation
---
# Mechanical Constraint Export

C03→C02/C04 handoff: Mechanical_Constraint_Export.json — component heights, external connectors/openings, heat sources, antenna/RF keepouts, battery envelope, ESD/EMC notes. Never inferred; only exported from real circuit data.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c03/ee/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c03.ee.guide.md]] @ c03-ee/GUIDE.md — source_weight 6

## Related

- → `input_to` [[workflow/c02-me|C02 ME — mechanical/enclosure constraints + draft model]]
- → `input_to` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- ← `output_of` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]

