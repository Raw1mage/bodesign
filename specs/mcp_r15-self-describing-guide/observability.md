# Observability: mcp_r15-self-describing-guide

## Events

- **Startup doctrine load** — on server import, `_load_doctrine()` reads
  `skills/bodesign/doctrine.md`; on success binds `BODESIGN_GUIDE_DOCTRINE`, on
  missing/empty raises `DOCTRINE_SOURCE_MISSING`/`_EMPTY` and the container exits
  non-zero (visible in `mcpctl.sh log` / `docker compose logs`).
- **`bodesign_init` tool call** — logged through the standard MCP `tools/call`
  dispatch path in `run_tool`; returns `{ok, doctrine, source}`.
- **`prompts/get bodesign_init`** — logged through the `get_prompt` handler path.
- **`initialize`** — the returned `instructions` (carrying the R15.3 signpost) is
  observable in any client's initialize response.

## Metrics

- **doctrine length (chars)** — `len(BODESIGN_GUIDE_DOCTRINE)`; live value ~11872.
  Cross-check tool-face vs prompts-face equality as the single-source drift metric
  (must be byte-identical).
- **container health** — 3 services (core/me/ee in workers mode) report healthy after
  restart as the deploy-readiness signal; a doctrine load failure surfaces as an
  unhealthy/exited core service.
- **signpost presence** — boolean: `initialize.instructions` and
  `mcp.json.instructions` both contain the `USAGE GUIDE` marker.
