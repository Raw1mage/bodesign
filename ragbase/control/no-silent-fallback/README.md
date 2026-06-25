---
slug: control/no-silent-fallback
title: No Silent Fallback
layer: ragbase
type: control
confidence: verified
locator: honesty-model.md / AGENTS.md §2
---
# No Silent Fallback

Missing field / missing geometry / missing datasheet evidence MUST fail fast with an explicit error + gap list — never proceed silently on a default, first-available value, or generic model. The repo's defining governance invariant (C02 never-guesses, orchestration SPINE_NOT_INITIALIZED, spice model_source visible).

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/honesty/model/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.honesty.model.md]] @ honesty-model.md: seven rules + per-stage + litmus test — source_weight 7

## Related

- → `constrains` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]
- → `constrains` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- → `constrains` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- ← `references` [[concept/impl-evidence-gaps|Evidence-Linked Knowledge, Explicit Gaps]]

