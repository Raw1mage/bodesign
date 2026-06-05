# Architecture

## Product Boundary

This repository will host `bodesign` as a host-agnostic MCP server plus web server. Agents and IDEs provide files or design instructions through MCP; the web server mounts the primary viewer at `/bodesign/`. The system boundary starts with source ingestion and normalization: datasheet/schematic/BOM-like evidence extraction, Gerber/drill/IPC upload, public reference-board evidence, and normalized component/design knowledge. Those normalized records feed `BoardDesign IR` generation/reconstruction, layout planning, `/bodesign/` circuit/PCB rendering, Gerber generation, deterministic validation, approval, and export. opencms/opencode is an optional first-class integration, not the product boundary. Factory test/debug guidance is deferred to a later phase.

## Planned Modules

- `apps/web`: `/bodesign/` web viewer for circuit/PCB view, Gerber layers, evidence overlays, confidence, component knowledge summaries, and reports.
- `services/api`: FastAPI/Python backend for project APIs, Postgres-backed design jobs, storage access, web APIs, MCP tool handlers, AI orchestration, validation, approval, Gerber generation, and export.
- `services/mcp`: Host-agnostic MCP server exposing bodesign tools to opencms, Cursor, Claude Desktop, VS Code, and other MCP-capable IDEs/agents.
- `integrations/opencms`: Optional opencms gateway/fileview adapter around the same web/API/MCP surfaces.
- `packages/design-ir`: Product-owned PCB source of truth, evidence model, schema validation, and versioning.
- `packages/component-kb`: Datasheet ingestion, part-number resolution, pinout/package normalization, interface grouping, and layout-rule knowledge.
- `packages/doc-core`: OpenMV schematic/datasheet evidence extraction and design-intent normalization.
- `packages/reverse-core`: Rockbox Gerber/drill/IPC evidence extraction, IR reconstruction, net inference, component clustering, and confidence scoring.
- `packages/source-core`: `BoardDesign IR` patch validation and source export helpers.
- `packages/gerber-core`: Python-first Gerber adapter around `pygerber`, geometry normalization, manufacturing checks, output comparison, and validation.
- `packages/shared`: Shared schemas and API types.
- `tests`: Fixture-based backend, frontend, and workflow tests.

## Data Flow

1. User provides chip models, target functions, OpenMV reference documents, Rockbox component placement/BOM-like files, Gerber/artwork, drill, IPC netlist, routing/report files, and optional annotations.
2. FastAPI stores raw files and creates a Postgres project/job record.
3. Source-ingestion pipeline classifies each input as component evidence, design-intent evidence, manufacturing evidence, or reference-board evidence.
4. Component knowledge pipeline extracts part numbers, resolves/ingests datasheets, and normalizes pinout/package/power/interface/layout knowledge.
5. Document and artifact pipelines extract evidence into a shared evidence model.
6. OpenMV flow generates initial `BoardDesign IR`; Rockbox flow reconstructs `BoardDesign IR` from component, Gerber, drill, and IPC evidence.
7. `/bodesign/` retrieves `BoardDesign IR`, original layers, confidence overlays, component knowledge, and generated output data for Canvas 2D rendering.
8. Validation checks verify IR schema, component knowledge coverage, connectivity evidence, DRC-like constraints, and generated Gerber outputs.
9. AI invokes EDA MCP tools to ingest knowledge, propose layout plans, reconstruct Rockbox, generate datasheet-derived designs, or create IR operations; deterministic validators gate every operation.
10. User reviews generated layout/Gerber candidates in `/bodesign/` or an IDE/host proposal UI and approves selected outputs.

## External Technology Baseline

- OpenMV schematic/datasheet extraction: needed for datasheet-to-layout flow.
- `ComponentKnowledge`: normalized datasheet and pinout knowledge is a Day 1 dependency for layout generation/reconstruction quality.
- `BoardDesign IR`: core product-owned EDA kernel and source of truth.
- Host integrations: opencms/opencode, Cursor, Claude Desktop, VS Code, and other MCP-capable clients can drive bodesign through MCP; no single host owns the product boundary.
- KiCad bridge: first practical target for layout file/export/DRC compatibility, kept behind adapter boundaries.
- `freerouting/freerouting`: candidate deterministic autorouter after IR emits placement, nets, keepouts, and routing constraints.
- `skidl`: optional OpenMV document-to-circuit/netlist evidence layer.
- `Argmaster/pygerber`: primary Gerber/artwork inspection/render candidate for FastAPI integration.
- IPC-356 parser: needed for net connectivity evidence when available.
- Drill parser: needed for vias, through-holes, and drill-to-copper checks.
- `tracespace/tracespace`: web visualization and layer-identification reference; not core dependency unless maintenance risk is accepted.
- `gerbv/gerbv`: mature comparison/reference viewer; GPL/native concerns prevent default embedding.

## Safety and State Rules

- AI suggestions are advisory until converted into typed `BoardDesign IR` operations.
- No layout or Gerber output is considered final without user approval.
- AI does not directly route copper or emit final fabrication files; deterministic IR validation, bridge export, and Gerber validation are required.
- Patch validation is deterministic and must fail fast on unsupported operations.
- `BoardDesign IR` is the source of truth for generated/reconstructed layouts.
- Component knowledge records are evidence-linked and confidence-scored; unknown datasheets must produce explicit gaps instead of silent assumptions.
- Raw uploads, normalized evidence, `BoardDesign IR`, generated Gerbers, findings, proposals, approvals, and exports remain separate states.

## Verification Baseline

- Component knowledge extraction, document extraction, artifact parsing, IR generation, and reconstruction behavior should be fixture-driven.
- First reconstruction spike must verify Gerber/drill/IPC inputs can recover board outline, layers, pads, vias, tracks, zones, net assignments, and confidence evidence.
- Gerber validation spike must verify `pygerber` support for layer bounds, apertures, flashes, tracks, regions, SVG/image rendering, and output comparison.
- API flows should verify upload, parse status, findings, proposal creation, approval, and export.
- Frontend tests should cover viewer controls and approval UI state transitions.
