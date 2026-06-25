---
slug: concept/artifact-enclosure
title: Enclosure CAD Package
layer: ragbase
type: concept
confidence: verified
locator: C02 ME GUIDE
---
# Enclosure CAD Package

C02 output: Enclosure.scad source → Enclosure.stl / draft STEP (build123d/OCP when present), 2D projection SVG derived from the 3D model (single-source-no-drift). Board outline + mounting + cutout envelope feeding C04 layout.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c02/me/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c02.me.guide.md]] @ c02-me/GUIDE.md — source_weight 5

## Related

- → `input_to` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- ← `output_of` [[workflow/c02-me|C02 ME — mechanical/enclosure constraints + draft model]]

