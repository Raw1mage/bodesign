---
slug: role/bodesign-orchestrator
title: bodesign orchestrator (the AI running the lifecycle)
layer: ragbase
type: role
confidence: verified
---
# bodesign orchestrator (the AI running the lifecycle)

The AI agent running bodesign is the **orchestrator**: it identifies the current stage, opens only that stage's GUIDE, follows its SOP, runs the readiness/gate self-check, and respects the handoff. It also runs the cross-stage reconciliation scan each time it would advance or report done (`list_blockers(unresolved_only=True)`), and drives both the bodesign MCP (generation) and the local engines (analysis/validation). It owns the honesty contract end-to-end: marks unproven things `draft`/`pending`/`not-run` with reasons, never fabricates an approval/verdict, and never flips a human-approval flag (`human_approved`, `me_approved`) to true itself.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/skill/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.skill.md]] @ SKILL.md spine: lifecycle table, router, DoD, design-review G2, debug-cost G6, MCP relationship — source_weight 5

## Related

- → `performs` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]
- → `performs` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- → `performs` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- → `performs` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]

