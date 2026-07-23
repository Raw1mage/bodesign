# Spec: c03-ee_passive-completeness-gate

## Purpose

Guarantee that a C03 composed schematic cannot pass analysis while an active IC carries zero
decoupling on its power rails. Installs PC-001 — a deterministic machine projection of the
9-class pin-obligation table onto a composed schematic — as the machine backstop the method
doc lacked, with an explicit, provenance-carrying waiver for honest partial deliverables.

## Requirements

### Requirement: Active-IC decoupling completeness

The analyzer SHALL emit a blocking `PC-001` finding (severity=error, confidence=deterministic,
evidence_source=topology) for any active IC (component type `ic`) with ≥1 power pin whose power
rails carry zero decoupling capacitance, UNLESS an explicit waiver in `passive_waivers.json`
covers that `(ref, obligation)` gap — in which case the gap SHALL be recorded as `waived`
(visible in the report) rather than suppressed.

#### Scenario: Pinout-only active IC

- **WHEN** a schematic contains an active IC with power pins and no decoupling caps, and no
  matching waiver
- **THEN** analysis emits a blocking PC-001 error naming the ref and the `decoupling` obligation

#### Scenario: Waived honest subset

- **WHEN** the same gap is listed in `passive_waivers.json` with source+reason+scope
- **THEN** analysis records the gap as `waived` (info) and does not emit a blocking error, and
  the waiver provenance appears in the report (no silent pass)

## Acceptance Checks

- [ ] Pinout-only fixture → PC-001 blocking error naming ref+obligation
- [ ] Decoupled fixture → no PC-001 error
- [ ] Waiver fixture → PASS with waiver recorded (not suppressed)
- [ ] Existing composer / check_c03 / analyzer tests remain green
