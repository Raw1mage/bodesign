# Design: feature_eda-mcp-toolchain

## Context

Derived from the first OpenMV/STM32N657/aiguard board run, whose C04 layout steps existed as host-side shell/Python scripts (`net2pcb.py`, `viainpad.py`, `pour.py`, `impedance.py`, `widen.py`, `length_match.py`, `gerber_*.py`, `build_c04.sh`, `finish_c04.sh`). A C00–C07 inventory (`c00-c07-inventory.md`) classified every stage's artifacts; C00–C06 document/package layers were already covered by workflow-core/MCP, leaving the C04 runtime as the immediate MCP gap. This slice promotes the reusable C04 primitives into MCP tools at the correct execution group.

## Goals / Non-Goals

### Goals
- Promote 4 validated C04 scripts to MCP tools with structured JSON I/O.
- Correct execution-group routing: pure math in core, `pcbnew` mutation in the EE worker.
- Fail-fast on missing deps/worker; no fabricated success.
- Prove the real MCP-protocol callable path with a durable socket-level test.

### Non-Goals
- No fabrication-ready claim without DRC/SI/user approval.
- No `meander` MCP tool (subsumed by length matching).
- No durable server-owned project storage / save-back.
- C03→C05 pin-map normalization, C04 build/finish orchestration, C06 verdict ingestion, C07 manufacturing transfer are recorded as follow-up backlog, not built here.

## Decisions

- **DD-1**: The integration unit is the C04 EDA toolchain, not isolated host scripts — promote at the right layer after a full C00–C07 inventory.
- **DD-2**: `pcbnew`/KiCad tools route to the EE worker via `_EE_GROUP_TOOLS`; core must not fake EE results when the worker is down.
- **DD-3**: `impedance_solve` lives in core because it is pure closed-form math; outputs are labelled guidance requiring fab-solver confirmation.
- **DD-4**: `meander.py` does not become a standalone MCP tool — `length_match.py` supersedes it.
- **DD-5**: Gerber preview renders a single layer for real; composite/front/stack return explicit `render-unavailable` rather than a decorative fallback, because no safe multilayer compositing renderer exists in core.
- **DD-6**: T10 socket-level smoke is satisfied by a durable, `import mcp`-gated test that drives `server.py --transport stdio` with the real MCP client — no fake socket substituted; skips on the bare host.

## Risks / Trade-offs

- **HEAD integrity**: the tool wiring (handlers + `__init__` exports) was committed while the implementation modules (`impedance.py`, gerber-core preview) were left untracked, breaking a fresh-checkout import. Repaired in commit `6dd6d3a` by committing the orphaned modules + tests.
- **Env-gated validation**: real-board EE widen/length-match and KiCad/`pcbnew` execution need an EE worker with `pcbnew`; not exercisable on this host. Documented as `env_gated_remaining`, not a verification gap for the protocol-callable claim.
- **Dependency footprint**: Gerber preview depends on pygerber; multilayer compositing intentionally omitted rather than risk a heavy/unsafe renderer.

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/impedance.py` — `solve_impedance` (core, pure math).
- `packages/eda-bridge/bodesign_eda_bridge/routing.py` — widen/length-match (EE), plus pre-existing C04 baseline.
- `packages/gerber-core/bodesign_gerber_core/contracts.py` + `__init__.py` — `render_gerber_preview`.
- `services/mcp/server.py` — handlers, schemas, `_EE_GROUP_TOOLS` grouping, `build_server`/stdio path.
- `tests/test_eda_bridge.py`, `tests/test_gerber_geometry.py`, `tests/test_mcp_server.py` — unit + socket-level smoke.
- `specs/architecture.md` — EDA-bridge coverage/boundaries.
