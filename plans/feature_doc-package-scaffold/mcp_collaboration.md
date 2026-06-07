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

## F-5 design (detailed): declarative backend binding + spine dispatch

**Goal:** let the C00 autonomous loop dispatch a C0x layer to whatever backend serves
it — a bodesign worker OR an external MCP server — **without scattered hardcoded
branches**. The decision "which backend serves which layer" is *data*; the dispatch
policy is the existing deterministic state machine; semantic judgment stays with the
LLM/human (bodesign never makes it). The only hand-wired code is a small per-MCP
*adapter* (an interface concern, not a judgment).

### 1. Declarative `backend` on each layer (data, not code)

Add a `backend` field to each section in `doc_architecture.template.json`; the
`agent_registry` surfaces it as `role.backend`. Three kinds:

```jsonc
"backend": { "kind": "native" }                                  // pure-python, runs in core
"backend": { "kind": "worker", "group": "me" }                   // bodesign own worker (/invoke)
"backend": { "kind": "external_mcp", "server": "drawmiat",        // external MCP via call_external_mcp_tool
             "adapter": "drawmiat_diagram" }
```

All C00–C06 ship as `native`/`worker` (their current reality) — F-5 is the *mechanism*;
specific `external_mcp` bindings are added later as a one-line data edit + one adapter,
when a real external-MCP-backed layer exists. No layer changes behaviour by default.

### 2. Spine dispatch reads `role.backend` (one general branch, not per-layer)

`c00_orchestration_tick` step 3 (dispatch a ready layer) consults `role.backend`:

- `native` / `worker` → unchanged: create a `work_packet` (C01 via `enter_c01_mode`).
- `external_mcp` → create the `work_packet` (for traceability + the contract), then
  invoke the named **adapter**, which calls `call_external_mcp_tool(server, tool, args)`
  and records the normalized result; if the external MCP is unavailable/starting, the
  dispatch records a **blocker** (reusing `worker_unavailable`/`worker_starting`) that
  surfaces to the user as "this layer's external tool isn't reachable" — never fabricated.

This is ONE `match role.backend.kind` in the dispatch step — not `if layer == ...`
branches per layer.

### 3. Per-MCP adapters (the only hand-wired part — interface, not judgment)

A small isolated registry `mcp_adapters.py` maps an adapter name → a function:

```python
def drawmiat_diagram(work_packet, project_state) -> dict:
    args = _build_drawmiat_args(work_packet, project_state)   # map packet → external API
    return call_external_mcp_tool("drawmiat", "generate_diagram", args)
```

One adapter per external-MCP integration; each is a thin argument-mapping + result
normalization. This cannot be pure data because every external MCP (docxmcp's
decompose/assemble, drawmiat's diagram schema) has its own API — but it is an interface
adapter, not a decision. Adapters are unit-tested with a mock `call_external_mcp_tool`.

### 4. Boundary recap (what is data vs code vs not-bodesign)

- **Backend selection (which MCP/worker):** data — `role.backend` from the template.
- **Dispatch policy (when/whether):** the existing deterministic spine (intentionally fixed).
- **Arg mapping per external tool:** isolated adapter code (interface, ~1 per integration).
- **Semantic judgment (is it good/right):** NOT bodesign's — LLM skill / human at gates.

### Acceptance (F-5)

- A layer declared `backend.kind = external_mcp` with a registered adapter is dispatched
  to that MCP by `c00_orchestration_tick`; the result/blocker is recorded.
- An external MCP that is unconfigured/unreachable yields a blocker (`worker_unavailable`/
  `worker_starting`), never a fabricated layer output.
- Layers without an `external_mcp` backend behave EXACTLY as today (no regression);
  determinism preserved (same state → same dispatch).
- Adding a new external-MCP-backed layer = one template data edit + one adapter; no
  changes to the dispatch policy.

## Future (after F-5)

- `emit_doc → docxmcp` convenience binding (a concrete adapter; needs docxmcp's
  decompose/assemble API mapping — a verifiable follow-up, F-4).
- Option 3 gateway only if a single-endpoint requirement appears (reuse, don't build).

## Sources

- FastMCP composition/proxy — https://gofastmcp.com/servers/composition , https://gofastmcp.com/servers/providers/proxy
- MCP spec discussion #94 (server-as-proxy-client guidance) — https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/94
- mcp-proxy (aggregate to one endpoint) — https://github.com/tbxark/mcp-proxy ; stdio↔HTTP bridge — https://github.com/sparfenyuk/mcp-proxy
- Microsoft mcp-gateway — https://github.com/microsoft/mcp-gateway
