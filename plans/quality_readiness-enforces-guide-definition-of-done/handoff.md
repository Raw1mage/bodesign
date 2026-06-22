# Handoff: quality_readiness-enforces-guide-definition-of-done

## Execution Contract

Implemented, tested, and live in the rebuilt container (2026-06-23). The readiness
family now enforces each stage's GUIDE Definition-of-Done as a machine-checkable
manifest (`dod_ok` is the real done-gate), detects fake-complete fields (answered +
placeholder value) and conditional violations (radio part vs `include_rf`), and
emits a `guide_compliance` block. Closes BR
`issue_20260623_readiness_only_checks_state_not_guide_dod`.

## Required Reads

- `issues/closed/issue_20260623_readiness_only_checks_state_not_guide_dod.md` — BR + dual-RCA.
- `spec.md` — invariants. `design.md` — DD-1..DD-7 + manifest schema + checker.
- `packages/workflow-core/bodesign_workflow_core/guide_dod.py` — the checker + placeholder detector.
- `templates/<stage>.dod.json` — the per-stage manifests (mirror the GUIDE tables).

## Stop Gates In Force

- **DD-1 sync**: the GUIDE.md table is the human SSOT; `<stage>.dod.json` is its
  mirror. When a GUIDE Required-deliverables row changes, update the manifest
  (each deliverable carries `guide_row`). A test asserts every deliverable has a
  `guide_row`; keep them paired.
- **Placeholder precision**: the fake-complete pattern is deliberately conservative
  (bounded EN tokens + specific CJK phrases, never bare 待). Do not broaden it
  without adding negative test corpus — a false positive flags a legitimate value.
- **No silent absence, no fake green**: a deferred deliverable must carry an honest
  `dod_status.json` entry; never relax `dod_ok` to paper over a gap.
- **Skill projection**: SKILL.md + GUIDE edits are repo SSOT; they go live only via
  `opencode skill resync bodesign` (capability projection), not a container rebuild.

## Validation Plan

- `tests/test_guide_dod.py` (12) + existing readiness tests (70) — green host + container.
- Real `.work/aiguard` C00 → `fake_complete_fields: [key_parts_or_references]`
  ("MPNs TBC"), `dod_ok: false`; package roll-up `dod_missing` across started stages.

## Execution-Ready Checklist

- [x] Dual RCA (AI behavior + product design) captured; fix targets product design (B).
- [x] Shared checker + 8 manifests + fake-complete + conditional-RF + family wiring.
- [x] Doc alignment (SKILL.md + 8 GUIDEs); skill projection resynced.
- [x] Tests green host + in-container; rebuilt images carry the manifests.
- [ ] (optional) Re-run against the real aiguard tree on the FUSE mount when visible,
  to confirm the BR's original 6-TBC/missing-RF case now reads `dod_ok: false`.
