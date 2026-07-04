# Spec: readiness enforces GUIDE Definition-of-Done

## Purpose

The readiness family must make each stage's GUIDE.md "Required deliverables —
Definition of Done" machine-checkable, so a green readiness signal means
GUIDE-DoD-green, not merely field-`state`-green. Skipping a required deliverable,
flipping a conditional flag to dodge one, or marking a hollow `TBC` value as
`answered` must each produce a RED signal (`dod_ok: false`), never a fake 100%.

## Requirements

### Requirement: Fake-complete fields cannot inflate readiness

A field whose `state == answered` but whose value is a placeholder is downgraded to
blocking and named.

#### Scenario: answered field with a TBC value
- **GIVEN** a C00 answer_state field `{state: answered, value: "... MPNs TBC"}`
- **WHEN** `bodesign_c00_readiness` runs
- **THEN** the field is counted blocking, listed in `fake_complete_fields`, and
  `dod_ok == false`
- **AND** a legitimate value (e.g. "STM32… Neural-ART", "待機電流 5uA") is NOT flagged

### Requirement: GUIDE Required-deliverables are enforced as a manifest

Each stage's DoD table is mirrored as `templates/<stage>.dod.json`; readiness
reports each deliverable as present / honest-status / missing / n-a.

#### Scenario: a required deliverable is silently absent
- **GIVEN** a stage folder missing a required file with no honest status recorded
- **WHEN** the stage readiness (or `bodesign_package_readiness`) runs
- **THEN** that deliverable is `missing` + `blocking`, named with its GUIDE row, and
  `dod_ok == false`

#### Scenario: a deliverable is honestly deferred
- **GIVEN** a missing required deliverable WITH a `dod_status.json` entry carrying an
  acceptable honest status + reason
- **WHEN** readiness runs
- **THEN** it is `honest-status` (non-blocking) and surfaced — silent absence is
  still not allowed

### Requirement: Conditional deliverables are enforced, not skippable

A conditional deliverable is required when its condition holds; a flag cannot be
flipped to dodge it.

#### Scenario: radio part with include_rf=false
- **GIVEN** a PRD whose fields name a radio part (Wi-Fi/BLE/…) but `include_rf=false`
- **WHEN** `bodesign_c00_readiness` runs
- **THEN** `dod_ok == false` with a warning that the RF appendix is required

#### Scenario: optional-on-condition item not triggered
- **GIVEN** c06 with no board brought up
- **WHEN** readiness runs
- **THEN** `EVT_Bringup_Findings.md` is `n-a` (not blocking)

### Requirement: guide_compliance is additive and backward compatible

`guide_compliance` + `dod_ok` are added to every readiness `to_dict()`; existing
keys are unchanged.

#### Scenario: a fully compliant stage
- **GIVEN** a stage folder with every required deliverable present
- **WHEN** readiness runs
- **THEN** `dod_ok == true`, `guide_compliance.missing_blocking == []`, and every
  prior key is present and unchanged

### Requirement: stages without a readiness tool are covered by the roll-up

c03 and c07 (no `cXX_readiness` tool) have their DoD checked via
`bodesign_package_readiness`.

#### Scenario: package roll-up names DoD gaps per stage
- **GIVEN** a project tree with several started stages
- **WHEN** `bodesign_package_readiness` runs
- **THEN** `guide_compliance` carries a per-stage entry and `dod_missing` names every
  stage whose GUIDE DoD is not met

## Acceptance Checks

- [x] answered+placeholder field → blocking + `fake_complete_fields` + `dod_ok:false`; legit values not flagged.
- [x] missing required deliverable → blocking, named with GUIDE row; honest `dod_status.json` → non-blocking.
- [x] radio part + `include_rf:false` → `dod_ok:false` with RF warning; optional-on-condition unknown → `n-a`.
- [x] `guide_compliance` + `dod_ok` additive on c00/c01/c04/c05/c06 + package; prior keys unchanged.
- [x] c03/c07 DoD reachable via `package_readiness`; per-stage `dod_missing` roll-up.
- [x] SKILL.md + 8 GUIDEs state `readiness_pct:100 ≠ done`; done = `dod_ok` + honesty.
- [x] `tests/test_guide_dod.py` (12) green host + in-container; existing readiness tests (70) unbroken.
