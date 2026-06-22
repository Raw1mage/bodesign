# Design: quality_readiness-enforces-guide-definition-of-done

## Context

The readiness family is the compass an agent reads each turn. Today its green
(`readiness_pct`, `state==answered` counts, filename-keyword checklist) covers only
the thinnest layer of each stage's GUIDE.md "Required deliverables — Definition of
Done". An agent that trusts the number (root cause A) gets a fake green while the
deliverables violate the GUIDE (root cause B). This change makes the machine signal
track the GUIDE DoD so skipping the guide produces a RED light.

## Architecture

```mermaid
flowchart TD
    GUIDE[stage GUIDE.md<br/>Required-deliverables table<br/>human SSOT] -. mirrored by hand .-> MAN[templates/<stage>.dod.json<br/>machine manifest]
    RDY[cXX_readiness / package_readiness] --> CK[assess_guide_dod base, manifest, conditions]
    MAN --> CK
    BASE[base dir<br/>c00=project root, c01..c06=stage folder] --> CK
    CK --> COMP[guide_compliance block<br/>per item: present | honest-status | missing-blocking | n/a]
    RDY --> FC[fake-complete check<br/>answered + placeholder value -> blocking]
    RDY --> RF[conditional-RF<br/>radio part vs include_rf]
    COMP --> OUT[readiness to_dict: + guide_compliance, + dod_ok]
    FC --> OUT
    RF --> OUT
```

One shared checker (`guide_dod.py`) + 8 authored manifests. Each readiness function
calls the checker with **its own** base dir (the convention it already uses) so
manifest paths resolve correctly. `package_readiness` calls the checker per stage
against the project tree for the roll-up.

## DoD manifest schema (`templates/<stage>.dod.json`)

```json
{
  "stage": "c00",
  "guide": "skills/bodesign/stages/c00-prd/GUIDE.md",
  "deliverables": [
    {"id": "answer_state", "title": "Answer state", "guide_row": 1,
     "any_of": ["C00-PRD/answer_state.json"], "required": true},
    {"id": "rf_requirements", "title": "RF requirements", "guide_row": 3,
     "any_of": ["C00-PRD/RF_Requirements.md", "C00-PRD/RF_Requirements.generated.md"],
     "required": true, "condition": "rf",
     "honest_states": ["external-needed", "blocked"]}
  ]
}
```

- `any_of`: ordered alternative paths (glob ok), relative to the readiness base.
  First match → `present` with that path as evidence.
- `condition` (optional): the deliverable is required only when the named condition
  holds (`rf`, `toolchain`, `high_speed`, `c04_frozen`, `board_brought_up`). The
  caller supplies a `conditions: dict[str,bool|None]`. `None` = unknown → required
  (fail-safe) unless the manifest marks it `condition_default_skip`.
