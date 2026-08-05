# BR_20260731 — 空輸入在閘門中讀作「通過」：`rca_spec_audit` / `reference_crosscheck` 對零筆輸入回報成功

| Field | Value |
| --- | --- |
| Title | Vacuous pass: zero-item input makes two verification gates report success in wording indistinguishable from a real pass |
| Component | `packages/component-kb` (`vault.audit_claims`), `packages/workflow-core` (`reference_crosscheck.crosscheck_nets`), `packages/eda-bridge` (`pin_allocation.build_pin_allocation`) |
| Reporter | ses_04db7a1c5 (bodesign coordinator) — surfaced while reproducing BR_20260730 round 7 |
| Date | 2026-07-31 |
| Severity | high — these are the gates AGENTS.md §2.4 and README name as the mechanism by which bodesign *demonstrates* rather than *claims* reliability. A gate that passes on nothing is not a weaker gate; it is a gate that reports the same word for "checked and clean" and "never checked anything". |
| Priority | P1 — no known live miscall yet, but the failure is silent by construction and the callers most likely to hit it (an extractor that found nothing, a netlist parse that yielded no nets) are exactly the ones whose failure it would mask. |
| Affected paths | `packages/component-kb/bodesign_component_kb/vault.py:222-252`; `packages/workflow-core/bodesign_workflow_core/reference_crosscheck.py:45-56`; `packages/eda-bridge/bodesign_eda_bridge/pin_allocation.py:51-64` |

```
State:
Fix: LANDED in commit b429b06 "fix(gates): empty input is a third state, never a pass"
Effect: verified effective 2026-08-05 by ses_030847a3affev5QmJelNWqSK41 (BRNS handler, round=1)
Custody: bodesign
Blocker: none
Disposition: filed — split out of BR_20260730 round 7 rather than folded in. Different
  surface (the compute verbs, not skill shipping), different owner-layer, and folding a
  P1 correctness defect into a BR about an HTTP endpoint would bury it.
Venue: bodesign
Status: OPEN
```

## 1. Symptom (verbatim, reproducible on HEAD)

```
$ PP=$(ls -d packages/*/ | tr '\n' ':') && PYTHONPATH="$PP" python3
>>> from bodesign_component_kb.vault import audit_claims
>>> audit_claims([], root="/tmp/empty-vault")
{'publishable': True, 'claim_count': 0, 'blocking_count': 0, 'claims': [], 'blocking': [],
 'advice': 'All asserted specs are datasheet-grounded.'}

>>> from bodesign_workflow_core import crosscheck_nets
>>> crosscheck_nets(set(), set(), "vacuous").to_dict()
{'label': 'vacuous', 'coverage_pct': 0, 'verdict': 'matches the reference exactly (0 nets).',
 'matched': [], 'missing': [], 'extra': [], 'provenance': {}}
```

Both sentences are what a **successful** audit and a **successful** cross-check say. Nothing
in either envelope distinguishes "I checked and it is clean" from "there was nothing to
check". `claim_count: 0` and `(0 nets)` are present but are *data*, not a verdict — every
consumer that branches on `publishable` or on the verdict prose is misled.

`build_pin_allocation` has the same shape one layer down: given a net dict in the wrong
form (`{"name","pin"}` rather than the contract's `{"nodes":["REF.PIN"]}`) it returns
`ok:true` with `net_count: 0` and a CSV containing only a header — no signal at all that
the input was not understood.

## 2. Why this is a defect and not a design choice

**The same repo already does it correctly, twice, in the same layer.** That is what makes
this an inconsistency rather than a philosophy:

```
>>> solve_impedance({}, [])
ValueError: missing required 'stackup'          # eda-bridge, refuses vacuous input outright

>>> plan_design_intent("").status
'needs-clarification'                            # workflow-core, 9 requirements + 9 open questions
```

`solve_impedance`'s docstring states the principle explicitly — *"no geometry defaults are
invented"* — and `plan_design_intent` demonstrates the richer form: an empty input yields a
**third state** that is neither pass nor fail, carrying the questions that must be answered.
Neither gate in §1 has that third state.

This is also precisely the failure shape AGENTS.md §2.1 (no silent fallback) and §2.2 (no
fabrication) exist to prevent, and the shape BR_20260730 spent seven verification rounds on
at the shipping layer: **something reporting success while having produced nothing.**

## 3. Where an empty input actually comes from

Not hypothetical — these are the ordinary paths:

- `rca_spec_audit`: an RCA whose claim-extraction step matched nothing (regex miss, prose
  phrased unusually, upstream returning `[]` on error). The audit then certifies the RCA as
  publishable *because* extraction failed. AGENTS.md 天條 #4 routes every pre-publication
  RCA through this gate, so a silent vacuous pass defeats the rule at exactly the point it
  is meant to bind.
- `reference_crosscheck`: a netlist that failed to parse, or a reference product whose net
  export produced nothing. Verdict: "matches the reference exactly".
- `pin_allocation`: any caller passing the composer's spec nets in a shape `_iter_nodes`
  does not recognise.

## 4. Proposed fix (not yet implemented — shape only)

Do NOT simply raise on empty; that loses the legitimate "genuinely zero claims" case and
would break callers. Follow the in-repo precedent instead:

1. **A third verdict state.** `audit_claims` returns `publishable: null` (or a
   `verdict: "vacuous"`) with advice naming the condition: *"no claims were submitted —
   this is not a pass; verify the extraction step ran."* Same for `crosscheck_nets`:
   an empty reference is `verdict: "no reference nets to compare against"`, never
   "matches exactly".
2. **`build_pin_allocation` reports unparsed nets** — count the net dicts from which
   `_iter_nodes` yielded nothing, and surface `unparsed_nets: N` so a wrong shape is loud.
3. **Guard with an accepting control on both sides** — a test that a real non-empty pass
   still passes, and a test that the vacuous case does NOT report the pass wording.
   Mutation-test both: reverting either fix must redden.

## 5. Explicitly NOT bugs

- `plan_design_intent("")` returning 9 open questions — correct, and the model to copy.
- `solve_impedance` raising — correct.
- `build_design_evidence_manifest([])` returning `counts:{parts:0,...}` — it is a manifest,
  not a gate; zero parts is honestly reported and no verdict word is attached.
- A verb typed-refusing on an absent artifact (`c00_readiness` on a missing answer-state) —
  correct behaviour, confirmed by BR_20260730 rounds 6 and 7.

## 6. Validation plan

- Reproduce §1 verbatim on HEAD before touching anything.
- Fix per §4; assert the vacuous envelope no longer contains the success wording.
- Accepting controls: a real 3-claim clean audit still reports `publishable: true`; a real
  matching net set still reports "matches the reference exactly (N nets)".
- Mutation: revert each fix, confirm the matching test reddens.
- Full-suite failing-NAME-set comparison against HEAD (not counts) — the peer has ~87
  uncommitted files on this tree, so compare via a copied tree with only the changed files
  reverted; never `git stash`.

## 7. Provenance

Found while reproducing BR_20260730 round 7's Z1 result. That round drove ~30 landing verbs
and correctly reported "no silent-empty successes" — because every verb it drove was given
*well-formed* input. The shape only appears when the input is empty or malformed, which is
the case a verifier supplies last and a broken upstream supplies first.
