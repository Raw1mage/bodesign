---
slug: workflow/c03-ee
title: C03 EE — design definition → schematic → BOM → netlist → bridges
layer: ragbase
type: workflow
confidence: verified
---
# C03 EE — design definition → schematic → BOM → netlist → bridges

C03 turns product intent (C00) + interface constraints (C01) into the **electrical truth**: design definition, captured KiCad schematic, complete machine BOM, netlist (pin→net), GPIO/interface pinmap, power-frontend, and the `Mechanical_Constraint_Export.json` bridge to C02/C04. This stage **has an execution engine** — the KiCad analysis engine — so you do not eyeball a schematic and assert it correct: run `analyze_schematic.py`, read the structured JSON, and carry every finding with its `confidence` + `evidence_source`.

Flow: define → capture (generate via MCP `compose_schematic`, or author in KiCad) → sync datasheets → run analyzer → verify analyzer output against raw schematic + datasheets (pin-to-net is the highest-value check) → cross-check against a reference control group → export tables → produce the mechanical bridge. Watch gate findings: **DS-001** (datasheet coverage), **SS-001** (MPN <50%, pre-fab blocker), **PP-001** (IC power pin reaches rail only through a cap), **RS-002** (rail depends on an open jumper).

**Required deliverables:** design definition + architecture, power tree, schematic, complete BOM, netlist, GPIO pinmap, `Netlist_Status.md` (iff full netlist not recoverable), `Mechanical_Constraint_Export.json` (`approval=false`), one consolidated `C03_*.docx`. **Re-run the feasibility triage on the firm component set.** Gate: analyzer clean of `high` findings (or each justified); every IC pin-to-net verified vs datasheet. There is no `c03_readiness` tool — the analyzer's gate is the self-check. Missing connectivity is a documented limit (`Netlist_Status.md`), never an invented net.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c03/ee/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c03.ee.guide.md]] @ c03-ee/GUIDE.md — source_weight 7

## Related

- → `output_of` [[concept/artifact-mech-constraints|Mechanical Constraint Export]]
- → `output_of` [[concept/artifact-pin-map|Pin Map Bridge]]
- → `output_of` [[concept/artifact-schematic|Schematic + Netlist + BOM]]
- → `references` [[concept/engine-kicad|KiCad analysis engine (the deterministic verifier)]]
- → `references` [[concept/engine-kidoc|kidoc documentation engine]]
- → `input_to` [[workflow/c02-me|C02 ME — mechanical/enclosure constraints + draft model]]
- → `input_to` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- → `input_to` [[workflow/c05-fw|C05 FW — firmware spec (not code)]]
- → `input_to` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- → `input_to` [[workflow/c07-mfg|C07 MFG — manufacturing-transfer readiness]]
- ← `input_to` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]
- ← `input_to` [[workflow/c01-id|C01 ID — industrial-design direction & interface constraints]]
- ← `constrains` [[concept/honesty-provenance-model|Honesty & provenance model (the soul of bodesign)]]
- ← `constrains` [[concept/canonical-owner|One canonical owner per cross-stage artifact]]
- ← `constrains` [[concept/feasibility-tier|Feasibility triage — how far bodesign takes a product at C04]]
- ← `constrains` [[concept/design-review-g2|Pre-implementation design review (G2 scenario walkthrough)]]
- ← `performs` [[role/bodesign-orchestrator|bodesign orchestrator (the AI running the lifecycle)]]
- ← `performs` [[role/ee-owner|EE owner (signs off the electrical design)]]
- ← `input_to` [[concept/artifact-prd|PRD Requirements Package]]
- ← `constrains` [[control/no-silent-fallback|No Silent Fallback]]
- ← `constrains` [[control/datasheet-grounded-claims|Datasheet-Grounded Electrical Claims]]
- ← `constrains` [[control/design-review-g2|Design Review Gate (G2)]]

## ICOM

- **Inputs**: PRD Requirements Package
- **Controls**: No Silent Fallback (honesty-model.md / AGENTS.md §2), Datasheet-Grounded Electrical Claims (C03 EE GUIDE / AGENTS.md §2.4), Design Review Gate (G2) (cross-stage-reconciliation.md / design-review G2)
- **Outputs**: Mechanical Constraint Export, Pin Map Bridge, Schematic + Netlist + BOM
- **Mechanisms**: bodesign orchestrator (the AI running the lifecycle), EE owner (signs off the electrical design)

