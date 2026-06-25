---
slug: workflow/c07-mfg
title: C07 MFG — manufacturing-transfer readiness
layer: ragbase
type: workflow
confidence: verified
---
# C07 MFG — manufacturing-transfer readiness

C07 produces the **manufacturing-transfer package**: what a fab + assembly house need to build the board, plus the cost/quantity/certification targets that gate whether a build is worth ordering. **The central honesty fact:** a manufacturing-transfer record is *not* a record of a built board. Derived products are **pre-fabrication** — C04 is still a layout draft, so there are no released Gerber/drill/IPC binaries; every fab deliverable is `pending` against the C04-freeze gate and no build is claimed.

Two modes: **(a) derived/in-progress** (produce a readiness record, everything `pending`) or **(b) archive of a real fabricated board** (preserve real fab outputs verbatim under `source/`, never mutate). Flow: confirm the C04 freeze (`fab_release_gate.py`) → generate the transfer scaffold (kidoc `manufacturing` type) → build the status-tracked fab-output inventory → pair the manufacturing BOM+CPL (only after C04 export) → read cost/qty/cert targets from C00 → write the DFM/handoff checklist → status conclusion.

**Owns:** the fab-output inventory (tracked by status), cost/qty targets (read from C00, never invented), certification targets (external-lab gates, never marked passed), the DFM checklist. **Does NOT** own routing/DRC (C04), design-BOM authoring (C03), verification verdicts (C06), or fabrication itself. **Required deliverables:** `Manufacturing_Transfer.md` (load-bearing), fab-output package (when C04 frozen), `mfg_bom.csv`+CPL (after C04 export), cost/qty/cert + DFM checklist. The design BOM ≠ a manufacturing BOM until C04 places parts. Never relax the C04 gate to make outputs 'exist'. No `c07_readiness` tool — use `fab_release_gate.py` + `package_readiness`.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c07/mfg/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c07.mfg.guide.md]] @ c07-mfg/GUIDE.md — source_weight 6

## Related

- → `output_of` [[concept/artifact-fab-package|Manufacturing Fab Package]]
- → `references` [[concept/engine-kidoc|kidoc documentation engine]]
- ← `input_to` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]
- ← `input_to` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- ← `input_to` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- ← `input_to` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- ← `constrains` [[concept/honesty-provenance-model|Honesty & provenance model (the soul of bodesign)]]
- ← `performs` [[role/external-cert-lab|External certification lab (owns the compliance verdict)]]
- ← `input_to` [[concept/artifact-routed-pcb|Routed PCB + Fab Outputs]]
- ← `input_to` [[concept/artifact-validation-evidence|Validation Evidence Package]]
- ← `constrains` [[control/deterministic-validation-before-fab|Deterministic Validation + User Approval Before Fab]]

## ICOM

- **Inputs**: Routed PCB + Fab Outputs, Validation Evidence Package
- **Controls**: Deterministic Validation + User Approval Before Fab (C07 MFG GUIDE / AGENTS.md §2.3)
- **Outputs**: Manufacturing Fab Package
- **Mechanisms**: External certification lab (owns the compliance verdict)

