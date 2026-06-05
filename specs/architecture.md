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
- `packages/reverse-core`: Rockbox evidence extraction and IR reconstruction. Current implementation parses Allegro `cds2f` placement/BOM-like exports into component instances and IPC-D-356A records into net/pad/via summaries; Gerber/drill geometry extraction, net inference beyond IPC evidence, and component clustering remain next steps.
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
6. OpenMV flow generates initial `BoardDesign IR`; Rockbox flow reconstructs `BoardDesign IR` from component placement, IPC net/pad/via summaries, Gerber/drill manifests, and confidence evidence.
7. `/bodesign/` retrieves `BoardDesign IR`, layer summaries, parsed component positions, IPC net summaries, confidence overlays, component knowledge, and generated output data for Canvas 2D rendering.
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
- First reconstruction spike now verifies placement and IPC inputs can recover component instances, copper layer labels, named nets, pad counts, via counts, and confidence evidence. Next reconstruction spikes must add Gerber/drill geometry for board outline, tracks, zones, apertures, and drill-to-copper relationships.
- Gerber validation spike must verify `pygerber` support for layer bounds, apertures, flashes, tracks, regions, SVG/image rendering, and output comparison.
- API flows should verify upload, parse status, findings, proposal creation, approval, and export.
- Frontend tests should cover viewer controls and approval UI state transitions.

## Immediate Capability Gaps

- Project workspace: current web UI has a builtin Rockbox fixture project, but per-project routes, durable artifact storage, and real upload/open flows are still missing.
- File visualization: source files must be rendered in type-specific viewers before the product claims a board/circuit view. PDFs, BOM/placement, IPC nets, Gerber metadata, drill files, and routing reports each need their own visual surface.
- Board View: must stay unavailable until true Gerber/drill geometry exists. Decorative placement sketches are explicitly disallowed because they misrepresent evidence as a PCB layout or circuit diagram.
- Geometry reconstruction: reverse-core must add RS-274X aperture/flash/draw/region/polarity parsing, drill tool/hit parsing, board outline detection, and normalized `GeometryPrimitive` output.
- Connectivity reconstruction: IPC nets, placement data, Gerber pads/flashes, vias, and drill hits must be fused into component-pad-net objects with confidence and cross-probing.
- Knowledge base: component-kb must move from placeholder records to user-provided datasheet extraction, part queueing, pinout/package/power/interface/layout guideline normalization, and explicit knowledge gaps.
- EDA bridge: KiCad should be introduced only behind adapter boundaries after `BoardDesign IR` has enough component, footprint, net, board-outline, layer-stack, and constraint data.
- AI design workflow: the agent path is ingest sources → resolve component knowledge → reconstruct/reference-board IR → propose subsystem/layout intent → deterministic validation → user approval; generated layouts remain non-final until export validation passes.
