# Tasks: quality_tool-generalization

## A1 — Define the generality check
- [ ] T1 — Write the 5-axis generality checklist (input-driven vs hardcoded, hidden defaults, toolchain coupling, domain breadth, silent-vs-reported) as a repeatable artifact in the repo (e.g. `docs/generality-check.md` or a checklist in this spec).
- [ ] T2 — Prototype a generality lint/test: import the tool registry, flag board/process constants in shipped tool logic that are not reachable as schema inputs; allow-list universal-physics constants. Warn-only initially.

## A2 — Classify hotspots
- [x] T3 — Severity-classify H1–H5 (done in proposal: silent-failure {H1,H2}, expose {H3,H4}, document {H5}).

## A3 — Remediate silent-failure overfits
- [ ] T4 — H1 `route_net2pcb`: add optional `connectors` pinmap input; keep built-in USB-C table as a named default; stop gating on `ref == "J1"`; return `applied_pinmaps` + `unmapped_connectors`.
- [ ] T5 — H1: update `services/mcp/server.py` schema/handler for the new `connectors` input and report fields.
- [ ] T6 — H2 `si_check`: promote `rdrv`, `cload`, `edge_ns`, `overshoot_pass_pct`, `overshoot_warn_pct` to optional inputs with documented STM32-class-CMOS defaults; echo effective values in the result.
- [ ] T7 — H2: update `services/mcp/server.py` schema/handler for the new SI inputs and effective-value echo.

## A4 — Validate generality
- [ ] T8 — H1 regression: test `route_net2pcb` on a non-J1 USB-C board asserts `unmapped_connectors` reported (no silent no-op); test explicit pinmap is applied + listed.
- [ ] T9 — H2 regression: test overridden `rdrv`/`cload` are used + echoed; test omitted inputs fall back to documented defaults that are reported.
- [ ] T10 — Confirm both fixed tools still fail-fast on missing required inputs and remain EE-worker-routed for `pcbnew`. Run the socket-level smoke (from feature_eda-mcp-toolchain) to confirm no regression in tool listing/calling.
- [ ] T11 — Expose-only follow-ups (lower priority): surface `emit_layout` grid params (H3) and `emit_fab` `pdf_layers` (H4) at the MCP schema; document `via_in_pad`/`pour_planes` process defaults (H5). May split to a follow-up slice.
- [ ] T12 — Update `specs/architecture.md` EDA-bridge section with the generality contract; record event log.

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
