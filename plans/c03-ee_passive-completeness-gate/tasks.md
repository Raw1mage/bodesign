# Tasks: c03-ee_passive-completeness-gate

## 1. PC-001 detector

- [x] 1.1 Implement `validate_passive_completeness(ctx)` in `validation_detectors.py`:
  walk active ICs (comp type=`ic`, ≥1 power pin), assert ≥1 decoupling cap on each power
  rail; emit blocking `make_finding` (PC-001, severity=error, confidence=deterministic,
  evidence_source=topology) per gap; unmet pulls/term/load → warning.
- [x] 1.2 Implement waiver: load `passive_waivers.json` sidecar next to the .kicad_sch;
  per-gap `(ref, obligation)` match; matched gap → recorded `waived` (severity=info,
  visible), unmatched → stays error. Malformed sidecar → fail-fast typed error.

## 2. Wire-in

- [x] 2.1 Import + dispatch `validate_passive_completeness` in `analyze_schematic.py`
  `analyze_signal_paths`; merge output into `results["validation_findings"]`.
- [x] 2.2 Register `PASSIVE_COMPLETENESS = 'validate_passive_completeness'` in `finding_schema.Det`.

## 3. Tests + fixtures

- [x] 3.1 Pinout-only fixture (active IC, power pins, zero passives) → PC-001 error naming ref.
- [x] 3.2 Decoupled fixture → PASS (no PC-001 error).
- [x] 3.3 Waiver fixture (honest interface-subset + `passive_waivers.json`) → PASS with waiver
  recorded (no silent pass).
- [x] 3.4 Regression: existing `test_composer.py` / `test_check_c03.py` / analyzer tests green.

## 4. Real-board validation

- [x] 4.1 aiguard `02_mcu_core` before/after: FAIL before decoupling added, PASS after
  (or documented waiver). Report evidence.

## 5. Docs + closeout

- [x] 5.1 Sync `specs/architecture.md` C03 section (new PC-001 gate).
- [x] 5.2 Event log closeout; close BR (move to `issues/closed/`).
