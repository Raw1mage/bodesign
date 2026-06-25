---
slug: workflow/c01-id
title: C01 ID — industrial-design direction & interface constraints
layer: ragbase
type: workflow
confidence: verified
---
# C01 ID — industrial-design direction & interface constraints

C01 turns the C00 vision into **design direction** + **measurable interface constraints**. It owns four decisions and one bridge: Design Direction (form archetype, posture, primary face, visual tone), CMF Direction (colour/material/finish + environment rationale), Display/UI-UX status model (the contract the firmware must satisfy), `Interface_Constraints.json` (the machine bridge to C02/C03/C04/C05), and `Handoff_to_ID_Designer.md`.

**The honest boundary:** bodesign authors **direction and constraints, not final art** — no final `.ai`/CMF sample/pixel UI/CAD/sign-off. Every artifact is `draft`/`drafted` until a human ID designer approves; never invent a placement/coordinate/hex value — the honest value is `draft/missing — C01 must ask user or ID designer`. The *electrical* host block diagram is C03's, not C01's.

**Required deliverables (all 5):** `Design_Direction.md`, `CMF_Direction.md`, `UIUX_Requirements.md`, `Interface_Constraints.json` (schema `bodesign.c01.interface_constraints.v1`, every exposed component carries `downstream_targets` + concrete `risk_notes`), `Handoff_to_ID_Designer.md`. Declare the **feasibility tier** in the handoff. Gate: self-check passes, JSON validates, every draft status carries a reason. C01 is never 'approved/final' from inside bodesign — ID/CMF/UI sign-off are human gates. Self-verify: `bodesign_c01_readiness`.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c01/id/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c01.id.guide.md]] @ c01-id/GUIDE.md — source_weight 6

## Related

- → `output_of` [[concept/artifact-id-package|Industrial Design Package]]
- → `input_to` [[workflow/c02-me|C02 ME — mechanical/enclosure constraints + draft model]]
- → `input_to` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- → `input_to` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- → `input_to` [[workflow/c05-fw|C05 FW — firmware spec (not code)]]
- ← `input_to` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]
- ← `constrains` [[concept/feasibility-tier|Feasibility triage — how far bodesign takes a product at C04]]
- ← `performs` [[role/id-designer|ID designer (owns final industrial design)]]
- ← `input_to` [[concept/artifact-prd|PRD Requirements Package]]
- ← `constrains` [[control/no-fabrication|No Fabrication of Deliverables]]

## ICOM

- **Inputs**: PRD Requirements Package
- **Controls**: No Fabrication of Deliverables (honesty-model.md / AGENTS.md §2)
- **Outputs**: Industrial Design Package
- **Mechanisms**: ID designer (owns final industrial design)