- `honest_states`: per-deliverable acceptable honest statuses (defaults to the
  stage's set). A missing deliverable that carries an honest status (see below) is
  reported `honest-status`, not blocking.
- `bucket` (optional): `"02_build"` → the file must be under `02_build/` (c04 #6).

## Honest-status override (no-fake mechanism)

A deliverable can be legitimately deferred. The agent records this in an explicit
`<base>/dod_status.json`: `{ "<deliverable_id>": {"status": "not-run", "reason":
"...", "owner": "..."} }`. The checker treats a missing deliverable WITH a matching
honest-status entry as `honest-status` (non-blocking but surfaced); a missing
deliverable WITHOUT one is `missing` (blocking). This gives a clean, auditable way
to mark deferral without faking a file — and keeps "silent absence is not allowed".

## guide_compliance output

```json
{"dod_ok": false,
 "deliverables": [
   {"id": "...", "title": "...", "guide_row": 1, "status": "present|honest-status|missing|n-a",
    "evidence": "<matched path or honest reason>", "blocking": true|false}],
 "missing_blocking": ["rf_requirements", ...]}
```

`dod_ok` is true iff no deliverable is `missing` (blocking) and no fake-complete /
condition violation. Additive on each readiness `to_dict()`.

## Fake-complete detection

In the answer_state scorer (`_assess_field`, c00; mirrored for c01 if answer-state
based): when `state == "answered"` and the field VALUE is a placeholder, downgrade
status to `blocking` and tag `fake_complete: true`. Placeholder = empty/whitespace,
or matches a calibrated set: `TBC|TBD|TODO|N/A|to be (confirmed|determined|defined|
provided)` (word-bounded, case-insensitive) and CJK `待填|待定|待補|待確認|未定|未填|尚未提供`.
`accepted-risk` is NOT flagged (it explicitly documents a gap). The pattern is
deliberately conservative to avoid false positives on legitimate values.

## Conditional-RF

A detector reads the BOM/PRD for radio parts (Wi-Fi/BLE/LoRa/cellular keywords or a
known radio MPN list) and the C00 `include_rf` flag. `radio detected && not
include_rf` → blocking guide_compliance entry "RF appendix required (radio part
detected) but include_rf=false". Feeds the `rf` condition for the c00 manifest.

## Goals / Non-Goals

### Goals
- A green readiness signal means GUIDE-DoD-green: `dod_ok` is the real done-gate,
  true only when every Required-deliverable is present (or honestly deferred) and no
  `answered` field is fake-complete.
- Skipping a required file, flipping a conditional flag, or hiding a `TBC` under
  `answered` each produce a RED signal, named with the GUIDE row.
- One shared checker + 8 manifests; backward-compatible additive output.

### Non-Goals
- Runtime markdown parsing of GUIDE.md (the manifest is the machine mirror).
- Auto-fixing non-compliance, or judging prose quality beyond placeholder detection.
- Changing the honest-status vocabulary or the readiness path-visibility/analyzer fixes.

## Decisions

- **DD-1**: Manifest is **authored JSON mirroring the GUIDE table**, NOT a runtime
  markdown parser. GUIDE.md stays the human SSOT; `<stage>.dod.json` is the machine
  mirror. Sync risk is mitigated by a test that every manifest deliverable cites a
  `guide_row` and a doc note pairing them (DD-7).
- **DD-2**: **One shared `assess_guide_dod` checker** + 8 manifests, not per-stage
  bespoke code. Each readiness function passes its own base dir (c00 project root /
  c01–c06 stage folder) so existing path conventions are untouched.
- **DD-3**: **Honest-status via explicit `dod_status.json`** — a missing deliverable
  is blocking unless an auditable honest-status entry exists. No silent absence, no
  faked file. (Where a stage already records status in-band — c00 answer_state field
  states, c03 `Netlist_Status.md` — the manifest points the checker at that.)
- **DD-4**: **Fake-complete = answered + placeholder value → blocking**, with a
  conservative calibrated pattern; `accepted-risk` exempt. Reported per field so the
  agent sees exactly which "answered" values are hollow.
- **DD-5**: **Conditional-required is enforced, not skippable** — `include_rf=false`
  while a radio part is detected is blocking. Unknown conditions default to required
  (fail-safe), never silently skipped.
- **DD-6**: **`guide_compliance` + `dod_ok` are additive** on every readiness
  `to_dict()`; existing keys unchanged (backward compatible). `readiness_pct` keeps
  its meaning but `dod_ok` is the real done-gate.
- **DD-7**: **SKILL.md + each GUIDE** state `readiness_pct: 100 ≠ done`; done =
  `dod_ok` (guide DoD manifest all-green) + honesty. "Self-verify" → "self-verify
  against the guide's DoD manifest (the readiness `guide_compliance` block)".

## Risks / Trade-offs

- **R1 — manifest ↔ GUIDE drift**: the JSON mirror can fall out of sync with the
  GUIDE table. Mitigation: each deliverable carries `guide_row`; a test asserts it;
  the GUIDE DoD-note + SKILL.md pair them as one human/machine contract (DD-1/-7).
- **R2 — placeholder false positives**: an over-broad pattern would flag a legitimate
  `answered` value (its own bug). Mitigation: conservative bounded-token + specific
  CJK design, string-only, with a negative test corpus (`STM32…Neural`, `待機`).
- **R3 — over-blocking conditionals**: defaulting unknown conditions to required would
  wrongly block optional-on-condition items (EVT/high-speed). Mitigation: conditional
  required ONLY when explicitly true; the dangerous case (RF) is detected explicitly.
- **R4 — folder-convention mismatch**: c00 uses project root, c01–c06 the stage folder.
  Mitigation: each readiness passes its own base; `guide_compliance_for` guards
  non-dir/invisible bases; package roll-up locates `C0N*` subdirs.

## Critical files

- `packages/workflow-core/bodesign_workflow_core/guide_dod.py` (new — checker).
- `packages/workflow-core/bodesign_workflow_core/templates/<stage>.dod.json` ×8 (new).
- `c00_prd_template.py` (fake-complete + manifest wire + conditional-RF),
  `c01_id_package.py`, `c02_me_package.py`, `c04_layout_constraints.py`,
  `c05_fw_spec.py`, `c06_test_plan.py`, `package_readiness.py` (manifest wire).
- `skills/bodesign/SKILL.md` + `stages/<stage>/GUIDE.md` (DD-7 wording).

## Code anchors

- c00_prd_template.py:654 `_assess_field` — fake-complete insertion point.
- c00_prd_template.py:185 `assess_c00_prd_readiness` — guide_compliance + RF wire.
- package_readiness.py — per-stage DoD roll-up.

## Verification strategy

- Unit: checker against fixtures (present / missing / honest-status / conditional);
  fake-complete pattern precision (positives + negative legit values); conditional-RF.
- Per-stage smoke: each manifest loads + checks a model tree (rockbox) green.
- Regression: aiguard-style C00 (naming/TBC/missing-RF) → `dod_ok: false` naming the
  gaps, NOT 100%.
- In-container rebuild + a readiness call shows `guide_compliance`.
