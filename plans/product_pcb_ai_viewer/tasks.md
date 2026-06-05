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

## Stop Gates

- [?] User approval required before creating the MCP/service/`/bodesign/` web scaffold.
- [?] Datasheet fetching policy must be decided before automatic external downloads.
- [!] Debug/test guidance is deferred and must not shape the MVP schema unless needed by layout generation.
- [!] No generated layout or Gerber is considered send-to-fab without deterministic validation and explicit user approval.
