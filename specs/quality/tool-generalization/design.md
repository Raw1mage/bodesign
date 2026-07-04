# Design: quality_tool-generalization

## Context

The bodesign MCP tool suite (68 tools) was derived from one real board run (OpenMV / STM32N657 / aiguard). A session generality inventory split it in two:

- **workflow-core (C00–C07), 45 core tools — GENERAL.** Templates explicitly de-productized; values keyword-extracted from the user's PRD or required as explicit inputs; missing inputs marked `missing`/`external-needed`, never fabricated. This is the reference bar.
- **eda-bridge (EE/ME runtime), 18 ee + 5 me — GENERAL-WITH-CAVEAT.** General in mechanism, but several tools bake small-board / JLCPCB / STM32-class values into defaults. Two of them fail *silently* on non-reference boards.

This work produces two artifacts at different layers: a **repeatable generality check** (process) and **remediation of the silent-failure overfits** (code).

## Goals / Non-Goals

### Goals
- A repeatable generality check (5-axis checklist + lint/test concept) applied to the shipped tool layer only (`packages/*/bodesign_*`, `services/mcp/server.py` handlers — not tests/docs/plans).
- Severity classification of hotspots H1–H5.
- Remediate the two silent-failure overfits (H1 `route_net2pcb`, H2 `si_check`) to caller-driven/reported.
- Regression tests proving the fixed tools behave correctly on a non-OpenMV board shape and still fail-fast on missing inputs.

### Non-Goals
- Not making tools universal to every PCB domain (RF / high-power / motor-driver). The bar is *no silent overfit*, not infinite coverage — an explicit, reported limitation is acceptable.
- No change to workflow-core (already general).
- No new EDA capability; this is hardening, not feature work.

## Decisions

<!-- DD entries appended by spec_record_decision -->
- **DD-1**: DD-1: The generality bar is "no SILENT overfit", not "universal coverage" — a board/process-specific value is acceptable if it is caller-overridable OR explicitly reported as applied/not-applied; it is a defect only when the tool silently does the wrong thing (or a no-op) on a non-reference board without telling the caller.
- **DD-2**: Remediation order is severity-first, not tool-count-first: fix the two silent-failure overfits (H1 route_net2pcb refdes-gated USB-C mapping, H2 si_check hardcoded rdrv/cload/edge/thresholds) before the visible acceptable-caveat ones (H3 emit_layout grid, H4 emit_fab layers, H5 process defaults), because silent-wrong output is more dangerous to a reusing agent than visibly-wrong output.
- **DD-3**: DD-3: Backward compatibility is preserved by making existing constants documented defaults that are echoed in tool results — not by removing them. The OpenMV board keeps producing identical output when callers omit the new inputs; the only behavioural change is that the effective values (and any unmapped connectors) are now reported instead of hidden.

## Risks / Trade-offs

- **Backward compatibility**: the OpenMV board must keep working. Mitigation — existing defaults become *documented* defaults (echoed in results), not removed behaviour. `rdrv/cload/edge`, the USB-C table, grid/PDF layers stay numerically identical when the caller omits them.
- **Scope creep into a "process profile" object**: tempting to centralize all stackup/clearance/via defaults into one shared object. Deferred (Open Question) — only H1/H2 are in scope now; over-refactoring H3–H5 risks touching every EE tool.
- **Lint false-positives**: a generality lint that greps for numeric constants will flag universal physics (speed of light, copper resistivity). Mitigation — the lint targets a curated allow/deny set, and the checklist (human judgment) is the primary gate until H1/H2 land; lint is warn-only first, hard gate after.
- **EE-worker dependency for board tests**: H1's `route_net2pcb` and the board-mutation path need `pcbnew`. Non-OpenMV-board regression for H2 `si_check` can run as pure ngspice; H1 may need the EE worker or a fixture board — a stop gate if neither is available.

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/routing.py` — `_USBC` table + J1 gate (H1, lines 37-38/113); `si_check` rdrv/cload/edge/thresholds + `PS_PER_MM_DEFAULT` (H2, lines 28/466-505); `via_in_pad`/`pour_planes` process defaults (H5, lines 139/196-205).
- `packages/eda-bridge/bodesign_eda_bridge/layout.py` — `emit_layout` grid/board defaults (H3, lines 39/56/85-86).
- `packages/eda-bridge/bodesign_eda_bridge/fab.py` — `_PDF_LAYERS` (H4, line 24).
- `services/mcp/server.py` — tool schemas/handlers that must expose the new inputs and echo effective values.
- `tests/test_eda_bridge.py`, `tests/test_mcp_server.py` — generality regression tests (non-OpenMV board shape).
- `specs/architecture.md` — EDA-bridge generality-contract note (at living transition).
