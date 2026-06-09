# Event: EDA MCP Toolchain Integration Plan

## 需求

- Convert the real OpenMV/STM32N657 C04 board-run experience into a plan-builder managed bodesign MCP integration plan.
- Treat the result as reusable toolchain knowledge, not a one-off script inventory.
- Correct the first plan draft so it starts with a full C00-C07 generated-artifact inventory, not only C04 routing scripts.

## 範圍(IN)

- Plan remaining MCP tool integrations beyond via-in-pad: impedance solving, clearance-safe widening, bus length matching, and Gerber preview.
- Add a mandatory C00-C07 inventory/classification pass before more implementation.
- Preserve already integrated MCP baseline: net2pcb, via-in-pad, pour planes, DRC gate, SI gate, autoroute.
- Capture worker routing, fail-fast behavior, validation gates, and practical limitations.

## 範圍(OUT)

- No implementation in this planning step.
- No claim of fabrication-ready output without DRC/SI/user approval.
- No new save-back or durable project storage semantics.

## 任務清單

- [x] Create plan package under `plans/feature_eda-mcp-toolchain/`.
- [x] Write `implementation-spec.md` from the real board-run lessons.
- [x] Write `tasks.md` with dependency and approval gates.
- [x] Write IDEF0/GRAFCET companion artifacts.
- [x] Record this event log.
- [x] Amend plan after review to require C00-C07 inventory before implementation.
- [x] Complete C00-C07 inventory/classification and write `plans/feature_eda-mcp-toolchain/c00-c07-inventory.md`.

## Key Decisions

- The integration unit is the C04 EDA toolchain, not isolated host scripts.
- `pcbnew` tools must route to EE worker; core must not fake results.
- `impedance_solve` can start in core because it is pure math.
- `meander.py` should not become a standalone MCP tool because `length_match.py` supersedes it.
- Gerber preview is useful review evidence but remains dependency-gated and is not a DRC substitute.
- The first plan draft was too C04-centered; C00-C07 intermediate artifacts must be inventoried and classified before deciding the full MCP/workflow promotion set.

## Issues Found

- Existing architecture docs predate the newly landed C04 routing/finishing MCP tools and still describe some KiCad/Freerouting pieces as pending.
- Gerber preview dependency placement is unresolved and should be decided during implementation.
- Quick repository scan found C01/C02/C03/C05/C06 generated JSON/SCAD/report artifacts in addition to C04 scripts, so the inventory is not complete yet.
- Completed inventory shows C00-C06 document/package layers are mostly already represented in workflow-core/MCP; C04 runtime tools remain the immediate MCP gap.
- New follow-up gaps found outside C04: C03→C05 pin-map normalization, C06 verdict ingestion from C04/verify reports, and C07 manufacturing-transfer assembler/readiness.

## Verification

- Read `specs/architecture.md` to align with bodesign module boundaries and safety rules.
- Read `services/mcp/server.py` EE tool routing to confirm existing C04 tools use `_EE_GROUP_TOOLS`.
- Read prior host-side scripts in `thesmart_products/openmv/C04-Layout/generated/tools/` during the inventory step.
- Read representative C00-C07 outputs and bodesign MCP/workflow handlers to classify existing coverage versus gaps.
- Architecture Sync: Pending for implementation slice; this planning slice records that architecture currently needs a later update once tool integration lands.

## Remaining

- Implement tasks T0-T11 in `plans/feature_eda-mcp-toolchain/tasks.md`.
- T0/T1 are complete; implement remaining T2-T11 in `plans/feature_eda-mcp-toolchain/tasks.md`.
- Update `specs/architecture.md` after runtime integration lands.

## Implementation Start — 2026-06-09

- Scope: begin executing T2-T11 from `plans/feature_eda-mcp-toolchain/tasks.md`.
- Initial checkpoint: prior validation confirmed `bodesign_via_in_pad` is already registered, exported, and routed to EE worker; remaining implementation starts with pure core `bodesign_impedance_solve`.
- Validation target: direct unit tests for pure impedance math, MCP schema/group checks, and socket-level smoke where dependencies allow.
- T8 Gerber preview landed as `bodesign_render_gerber_preview` in core using the existing gerber-core pygerber raster path for real single-layer rendering. Composite/front/stack modes now return explicit `render-unavailable` because no safe multilayer compositing renderer exists in the current core/reverse-core infrastructure; no decorative fallback was added.
- T8 validation: `tests/test_gerber_geometry.py` passed (8 tests, 1 skipped) and targeted MCP schema/group tests for `bodesign_render_gerber_preview` passed. Full `tests/test_mcp_server.py` remains blocked in this interpreter by pre-existing missing `bodesign_design_ir`/`httpx` dependencies, unrelated to T8.

## Implementation Checkpoint — 2026-06-09

- Completed T2-T9: added `bodesign_impedance_solve`, `bodesign_widen_bus_tracks`, `bodesign_length_match_bus`, and `bodesign_render_gerber_preview`; updated MCP schemas, exports, EE/core grouping, and direct unit tests.
- Validation passed: `PYTHONPATH="services/mcp:packages/workflow-core:packages/eda-bridge:packages/gerber-core:packages/reverse-core:packages/me-bridge:packages/shared" python3 -m unittest tests.test_eda_bridge tests.test_gerber_geometry tests.test_mcp_server.McpServerTests.test_tool_groups_assigned tests.test_mcp_server.McpServerTests.test_render_gerber_preview_schema_and_core_unavailable_mode tests.test_mcp_server.McpServerTests.test_run_tool_impedance_solve_is_core_and_structured tests.test_mcp_server.McpServerTests.test_widen_bus_tracks_schema_and_core_routing tests.test_mcp_server.McpServerTests.test_length_match_bus_schema_and_core_routing` → 19 tests OK, 1 skipped.
- T10 blocker: socket-level MCP smoke cannot run in the current host interpreter because `tests.test_mcp_server.McpServerTests.test_build_server_when_mcp_available` is skipped when the MCP SDK is unavailable; no fake socket validation was substituted.
- Architecture Sync: Updated `specs/architecture.md` EDA bridge section to reflect current C04 MCP coverage, core/EE worker boundaries, fail-fast preview behavior, and remaining multilayer/fabrication limits.
- Remaining: install/use an environment with MCP SDK and required runtime dependencies, then run real MCP list/call socket smoke before marking T10 complete and closing T11.
