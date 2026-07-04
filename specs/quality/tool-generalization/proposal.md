# Proposal: quality_tool-generalization

## Why

- The bodesign MCP tool suite (68 tools) was derived from one real end-to-end board run (OpenMV / STM32N657 / aiguard). A session-level generality inventory found that while the **structure and input contracts are general**, several **eda-bridge runtime tools bake prototyping-process and board-specific values into their defaults** — and two of them **fail silently** (wrong/no-op behaviour the caller is never told about) on boards unlike the OpenMV reference.
- Silent overfit is worse than an explicit limitation: an agent reusing these tools on a different board gets plausible-but-wrong output with no signal. This plan turns the ad-hoc inventory into (a) a **repeatable generality check** so regressions are caught, and (b) a **prioritized remediation backlog** that lifts the silent-failure overfits first.

## Original Requirement Wording (Baseline)

- "盤點之後要開一個 tool generalization check plan" — following the session inventory of whether the bodesign tool suite (68 tools) has 泛用性 (generality) vs is overfit to the OpenMV/STM32N657 prototype board.

## Requirement Revision History

- 2026-06-09: initial draft created via plan-init.ts
- 2026-06-09: seeded with the session generality-inventory findings (5 overfit hotspots, line-verified).

## Effective Requirement Description

1. Define a **repeatable generality check** (a checklist + ideally a test/lint pass) that flags any shipped tool logic carrying board-specific or process-specific constants that are not caller-overridable.
2. Classify every existing overfit hotspot as: silent-failure (must fix), hidden-default rule-violation (should fix), or acceptable-caveat (document only).
3. Remediate the two **silent-failure** overfits first: `route_net2pcb` USB-C/refdes assumption and `si_check` hardcoded driver/load/edge constants.
4. Keep the audit evidence and verdicts as living knowledge so future tool additions are checked against the same bar.

## Inventory Baseline (line-verified this session)

Two-layer split:

- **workflow-core (C00–C07), 45 core tools — GENERAL ✅.** Templates explicitly "de-productized"; behaviour is keyword-extracted from the user's PRD or driven by explicit inputs; never fabricates values or human approval. OpenMV appears only in docstrings/narrative, not logic. No remediation needed; serves as the reference bar for what "general" looks like.
- **eda-bridge (EE/ME runtime), 18 ee + 5 me — GENERAL-WITH-CAVEAT ⚠️.** General in mechanism, but several tools焊死 small-board / JLCPCB / STM32-class defaults.

### Overfit hotspots (severity-ranked)

| # | Tool | Location | Issue | Severity |
|---|---|---|---|---|
| H1 | `route_net2pcb` | [routing.py:37-38,113](../../packages/eda-bridge/bodesign_eda_bridge/routing.py#L37) | `_USBC` pinout applied only when `ref == "J1" and "USB" in footprint`; on a board where USB-C is not refdes J1 it **silently no-ops** — no mapping, no warning. | **silent-failure** |
| H2 | `si_check` | [routing.py:471,28,479-481,500](../../packages/eda-bridge/bodesign_eda_bridge/routing.py#L466) | `rdrv=17.0, cload=3e-12` driver/load constants + fixed `0.3ns` edge + `PS_PER_MM_DEFAULT=5.97` (4-layer JLC stack) + hardcoded overshoot/undershoot thresholds; **not caller-overridable** → violates the project's "no hidden defaults" rule and assumes an STM32-class CMOS output buffer. | **silent-failure / rule-violation** |
| H3 | `emit_layout` | [layout.py:39,56,85-86](../../packages/eda-bridge/bodesign_eda_bridge/layout.py#L52) | Auto-place grid `start 15mm / pitch 12mm / margin 10mm`, default board `60×40mm` — overfits small prototype boards; mis-places on large/dense layouts. Tunable params exist but are not exposed at the MCP handler layer. | acceptable-caveat (expose) |
| H4 | `emit_fab` | [fab.py:24](../../packages/eda-bridge/bodesign_eda_bridge/fab.py#L24) | `_PDF_LAYERS` hardcoded to F/B Cu+SilkS+Edge.Cuts → 6+ layer inner copper omitted from the fab PDF. | acceptable-caveat (expose) |
| H5 | `via_in_pad`, `pour_planes` | [routing.py:139,196-205](../../packages/eda-bridge/bodesign_eda_bridge/routing.py#L139) | JLCPCB fine-pitch-BGA process defaults (drill 0.2 / pad 0.3 / keep 2; stitch grid 14mm, via 0.6/0.3); fail-soft and tunable, but baked. | acceptable-caveat (document) |

Pure-general (no action): `impedance_solve` (universal microstrip physics only), `layout_drc_gate`, `autoroute`, `render_gerber_preview`, `simulate`, `analyze_emc`, `analyze_thermal`, `export_bom`, `export_netlist`, `emit_symbol`.

## Scope

### IN
- A documented, repeatable **generality check** (checklist + lint/test pass concept) applied to the shipped tool layer.
- Severity classification of all overfit hotspots H1–H5.
- Remediation of the two silent-failure overfits: H1 (`route_net2pcb` connector mapping → caller-provided pinmap, or report applied/not-applied) and H2 (`si_check` `rdrv`/`cload`/edge/thresholds → optional inputs like the existing `z0`/`rs`/`vdd`).
- Tests proving the fixed tools behave correctly on a non-OpenMV board shape and still fail-fast on missing inputs.

### OUT
- No change to workflow-core (C00–C07) — already general; only referenced as the bar.
- No new EDA capability; this is generality hardening, not feature work.
- No silent behaviour change to acceptable-caveat tools (H3–H5) beyond optionally exposing their params; their process defaults stay until a concrete non-prototype board needs them.

## Non-Goals

- Not making the tools universal to every PCB domain (RF, high-power, motor-driver) — the goal is **no silent overfit**, not infinite coverage. An explicit, reported limitation is an acceptable outcome.

## Constraints

- Must preserve the project's hard rules: `pcbnew` tools stay EE-worker-routed; no fabricated success; mutating tools write a new path and return it.
- Fixes must remain backward-compatible for the OpenMV board (the existing defaults become the *documented defaults*, not removed behaviour) while becoming overridable/reported.

## What Changes

- `route_net2pcb`: accept an explicit connector pinmap (or detect-and-report) instead of the implicit `J1`-gated `_USBC` table.
- `si_check`: promote `rdrv`, `cload`, edge time, and overshoot/undershoot thresholds to optional caller inputs with documented defaults.
- New: a generality-check artifact (checklist) + a regression test asserting no un-overridable board-specific constant sneaks into the shipped tool layer.

## Capabilities

### New Capabilities
- Generality check: a repeatable audit (and lint/test) that flags board/process constants not exposed as caller inputs.

### Modified Capabilities
- `route_net2pcb`: connector pin mapping becomes caller-driven / reported instead of silently refdes-gated.
- `si_check`: SI driver/load/edge/threshold assumptions become overridable; defaults documented as STM32-class-CMOS reference.

## Impact

- Affected code: `packages/eda-bridge/bodesign_eda_bridge/routing.py`, `layout.py`, `fab.py`; MCP handlers + schemas in `services/mcp/server.py`; tests under `tests/`.
- Affected docs: `specs/architecture.md` EDA-bridge section (note the generality contract).
- No impact on workflow-core or the C00–C07 product flow.
