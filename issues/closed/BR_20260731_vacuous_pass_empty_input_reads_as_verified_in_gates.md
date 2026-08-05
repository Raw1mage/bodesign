# BR_20260731 — 空輸入在閘門中讀作「通過」：`rca_spec_audit` / `reference_crosscheck` 對零筆輸入回報成功

| Field | Value |
| --- | --- |
| Title | Vacuous pass: zero-item input makes two verification gates report success in wording indistinguishable from a real pass |
| Component | `packages/component-kb` (`vault.audit_claims`), `packages/workflow-core` (`reference_crosscheck.crosscheck_nets`), `packages/eda-bridge` (`pin_allocation.build_pin_allocation`) |
| Reporter | ses_04db7a1c5 (bodesign coordinator) — surfaced while reproducing BR_20260730 round 7 |
| Date | 2026-07-31 |
| Severity | high — these are the gates AGENTS.md §2.4 and README name as the mechanism by which bodesign *demonstrates* rather than *claims* reliability. A gate that passes on nothing is not a weaker gate; it is a gate that reports the same word for "checked and clean" and "never checked anything". |
| Priority | P1 — no known live miscall yet, but the failure is silent by construction and the callers most likely to hit it (an extractor that found nothing, a netlist parse that yielded no nets) are exactly the ones whose failure it would mask. |
| Affected paths | `packages/component-kb/bodesign_component_kb/vault.py:222-252`; `packages/workflow-core/bodesign_workflow_core/reference_crosscheck.py:45-56`; `packages/eda-bridge/bodesign_eda_bridge/pin_allocation.py:51-64`; `skills/bodesign/engines/kicad/scripts/domain_detectors.py:1294-1379` (`_check_rf_reference_values`, the fourth site — found and fixed later in `3de27b2`, backfilled into this header 2026-08-05) |

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
Status: FIXED — verified effective 2026-08-05 (b429b06 on HEAD; runtime re-verified with
  fresh __pycache__: audit_claims([]) -> publishable=None/verdict=vacuous,
  crosscheck vacuous -> "NOT a match", accepting control real-2-nets -> "matches exactly (2 nets)";
  tests/test_vacuous_pass_gates.py 17 passed)
Evidence upgraded: 2026-08-05 by ses_030047beeffel0rxLmCS0SgNWs. The "17 passed" above was
  NOT evidence for the fourth site: mutation showed those 17 tests had ZERO discriminating
  power over the capacitor range branch (§8). An 18th test (b2fdfc2) now kills it. §9 states
  what is verified and what is still unverified — they are not the same thing.
Closed: 2026-08-05 by ses_04db7a1c5ffelvbxyLP1p6xlRH
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

## 8. Mutation evidence (backfilled 2026-08-05 — the "17 tests OK" was not evidence)

`Effect: verified effective` above originally rested on a single fact: `tests/test_vacuous_pass_gates.py`
reported **17 passed**. A green suite is not evidence that a suite *would have gone red* had
the fix been absent — that is the same defect shape this BR is about, one layer up: a test
count that reads identically for "the branch is guarded and tested" and "the branch is
guarded and nobody looks at it".

Measured 2026-08-05 on the fourth site (`ses_03010dd61`; independently re-measured by
`ses_030047beeffel0rxLmCS0SgNWs`). Subject file, exact identity at measurement time:

```
skills/bodesign/engines/kicad/scripts/domain_detectors.py
6125 lines
sha256 ac1953ddd9a0de10e6248e96a1d587626c42612d399f0d9992c5526947e2ebd5
```

Two same-named lines exist in that file and must not be confused:

```
:1346   8-space indent    inside  _check_rf_reference_values   (def @1294)   <- this BR's site
:1521  12-space indent    inside  detect_rf_matching           (def @1382)   <- NOT this BR; see §9
```

Note `detect_rf_matching` has **no leading underscore**; `_check_rf_reference_values` does.

**M21** = `:1346` `elif mc["type"] == "capacitor":` → `elif False:` (`substitutions=1`).
All runs in an isolated copy tree under `$XDG_RUNTIME_DIR`; the main-tree sha256 above is
byte-identical before and after. `__pycache__` deleted between every run (a mutate/restore
of equal length inside one second otherwise leaves stale bytecode live).

| # | Condition | Result | Reads as |
| --- | --- | --- | --- |
| 1 | M21 present, **17** tests (pre-`b2fdfc2`) | `Ran 17 tests` / `OK` | mutant **SURVIVED** |
| 2 | M21 present, **18** tests (post-`b2fdfc2`) | `Ran 18 tests` / `FAILED (failures=1)` | mutant **KILLED** |
| 3 | **reverse control** — M21 present, new test `@unittest.skip` | `Ran 18 tests` / `OK (skipped=1)` | the new test is the **only** killer |
| 4 | **accepting control** — `:1337` inductor branch → `if False:`, 18 tests | `FAILED (failures=1)`, red test = `test_control_out_of_range_still_reports_false` | the mutation pipeline itself is live |

In row 2 the single failure is exactly `test_control_out_of_range_capacitor_still_reports_false`;
the other 17 stay green. Row 3 is the load-bearing one: with M21 in place and the new test
absent, the suite is fully green — so the pre-existing 17 tests have **zero discriminating
power** over the capacitor range branch. Row 4 rules out "the mutation never took effect".

The 18th test landed as:

```
b2fdfc2f336f89dffb5815a5f48ed89d51848838
test(vacuous-gates): cover the capacitor range branch that survived mutation
tests/test_vacuous_pass_gates.py   +11  -0
```

## 9. Scope of verification — what is verified, and what is NOT

These are **two different kinds of gap** and must not be merged; merging them understates
the second by an order of magnitude.

**VERIFIED** — `_check_rf_reference_values` (`domain_detectors.py:1294-1380`), capacitor
value-range branch at `:1346`. M21 KILLED by `test_control_out_of_range_capacitor_still_reports_false`,
with both a reverse control (row 3) and an accepting control (row 4) above. Shape of the
gap that was closed: *the function was tested, one branch inside it was not.* Cost to close:
one test, +11 lines.

**NOT VERIFIED** — `detect_rf_matching` (same file, `def @1382`) has **no test coverage at
all**.

```
$ grep -rn 'detect_rf_matching' tests/          -> (empty), rc=1
$ grep -rn 'detect_rf_matching' --include='*.py' .   -> 6 hits, rc=0
    domain_detectors.py:1382   (def)
    domain_detectors.py:1547   ("detector": "detect_rf_matching")
    analyze_schematic.py:103   (import)
    analyze_schematic.py:755   (call site)
    finding_schema.py:297      (RF_MATCHING enum)
    finding_schema.py:403      (findings-category map)
```

The repo-wide control is what makes the empty result readable: the symbol is referenced in
production and imported by the analyzer, so the empty `tests/` result is a genuine coverage
hole, not a broken grep. Three mutants at `:1521` (`elif False:` / altered comparison string
/ shunt-series counts transposed) **all SURVIVED under the full 1775-test suite**, with the
failing-name set byte-identical to baseline.

Shape of that gap: *the function has no tests at all.* Closing it is not "add a test" — it
is standing up an entire test surface for a detector with none. **Tracked separately; do
not fold it into this BR.**

Provenance of each row, so the confidence is not uniform where the measurement was not:
the two grep results above and every row of §8's table were re-run from scratch by
`ses_030047beeffel0rxLmCS0SgNWs` on 2026-08-05 in an isolated tree. The `:1521`
three-mutant / 1775-test result is `ses_03010dd61`'s measurement, carried here **without**
independent re-measurement — it is reported, not verified twice.
