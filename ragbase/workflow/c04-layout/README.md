---
slug: workflow/c04-layout
title: C04 Layout — verified netlist → DRC-clean, gated, fab-ready board
layer: ragbase
type: workflow
confidence: verified
---
# C04 Layout — verified netlist → DRC-clean, gated, fab-ready board

C04 owns the **physical board**: placement, routing, layer stackup, controlled-impedance constraints, the routed `.kicad_pcb`, and the **gated fab + assembly output package**. Takes C03's verified netlist + mechanical/interface constraints; produces a board that is either a **draft** or has passed the C04 gate. **Honour the feasibility tier:** Tier 1–2 is the autonomous lane (route + gate); **Tier 3** is not routable on KiCad+MCP → emit the SI constraint export and hand routing to pro-EDA (the handoff IS the deliverable).

SOP: assemble `Layout_Constraints.json` → define stackup + compute impedance widths (`impedance_solve`) → build the board via MCP (`route_net2pcb`/`autoroute`, one-shot `c04_emit_layout_package`) → finishing chain (`widen_bus_tracks` → `pour_planes` → `length_match_bus` → `si_check`, each DRC-guarded) → cross-check vs C03 + run the fab-release gate.

**The central lesson — the floating-PSRAM false-pass:** a BGA footprint's pad names didn't match the symbol, 24 pads were silently unnetted, yet the gate said COMPLETE. The fix was NOT to relax anything — it made the gate parse DRC honestly + added an unmapped-pad gate. **Never relax a threshold to make a board pass.** The C04 gate (`layout_drc_gate` + `c04_readiness`) HARD-FAILS on: missing board, DRC copper>0 OR unconnected>0, unmapped pads>0, missing fab outputs, SI worst=fail. WARNS on silk overlaps + length-match-over-budget. 'COMPLETE with warns' is a truthful done-state; a clean pass by widening a threshold is not.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c04/layout/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c04.layout.guide.md]] @ c04-layout/GUIDE.md — source_weight 7

## Related

- → `output_of` [[concept/artifact-routed-pcb|Routed PCB + Fab Outputs]]
- → `references` [[concept/engine-kicad|KiCad analysis engine (the deterministic verifier)]]
- → `input_to` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- → `input_to` [[workflow/c07-mfg|C07 MFG — manufacturing-transfer readiness]]
- ← `input_to` [[workflow/c01-id|C01 ID — industrial-design direction & interface constraints]]
- ← `input_to` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- ← `input_to` [[workflow/c02-me|C02 ME — mechanical/enclosure constraints + draft model]]
- ← `constrains` [[concept/honesty-provenance-model|Honesty & provenance model (the soul of bodesign)]]
- ← `constrains` [[concept/feasibility-tier|Feasibility triage — how far bodesign takes a product at C04]]
- ← `constrains` [[concept/si-constraint-handoff|SI constraint handoff — the Tier-3 routing-wall handoff]]
- ← `constrains` [[concept/design-review-g2|Pre-implementation design review (G2 scenario walkthrough)]]
- ← `constrains` [[concept/debug-cost-ordering-g6|Debug cost-ordering discipline (G6)]]
- ← `performs` [[role/bodesign-orchestrator|bodesign orchestrator (the AI running the lifecycle)]]
- ← `input_to` [[concept/artifact-enclosure|Enclosure CAD Package]]
- ← `input_to` [[concept/artifact-mech-constraints|Mechanical Constraint Export]]
- ← `input_to` [[concept/artifact-schematic|Schematic + Netlist + BOM]]
- ← `constrains` [[control/design-review-g2|Design Review Gate (G2)]]

## ICOM

- **Inputs**: Enclosure CAD Package, Mechanical Constraint Export, Schematic + Netlist + BOM
- **Controls**: Design Review Gate (G2) (cross-stage-reconciliation.md / design-review G2)
- **Outputs**: Routed PCB + Fab Outputs
- **Mechanisms**: bodesign orchestrator (the AI running the lifecycle)

