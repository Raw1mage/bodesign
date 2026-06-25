---
slug: role/external-cert-lab
title: External certification lab (owns the compliance verdict)
layer: ragbase
type: role
confidence: verified
---
# External certification lab (owns the compliance verdict)

The external lab / physical-build process that decides EVT/DVT, FCC Part 15, CE RED, EN 55032 / CISPR 32, IEC 62368-1, RoHS/REACH, and ESD verdicts. bodesign records these as **targets + plans** in `certification_targets[]` and **never** marks them passed — they are decided on a physical build by an external party. C06 produces tool verdicts (pass/warn/fail) only; compliance and EVT/DVT sign-off live here.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c06/verify/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c06.verify.guide.md]] @ c06-verify/GUIDE.md — source_weight 4

## Related

- → `performs` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- → `performs` [[workflow/c07-mfg|C07 MFG — manufacturing-transfer readiness]]

