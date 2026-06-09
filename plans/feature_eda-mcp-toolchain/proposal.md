# Proposal: feature_eda-mcp-toolchain

## Why

- The first end-to-end board run (OpenMV / STM32N657 / aiguard) produced its C04 EDA steps as ad-hoc host-side shell/Python scripts and loose generated files. The reusable unit is the deterministic C04 toolchain, not a single via-in-pad helper. Promoting the validated scripts into first-class bodesign MCP tools lets future agents execute the real product-development workflow through typed calls instead of re-deriving shell scripts each time.
- Before promoting more C04 tools, a full C00–C07 inventory was required so reusable capabilities land at the right layer (MCP tool vs workflow-core vs template vs fixture) and nothing is overfit to one board.

## What Changes

- A mandatory C00–C07 inventory/classification pass precedes implementation (recorded in `c00-c07-inventory.md`).
- Four new C04 MCP tools land: `bodesign_impedance_solve` (pure core), `bodesign_widen_bus_tracks`, `bodesign_length_match_bus` (EE worker), `bodesign_render_gerber_preview` (core, dependency-gated).
- The pre-existing C04 baseline (`route_net2pcb`, `via_in_pad`, `pour_planes`, `layout_drc_gate`, `si_check`, `autoroute`) is preserved and documented.
- `pcbnew`/KiCad-dependent tools route to the EE worker via `_EE_GROUP_TOOLS`; pure math stays in core.
- A durable socket-level MCP smoke test proves the tools are callable through the real server path.

## Capabilities

### New Capabilities
- `bodesign_impedance_solve`: closed-form microstrip/differential class widths + delay constants from explicit stackup + targets (guidance, fab-solver-confirmed).
- `bodesign_widen_bus_tracks`: clearance-safe recovery of high-speed bus widths after neckdown (EE worker).
- `bodesign_length_match_bus`: clearance-aware serpentine skew tuning within an explicit timing budget (EE worker).
- `bodesign_render_gerber_preview`: single-layer Gerber raster for review evidence; explicit `render-unavailable` for composite/stack modes (no decorative fallback).

### Modified Capabilities
- MCP server tool registry + grouping in `services/mcp/server.py` gains the four tools with EE/core routing.

## Impact

- Affected code: `packages/eda-bridge/bodesign_eda_bridge/` (impedance.py, routing.py), `packages/gerber-core/bodesign_gerber_core/` (preview), `services/mcp/server.py` (schemas/handlers/grouping), `tests/`.
- Affected docs: `specs/architecture.md` EDA-bridge section.
- Out of scope: fabrication-ready claims without DRC/SI/approval; durable server-owned project storage; a separate `meander` tool (subsumed by length matching).
