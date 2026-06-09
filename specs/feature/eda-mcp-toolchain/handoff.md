# Handoff: feature_eda-mcp-toolchain

## Execution Contract

- Promote validated C04 scripts to MCP tools with structured JSON I/O; never port them as shell wrappers.
- `pcbnew`/KiCad tools execute in the EE worker (`_EE_GROUP_TOOLS`); core must not fake EE results. Pure math (`impedance_solve`) stays in core.
- Fail-fast on missing deps/worker; mutating board tools write a new output path and return it.
- No fabrication-ready claim without DRC/SI/user approval; no decorative render fallback.

## Required Reads

- `plans/feature_eda-mcp-toolchain/proposal.md`, `spec.md`, `design.md` — scope, contracts, decisions.
- `plans/feature_eda-mcp-toolchain/c00-c07-inventory.md` — stage-by-stage classification (why C04 is the gap).
- `plans/feature_eda-mcp-toolchain/implementation-spec.md` — original detailed implementation spec (supporting).
- `services/mcp/server.py` — handler/schema/grouping conventions and `build_server`/stdio path.
- `tests/test_mcp_server.py` — the socket-level smoke pattern.

## Stop Gates In Force

- STOP if the EE worker cannot import `pcbnew` for board-mutating tools (do not fall back to core).
- STOP if a tool would need hidden defaults for stackup, timing budget, or process capability.
- STOP if socket-level MCP execution cannot prove the tool is callable through the real server path.

## Execution-Ready Checklist

- [x] C00–C07 inventory complete and classified.
- [x] EE worker boundary (`_EE_GROUP_TOOLS`) understood for `pcbnew` tools.
- [x] MCP-SDK environment available for the socket-level smoke (venv path used; skips on bare host).
- [x] HEAD self-consistency verified (orphaned impl modules committed).
