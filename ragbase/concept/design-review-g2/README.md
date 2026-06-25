---
slug: concept/design-review-g2
title: Pre-implementation design review (G2 scenario walkthrough)
layer: ragbase
type: concept
confidence: verified
---
# Pre-implementation design review (G2 scenario walkthrough)

Between "propose subsystem/layout intent" and "deterministic validation" sits a mandatory `design-review` stage. You reason through failure scenarios against the candidate intent, then record a verdict. The workflow gate (`record_design_review` / `review_gate_status`) verifies a review happened and produced a verdict; the thinking is yours.

Minimum scenario set (skipping an applicable one is a review defect): **power sequencing** (rail bring-up order, inrush), **reset chain** (POR timing, strapping pins), **I2C address conflict** (every 7-bit address incl. straps), **level compatibility** (VIH/VIL/VOH/VOL across domains), **diff-pair topology** (USB/Ethernet/LVDS routing intent, polarity, AC coupling). Each scenario gets `{name, walkthrough, conclusion, severity}`. Verdict ∈ APPROVE / APPROVE_WITH_CONCERNS / REJECT. REJECT keeps deterministic validation blocked; a missing review record blocks it too (`REVIEW_MISSING`). Persists to `_design_review/design_review.json` — reviews that live only in chat are not reviews.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/skill/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.skill.md]] @ SKILL.md spine: lifecycle table, router, DoD, design-review G2, debug-cost G6, MCP relationship — source_weight 5

## Related

- → `constrains` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- → `constrains` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]

