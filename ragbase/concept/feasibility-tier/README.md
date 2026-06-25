---
slug: concept/feasibility-tier
title: Feasibility triage — how far bodesign takes a product at C04
layer: ragbase
type: concept
confidence: verified
---
# Feasibility triage — how far bodesign takes a product at C04

The promise is "give C00, get C01–C04". The honest qualifier is *how far* C04 goes, decided almost entirely by whether KiCad + the bodesign MCP can **route** the board. Signals (estimated at C00, firm at C03): `layer_count`, `finest_bga_pitch_mm`, `hdi_required`, `high_speed_nets` (DDR/USB3/MIPI/SerDes), `rf`, density. The tier is set by the **hardest driver** — one HDI-class constraint pulls the whole product up.

- **Tier 1 · fab-ready** — ≤4 layer, ≥0.65 mm pitch, no/low high-speed, no RF → a gated, DRC/SI-clean, fab-ready board package.
- **Tier 2 · routed-draft** — 0.5 mm pitch / 6–7 layer / 1–15 controlled-Z nets / RF / very dense → MCP routes most; critical nets need human/pro SI sign-off.
- **Tier 3 · concept+constraints → pro-EDA** — HDI/any-layer / ≤0.4 mm pitch / ≥8 layer / ≥16 high-speed nets → architecture+stackup+floorplan intent + full SI constraint set; routing handed to Allegro/Xpedition + human SI + HDI fab.

The sweet spot for autonomous C00→C04 is Tier 1–2. **Declare the tier up front** in the C01 handoff/README; re-run at C03 on the firm component set (confidence `firm`). A tier that clashes with user expectation is a reconciliation routed to C00/C01, surfaced early while cheap — never a silent downgrade.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/feasibility/triage/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.feasibility.triage.md]] @ feasibility-triage.md: signals, 3 tiers, declare-up-front — source_weight 1

## Related

- → `constrains` [[workflow/c01-id|C01 ID — industrial-design direction & interface constraints]]
- → `constrains` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- → `constrains` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]

