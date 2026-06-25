---
slug: concept/debug-cost-ordering-g6
title: Debug cost-ordering discipline (G6)
layer: ragbase
type: concept
confidence: verified
---
# Debug cost-ordering discipline (G6)

When a verification gate fails (DRC/ERC/SI/reference-crosscheck mismatch), do **not** jump to structural proposals (re-layout, layer-count change, subsystem rework). Most failures have cheap causes. Mandatory order:

1. **Enumerate `simple_fix_candidates` first** and attach to the blocker: each `{hypothesis, check_method, ruled_out, evidence_ref}`. Typical cheap hypotheses — DRC rule parameter wrong (rule file value, not the copper); a single net/pad exception not a systemic problem; footprint pin-definition error (symbol↔footprint mapping); stale generated output (re-run the deterministic tool before trusting the failure).
2. **Rule each candidate out with evidence** — `ruled_out: true` requires an `evidence_ref`; the schema rejects evidence-free rule-outs.
3. **Only after all candidates are ruled_out** may a structural proposal be made (`BlockerReturn.structural_proposal_allowed` is the machine gate).

Same principle as "verify the premise before stacking fixes": a structural change made while a cheap explanation is still alive destroys evidence and multiplies blast radius.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/skill/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.skill.md]] @ SKILL.md spine: lifecycle table, router, DoD, design-review G2, debug-cost G6, MCP relationship — source_weight 5

## Related

- → `constrains` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- → `constrains` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]

