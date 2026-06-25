---
slug: concept/impl-product-boundary
title: Host-Agnostic MCP Product Boundary
layer: ragbase
type: concept
confidence: verified
locator: specs/architecture.md §Product Boundary
---
# Host-Agnostic MCP Product Boundary

Implementation-side confirmation of the lifecycle: bodesign is a host-agnostic MCP server + web server. The system boundary starts at source ingestion/normalization (datasheet/schematic/BOM/Gerber/IPC evidence) and flows through BoardDesign IR generation, layout planning, Gerber generation, deterministic validation, approval, and export. bodesign is independently operable; no host shell owns the boundary — corroborates the C00–C07 lifecycle from the code architecture.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/specs/architecture/md/text|text: asset.home.pkcs12.projects.bodesign.specs.architecture.md]] @ specs/architecture.md (full) — source_weight 2

## Related

- → `references` [[concept/container-boundary|Container boundary — host paths vs the file model]]
- → `references` [[concept/lifecycle-c00-c07|C00–C07 hardware product-design lifecycle]]

