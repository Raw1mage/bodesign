# Tasks: EDA MCP Toolchain Integration

- [x] T0 — Inventory C00-C07 generated scripts, JSON bridges, package files, reports, and handoff artifacts.
- [x] T1 — Classify each inventory item as MCP, workflow-core, template/package output, fixture/evidence, discard, or blocker.
- [x] T2 — Extract impedance solver into `bodesign_eda_bridge` with structured return values.
- [x] T3 — Register `bodesign_impedance_solve` MCP handler/schema in core.
- [x] T4 — Extract clearance-safe widening into `bodesign_eda_bridge`.
- [x] T5 — Register `bodesign_widen_bus_tracks` and route it to EE worker.
- [x] T6 — Extract clearance-aware bus length matching into `bodesign_eda_bridge`.
- [x] T7 — Register `bodesign_length_match_bus` and route it to EE worker.
- [x] T8 — Consolidate Gerber preview scripts behind one MCP preview tool or record dependency blocker.
- [x] T9 — Add direct/unit tests for handlers, tool grouping, and pure math outputs.
- [!] T10 — Run socket-level smoke tests for new MCP tools. Blocked in current host Python: MCP SDK unavailable (`test_build_server_when_mcp_available` skipped), so real socket-level MCP list/call cannot be launched here.
- [x] T11 — Update event log and architecture sync notes before completion.

## Dependencies

- T1 depends on T0.
- T2 depends on T1.
- T3 depends on T2.
- T5 depends on T4.
- T7 depends on T6.
- T10 depends on T3, T5, T7, and T8 decision.
- T11 depends on validation evidence from T9/T10.

## Inventory Result

- See `c00-c07-inventory.md` for the stage-by-stage classification.
- Immediate MCP implementation remains C04-focused because C00-C06 document/package layers are largely already covered by workflow-core/MCP.
- New non-C04 follow-up backlog: C03→C05 pin-map normalization, C04 build/finish manifest orchestration, C06 verdict ingestion, and C07 manufacturing-transfer assembler/readiness.

## Approval Gates

- Gerber preview dependency placement requires a design decision if core image size or Cairo dependency risk is high.
- Any automatic mutation of user-owned project folders remains out of scope and requires separate approval.
