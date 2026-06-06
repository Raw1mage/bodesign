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

- Project workspace and document management: current web UI has a builtin Rockbox fixture project, but real client-shared project folder browsing/editing is still missing. The intended storage boundary is client-owned local folders: users manage all raw documents, extracted source chunks, datasheets, schematics, board files, edits, and generated artifacts in project folder structure on the client side. The MCP server is a lightweight analyzer/indexer/web surface that may cache render outputs and parse indexes, but cache is disposable and not authoritative.
- File visualization: source files must be rendered in type-specific viewers before the product claims a board/circuit view. PDFs, BOM/placement, IPC nets, Gerber metadata, drill files, and routing reports each need their own visual surface.
- Board View: must stabilize on a third-party raster/CAD-style Gerber renderer before further reconstruction work. The current work-in-progress is moving from pygerber SVG/fallback experiments to pygerber raster output with explicit fail-fast errors when rendering is unavailable. Decorative placement sketches and hand-written SVG approximations are explicitly disallowed as the default PCB view; pan/zoom/layer toggles, multi-layer compositing, and full board-outline-aware rendering remain pending.
- Geometry reconstruction: gerber-core now parses RS-274X aperture/flash/draw/region/polarity summaries, normalizes Allegro compatibility header blocks for pygerber, and parses drill tool/hit summaries for Rockbox fixture files. Full board outline detection, repeated drill command expansion, polarity-aware regions, and normalized `GeometryPrimitive` IR output remain pending.
- Connectivity reconstruction: the current first-pass fusion summarizes placement components against IPC pin/net evidence in the geometry API and Board View. First-pass cross-probing links component, IPC net, and source artifact evidence through `/cross-probe/{probe_id}`. Spatial fusion of Gerber pads/flashes, vias, drill hits, confidence scoring, and layer/object-level derived IR cross-probing remains pending.
- Knowledge base: component-kb now exposes a first-pass reusable part queue from Rockbox placement evidence through `/knowledge/queue`, including reusable keys, occurrence counts, priority, refdes samples, and knowledge gaps. User-provided datasheet ingestion can read local text-like files and best-effort PDF tokens without external downloads, record extraction metadata, and infer simple package hints. The preferred next architecture is a docxmcp-style PDF-to-src adapter that decomposes PDFs into chunked text/table/page source assets with provenance before component extraction. OpenMV reference extraction, structured pinout/electrical/layout normalization, source trust checks, and persistent storage remain pending.
- EDA bridge: KiCad is introduced behind adapter boundaries through an `eda-bridge` plan contract. The current integration records intended plugin/submodule export/import/DRC workflow steps and deliberately avoids invoking native KiCad/freerouting tools directly from the server path until `BoardDesign IR` has enough component, footprint, net, board-outline, layer-stack, and constraint data.
- AI design workflow: workflow-core exposes a deterministic reference-board workflow plan for ingest sources → resolve component knowledge → reconstruct/reference-board IR → propose subsystem/layout intent → deterministic validation → user approval. The current APIs are `/workflow/reference-board` and `/candidates/generated-design`; they are client-orchestrated, report blockers/approval gates, and do not execute AI generation, native EDA tools, or fabrication export automatically. The Candidates web tab shows diff/evidence/validation review with approval state defaulting to `not-approved`. Generated layouts remain non-final until export validation passes.

Doc-source pipeline: doc-core now includes a first-pass `DocumentSourceChunk` adapter that decomposes local text/PDF-like documents into chunked source assets with `EvidenceRef` anchors before downstream extraction. This is the local contract for the proposed docxmcp-style PDF workflow. The preferred MVP integration is client-side orchestration across bodesign MCP and docxmcp; an internal MCP bridge is possible later only behind an adapter boundary so bodesign does not depend directly on docxmcp runtime/accounts/permissions.

Client↔MCP storage share: the product should follow a docxmcp-like split where the client owns durable files and exposes a scoped project folder manifest/read/write capability to the MCP. The MCP can analyze, split PDFs into source chunks, render online views, suggest edits, and write back through that scoped share; it should not silently migrate user content into server-owned durable storage. Required open design points include manifest schema, permission scope, cache invalidation, conflict handling, and whether writes are direct MCP writes or client-applied patch operations.

