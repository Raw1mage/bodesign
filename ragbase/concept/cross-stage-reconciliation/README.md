---
slug: concept/cross-stage-reconciliation
title: Cross-stage reconciliation — escalate-back as a tracked state
layer: ragbase
type: concept
confidence: verified
---
# Cross-stage reconciliation — escalate-back as a tracked state

bodesign runs mostly forward, but some constraints can only be checked by combining facts several stages own — and when such a check **fails**, the honest response is to send work *back upstream*, not quietly proceed. When a stage computes a **cross-stage budget** (area / thermal / height / power / cost) and it does not close, it MUST emit an open **reconciliation record** — never absorb the overage silently (honesty rule 6 across stages).

This is the existing `BlockerReturn` primitive in `workflow-core.orchestration`: `return_blocker` (emit), `list_blockers(unresolved_only=True)` (scan), `ingest_blocker` (resolve). The record names the quantified delta, lever owners, escalation options routed to their stages, and which stage must act next (`must_act`). It stays `open` until a named stage changes something — or a **human** marks it `accepted_risk` (AI never accepts a cross-stage risk alone).

Two trigger directions: **forward** (design-time budget overflow, C02/C03/C04) and **backward** (verify-time verdict fail at C06 → routes to the owning design stage). Both obey the floating-PSRAM rule: the `must_act` stage resolves by **fixing the design**, never by relaxing the threshold. A downstream stage must not declare done while an open reconciliation names it.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/cross/stage/reconciliation/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.cross.stage.reconciliation.md]] @ cross-stage-reconciliation.md: BlockerReturn, budget overflow, iterative loop — source_weight 1

## Related

- → `constrains` [[workflow/c02-me|C02 ME — mechanical/enclosure constraints + draft model]]
- → `constrains` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]

