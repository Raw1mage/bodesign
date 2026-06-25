---
slug: concept/container-boundary
title: Container boundary — host paths vs the file model
layer: ragbase
type: concept
confidence: verified
---
# Container boundary — host paths vs the file model

The bodesign MCP runs inside a Docker container (per-user compose project `bodesign-${USER}`, managed only via `./mcpctl.sh`). The container's mount namespace is narrow: only `<repo>/.run`, the sessions volume, and the vault volume are visible. Everything else on the host (project folders, FUSE mounts, /home, /tmp) is **invisible** to every tool — readability from your shell says nothing about container visibility.

Readiness tools return `root_visible: false` + a warning for an invisible/typo'd root. **Never** treat `readiness_pct: 0` as "deliverables missing" without first confirming `root_visible: true`. For unmounted trees use the **file model**: upload a tarball to `POST /files` (or `bodesign_stage_dir`) → get `{token, doc_dir}` → pass `token` + relative `folder`, or the absolute `doc_dir`. Readiness scoring only needs text/json — exclude heavy binaries (.glb, PNG, generated KiCad output) from uploads.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/container/boundary/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.container.boundary.md]] @ container-boundary.md: mount namespace, root_visible, file model — source_weight 5

## Related

- → `constrains` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]
- ← `references` [[concept/impl-product-boundary|Host-Agnostic MCP Product Boundary]]

