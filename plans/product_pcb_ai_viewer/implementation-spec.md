# Implementation Spec: AI Reference Board Rebuilder

## Goal

Build a host-agnostic `bodesign` MCP server and web server where agents can provide files or design instructions, ingest heterogeneous hardware evidence, normalize it into reusable core data, reconstruct or generate PCB layout designs in a product-owned `BoardDesign IR`, and display the resulting Rockbox/OpenMV-style circuit/PCB view at `/bodesign/`.

## Confirmed Product Decisions

- MVP vision: provide a website mounted at `/bodesign/`; after an agent supplies files or instructions, the web interface displays the Rockbox circuit/PCB design reconstructed from Gerber/IPC evidence or generated from datasheet-derived component knowledge.
- Host strategy: `bodesign` is host-agnostic. Any MCP-capable IDE/agent client can drive it. opencms/opencode is a strong optional integration, not the product boundary.
- Stack: EDA tools are exposed primarily as MCP tools backed by FastAPI/Python services and shared schemas; visual output is served by the bodesign web server at `/bodesign/`, with optional host integrations for opencms fileview/gateway.
- AI behavior: assistant proposes modifications; user approval is required before changes are applied.
- Persistence: Postgres for project, job, finding, proposal, approval, and export metadata.
- Renderer: React Canvas 2D first, with room to evolve to WebGL after geometry scale is understood.
- Source strategy: `BoardDesign IR` is the source of truth for this product; it can be generated from datasheets/schematics/reference docs or reconstructed from Gerber/drill/IPC evidence.
- Parser strategy: use document extraction for OpenMV reference documents, `pygerber` for Gerber inspection, and drill/IPC parsing for reconstruction evidence.
- Component knowledge strategy: datasheet/component normalization is a Day 1 core capability, not a later analysis feature. The system must normalize PDFs and heterogeneous documents into reusable component records.

## Responsibility Areas

1. Source ingestion and normalization: read datasheets, schematics, BOM-like placement files, Gerber/artwork, drill, IPC netlists, routing reports, reference documents, and public reference-board evidence; normalize them into evidence-linked `ComponentKnowledge`, `DesignIntent`, and `BoardDesign IR` records.
2. Design compiler core: convert normalized core data into `BoardDesign IR`, convert reconstructed/generated IR into EDA/export targets, and keep evidence/confidence traceability through every transformation.
3. Viewer: render `BoardDesign IR`, original manufacturing outputs, generated/reconstructed circuit views, regenerated Gerbers, confidence overlays, and AI proposals through the `/bodesign/` web interface, with optional host fileview/gateway integrations.
4. Analysis and design intelligence: use normalized component knowledge, pinouts, electrical roles, layout guidelines, and reference-board evidence to identify risks and propose layout/design operations. Deep factory debug/test guidance remains future scope.

## Available Reference Data

- `01.ROCKBOX`: strong reconstruction fixture. It contains Allegro 22.1 RS-274X artwork files for a 6-layer board, Excellon-like drill output, IPC-D-356A netlist, routing output, stackup spreadsheet, and panel PDF.
- `01.ROCKBOX/gerber/ROCKBOX_V2.ipc`: high-value net evidence. It includes layer stack metadata, padstack information, net names, reference designators, pin numbers, pad geometry, coordinates, sides, and via records.
- `01.ROCKBOX/gerber/cds2f_ROCKBOX_V2.txt`: high-value component placement/BOM-like evidence. It exposes refdes, part number/value, package symbol, side, rotation, and XY placement; examples include `MDBT53-P1M`, `AN7002Q`, `W25Q128JVSIQ`, `RT9471DGQW`, `TCK106AG_LF`, `SIM8060-6-1-14-00-A`, and multiple connectors/passives.
- `02.OpenMV`: design target/reference corpus. It contains schematic PDF and component datasheets for STM32N657/OpenMV N6-related processor, flash, PSRAM, camera/MIPI protection, mic, IMU, Ethernet, WiFi/BLE, USB, power, and battery circuits, but no manufacturing output package was found in the current folder.
- MVP reconstruction spike should start with Rockbox, while OpenMV should seed the component knowledge base and inform AI layout-planning heuristics and target subsystem rules.

## MVP In Scope

- OpenMV path: ingest schematic PDF and datasheets, extract components/interfaces/constraints, create an initial `BoardDesign IR`, generate placement/routing intent, and export Gerber candidates.
- Rockbox path: ingest Gerber/artwork, drill, IPC-356 netlist, routing/report files, and reconstruct `BoardDesign IR` with evidence and confidence scores.
- Component knowledge path: extract part numbers from BOM-like placement files, schematic references, and datasheets; resolve or request datasheets; normalize pinouts, packages, electrical roles, power pins, interface pins, layout constraints, and reference-design notes.
- Viewer path: render `BoardDesign IR`, original Gerber layers, reconstructed objects, confidence overlays, and generated Gerber outputs in the browser.
- Export path: generate Gerber/manufacturing outputs from `BoardDesign IR` and produce a validation/reconstruction report.
- Safety path: require deterministic validation and explicit user approval before any generated layout is treated as send-to-fab output.

