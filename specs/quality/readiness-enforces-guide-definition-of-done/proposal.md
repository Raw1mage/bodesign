# Proposal: quality_readiness-enforces-guide-definition-of-done

## Why

- `cXX_readiness` / `package_readiness` only check whether answer_state fields have
  `state == answered`. They do **not** check (a) the field VALUE quality (a field
  can be `answered` while its value is `TBC`/`待`), (b) the GUIDE.md "Required
  deliverables — Definition of Done" manifest (required files exist, named/located
  correctly, required diagrams present), or (c) conditional required items
  (`include_rf=false` while the BOM/PRD clearly has a radio part). So an agent that
  trusts the green number gets `100% / 69/69` while the deliverables are NOT
  compliant with the GUIDE DoD — the machine signal diverges from the real standard
  in the most dangerous direction (reports better than reality).
- Source BR: `issues/issue_20260623_readiness_only_checks_state_not_guide_dod.md`.
  Concrete failure: aiguard C00 reported 100% with naming/structure violations,
  missing required diagrams, skipped RF appendix, and 6 `answered`-but-`TBC` fields.
- Dual root cause (from the BR): **A** AI behavior (trusted the readiness number as
  the acceptance oracle, never opened the GUIDE) and **B** product design (the only
  machine-checkable gate covers the thinnest layer — field `state`). A is the
  trigger; B is the system condition that makes A inevitable and unattended. Fixing
  only A ("read the guide next time") recurs because that is the same prose that
  already failed; **B must change so that skipping the guide produces a RED light,
  not a fake green one.**

## Original Requirement Wording (Baseline)

- "整套實作(8 stage manifest 全做)" — implement the full fix: fake-complete
  detection + per-stage GUIDE Required-deliverables manifest + conditional-RF +
  `guide_compliance` block + SKILL self-verify wording.

## Requirement Revision History

- 2026-06-23: created from BR `issue_20260623_readiness_only_checks_state_not_guide_dod`.

## Effective Requirement Description

1. **Fake-complete detection**: a field whose `state` claims real content
   (`answered`) but whose value is a placeholder (`TBC`/`TBD`/`待…`/`未定`/empty)
   is downgraded to blocking and reported — never counted toward `complete`.
2. **GUIDE DoD manifest**: every stage's "Required deliverables" table becomes a
   machine-checkable manifest. readiness checks each required deliverable: a
   matching file exists (right name + bucket) OR an honest status
   (`blocked`/`external-needed`/`not-run`/`pending`/`draft`) with a reason is
   recorded. A required deliverable that is silently absent is blocking, naming the
   missing item + its GUIDE row.
3. **Conditional required items**: a deliverable required only under a condition
   (RF present, toolchain present, high-speed, C04 frozen, board brought up) is
   enforced when its condition holds; in particular `include_rf=false` while a
   radio part is detected is blocking — a flag cannot be flipped to skip a required
   deliverable.
4. **`guide_compliance` block**: every readiness result carries a `guide_compliance`
   section listing each DoD item → pass/honest-status/missing + evidence + GUIDE
   reference. `readiness_pct: 100` no longer implies done.
5. **Doc alignment**: SKILL.md + each GUIDE state `readiness 100% ≠ done`; done =
   guide DoD manifest all-green + honesty model. "Self-verify" becomes "self-verify
   against the guide's DoD manifest".

## Scope

### IN
- A shared DoD-manifest schema + one checker (`guide_dod.py`) in `workflow-core`.
- 8 per-stage DoD manifests (`templates/<stage>.dod.json`) encoding the GUIDE tables.
- Fake-complete (placeholder-value) detection in the answer_state scoring.
- Conditional-RF detection (radio part vs `include_rf`).
- Wire `guide_compliance` into c00–c06 readiness + `package_readiness`.
- SKILL.md + GUIDE doc alignment.
- Tests (manifest checker, fake-complete, conditional-RF, per-stage smoke).

### OUT
- Re-deriving the GUIDE DoD content (the tables are the source of truth; the
  manifest mirrors them — kept in sync, see Risks).
- Auto-fixing non-compliance (readiness reports; the agent/user fixes).
- The readiness path-visibility + analyzer-engine fixes (separate, done).
- Changing the honest-status vocabulary itself.

## Non-Goals

- A general markdown-table parser for GUIDE.md at runtime (fragile) — the manifest
  is authored JSON, the GUIDE table is the human view.
- Enforcing prose-quality of an `answered` value beyond placeholder detection.

## Constraints

- c03 and c07 have **no** `cXX_readiness` tool — their DoD must be reachable via
  `package_readiness` (the roll-up), so the checker is callable there too.
- Honest-status states differ per stage (draft / blocked / external-needed /
  not-run / pending) — the manifest carries each deliverable's acceptable honest
  states.
- Many deliverables have alternative filenames/locations (`A.md` or `dir/A.md`) —
  the manifest matches any-of.
- Backward compatible: existing readiness keys unchanged; `guide_compliance` is
  additive. A folder that IS compliant must still read green.

## What Changes

- readiness stops reporting green when the GUIDE DoD is not met: fake-complete
  fields, missing required files, and condition-violations become blocking, each
  named with its GUIDE reference.

## Capabilities

### New Capabilities
- `guide_compliance`: machine-checkable GUIDE Definition-of-Done per stage.
- fake-complete detection; conditional-required enforcement.

### Modified Capabilities
- `cXX_readiness` / `package_readiness`: green now means GUIDE-DoD-green, not just
  field-state-green.

## Impact

- `packages/workflow-core/bodesign_workflow_core/`: new `guide_dod.py`,
  `templates/<stage>.dod.json` ×8, edits to `c00_prd_template.py`,
  `c01_id_package.py`, `c02_me_package.py`, `c04_layout_constraints.py`,
  `c05_fw_spec.py`, `c06_test_plan.py`, `package_readiness.py`.
- `skills/bodesign/SKILL.md` + each `stages/<stage>/GUIDE.md` self-verify wording.
- Agents/users relying on readiness as the acceptance oracle (now trustworthy).
