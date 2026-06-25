---
slug: control/datasheet-grounded-claims
title: Datasheet-Grounded Electrical Claims
layer: ragbase
type: control
confidence: verified
locator: C03 EE GUIDE / AGENTS.md §2.4
---
# Datasheet-Grounded Electrical Claims

Any electrical spec claim must first be grounded via datasheet_lookup / vault_spec_check; RCA gated by rca_spec_audit. A spec value with no datasheet source = BLOCKING, never guessed. Constrains EE schematic capture and verification.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c03/ee/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c03.ee.guide.md]] @ c03-ee/GUIDE.md — source_weight 7

## Related

- → `constrains` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- → `constrains` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- ← `references` [[concept/impl-evidence-gaps|Evidence-Linked Knowledge, Explicit Gaps]]

