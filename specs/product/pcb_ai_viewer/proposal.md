# Proposal: bodesign — AI PCB Design Copilot (MCP)

## Why

Producing a manufacturer-ready electronics document package (schematic, BOM, layout, fab outputs, verification) is gated on EE expertise that a product owner may not have, and on stitching together many tools by hand. There is no system that, driven by natural-language conversation and raw input files, *guides* a non-EE owner from a product idea to a submittable design package — generating what it can, orchestrating mature EDA tools for the rest, and **demonstrating reliability** rather than asserting it.

bodesign is that system: a **KiCad-lifecycle MCP** with a **docxmcp-style file/folder surface**. The user talks and submits raw data (a project folder, datasheets); bodesign lands files (PRD, schematic, BOM, companions, reports) into the client-owned folder and tells them, each turn, the single next step and how reliable the result is versus a known-good reference.

## What Changes

- **Before:** PCB design requires an EE who hand-drives KiCad + a chain of analysis/sourcing/fab tools; reliability is asserted, not shown; there is no conversation-driven path from idea to a submittable package.
- **After:** a standalone MCP server walks the full lifecycle — ingest → plan → generate (symbol + `kicad-cli`-validated schematic) → layout/fab → verify → docs/readiness — driven by dialogue and raw files, shipping every engineering file with a readable companion and a reliability verdict versus a known-good reference.
- **Boundary shift:** bodesign *generates* what is safe to generate and *orchestrates* mature EDA skills for the rest; KiCad stays the editor, accredited labs stay the certifier — bodesign emits nothing to fab without deterministic validation + explicit approval.

## Capabilities

- **Ingest & index** a whole client project tree read-only (docxmcp-style decompose).
- **Plan requirements** from a natural-language spec, asking back for missing specs/interfaces.
- **Generate** KiCad symbols + a `kicad-cli`-validated schematic from reference-grounded evidence.
- **Lay out** (footprint placement + `pcbnew` DRC) and **export fab** (gerbers/drill/pos/STEP).
- **Verify** in four layers: ERC/DRC · reference cross-check (control group) · SPICE · EMC/thermal.
- **Render companions** (pdf/png/svg/xlsx) for every non-readable engineering file.
- **Track readiness** via a file-based compass that drives the next single step.
- **Orchestrate** the EDA skill suite (`kicad`, `kidoc`, `emc`, `spice`, `datasheets`, `bom`/distributors/fab).

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

## Impact

- **For a non-EE product owner:** a conversational path from idea to a reviewable, reliability-scored design package, without owning the whole EDA toolchain.
- **For an EE:** the mechanical work (ingest, symbol/schematic emit, companions, cross-check, sim/EMC pre-screen) is automated and evidence-backed; their judgement is spent on approval and novel circuits.
- **For the design data:** bodesign ships **no working data** — client trees enter at runtime via the token file API (TTL-GC'd); the program stays generic and publishable.

## Exemplar / control group

The forward generation is validated against a **known-good shipped reference board** (the control group): generated nets/parts are cross-checked against the reference with provenance, so reliability is *demonstrated*. Reference data is client-owned and supplied at runtime — it is not part of the program. Novel parts with no reference fall back to the analysis skills + explicit EE/user approval.
