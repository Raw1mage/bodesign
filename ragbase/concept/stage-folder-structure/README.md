---
slug: concept/stage-folder-structure
title: Stage folder structure — deliverables flat at the root
layer: ragbase
type: concept
confidence: verified
---
# Stage folder structure — deliverables flat at the root

Every `cXX-*/` stage folder is organised so a reader sees the **deliverables immediately**: clean outputs sit flat at the stage root with **no deliverable subfolders**; only two numbered support buckets exist — `01_refs/` (external inputs the stage consumes) and `02_build/` (garbage-collectable intermediates + workspaces + the editable `.md` doc sources). The stage root holds only `README.md`/`CHANGELOG.md` (meta) plus the deliverables.

Conventions: document deliverables ship as **`.docx` in 繁體中文** (the editable `.md` source stays in `02_build/`); every human-facing deliverable carries a **`C0N_` filename prefix**; each `.docx` is **self-contained** (figures/tables embedded, not loose). Intermediate `.md` is never a stage-root deliverable. The deliverables at the root *are* the Definition of Done; readiness tools score them.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/stage/structure/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.stage.structure.md]] @ stage-structure.md: flat-root deliverables, 01_refs/02_build, C0N_ docx, canonical owner — source_weight 6

## Related

- → `constrains` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]

