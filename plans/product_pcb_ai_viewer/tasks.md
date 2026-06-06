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

- [~] T13 Replace hard-coded Rockbox demo with per-project workspace routes and client-owned project folder records — per-project routes and fixture artifact records are implemented; next storage model should index client-managed local folders rather than making the MCP server the durable content owner
- [~] T14 Add real web import/open/browse flow for uploaded or client-shared project folders — fixture-backed browsing is implemented; next UI should browse the client-owned folder tree, show document/circuit/datasheet views online, and save edits back through the client-managed storage share
- [x] T14a Define client↔MCP storage-share protocol for local project folders — storage-core now exposes a client-owned project folder manifest with human-facing folders, hidden `.bodesign` workspace, scoped read/write permissions, disposable cache policy, save-back mode, and conflict policy; API returns it at `/bodesign/api/projects/{project_id}/storage-share`
- [x] T14b Define human-facing KiCad/EDA project folder taxonomy — storage-core now classifies human-facing `docs/`/`inputs/`, `eda/`, `libraries/`, `outputs/`, and `reports/` paths, detects `.kicad_pro`/`.kicad_sch`/`.kicad_pcb` sources and manufacturing outputs, and excludes hidden `.bodesign` machine paths from root taxonomy
- [x] T14c Define KiCad Happy analysis-cache integration — storage-core now maps `.kicad-happy.json` compatibility config and analyzer artifacts to hidden `.bodesign/analysis/kicad-happy/` by default with `track_in_git=false`, while retaining visible `analysis/` as an explicit opt-in compatibility mode
- [x] T14d Implement KiCad-native foundation workflow — API/UI now expose storage-share, KiCad source/taxonomy detection, hidden KiCad Happy cache mapping, safe save-back policy, and native KiCad plugin/sidecar boundary so KiCad remains the schematic/PCB editor while bodesign supplies companion analysis/workflow surfaces
- [x] T14e Reframe Web frontend as a KiCad companion dashboard, not a KiCad editor — web shell now labels Schematic/PCB as status/evidence panels, states native KiCad owns editing/canvas/DRC/ERC, and exposes native extension handoff context instead of implying browser-native schematic/PCB editing
- [x] T14f Add KiCad native plugin/sidecar extension contract — eda-bridge now defines Action Plugin/MCP sidecar capabilities for opening bodesign context from KiCad, requesting analysis, reviewing evidence/candidate patches, applying user-approved edits through KiCad-native APIs, and round-tripping status without reimplementing KiCad's editors in the browser
- [x] T14g Scaffold KiCad Action Plugin sidecar entrypoint — kicad-plugin now provides KiCad-safe import without `pcbnew`, sidecar config/default URLs, active project context discovery from `.kicad_pro`/`.kicad_sch`/`.kicad_pcb`, open-dashboard/request-analysis request builders, and approved-patch-only guards without executing DRC/ERC or mutating files
- [x] T15 Build source-file viewers for PDFs, BOM/placement, IPC nets, Gerber layer metadata, drill files, and routing reports
- [x] T16 Integrate Gerber parser/render spike for RS-274X metadata, apertures, bounds, flashes, draws, regions, polarity, and pygerber-backed SVG output
- [x] T17 Integrate drill parser for tool tables, drill hits, plated/non-plated hints, and board-outline candidates
- [~] T18 Normalize Gerber/drill geometry into `BoardDesign IR` primitives with evidence refs and confidence — geometry summaries and third-party render artifacts are available; full `GeometryPrimitive` IR fusion is pending
- [x] T19 Stabilize Board View on a third-party raster renderer before advancing reconstruction — Board View now uses pygerber raster-only rendering with explicit fail-fast error state (no hand-written SVG fallback), and tests/docs are synchronized on the raster contract
- [x] T19a Commit the raster-only Board View stabilization slice after `compileall` and unittest pass
- [~] T20 Fuse IPC nets, placement, Gerber pads/flashes, vias, and drill hits into component-pad-net reconstruction — first-pass component/net fusion summary is exposed in geometry API and Board View from placement + IPC evidence; Gerber pad/flash/via/drill spatial fusion remains pending
- [~] T21 Add cross-probing between components, nets, layers, artifacts, and derived IR objects — first-pass API/UI links connect components, IPC nets, and source artifacts; layer/object-level derived IR cross-probing remains pending until spatial geometry primitives exist
- [~] T22 Build reusable component knowledge queue from Rockbox parts and OpenMV references — Rockbox component queue API groups reusable part candidates with priority/gaps; OpenMV reference extraction remains pending
- [~] T23 Implement user-provided datasheet PDF/text extraction into `ComponentKnowledge` records — local text extraction and best-effort PDF token scanning populate extraction metadata/package hints; structured pin/electrical extraction remains pending
- [~] T23b Add docxmcp-style PDF-to-src workflow adapter so PDFs become chunked, provenance-preserving source assets before component extraction — doc-core now produces provenance chunks for local text/PDF-like sources; fastest product path is client-side orchestration across bodesign MCP + docxmcp, while internal MCP direct bridge remains a later adapter-bound option
- [x] T24 Add explicit external datasheet fetching policy gate before any automatic public web download — `/knowledge/external-fetch` is disabled by default and returns an approval-required policy block instead of downloading
- [x] T25 Add KiCad bridge design spike for IR-to-KiCad export/import/DRC behind adapter boundaries — eda-bridge now defines an adapter-bound KiCad plan contract for plugin/submodule workflow integration without invoking native tools directly
- [x] T26 Add AI reference-board workflow: ingest sources → resolve knowledge → reconstruct IR → propose subsystem/layout intent → validate → approval — workflow-core now exposes a deterministic client-orchestrated reference-board workflow plan with explicit blockers and approval gates
- [x] T27 Add generated design candidate workspace with diff/evidence/approval UI — workflow-core now exposes a generated design candidate workspace with diff summary, evidence refs, validation gates, and default `not-approved` approval state in API and web UI

## Stop Gates

- [?] User approval required before creating the MCP/service/`/bodesign/` web scaffold.
- [?] Datasheet fetching policy must be decided before automatic external downloads.
- [?] KiCad/freerouting integration posture must be approved before embedding GPL/native tools directly.
- [!] Debug/test guidance is deferred and must not shape the MVP schema unless needed by layout generation.
- [!] No generated layout or Gerber is considered send-to-fab without deterministic validation and explicit user approval.
- [!] Board View must not display decorative/fake circuit drawings or hand-written SVG approximations as the default PCB view; it must use a third-party Gerber/CAD renderer, verified evidence views, or an explicit unavailable/error state.
- [!] MCP server must not become the authoritative document store for user projects; durable project content belongs to the client-managed local folder unless the user explicitly approves a different storage backend.
- [!] Project folder UX must not expose exploded machine intermediate trees at the root; use a small human-facing taxonomy plus hidden/system subtrees for MCP internals.
- [!] KiCad Happy analyzer outputs must be treated as evidence/cache artifacts, not user-facing source folders; expose them through web evidence views unless the user explicitly chooses visible analysis folders.
- [!] Gerber→design-source and datasheet/reference→design-source pipelines must remain blocked until native KiCad integration can reliably browse, analyze, cache, propose, and round-trip ordinary KiCad projects through approved plugin/sidecar workflows.
- [!] Web frontend must not pretend to be a KiCad-native schematic/PCB editor. Native KiCad owns editing/canvas/DRC/ERC; bodesign Web is a companion dashboard for evidence, documents, workflow state, and approval gates.
