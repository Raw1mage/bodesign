---
slug: workflow/c00-prd
title: C00 PRD — author the product requirements contract
layer: ragbase
type: workflow
confidence: verified
---
# C00 PRD — author the product requirements contract

C00 fixes **what we're building, why, for whom, to which targets** — honestly. It is the head of the lifecycle; inputs are external (product brief, optional reference design, optional prior PRD). Built as an **answer-state model** (`answer_state.json`, 12 sections s01–s12 + RF appendix rf01–rf03, every field initialised `missing`), then rendered to source-of-truth markdown.

**Owns:** product vision/strategy, system architecture (block diagram), requirements split by discipline (ID/ME, EE, SW), and the **targets** downstream must honour (cost, quantity EVT/DVT/MP, certification, schedule), roles, assumptions, PM cadence. **Does NOT own** schematic/BOM/pin (C03), enclosure CAD (C02), CMF/UX detail (C01), FW code (C05), any test verdict/compliance (C06/C07).

Field states each need a reason: `missing`/`drafted`/`answered`/`external-needed`/`blocked`/`accepted-risk`. **Required deliverables:** `answer_state.json`, `Project_Requirements.md`, `RF_Requirements.md` (iff RF), `C00_Handoff_Report.md`. **Gate (PRD freeze):** every gating section answered or explicitly accepted-risk/external-needed with owner; downstream handoff gates ready; `human_approved: true` set by the named approver (never by the AI). Targets are not results; certification is external-lab. Self-verify: `bodesign_c00_readiness` + boundary check (no C03/C05 detail leaked) + evidence check (every value sourced).

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c00/prd/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c00.prd.guide.md]] @ c00-prd/GUIDE.md — source_weight 6

## Related

- → `output_of` [[concept/artifact-prd|PRD Requirements Package]]
- → `input_to` [[workflow/c01-id|C01 ID — industrial-design direction & interface constraints]]
- → `input_to` [[workflow/c02-me|C02 ME — mechanical/enclosure constraints + draft model]]
- → `input_to` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- → `input_to` [[workflow/c05-fw|C05 FW — firmware spec (not code)]]
- → `input_to` [[workflow/c07-mfg|C07 MFG — manufacturing-transfer readiness]]
- ← `constrains` [[concept/honesty-provenance-model|Honesty & provenance model (the soul of bodesign)]]
- ← `constrains` [[concept/definition-of-done|Definition of Done — dod_ok, not readiness_pct]]
- ← `constrains` [[concept/stage-folder-structure|Stage folder structure — deliverables flat at the root]]
- ← `constrains` [[concept/container-boundary|Container boundary — host paths vs the file model]]
- ← `performs` [[role/bodesign-orchestrator|bodesign orchestrator (the AI running the lifecycle)]]
- ← `input_to` [[concept/artifact-design-intent|Design Intent Spec]]
- ← `constrains` [[control/no-silent-fallback|No Silent Fallback]]

## ICOM

- **Inputs**: Design Intent Spec
- **Controls**: No Silent Fallback (honesty-model.md / AGENTS.md §2)
- **Outputs**: PRD Requirements Package
- **Mechanisms**: bodesign orchestrator (the AI running the lifecycle)

