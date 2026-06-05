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

## Current State

This is an initial scaffold only. It does not parse Gerber files, reconstruct Rockbox, or generate PCB layouts yet.
