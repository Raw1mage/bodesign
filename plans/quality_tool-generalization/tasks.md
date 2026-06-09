# Tasks: quality_tool-generalization

## A1 — Define the generality check
- [x] T1 — Wrote the 5-axis generality checklist as `docs/generality-check.md` (bar, scope, severity classes, current audit table, automated arm).
- [x] T2 — Built `tests/test_tool_generality.py`: encodes the contract as data (tool -> required override inputs + required report fields) asserted against live MCP schemas; schema-level, no pcbnew/ngspice, fails if any de-overfit override is later dropped.

## A2 — Classify hotspots
- [x] T3 — Severity-classify H1–H5 (done in proposal: silent-failure {H1,H2}, expose {H3,H4}, document {H5}).

## A3 — Remediate silent-failure overfits
- [x] T4 — H1 `route_net2pcb`: added optional `connectors` pinmap input; built-in USB-C table kept as a named default; J1 gating removed (now applies to any USB-C footprint by FPID on any refdes); returns `applied_pinmaps` + `unmapped_connectors`. Silent-failure decision extracted to pure `resolve_connector_pads`.
- [x] T5 — H1: `services/mcp/server.py` schema/handler updated with the `connectors` input and the report fields documented in the tool description.
- [x] T6 — H2 `si_check`: promoted `rdrv`, `cload`, `edge_ns`, `overshoot_pass_pct`, `overshoot_warn_pct` to optional inputs with documented STM32-class-CMOS defaults; result echoes `effective`. Threshold classification extracted to pure `si_status`.
- [x] T7 — H2: `services/mcp/server.py` schema/handler updated with the new SI inputs and the effective-value echo documented.

## A4 — Validate generality
- [x] T8 — H1 regression (pure-helper level): `resolve_connector_pads` tests assert USB-C expands on non-J1 refdes (J5), J1 stays backward-compatible (DD-3), explicit pinmap wins, and a non-match keeps the single pin with `expanded=False` (the report signal). Board-level mutation regression is env-gated (needs `pcbnew`/EE worker) — same posture as feature_eda-mcp-toolchain T10.
- [x] T9 — H2 regression: `si_status` tests assert default thresholds AND that overridden thresholds change the verdict (stricter device fails 15%, looser passes). MCP schema test asserts the new inputs are reachable.
- [x] T10 — EE grouping confirmed for both tools; socket-level smoke re-run on the modified server (initialize→list_tools→call_tool) passes with no regression. Board-mutating fail-fast (`_need_pcbnew`) on the host is env-gated.
- [x] T11 — H3 `emit_layout` (board_mm/columns/place_start_mm/place_pitch_mm/margin_mm) and H4 `emit_fab` (pdf_layers) exposed at the MCP schema; H5 `via_in_pad` (drill/pad/keep_rings, already exposed, now documented) and `pour_planes` (stitch_net/stitch_pitch_mm/stitch_drill_mm/stitch_pad_mm — newly exposed, were baked) now caller-overridable with documented JLCPCB-class defaults.
- [x] T12 — `specs/architecture.md` EDA-bridge section records the full generality contract (H1–H5 overridable/reported); event log recorded.

## Remaining (env-gated only)
- Full board-level mutation regression for H1/H3/H5 (real `route_net2pcb`/`emit_layout`/`pour_planes` on a board) is env-gated on a `pcbnew` EE worker — same posture as feature_eda-mcp-toolchain T10. The decision logic is covered by pure-helper + schema tests on the bare host.

## Dependencies
- T1 → T2 (lint operationalizes the checklist).
- T4 → T5 → T8 (H1 chain).
- T6 → T7 → T9 (H2 chain).
- T10 depends on T5/T7 landing.
- T12 depends on validation evidence from T8/T9/T10.

## Approval / Stop Gates
- A fix must never fabricate a board/process default to "fill a gap" — if a value is genuinely unknown, fail fast (stop gate).
- H1 board-mutation regression may require the EE worker / a fixture board with `pcbnew`; if unavailable, record an env blocker like feature_eda-mcp-toolchain T10 rather than faking it.
- H3–H5 (T11) change no defaults; if scope grows into a shared "process profile" object, split a separate plan rather than expanding this one.
