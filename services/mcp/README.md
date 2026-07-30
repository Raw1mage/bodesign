# services/mcp

Host-agnostic MCP server surface for bodesign. Any MCP-capable IDE or agent can
drive the same core service. Conforms to the **MCP Integration Standard**
(`opencode/specs/mcp-integration-standard/`).

## Server

`server.py` is the live server (`mcp.server.Server` + Starlette + uvicorn). It
serves the `bodesign_*` tools over MCP and exposes the standard introspection +
file surface. Two transports (`--transport`):

- `stdio` (default) — JSON-RPC over stdin/stdout (direct IDE/agent / non-opencode hosts).
- `http` — MCP Streamable HTTP on `/mcp`, over a `--uds` socket (inward, local)
  and/or a `--host/--port` TCP bind. NOTE: compose binds `:8077` INSIDE the
  container but does **not** publish it to the host (BR_20260730d) — outward
  HTTP belongs behind a gateway in front of the socket.

The tool registry (`TOOLS`) maps each MCP tool name onto a bodesign capability
function; imports are lazy so a missing optional dep fails only that tool.
Tools may be split across worker containers by group (`--tools me|ee|core`); the
front forwards a non-local tool to its worker or reports it unavailable.

## HTTP surface (MCP Integration Standard)

| Endpoint | Std | Purpose |
| --- | --- | --- |
| `POST /files` (tar / `bodesign_stage_dir` inline map) | R2 | upload a project tree → `{token, doc_dir, files}` |
| `GET /files/{token}/blob/{rel}` | R2.1 | download a produced file (results list `{rel, url}`) |
| `GET /tools`, `GET /tools/{name}` | R8.1 | authoritative, current tool schemas |
| `GET /health` (`/healthz` alias) | R8.3 | liveness/readiness |
| `GET /skills` | R8.2 / R9.2 | companion-skill list — `skills[].name` is a **bare name**, `bundles[]` holds the vendored EDA archives |
| `GET /skills/{name}.zip` | R9.2 | download a declared skill, packed live from `mcp.json skillPaths` (`.tar.gz` also served, same tree) |
| `Mount /mcp` | R1 | MCP Streamable HTTP |

Path args resolve **inside** the token's `doc_dir` when a `token` is passed
(traversal outside it is rejected); without a token they stay host paths (the
local same-host UDS case).

## Lifecycle & conformance

- `../../webctl.sh` — standard R7 verb set `{start|stop|restart|refresh|health|clean|purge}`
  over the per-user compose project `bodesign-${USER}` (honours `BODESIGN_DEV` /
  `BODESIGN_WORKERS`). `../../mcpctl.sh` remains the richer dev loop (rebuild/log/status).
- `../../scripts/bodesign-self-heal.sh --check|--heal` — idempotent R7.4 recovery
  (probes the UDS socket, recreates only bodesign's own project, never a competing daemon).
- R7.3 socket perms: `webctl.sh` sets the socket dir `0755`; the server relaxes
  the bound socket to `0666` on startup so any local user / the rootful-docker
  gateway can connect.
- R9 `skillPaths: ["skills"]` is declared in `../../mcp.json`; the companion
  skill bundles ship under `assets/skills/` and are listed at `GET /skills`.

`mcp_delegate.py` is the MCP-to-MCP client (`bodesign_mcp_call`): drive an
external MCP server (docxmcp/drawmiat/…) through bodesign, degrading cleanly.
