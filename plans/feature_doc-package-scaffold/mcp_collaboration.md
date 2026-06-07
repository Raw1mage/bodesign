# MCP-to-MCP Collaboration (Batch F — design)

Status: planned (design before code). Researched 2026-06-08; see sources at bottom.

## Decision

MCP has **no native server-to-server** mechanism — aggregation is a community
proxy/gateway pattern ("present as a server to the client, act as a client to the
backends"). For bodesign we adopt:

- **Option 4 — targeted delegation (PRIMARY):** bodesign gains a thin MCP *client*
  capability so a bodesign tool / the C00 spine can call a specific external MCP
  server's tool, with graceful degradation. **No new dependency** — bodesign already
  depends on `mcp>=1.27`; the client side (`mcp.client.streamable_http` +
  `ClientSession`) is already available.
- **Option 1 — host-side aggregation (DEFAULT for unification):** the agent/host
  connects to bodesign + docxmcp + drawmiat independently (this is how the current
  session already works). Preserves "each server independently operable".
- **Option 3 — external gateway (FUTURE, if a single endpoint is ever required):**
  put a ready-made proxy in front (FastMCP proxy / TBXark mcp-proxy / AgentGateway /
  MS mcp-gateway). Do NOT rebuild a gateway inside bodesign-core.

We explicitly do NOT turn bodesign-core into a full aggregating gateway (Option 2):
heavy, and it fights the "no host shell or gateway, independently operable" design.

## Why Option 4 fits the worker spine

The worker router already decides `local | forward(/invoke → bodesign worker) |
worker_unavailable`. Option 4 adds a **fourth state: `forward(mcp)` → external MCP
server**. So:

- bodesign's own heavy libs → `/invoke` workers (Batch E, custom HTTP).
- external MCP servers (docxmcp, drawmiat, future) → real MCP client calls.
- The `agent_registry` per-layer `skill`/toolchain binding generalizes to "this
  layer/tool is backed by an external MCP server", so the `work_packet` spine can
  dispatch a C0x layer to an external MCP — the mechanism that lets C00–C07 chain
  *many* professional toolchains.

## Components

### External-MCP registry (config)

A small registry mapping a logical name → endpoint + optional auth header source:

- `BODESIGN_MCP_SERVERS` = JSON `{ "<name>": { "url": "...", "headers_env": "ENV" } }`,
  or per-name `BODESIGN_MCP_<NAME>_URL`. Unconfigured name → degraded (never crash).
- Streamable HTTP endpoints (the current MCP transport). stdio/subprocess backends
  are out of scope for now (HTTP first; a subprocess bridge can come later).

### Delegation primitive (`mcp_delegate.py`)

- `call_external_mcp_tool(server, tool, arguments) -> dict` — resolve the server URL,
  open an MCP client session over Streamable HTTP, `initialize()`, `call_tool()`,
  return the tool result (normalized to bodesign's `{ok, result}` shape).
- Sync-over-async bridge: the MCP client is async and `run_tool` is sync (called
  inside the server's async handler), so the call runs in a worker thread with its
  own event loop (`asyncio.run` in a thread) — robust regardless of the outer loop.
- **Degradation reuses the worker semantics:** unreachable/booting →
  `worker_starting` + `retry_after_seconds`; unknown/unconfigured server →
  `worker_unavailable`. Never fabricate a result. (Headless/cron note: an
  interactively-authenticated external MCP — e.g. docxmcp — may be unreachable;
  that degrades cleanly to `worker_unavailable`.)

### Generic passthrough tool (`bodesign_mcp_call`)

`bodesign_mcp_call(server, tool, arguments)` lets the agent / the spine call any
registered external MCP tool *through* bodesign with uniform degradation — the
minimal, general enabler. Specific convenience bindings (e.g. `emit_doc → docxmcp`)
are layered on top later, once each external API mapping is verified.

## Caveats designed around (from the research)

- **Namespacing:** when/if bodesign re-exposes external tools (future aggregation),
  prefix `server__tool` to avoid collisions. Targeted delegation keeps bodesign's own
  tool names and calls internally, so no collision now.
- **~100-tool LLM limit:** do NOT bulk re-expose every external tool. Targeted
  delegation + a single `bodesign_mcp_call` keeps the surface small.
- **`list_changed`, capability negotiation, auth:** out of scope for targeted
  delegation (we call one known tool on one known server); revisit if we ever build
  aggregation.
- **Latency / error propagation:** external calls are network hops; surface the
  external error verbatim under `{ok: false, error}`; bound connect timeout.

## First slice (this batch)

1. `mcp_delegate.py`: registry resolution + `call_external_mcp_tool` (thread-bridged
   async client) + degradation.
2. `bodesign_mcp_call` MCP tool.
3. Tests: registry/unknown-server resolution, unreachable → degraded (fast), and an
   in-session smoke connecting to a live bodesign HTTP server (bodesign→bodesign over
   *real* MCP) to prove the round-trip — mirroring how the `/invoke` worker was
   validated.

## Acceptance

- bodesign can call a tool on an external MCP server (Streamable HTTP) and return its
  result; an unconfigured/unreachable server degrades to `worker_unavailable` /
  `worker_starting` without crashing or fabricating.
- No new dependency (uses the existing `mcp` SDK client).
- The single external endpoint and "independently operable" design are unchanged.

## Future

- `emit_doc → docxmcp` convenience binding (needs docxmcp's decompose/assemble API
  mapping — a verifiable follow-up).
- Spine dispatch: let `agent_registry` mark a layer external-MCP-backed and have the
  C00 loop dispatch to it via `call_external_mcp_tool`.
- Option 3 gateway only if a single-endpoint requirement appears (reuse, don't build).

## Sources

- FastMCP composition/proxy — https://gofastmcp.com/servers/composition , https://gofastmcp.com/servers/providers/proxy
- MCP spec discussion #94 (server-as-proxy-client guidance) — https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/94
- mcp-proxy (aggregate to one endpoint) — https://github.com/tbxark/mcp-proxy ; stdio↔HTTP bridge — https://github.com/sparfenyuk/mcp-proxy
- Microsoft mcp-gateway — https://github.com/microsoft/mcp-gateway
