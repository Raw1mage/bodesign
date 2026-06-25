---
slug: concept/impl-ir-source-of-truth
title: BoardDesign IR as Source of Truth
layer: ragbase
type: concept
confidence: verified
locator: specs/architecture.md §Safety and State Rules
---
# BoardDesign IR as Source of Truth

Implementation invariant corroborating the honesty/provenance model: BoardDesign IR is the product-owned source of truth for generated/reconstructed layouts. AI suggestions are advisory until converted into typed IR operations; AI does not directly route copper or emit final fabrication files. Deterministic IR validation + bridge export + Gerber validation are required — the code-side echo of the skill's deterministic-validation discipline.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/specs/architecture/md/text|text: asset.home.pkcs12.projects.bodesign.specs.architecture.md]] @ specs/architecture.md (full) — source_weight 2

## Related

- → `references` [[concept/honesty-provenance-model|Honesty & provenance model (the soul of bodesign)]]
- → `references` [[control/deterministic-validation-before-fab|Deterministic Validation + User Approval Before Fab]]

