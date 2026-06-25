---
slug: concept/canonical-owner
title: One canonical owner per cross-stage artifact
layer: ragbase
type: concept
confidence: verified
---
# One canonical owner per cross-stage artifact

The worst structural failure mode is the same data living in three stages and drifting. Each shared artifact has **exactly one owning stage** that produces the canonical copy at its root; every downstream stage that needs it **references that path** (a `01_refs/` mirror or a `_consumed_from` pointer) and adds only its own fields — never an editable duplicate.

- **Mechanical constraints** — owned by C03 (`Mechanical_Constraint_Export.json`); C02 and C04 consume it.
- **Pin/GPIO map** — owned by C03; C05's `Pin_Map_Bridge.json` derives from it (zero invented pins).
- **PRD targets** (cost/qty/cert) — owned by C00; C07 cites them, never restates as truth.

If you find yourself editing the same array in two stages, stop: pick the owner, make the others reference it, leave a `_consumed_from` note. Fix the data in the owner and re-consume.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/stage/structure/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.stage.structure.md]] @ stage-structure.md: flat-root deliverables, 01_refs/02_build, C0N_ docx, canonical owner — source_weight 5

## Related

- → `constrains` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]

