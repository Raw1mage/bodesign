---
slug: concept/impl-evidence-gaps
title: Evidence-Linked Knowledge, Explicit Gaps
layer: ragbase
type: concept
confidence: verified
locator: specs/architecture.md §Safety / Knowledge base / AI design workflow
---
# Evidence-Linked Knowledge, Explicit Gaps

Implementation corroboration of no-silent-fallback: component knowledge records are evidence-linked and confidence-scored; unknown datasheets MUST produce explicit gaps instead of silent assumptions. The Component Vault fails fast (VAULT-E001/E002) on missing env/dir/corrupt DB, never rebuilt silently. Orchestration reports SPINE_NOT_INITIALIZED rather than a silent fallback — the same governance invariant the honesty-model reference states, verified in code.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/specs/architecture/md/text|text: asset.home.pkcs12.projects.bodesign.specs.architecture.md]] @ specs/architecture.md (full) — source_weight 2

## Related

- → `references` [[control/datasheet-grounded-claims|Datasheet-Grounded Electrical Claims]]
- → `references` [[control/no-silent-fallback|No Silent Fallback]]

