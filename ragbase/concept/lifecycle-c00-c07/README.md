---
slug: concept/lifecycle-c00-c07
title: C00–C07 hardware product-design lifecycle
layer: ragbase
type: concept
confidence: verified
---
# C00–C07 hardware product-design lifecycle

bodesign organises hardware product design as eight stages: **C00 PRD** (product requirements) → **C01 ID** (industrial design) → **C02 ME** (mechanical/enclosure) → **C03 EE** (electrical: schematic/BOM/netlist) → **C04 Layout** (PCB placement/routing/fab) → **C05 FW** (firmware *spec*, not code) → **C06 Verify** (verdicts + cross-check) → **C07 MFG** (manufacturing transfer).

The chain is **directional but iterative**: later stages feed constraints back (C03 exports a mechanical-constraint JSON for C02/C04; C04 freeze unblocks C07; a C06 verdict-fail routes back to the owning design stage). Each stage's GUIDE names exactly what it receives upstream and what it must hand downstream. The tooling (bodesign MCP) is *just an executor* — doing good work requires knowing the workflow: what each stage consumes/produces, which gate it must pass, and the honesty rules that forbid faking any of it.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/skill/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.skill.md]] @ SKILL.md spine: lifecycle table, router, DoD, design-review G2, debug-cost G6, MCP relationship — source_weight 1

## Related

- ← `references` [[concept/impl-product-boundary|Host-Agnostic MCP Product Boundary]]

