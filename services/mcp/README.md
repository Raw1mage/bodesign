# services/mcp

Host-agnostic MCP server surface for bodesign. Any MCP-capable IDE or agent can drive the same core service.

## Planned Tools

- `ingest_sources`: register user-provided Gerber, drill, IPC, schematic, datasheet, BOM-like placement, and reference files.
- `ingest_knowledge`: absorb datasheets and reference documents into reusable component knowledge.
- `normalize_sources`: classify and normalize raw inputs into evidence-linked records.
- `reconstruct_board`: reconstruct `BoardDesign IR` from Rockbox-style Gerber/drill/IPC/component evidence.
- `generate_board`: generate a `BoardDesign IR` candidate from datasheet-derived component knowledge and design instructions.
- `validate_design`: run deterministic schema, knowledge coverage, DRC-like, and export checks.
- `export_gerber`: export validated manufacturing outputs from approved `BoardDesign IR`.
- `open_viewer`: return or open a `/bodesign/` viewer URL for a project.

## Current Scaffold

`bodesign_mcp.py` provides synchronous placeholder handlers for the planned tools. It is not a full MCP transport yet; it exists so IDE/agent integration can call the same stable tool-shaped functions while the protocol server is built.
