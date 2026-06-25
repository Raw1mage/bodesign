---
slug: workflow/c06-verify
title: C06 Verify — evidence → honest pass/warn/fail verdicts
layer: ragbase
type: workflow
confidence: verified
---
# C06 Verify — evidence → honest pass/warn/fail verdicts

C06 owns the **verification record**: it takes what C03/C04 *produced* and decides what they *prove*. A tool run yields a **verdict**, not a certification — C06 converts evidence into pass/warn/fail *only where a tool actually ran*; everything else stays `not-run` with a reason. It is the stage most tempted to over-claim, so it has the strictest honesty contract.

**Does NOT** produce the artifacts it grades (DRC/SI/length-match/netlist come from C04/C03), certify compliance (FCC/CE/CISPR/IEC 62368-1/RoHS/ESD are external-lab gates), sign off EVT/DVT, or invent a measurement. Flow: gather evidence + confirm what ran → **reference cross-check against the control group** (`cross_verify.py`: record `matched`/`missing[]`/`orphans[]` both directions — 'show, don't assert') → fab-release gate → sim companions (SPICE/EMC/thermal — only what is installed) → lifecycle audit → assemble deliverables.

**Required deliverables:** `Verification_Summary.json` (schema `...v1`, the invariant `status:not-run ⇔ has_verdict:false`, external gates in `certification_targets[]` never in `checks[]`), `Test_Plan.md`, `Bring_Up_Checklist.md`, `cross_verify.json`, `EVT_Bringup_Findings.md` (when a board was brought up). A record where SPICE/EMC/thermal are honestly `not-run` and only the cross-check is `pass` is a **legitimate done-state**. A failing verdict with a design owner is routed back via a reconciliation record (`must_act` stage fixes the design, never relaxes the threshold). Self-verify: `bodesign_c06_readiness`.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c06/verify/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c06.verify.guide.md]] @ c06-verify/GUIDE.md — source_weight 7

## Related

- → `output_of` [[concept/artifact-validation-evidence|Validation Evidence Package]]
- → `references` [[concept/engine-kicad|KiCad analysis engine (the deterministic verifier)]]
- → `references` [[concept/engine-kidoc|kidoc documentation engine]]
- → `input_to` [[workflow/c07-mfg|C07 MFG — manufacturing-transfer readiness]]
- ← `input_to` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- ← `input_to` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- ← `input_to` [[workflow/c05-fw|C05 FW — firmware spec (not code)]]
- ← `constrains` [[concept/honesty-provenance-model|Honesty & provenance model (the soul of bodesign)]]
- ← `constrains` [[concept/cross-stage-reconciliation|Cross-stage reconciliation — escalate-back as a tracked state]]
- ← `constrains` [[concept/debug-cost-ordering-g6|Debug cost-ordering discipline (G6)]]
- ← `performs` [[role/bodesign-orchestrator|bodesign orchestrator (the AI running the lifecycle)]]
- ← `performs` [[role/external-cert-lab|External certification lab (owns the compliance verdict)]]
- ← `input_to` [[concept/artifact-routed-pcb|Routed PCB + Fab Outputs]]
- ← `input_to` [[concept/artifact-fw-spec|Firmware Spec Package]]
- ← `constrains` [[control/no-silent-fallback|No Silent Fallback]]
- ← `constrains` [[control/datasheet-grounded-claims|Datasheet-Grounded Electrical Claims]]
- ← `constrains` [[control/deterministic-validation-before-fab|Deterministic Validation + User Approval Before Fab]]

## ICOM

- **Inputs**: Routed PCB + Fab Outputs, Firmware Spec Package
- **Controls**: No Silent Fallback (honesty-model.md / AGENTS.md §2), Datasheet-Grounded Electrical Claims (C03 EE GUIDE / AGENTS.md §2.4), Deterministic Validation + User Approval Before Fab (C07 MFG GUIDE / AGENTS.md §2.3)
- **Outputs**: Validation Evidence Package
- **Mechanisms**: bodesign orchestrator (the AI running the lifecycle), External certification lab (owns the compliance verdict)