## MVP Out of Scope

- Full automatic routing or placement without user approval.
- Guaranteed recovery of original schematic, original EDA project, exact original constraints, or original design intent.
- Full foundry-grade DRC parity with every PCB manufacturer.
- Automatic silent repair of design files.
- Automated factory test/debug guidance and theoretical voltage/resistance calculation; this is intentionally deferred to a later research phase.
- Multi-user collaboration, billing, and organization management.

## Proposed Repository Layout

```text
apps/web/                 `/bodesign/` web viewer for circuit/PCB view, Gerber layers, evidence, confidence, and reports
services/api/             FastAPI/Python service for EDA jobs, web APIs, MCP tool handlers, validation, export
services/mcp/             Host-agnostic MCP server exposing bodesign tools to IDEs/agents
integrations/opencms/      Optional opencms fileview/gateway adapter
packages/design-ir/       Product-owned PCB source of truth and schema validators
packages/component-kb/    Datasheet ingestion, part normalization, pinout/package/layout knowledge
packages/doc-core/        Datasheet/schematic extraction into BoardDesign IR evidence
packages/reverse-core/    Gerber/drill/IPC reconstruction, editable PCB model, confidence scoring
packages/source-core/     BoardDesign IR patch validation and source export helpers
packages/gerber-core/     Gerber inspection, comparison, and manufacturing validation helpers
packages/shared/          Shared schemas and generated API types
storage/                  Local development upload/output root, gitignored
tests/                    MCP, service, viewer, fixture, and integration tests
```

## Backend Architecture

- FastAPI/Python services expose upload, project, design IR, reconstruction, generated output, finding, proposal, approval, export, and MCP tool endpoints.
- Postgres stores durable project/job/finding/proposal/approval state; raw artifacts stay in file/object storage.
- Upload handler stores raw files and creates a project/job record.
- Document pipeline converts OpenMV schematic/datasheets into component, pin, interface, power, footprint, and constraint evidence.
- Component knowledge pipeline normalizes part numbers, datasheets, pinouts, packages, power/interface roles, and layout guidelines into reusable records linked to `BoardDesign IR` objects.
- Reconstruction pipeline converts Gerber/drill/IPC artifacts into `BoardDesign IR` with confidence metadata and source evidence references.
- Gerber parser adapter starts with `pygerber` for RS-274X/artwork inspection and output validation; drill and IPC parsers add hole and net evidence.
- Rule-check service emits deterministic findings with severity, affected reconstructed object/layer, geometry reference, evidence, and confidence impact.
- AI proposal service receives structured `BoardDesign IR` summaries, confidence scores, extracted constraints, selected geometry snippets, and user intent, then returns proposed operations.
- Patch applier validates each operation against allowed source-edit types and applies only approved changes.
- Export service generates manufacturing outputs and packages original inputs, `BoardDesign IR`, Gerber outputs, and a reconstruction/design review report.

## MCP and Web Architecture

- MCP tools are the primary AI/IDE interface for knowledge ingestion, source ingestion, normalization, reconstruction, generation, validation, export, and opening viewer URLs.
- The web server mounts the primary viewer at `/bodesign/` and serves circuit/PCB views, Gerber previews, evidence/confidence overlays, component knowledge summaries, and reports.
- The viewer uses Canvas 2D to draw normalized geometry or server-generated SVG/image layers and overlays findings/proposals.
- Knowledge ingestion tools can absorb datasheets and reference documents into the component knowledge base so future design requests can reuse chip/package/pinout/layout knowledge.
- opencms integration remains optional: fileview handlers or gateway route registration may wrap the same `/bodesign/` surfaces without changing core APIs.
- State model keeps raw reference documents, raw manufacturing outputs, normalized evidence, `BoardDesign IR`, generated Gerbers, findings, proposals, and approvals separate.
- Approval is explicit in opencms dialog or proposal UI: preview diff, accept/reject each operation, then apply.

## Technology Research Summary