Project folder UX: users should not see an exploded machine intermediate tree at the root. The human-facing project root should stay close to KiCad/EDA concepts: `docs/` or `inputs/` for datasheets, application notes, reference designs, and incoming manufacturing packages; `eda/` for KiCad-native `.kicad_pro`, `.kicad_sch`, `.kicad_pcb`, project settings, and reviewable schematic/board sources; `libraries/` for project-local symbols, footprints, 3D models, and vendor libraries; `outputs/` for reviewed PDFs, Gerbers, drill files, BOM, pick-and-place/position files, STEP/3D exports, and release packages; `reports/` for reconstruction/validation summaries. Machine-only data — source chunks, OCR/table extraction, normalized IR, parse caches, embeddings, render artifacts, provenance indexes, workflow state, and temporary bridge outputs — belongs in a hidden/system workspace such as `.bodesign/`. The MCP manifest maps standard EDA folder locations to semantic roles and the MCP web UI exposes internals as evidence views without making the underlying folder structure noisy.

KiCad Happy integration: the existing KiCad Happy skill uses `.kicad-happy.json` and an analyzer cache convention (`analysis/<run_id>/`, `analysis/manifest.json`, optional report figures). bodesign should interoperate with that convention but default MCP-run analysis to hidden cache paths such as `.bodesign/analysis/kicad-happy/` with `track_in_git=false`, then present findings, trust summaries, diffs, renders, DRC/ERC/DFM/EMC/thermal evidence, and report inputs through the web UI. Visible `analysis/` folders are an opt-in compatibility mode for engineers already using KiCad Happy directly.

KiCad-native foundation gate: near-term product work should focus on making client-owned KiCad projects usable through native KiCad plus bodesign companion surfaces before trying to complete Gerber→design-source or datasheet/reference→design-source automation. Native KiCad remains authoritative for schematic/PCB editing, canvas behavior, libraries, and DRC/ERC. bodesign supplies storage-share, file/library/output detection, hidden KiCad Happy analysis cache, Web evidence views, reports/manufacturing output browsing, AI workflow state, candidate review, and safe save-back/patch semantics. The two conversion paths remain research-grade until native KiCad plugin/sidecar workflows can reliably browse, analyze, propose, and round-trip ordinary KiCad projects.

KiCad plugin scaffold: `packages/kicad-plugin` is the first native entrypoint. It is intentionally importable without KiCad for tests, degrades when `pcbnew` is unavailable, and only represents sidecar operations: active project discovery, bodesign dashboard URL generation, sidecar handshake payloads, analysis request construction, and approved-patch request representation. The bodesign API exposes a deterministic plugin handshake that reports sidecar readiness, URLs, approved capabilities, blockers, and approved-patch-only policy. It must not run DRC/ERC or mutate `.kicad_*` files until a user-approved KiCad-native plugin workflow exists.

Client folder browsing: the next storage surface should expose a manifest-derived project tree, not raw server filesystem access. It should present human-facing KiCad/EDA folders (`docs`/`inputs`, `eda`, `libraries`, `outputs`, `reports`) and summarized hidden `.bodesign` cache/evidence state in the companion dashboard. Read/write scope is governed by storage-share policy; initial implementation remains read-only/fixture-backed until client-provided folder handles and approved save-back semantics exist.

Project registry: bodesign should route projects through lightweight client-owned project records rather than a hard-coded demo id or server-owned durable store. A registry record names the project, stores non-authoritative folder-handle metadata/status, links storage-share/project-tree/KiCad-native surfaces, and reports blockers for real client handles and save-back. The registry itself is metadata/evidence; durable source files remain under client control.

Folder open/import request: bodesign represents client-side folder handle requests but does not open arbitrary server paths. The request contract records requested permissions, read/write scopes, `needs-client-grant/not-approved` approval state, fail-fast blockers, and post-grant refresh actions for registry, storage-share, project-tree, and KiCad foundation surfaces. File reads/writes remain unavailable until the client grants a scoped handle and approves save-back/conflict policy.

Frontend axis: the web frontend is a KiCad companion dashboard, not a KiCad-native editor. Top-level experience should organize around Project Overview, Schematic Status, PCB Layout Status, Libraries, Datasheets/Docs, Analysis, Manufacturing Outputs, Reports, and Candidate Review. Gerber/drill/IPC/BOM/placement/raster/reconstruction data remain important evidence panels and cross-probe surfaces. Actual schematic/PCB editing, KiCad canvas operations, and DRC/ERC execution belong in native KiCad via plugin/sidecar integration.

External datasheet policy: automatic public web downloads are disabled by default. `/knowledge/external-fetch` is a fail-fast policy gate that returns an approval-required response; accepted inputs before approval are user-provided PDFs/text and docxmcp-derived source chunks.
