---
slug: control/design-review-g2
title: Design Review Gate (G2)
layer: ragbase
type: control
confidence: verified
locator: cross-stage-reconciliation.md / design-review G2
---
# Design Review Gate (G2)

Cross-stage design-review gate reconciling C01/C02/C03/C04 before committing to layout/fab: feasibility tier, mechanical/electrical constraint consistency, canonical-owner conflicts. Constrains EE and layout stages.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/cross/stage/reconciliation/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.cross.stage.reconciliation.md]] @ cross-stage-reconciliation.md: BlockerReturn, budget overflow, iterative loop — source_weight 6

## Related

- → `constrains` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- → `constrains` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]

