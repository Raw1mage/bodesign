---
id: BR_20261009_s1_class_e_sensors_miss_a_foreign_net_wire_passing_a_power_port_pin_tip
title: S1 class-e sensors miss a foreign-net wire passing a power-port pin tip at 4 line-widths (false negative on a reviewer-rejected location)
date: 2026-10-09
status: open
instances: 2 — Review 6 usbc b25d7d50 (VBUS_CON wire 4 lw from VBUS port tip, officer-dispatched class-e reviewer ses_edfe35a76); Review 7 power_rail 1acb3d76 (IN wire along VBUS flag top edge 4–5 lw, reviewer ses_edfc83d67). Same net in the second case: corridor ambiguity, not a short. Pattern across two leaves, two reviewers; instrument class e zero on both. See s1-instrument-receipt.md §14.4–14.5.
severity: medium
priority: P2
component: packages/eda-bridge/bodesign_eda_bridge/readability_render.py (class e sensors)
reporter_session: ses_04db7a1c5ffelvbxyLP1p6xlRH
edges:
  - to: plans/eda-bridge_unified-collaborative-rebuild/s1-instrument-receipt.md#144-class-e-targeted-review-of-the-review-6-candidate-officer-dispatch-2026-10-09
    type: surfaced-by
    reason: The targeted class-e review that produced the rejecting reading on bytes the instrument scored zero.
  - to: plans/eda-bridge_unified-collaborative-rebuild/s1-instrument-receipt.md#12-class-e-scope-annotation-packagegroup-coherence-is-not-assessed-astra-r4-2026-10-06
    type: same-family
    reason: Second documented class-e population the implemented sensors do not model.
---
# S1 class-e sensors miss a foreign-net wire passing a power-port pin tip

- **Status**: OPEN — measured false-negative candidate; detector work not started (user ruling 2026-10-09: find new accepting candidate first, then fix)

## 1. Symptom (measured)

Subject: Review 6 usbc candidate, PNG sha256 `b25d7d50b3530627ec8f12a2330e568a0321d57f717d23fe5e1a3f909b261004`
(`~/.cache/scratch/s3-elk-spike/run-r6-173849/native/pdfpath/usbc-1.png`, 1754×1241), manifest root
`174b3b46…`.

- Instrument `readability_render.py` `9c18bc51…` (Review 6) and `f98dc237…` (current): class e
  `findings = []`, verdict a–f zero findings, overall `indeterminate` (calibration partial).
- Independent blind reviewer (`task(general)` `ses_edfe35a76`, class-e question only, 1:1 crops):
  **NEAR-TOUCH** — VBUS_CON vertical wire at x=397 passes the VBUS power-port symbol pin tip at
  (397–401, 286), gap ≈ 4 px ≈ 4 line-widths; "reader hesitates whether VBUS port lands on the
  passing wire". No OVERLAP anywhere else; five other corridors CLEAR at ≥19 lw.

Same bytes, instrument silent, reviewer rejects → class-e false-negative candidate.

## 2. RCA (observed + hypothesis)

Observed: the implemented class-e sensors are `E_WIRE_THROUGH_BODY`, over-unconnected-pin, and
`E_PIN_ROW_CORRIDOR` (receipt §4, §12). Their populations are symbol bodies and multi-pin rows.
Hypothesis, unverified against source: a power-port / flag symbol has one pin and a glyph, not a
body rectangle or a pin row, so a foreign-net wire passing its pin tip falls in no sensor's
population. The 4-lw gap is also below any corridor clearance that would have fired on a
multi-pin row.

## 3. Proposed remediation (owner ruling needed on scope; NOT authorized yet)

1. Add a class-e sensor: foreign-net wire segment within `E_PORT_TIP_CLEARANCE_LW` (candidate
   value: 6 lw, to be frozen before measurement) of a power-port / global-label / hierarchical-
   label pin tip, where the wire's net ≠ the port's net. Report evidence region in mm and px.
2. Rejecting fixture: the R6 candidate native triple (.kicad_sch/.svg/.net already pinned in
   `tests/fixtures/readability_render/s3_usbc_20261006/` or r5b) — confirm which bytes
   correspond to PNG `b25d7d50` before pinning.
3. FP check: the sensor must stay silent on `clean_divider`, `b1`, and every CP3 sheet where the
   reviewer did not cite a port-tip near-touch; report per-sheet counts.
4. New instrument identity (hash changes); policy digest `443bbb0185d5a914` must be re-derived
   and the calibration record re-resolved; §13.4-style before/after population rerun.

## 4. Acceptance

- Sensor fires once on the R6 candidate at the reviewer's location (±2 lw) and nowhere else on
  that sheet.
- Zero new findings on the accepting exemplars (clean, b1) and on CP3 cells not cited for this
  pattern.
- Control: moving the port 3 grid units away in a synthetic copy silences the sensor.
- The 108-test suite still passes, plus the new sensor's tests.

## 5. Not in scope

- Resolving the Review 6 residual (b) (VBUS_CON/CC2 shared column) — different location.
- Class-e package/group coherence (receipt §12) — separate unmodelled population.
- Any router or placement edit to the candidate.
