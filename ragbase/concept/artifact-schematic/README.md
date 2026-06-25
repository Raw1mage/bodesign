---
slug: concept/artifact-schematic
title: Schematic + Netlist + BOM
layer: ragbase
type: concept
confidence: verified
locator: C03 EE GUIDE
---
# Schematic + Netlist + BOM

C03 output: kicad-cli-validated schematic, exported netlist, grouped BOM (qty+MPN, DNP excluded). Reference-design-grounded. Primary electrical input to C04 layout.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c03/ee/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c03.ee.guide.md]] @ c03-ee/GUIDE.md — source_weight 6

## Related

- → `input_to` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- ← `output_of` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]

