# Handoff: bodesign — AI PCB Design Copilot (MCP)

How to build, run, test, and extend bodesign. Architecture is in `design.md`; the contract is in `spec.md`.

## Execution Contract

bodesign is delivered and operated as a standalone MCP server. Run it, connect over MCP, drive the lifecycle via tools. No host shell/gateway is required; no fab output without validation + explicit approval (DD-8); no working data committed.

## Required Reads

Before extending: `spec.md` (contract), `design.md` (architecture + DD-*), `tasks.md` (node map N1–N19 + build queue), `errors.md` (failure handling), `data-schema.json` (IRs). For diagrams: `idef0.svg` / `grafcet.svg`.

## Stop Gates In Force

- No send-to-fab output without deterministic validation + explicit approval (DD-8).
- No working data written into the repo (only `Token.doc_dir` runtime or `data_root()` external).
- Generation reported ready only after `kicad-cli` validation passes.
- Verification degrades to `skipped`-with-reason, never a false pass.

## Execution-Ready Checklist

- [x] Toolchain present (Docker image or host `kicad-cli`/`pcbnew`/`soffice`/`ngspice`).
- [x] Server reachable on `/mcp/` + `/healthz` (UDS and/or TCP).
- [x] Suite green on a clean clone (`data_root()` guards skip data-dependent tests).
- [x] `mcp.json` registered with the client.

## Run

**Docker (portable):** `./mcpctl.sh start | status | log | stop` — builds the image (KiCad 9 + LibreOffice + ngspice + toolchain), starts the container with a UDS at `./.run/bodesign.sock` + TCP `:8077`.

**Host:** `pip install -r services/mcp/requirements.txt` then `python services/mcp/server.py --transport http --uds .run/bodesign.sock --port 8077` (or `--transport stdio`). Requires `kicad-cli`, `pcbnew`, `soffice`, `ngspice` on PATH.

**Connect:** MCP Streamable HTTP at `unix://….sock:/mcp/` (local) or `http://<host>:8077/mcp/` (external); manifest in `mcp.json`; live guide at `/`, tool schemas at `/tools` + `/tools/{name}`.

## Test

```bash
PYTHONPATH="packages/*:services/mcp:." python3 -m unittest discover -s tests
```

- Green on a **clean clone** (no working data): data-dependent tests skip via `data_root()` guards.
- With reference data present, set `BODESIGN_DATA_DIR=<root>` (layout: `fixtures/<board>/…`, `products/<name>/…`).
- Test→requirement traceability is in `test-vectors.json`.

## Repository map

- `services/mcp/` — the server (`server.py`), token store (`token_store.py`), requirements, skill-pack assets, `mcp.json`, `mcpctl.sh`, `Dockerfile`, `docker-compose.yml`.
- `packages/` — generic capability libraries (`shared`, `design-ir`, `component-kb`, `doc-core`, `source-core`, `reverse-core`, `gerber-core`, `eda-bridge`, `workflow-core`, `storage-core`, `kicad-plugin`).
- `specs/product/pcb_ai_viewer/` — this spec.

## Extend

- **New part type:** harvest a pinout via the `datasheets` skill → `emit_kicad_symbol` (generic). No product recipe code.
- **New verify dimension:** add an analyzer in `eda-bridge/pcb_verify.py` returning `passed|failed|skipped` + reason; wire into the server tool list.
- **New tool:** add to `services/mcp/server.py` (`build_server`), declare path args in `PATH_ARG_KEYS` for token resolution, add a `/tools/{name}` schema entry, cover with a test + a `test-vectors.json` row.
- **Data isolation rule:** never commit working data; read external data only via `bodesign_shared.data_root()`.

## Roadmap (deferred — not in verified scope)

See `tasks.md` §Roadmap: multi-chip composition proof (R7), generalized symbol/footprint gen (R8), footprint/PCB emit + freerouting (R10), the interactive requirement loop / vibe front end (T30), and the in-KiCad Action Plugin (T31, cannot run headless).
