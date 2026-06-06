# Proposal: bodesign — AI PCB Design Copilot (MCP)

## Why

Producing a manufacturer-ready electronics document package (schematic, BOM, layout, fab outputs, verification) is gated on EE expertise that a product owner may not have, and on stitching together many tools by hand. There is no system that, driven by natural-language conversation and raw input files, *guides* a non-EE owner from a product idea to a submittable design package — generating what it can, orchestrating mature EDA tools for the rest, and **demonstrating reliability** rather than asserting it.

bodesign is that system: a **KiCad-lifecycle MCP** with a **docxmcp-style file/folder surface**. The user talks and submits raw data (a project folder, datasheets); bodesign lands files (PRD, schematic, BOM, companions, reports) into the client-owned folder and tells them, each turn, the single next step and how reliable the result is versus a known-good reference.

## Effective requirements

- **R1** Ingest an entire client project folder (KiCad/EDA/docs/Gerber) read-only and index it (docxmcp-style decompose).
- **R2** Forward generation that no analysis tool does: requirements→plan, evidence sourcing, symbol generation, subsystem composition, schematic emit — validated by `kicad-cli`.
- **R3** Orchestrate the mature KiCad/EDA skills (`kicad`, `kidoc`, `emc`, `spice`, `datasheets`, `bom`/distributors/fab) for analysis, documentation, simulation, sourcing, and fabrication.
- **R4** Every non-readable engineering file ships with a readable companion (pdf/png/svg/xlsx); the user reviews in native apps.
- **R5** A file-based readiness compass (the package folder *is* the state) drives the prompt-driven, plan-builder-shaped loop (agent-as-wizard).
- **R6** Reliability is demonstrated by cross-checking generated output against a known-good shipped product (control group), with provenance; novel parts fall back to analysis skills + EE/user approval.
- **R7** No send-to-fab output without deterministic validation + explicit user approval.

## Scope

**In:** the forward-generation/surface/state/trust layer (ingest, requirement planning, evidence sourcing, symbol/footprint generation, subsystem composition, schematic emit, layout via `pcbnew`, fab-output export, companion rendering, readiness compass, reference cross-check, doc/interface emitters), plus orchestration of the EDA skills.

**Out (by design):** a browser-native schematic/PCB editor (native KiCad owns editing; no web UI); ID/ME/firmware content (other teams; bodesign supplies interface constraints only); autonomous auto-routing to a finished layout (freerouting/manual, bounded); physical EVT/DVT testing + certification (outsourced labs); guaranteed EE correctness of novel/from-scratch circuits (only faithful reuse of references is high-confidence).

## Driving product

The concrete target driving the roadmap is **TheSmartAI Edge AI device** (`product_edge_ai_device`), V1 OpenMV-derived. The OpenMV datasheet→KiCad work (`product_openmv_datasheet_kicad_source`) is the proven exemplar and the control group.
