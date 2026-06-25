---
slug: role/me-vendor
title: ME / fab vendor (owns manufacturable enclosure)
layer: ragbase
type: role
confidence: verified
---
# ME / fab vendor (owns manufacturable enclosure)

The mechanical engineer / fab vendor who owns DFM sign-off, tolerance/draft/undercut approval, waterproofing/strength/thermal validation, the final refined STEP, and production injection-mould tooling. bodesign produces mechanical constraints + a prototype model; `me_approved` stays `false` inside bodesign. `Vendor_Handoff.md` + `STEP_Draft_Handoff.md` are the entry points; the vendor returns a refined STEP, assembly approach, DFM risks, and a quote.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/stages/c02/me/guide/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.stages.c02.me.guide.md]] @ c02-me/GUIDE.md — source_weight 4

## Related

- → `performs` [[workflow/c02-me|C02 ME — mechanical/enclosure constraints + draft model]]

