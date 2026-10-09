---
id: BR_20261009_check_c03_pc001_identifies_no_power_rail_on_u1_u2_while_detector_judges_them_ok
title: Served bodesign_check_c03 PC-001 finds no identifiable power rail on U1/U2 of the S36 board (status not_run) while the public detector judges both ICs decoupled OK — two seams disagree on identical bytes
date: 2026-10-09
status: open
severity: high
priority: P1
component: services/mcp/server.py (_h_check_c03 PC-001 port), skills/bodesign/engines/kicad/scripts/validation_detectors.py (PC-001)
reporter_session: ses_04db7a1c5ffelvbxyLP1p6xlRH
edges:
  - to: plans/eda-bridge_unified-collaborative-rebuild/pc001-bounds-receipt-20261009.md
    type: evidence
  - to: plans/c03_pc001_coverage_and_waiver_sidecar/tasks.md
    type: related
  - to: issues/closed/BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate.md
    type: recurrence-of
---

## Symptom

Same subject bytes (`experiments/s3-formal/c03_engine-v1/`, HEAD `f8148a2`), two PC-001 seams:

| IC | public detector (`validation_detectors.py`) | served `bodesign_check_c03` |
| --- | --- | --- |
| U1 ETA6003 | 4 `power_in` pins; rail VBUS; decoupling C1/C2; **OK** | pinfunction `IN/SYS/BATT` match 0 hints; **no rail**; `not_run` |
| U2 Pico_W | 2 `power_in` pins; rail +3V3; decoupling C9/C10/C11; **OK** | pinfunction `VSYS/ADC_VREF/3V3/VBUS` match 0 hints; **no rail**; `not_run` |

Served report: `passive_completeness.status = not_run`, `ics_without_identifiable_rail = [U1, U2]`,
`waivers.status = not_run`. Raw outputs in the receipt.

## Why it matters

`bodesign_check_c03` is the C03→C04 STAGE-ENTRY gate. On this board it examines zero rails and
reports `not_run` — a non-verdict that reads as "nothing wrong" at a glance. The public detector
reaches a verdict because it uses the symbol's `power_in` electrical type; the served port
re-derives power pins from netlist `pinfunction` text against `_PC_POWER_PIN_HINTS` and net names
against `_PWR_PATTERN`, both of which miss this board's vocabulary (`IN`, `VSYS`, `3V3` without
`+`, net `SYS`). Two implementations of one rule; the gate is the weaker one.

## Bounded gaps also measured (not fixed, tests assert current behaviour)

- Isolated active IC (power_in pins with no nets) → public detector 0 findings (skip at
  `validation_detectors.py:1290`), served names it under `ics_without_identifiable_rail`.
- NC-marked power pin → both seams silent.
- Leaf `passive_waivers.json` not honoured when `check_c03` runs on the root (DD-3 sidecar not
  ported to the delivery path; plan `c03_pc001_coverage_and_waiver_sidecar` 2.7).

Tests: `tests/test_passive_completeness.py` (+3), `tests/test_check_c03_passive_completeness.py`
(+1), S38 `dba613a`.

## Expected

One PC-001 implementation consumed by both seams; power-pin identification by symbol electrical
type first, name hints second; `not_run` must be surfaced as a BLOCKING non-verdict at stage
entry, never as a quiet pass.
