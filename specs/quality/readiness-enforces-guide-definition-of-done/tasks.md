# Tasks: quality_readiness-enforces-guide-definition-of-done

> Implemented + verified 2026-06-23 (the user authorized the full build). Each task
> names its file(s) + acceptance.

## 1. Shared DoD checker

- [x] 1.1 `guide_dod.py`: `assess_guide_dod(base, stage, conditions)` → guide_compliance
  (present / honest-status / missing / n-a) with `any_of` / `all_of` / `bucket` /
  `condition` + `dod_status.json` honest override.
- [x] 1.2 `is_placeholder_value()` — conservative fake-complete detector (bounded EN
  tokens + specific CJK phrases, NOT bare 待); only regex-checks string values.
- [x] 1.3 `guide_compliance_for()` wrapper guarding invisible root / inline (non-dir) folder.

## 2. Per-stage DoD manifests (mirror GUIDE tables)

- [x] 2.1 `templates/c00..c07.dod.json` (8) — each row → deliverable with `guide_row`,
  paths, honest_states, conditions. c00 paths project-root-relative; c01–c07 stage-folder.

## 3. Fake-complete + conditional-RF (c00)

- [x] 3.1 `c00_prd_template.py` `_assess_field`: `answered` + placeholder value →
  blocking + `fake_complete: true` (`accepted-risk` exempt).
- [x] 3.2 `_detect_radio` + conditional-RF: radio part with `include_rf=false` → blocking.
- [x] 3.3 `assess_c00_prd_readiness`: compute guide_compliance (conditions={rf}),
  `dod_ok`, `fake_complete_fields`; surface in `to_dict`.

## 4. Wire guide_compliance into the family

- [x] 4.1 c01 / c04 / c05 / c06 readiness `to_dict`: add `guide_compliance` + `dod_ok`
  via `guide_compliance_for`. (c02 readiness is constraint-based → covered by package.)
- [x] 4.2 `package_readiness.py`: per-stage DoD roll-up (`_stage_subdir`), reuse the
  RF-aware c00 result; add `guide_compliance` map + `dod_ok` + `dod_missing` (covers
  c02/c03/c07 which have no `cXX_readiness` tool).

## 5. Doc alignment (DD-7)

- [x] 5.1 `SKILL.md`: `readiness_pct:100 ≠ done`; read `dod_ok` + `guide_compliance`;
  self-verify against the guide's DoD manifest.
- [x] 5.2 All 8 `stages/<stage>/GUIDE.md`: DoD-note after the Required-deliverables header.

## 6. Tests + verification

- [x] 6.1 `tests/test_guide_dod.py` (12): placeholder precision, checker
  (present/missing/honest/conditional/all_of), c00 fake-complete + conditional-RF,
  manifest completeness.
- [x] 6.2 Regression: existing readiness tests (70 across c00/c01/c04/c05/c06/package/
  invisible-path) unbroken.
- [x] 6.3 In-container (rebuilt ee + monolith): test_guide_dod 12/12, all 8 manifests
  bundled, real `.work/aiguard` c00 → fake-complete caught (`key_parts_or_references`
  "MPNs TBC") + package roll-up `dod_missing` across stages.

## 7. Skill projection

- [x] 7.1 `opencode skill resync bodesign --accept-source` so the SKILL.md + GUIDE
  DoD-notes go live in the projected skill.

> Optional non-blocking follow-up (residual risk — see handoff.md): re-run against the
> real aiguard tree on the FUSE mount when visible, to confirm the BR's original
> 6-TBC/missing-RF case reads `dod_ok: false` end-to-end. Verified here with a
> generated/`.work` fixture.
