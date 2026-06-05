# Tasks: AI Reference Board Rebuilder

- [x] T1 Define source-ingestion taxonomy and evidence schemas
- [x] T2 Define ComponentKnowledge, DesignIntent, and BoardDesign IR schemas
- [x] T3 Scaffold MCP server, FastAPI service, and `/bodesign/` web viewer
- [x] T4 Implement upload, artifact/document detection, and job model
- [x] T5 Add OpenMV document-to-knowledge/design planning interfaces
- [x] T6 Add Rockbox component, Gerber, drill, and IPC-to-IR interfaces
- [x] T7 Render Rockbox BoardDesign IR and Gerber layers at `/bodesign/`
- [x] T8 Add Gerber generation and validation from BoardDesign IR
- [x] T9 Add MCP AI planning tools for OpenMV and Rockbox flows
- [x] T10 Produce design/reconstruction reports for generated outputs
- [x] T11 Add datasheet knowledge ingestion and reuse tests
- [x] T12 Add targeted backend, MCP, and frontend verification

## Next Functional Gap Tasks

- [~] T13 Replace hard-coded Rockbox demo with per-project workspace routes and durable project/artifact records — per-project routes and fixture artifact records are implemented; durable DB/file storage is still pending
- [~] T14 Add real web import/open/browse flow for uploaded project folders and fixture-backed projects — fixture-backed browsing is implemented; upload/drop flow is still pending
- [x] T15 Build source-file viewers for PDFs, BOM/placement, IPC nets, Gerber layer metadata, drill files, and routing reports
- [ ] T16 Integrate Gerber parser/render spike for RS-274X metadata, apertures, bounds, flashes, draws, regions, polarity, and SVG/image output
- [ ] T17 Integrate drill parser for tool tables, drill hits, plated/non-plated hints, and board-outline candidates
- [ ] T18 Normalize Gerber/drill geometry into `BoardDesign IR` primitives with evidence refs and confidence
- [ ] T19 Re-enable Board View only after true PCB layer geometry can be rendered with pan/zoom/layer toggles
- [ ] T20 Fuse IPC nets, placement, Gerber pads/flashes, vias, and drill hits into component-pad-net reconstruction
- [ ] T21 Add cross-probing between components, nets, layers, artifacts, and derived IR objects
- [ ] T22 Build reusable component knowledge queue from Rockbox parts and OpenMV references
- [ ] T23 Implement user-provided datasheet PDF/text extraction into `ComponentKnowledge` records
- [ ] T24 Add explicit external datasheet fetching policy gate before any automatic public web download
- [ ] T25 Add KiCad bridge design spike for IR-to-KiCad export/import/DRC behind adapter boundaries
- [ ] T26 Add AI reference-board workflow: ingest sources → resolve knowledge → reconstruct IR → propose subsystem/layout intent → validate → approval
- [ ] T27 Add generated design candidate workspace with diff/evidence/approval UI

## Stop Gates

- [?] User approval required before creating the MCP/service/`/bodesign/` web scaffold.
- [?] Datasheet fetching policy must be decided before automatic external downloads.
- [?] KiCad/freerouting integration posture must be approved before embedding GPL/native tools directly.
- [!] Debug/test guidance is deferred and must not shape the MVP schema unless needed by layout generation.
- [!] No generated layout or Gerber is considered send-to-fab without deterministic validation and explicit user approval.
- [!] Board View must not display decorative/fake circuit drawings; it can only render true source/geometry evidence or an explicit unavailable state.
