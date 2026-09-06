# Proposal: c03_pc001_coverage_and_waiver_sidecar

## Why

- `c03_delivery_contract_and_engine_seams` relocated the PC-001 passive-completeness
  rule into the delivery path (`check_c03.py`) and is otherwise complete. Two tasks
  from its WP2 are **structurally unfinished** and were carved out here so that the
  parent package could reach `verified` without either (a) ticking an untrue claim or
  (b) carrying an open task into a `verified` state.
- **The load-bearing sentence being preserved by this package** (verbatim from the
  parent's task 2.8, which is why that task is reproduced word-for-word in `tasks.md`):

  > Until this runs, PC-001's real coverage on this board is 9/16, NOT 16/16, and no
  > statement to the contrary may be made.

  The parent package's `verified` green light does **not** authorize any statement
  that PC-001 covers 16/16. That boundary is declared in the parent's
  `tasks.md` §2 pointer and in `plans/c03_delivery_contract_and_engine_seams/README.en.md`.

## Original Requirement Wording (Baseline)

- "把那兩條移到新 plan 包，本包 promote 到 verified" — user adjudication relayed
  2026-09-06 via `[BRNS-DISPATCH … round=4]`, with the hard requirement:
  "搬移不得讓這句話消失，也不得讓它變得更難被看到 … 拆包最容易失敗的方式不是搬錯地方，
  是搬完之後沒有人再讀到它".

## Requirement Revision History

- 2026-09-06: initial draft created via plan-init.ts; tasks 2.7/2.8 carved out of
  `c03_delivery_contract_and_engine_seams` verbatim.

## Effective Requirement Description

1. Port the DD-3 waiver sidecar (`passive_waivers.json`) to the delivery path, so a
   well-provenanced waiver is honoured there rather than silently absent
   (currently reported as `passive_completeness.waivers.status == "not_run"`).
2. Diagnose the 7 ICs that PC-001 did **not** cover on the aiguard board, deciding
   per-ref between the two causes (missing `pinfunction` upstream vs a too-narrow
   rail predicate) by measurement, not judgement.

## Scope

### IN
- `packages/workflow-core/bodesign_workflow_core/check_c03.py` — waiver sidecar
  ingestion; `_PWR_PREFIXES` / `_PWR_PATTERN` rail predicate if cause (b) is measured.
- Per-ref measurement on `experiments/aiguard_c03_verify/ccm.net`.

### OUT
- The skill-side P2 INTERNAL-TOOL copy at `validation_detectors.py:1261`. Under DD-01
  the two criteria are **deliberately NOT kept in sync** and already differ
  (`comp.type == 'ic'` there vs a `U*` refdes-prefix proxy in the delivery path).
  Only the delivery-path copy governs a C03 verdict.
- Exposing `readability_gate` as an MCP verb (dispatcher deferred that to its own
  package; it is gated on the `scored_subject` field landing first).

## Non-Goals

- Widening PC-001 beyond PRESENCE of a rail→GND decoupling cap. Value, count and
  placement adequacy stay in `not_checked` regardless of what this package lands.

## Constraints

- The 9/16 sentence above must remain readable from the parent package. Any edit here
  that makes it harder to reach is a defect of this package, not a simplification.
- `ics_without_identifiable_rail` must keep naming the ICs it did not examine; the
  fix must not silently fold them into the green.

## What Changes

- The delivery path gains waiver-sidecar support (status moves off `not_run`).
- PC-001's measured coverage on the aiguard board moves off 9/16 — or the residual
  gap is explained per-ref with an upstream owner named.

## Capabilities

### New Capabilities
- delivery-path waiver honouring: `passive_completeness.waivers` reports a real
  adjudication instead of `not_run`.

### Modified Capabilities
- `_ic_power_rails` rail predicate: possibly widened, only if the per-ref measurement
  shows cause (b). If the measurement shows cause (a), **no change here is correct**
  and the fix belongs to whatever produced the netlist.

## Impact

- `packages/workflow-core/bodesign_workflow_core/check_c03.py`
- `tests/test_check_c03_passive_completeness.py`
- `specs/architecture.md` (PC-001 coverage statement)
- Parent package `c03_delivery_contract_and_engine_seams` (effect-boundary pointer)
