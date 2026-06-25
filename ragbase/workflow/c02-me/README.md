---
slug: workflow/c02-me
title: C02 ME — mechanical/enclosure constraints + draft model
layer: ragbase
type: workflow
confidence: verified
---
# C02 ME — mechanical/enclosure constraints + draft model

C02 turns upstream form-factor + electrical/interface facts into a **mechanical constraint package** + a **draft enclosure model** an ME/vendor can refine. Consumes C00 form-factor, C01 `Interface_Constraints.json`, and C03 `Mechanical_Constraint_Export.json` (the explicit-only EE facts: component heights, connector openings, heat sources, antenna keepouts, battery envelope).

**Owns:** `Mechanical_Constraints.json` (enclosure contract + `constraint_status`/`approval_status` ledgers), `Mechanical_Assumptions.md`, `Enclosure.scad` (parametric source, all variables derived from constraints), a draft STEP (**only if build123d present** — else `not-run` with reason, never hand-written), and handoff notes (Assembly/Print/STEP/SketchUp/Vendor). **The honest boundary:** constraints + prototype model, NOT a manufacturable enclosure — no production tooling, DFM/tolerance/strength/waterproofing sign-off, or final vendor STEP. `me_approved` is **always false**; the board outline is **provisional** (authoritative outline owned by C04). 

**Environment honesty:** verify `which openscad` / `python3 -c 'import build123d'` before claiming any STL/STEP export. Missing inputs (board outline, heights, mounting) become `engineering_pending` with an owner — never invented. C02 is a lever owner for the **area** and **thermal** cross-stage budgets. Self-verify: `bodesign_c02_readiness`.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c02/me/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c02.me.guide.md]] @ c02-me/GUIDE.md — source_weight 6

## Related

- → `output_of` [[concept/artifact-enclosure|Enclosure CAD Package]]
- → `input_to` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- ← `input_to` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]
- ← `input_to` [[workflow/c01-id|C01 ID — industrial-design direction & interface constraints]]
- ← `input_to` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- ← `constrains` [[concept/cross-stage-reconciliation|Cross-stage reconciliation — escalate-back as a tracked state]]
- ← `performs` [[role/me-vendor|ME / fab vendor (owns manufacturable enclosure)]]
- ← `input_to` [[concept/artifact-id-package|Industrial Design Package]]
- ← `input_to` [[concept/artifact-mech-constraints|Mechanical Constraint Export]]
- ← `constrains` [[control/no-fabrication|No Fabrication of Deliverables]]

## ICOM

- **Inputs**: Industrial Design Package, Mechanical Constraint Export
- **Controls**: No Fabrication of Deliverables (honesty-model.md / AGENTS.md §2)
- **Outputs**: Enclosure CAD Package
- **Mechanisms**: ME / fab vendor (owns manufacturable enclosure)

