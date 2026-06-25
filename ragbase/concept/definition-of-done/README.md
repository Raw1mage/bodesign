---
slug: concept/definition-of-done
title: Definition of Done — dod_ok, not readiness_pct
layer: ragbase
type: concept
confidence: verified
---
# Definition of Done — dod_ok, not readiness_pct

Every stage has a fixed **Required deliverables — Definition of Done** block at the top of its GUIDE. This is a contract, not a menu: when you enter a stage, commit to producing its *entire* required set in one pass, then report. The anti-pattern this kills: doing one or two artifacts, narrating what *could* be produced, and stopping until asked again.

A stage is **NOT done** until every required deliverable either exists on disk OR carries an explicit `blocked`/`not-run` status with a reason and an owner. Silent absence is forbidden; an honest blocked artifact is allowed.

Critically: **`readiness_pct: 100` ≠ done.** The readiness tools enforce each GUIDE's DoD as a machine-checkable manifest; the real gate is **`dod_ok: true`** — true only when every Required-deliverable is `present` (or honestly deferred via `dod_status.json`) AND no `answered` field is *fake-complete* (a `TBC`/placeholder hiding under `answered`). Self-verify against the `guide_compliance` block, never the bare percentage. A stage is also not done while an open cross-stage reconciliation names it in `affected_downstream_layers`.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/skill/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.skill.md]] @ SKILL.md spine: lifecycle table, router, DoD, design-review G2, debug-cost G6, MCP relationship — source_weight 6

## Related

- → `constrains` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]

