# bodesign

`bodesign` is a host-agnostic web service plus MCP server for AI-assisted PCB reference-board rebuilding. The web route lives under `/bodesign/`, and the same product exposes MCP tools so IDEs/agents can drive ingestion, knowledge normalization, reconstruction, generation, validation, export, and viewer opening.

## MVP Vision

- Agents or IDEs provide files and design instructions through MCP.
- The web viewer is mounted at `/bodesign/`, with bodesign-scoped API aliases under `/bodesign/api/*`.
- The web product includes both browser-facing routes and MCP-facing agent tools; these are one bodesign capability surface, not separate products.
- Rockbox is the first reconstruction target from Gerber, drill, IPC, and placement/BOM-like evidence.
- OpenMV is the first document-driven design target from schematics, datasheets, and reference documents.
- Datasheets and reference documents are absorbed into a reusable component knowledge base so future requests can reuse chip, package, pinout, and layout knowledge.

## Surfaces

- `services/mcp`: planned MCP tools for ingestion, normalization, reconstruction, generation, validation, export, and viewer opening.
- `services/api`: FastAPI/Python service for web APIs and EDA job orchestration; bodesign-facing routes are registered under `/bodesign/` and `/bodesign/api/*`, with legacy `/api/*` aliases kept for local scaffold compatibility.
- `apps/web`: `/bodesign/` viewer surface for circuit/PCB views, Gerber previews, evidence, confidence, and reports.

## Run the Web Surface

```bash
python3 -m pip install -r services/api/requirements.txt
python3 -m services.api
```

Then open:

- `http://127.0.0.1:8765/bodesign/` for the Rockbox viewer.
- `http://127.0.0.1:8765/bodesign/routes` for the visible route index.
- `http://127.0.0.1:8765/bodesign/api/routes` for the JSON route registry.

## Current State

The current MVP parses Rockbox placement/BOM-like and IPC-356 fixture evidence into a `BoardDesign IR` summary, exposes it through MCP/API reconstruction handlers, and renders the summary at `/bodesign/`. Exact Gerber geometry rendering, full source reconstruction, and layout generation are still pending.