- `BoardDesign IR` is the core EDA design kernel; `pygerber` is not sufficient for PCB layout design because it only covers manufacturing-output parsing/rendering.
- KiCad should be the first practical EDA bridge for file/export/DRC semantics, while remaining behind adapters so the product-owned IR stays independent.
- `freerouting` is the best initial autorouting candidate after placement/routing constraints can be emitted from IR.
- `skidl` is a useful optional bridge for OpenMV document evidence to structured circuit/netlist generation, but not a PCB layout engine.
- `Argmaster/pygerber` remains the recommended Gerber inspection/rendering starting point because it is Python-native, MIT licensed, published on PyPI, supports modern and legacy Gerber variants, and exposes CLI/API rendering paths.
- IPC-356 parsing and drill parsing become first-class reconstruction inputs because they can recover net and hole evidence that Gerber geometry alone cannot reliably provide.
- `BoardDesign IR` should be implemented before any specific EDA export target; KiCad export remains a strong future candidate if IR mapping is clean.
- `tracespace/tracespace` is the strongest web visualization reference, but its maintainer notes an indefinite hiatus; keep it as reference or optional experiment rather than the core dependency.
- `gerbv/gerbv` is mature and maintained but GPL/native; use it only as a comparison/reference tool unless license review approves deeper integration.
- `curtacircuitos/pcb-tools` is archived; avoid as primary dependency.

## Data Model Draft

- `Project`: id, name, status, uploaded files, created timestamp.
- `InputArtifact`: project id, artifact type, filename, detected format, layer guess, parse status.
- `ComponentKnowledge`: manufacturer part number, aliases, package, pinout, pin roles, power rails, interface groups, layout guidelines, source datasheets, extraction confidence.
- `ComponentInstance`: refdes, normalized part ref, package/footprint, placement, rotation, side, value, evidence refs.
- `BoardDesign`: project id, version, stackup, components, footprints, nets, board objects, constraints, generated outputs, evidence refs.
- `Evidence`: id, source artifact, extraction method, target object refs, confidence, raw location.
- `Reconstruction`: project id, status, model version, confidence summary, evidence refs.
- `Component`: id, inferred reference designator, footprint guess, role guess, position, rotation, confidence, evidence refs.
- `Net`: id, name or inferred name, class guess, constraints, connected pads, IPC evidence, confidence.
- `BoardObject`: id, type, layer, geometry, net refs, confidence, source evidence refs.
- `Layer`: id, project id, type, source file, bounds, visible flag.
- `GeometryPrimitive`: id, layer id, type, coordinates, aperture/tool metadata.
- `Finding`: id, project id, rule id, severity, title, evidence, geometry refs.
- `Proposal`: id, finding/user prompt refs, rationale, operations, status.
- `PatchOperation`: type, target reconstructed source object/file, parameters, validation result.

## AI Safety Contract

- AI cannot directly write output files.
- AI output must be converted into typed `BoardDesign IR` patch operations.
- Every operation is validated deterministically before preview.
- User approval is required before applying operations.
- Gerber patching is not the main edit path; Gerber is generated from approved `BoardDesign IR` whenever possible.
- Export must include a report listing reconstruction confidence, original findings, accepted changes, rejected changes, generated outputs, and remaining warnings.

## Validation Plan

- Backend unit tests for datasheet/component normalization, document extraction, artifact classification, Gerber/drill/IPC parsing, IR validation, reconstruction confidence, generated Gerber validation, and patch validation.
- API tests for upload, job status, findings, proposal creation, approval, and export.
- Frontend component tests for viewer controls and proposal approval states.
- Fixture-based regression tests using OpenMV reference docs and Rockbox Gerber/drill/IPC packages.

## Implementation Order

1. Define source-ingestion taxonomy, evidence model, `ComponentKnowledge`, `DesignIntent`, and `BoardDesign IR` contracts.
2. Scaffold host-agnostic MCP server, FastAPI service, and `/bodesign/` web viewer contracts.
3. Add upload API, project/job persistence, and document/artifact classification.
4. Add Rockbox component placement/BOM evidence plus Gerber/drill/IPC reconstruction MCP interfaces.
5. Add OpenMV schematic/datasheet to component knowledge and design-intent interfaces.
6. Add Canvas viewer for `BoardDesign IR`, original outputs, confidence overlays, and generated Gerbers.
7. Add Gerber export/validation pipeline from `BoardDesign IR`.
8. Add AI planning interfaces for OpenMV generation and Rockbox reconstruction.

## Open Decisions

- Confirm whether Rockbox can be used as the first checked-in fixture, or whether fixture data must remain external/private.
- Decide initial `BoardDesign IR` persistence format and schema versioning policy.
- Decide initial `ComponentKnowledge` persistence format and datasheet cache policy.
- Decide first EDA bridge target: product JSON only, KiCad `.kicad_pcb`, or product JSON plus KiCad adapter.
- Decide KiCad/freerouting GPL integration posture before embedding either tool directly.
- Define minimum layout operation set needed for AI to generate OpenMV layout candidates.
- Confirm whether regenerated Gerber viewer displays server-generated SVG/images or fully normalized geometry primitives.
