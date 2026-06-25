---
slug: control/deterministic-validation-before-fab
title: Deterministic Validation + User Approval Before Fab
layer: ragbase
type: control
confidence: verified
locator: C07 MFG GUIDE / AGENTS.md §2.3
---
# Deterministic Validation + User Approval Before Fab

No send-to-fab output without passing deterministic validation (DRC gate / crosscheck / SI / SPICE) AND explicit user approval. Reliability is SHOWN by control-group crosscheck, not asserted. The hard gate on C07 release.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c07/mfg/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c07.mfg.guide.md]] @ c07-mfg/GUIDE.md — source_weight 7

## Related

- → `constrains` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- → `constrains` [[workflow/c07-mfg|C07 MFG — manufacturing-transfer readiness]]
- ← `references` [[concept/impl-ir-source-of-truth|BoardDesign IR as Source of Truth]]

