# BR_20260906 — gate unit fixtures are blind to emission-site mutation: 23 tests stay green while the producer emits a constant

- **Status**: OPEN (finding recorded; the specific gap it exposed is CLOSED — see "What was already fixed")
- **Family**: `G13-harness-disclosure` — the defect is that a pass count cannot express the difference between "the consumer is covered" and "the producer is covered"
- **Component**: `tests/test_readability_gate.py`, `packages/eda-bridge/bodesign_eda_bridge/composer.py:2740`
- **Filed**: 2026-09-06, during WP6 of `plans/c03_delivery_contract_and_engine_seams`
- **Related**: this plan's **DD-10** (the emission points exist because `route_stats` carried neither quantity), AGENTS.md §6.3 (stale `.pyc` invalidates mutation proofs), `BR_20260906_occupancy_ledger_wire_reserves_never_survive_to_final_ledger.md`
- **KB**: distilled as `tooling-failmodes.failure-mode.consumer-fixtures-cannot-see-producer-emission-site`

## The finding

A test suite of 23 tests, every one of them written with a stated question and a
paired control, **scored 100% green while the value it exists to check was
replaced by the constant `0` at its production site.**

The tests are not weak. They are pointed at the wrong side of a seam: they feed
the gate hand-written `route_stats` dicts and assert on the gate's verdict. The
gate was correct throughout. What broke was the *producer* that fills those dicts
in real use — and no fixture can observe a producer it substitutes for.

**"We have 23 passing tests on this module" and "this module's inputs are
verified" are different claims, and the pass count renders them identically.**

## Measurement

Mutant applied at the emission site, `composer.py:2740`:

```python
-        route_stats.drawn_subcircuits = sum(1 for g in _groups.values() if len(g) >= 2)
+        route_stats.drawn_subcircuits = 0  # MUTANT1
```

`__pycache__` purged before every run (AGENTS.md §6.3: `python3 -B` does **not**
evict an existing stale `.pyc`, and a same-length edit can otherwise leave the
mutant unapplied — which would produce a green result meaning nothing).

| suite slice | tests | result under MUTANT1 |
| --- | --- | --- |
| the 8 fixture-driven classes (`DisclaimerAlwaysPresent`, `PositiveControl`, `Br20260905PowerClustering…`, `LabelFarmVersusFragmentation`, `AbsenceIsNeverAPass`, `Denominator`, `IndeterminateArm`, `AntiFusionCriterion`) | **Ran 23** | **OK** ← the defect |
| `LiveEmissionTests` (added in response to this finding) | **Ran 6** | **FAILED (failures=1)** |
| whole module | Ran 29 | FAILED (failures=1) |

The failing assertion, verbatim:

```
FAIL: test_drawn_subcircuits_is_computed_not_constant
  File "tests/test_readability_gate.py", line 373
    self.assertEqual(1, self.result.route_stats.to_dict()["drawn_subcircuits"])
AssertionError: 1 != 0
```

**Controls.**
- *The mutant really was applied*: `grep -c 'MUTANT1' composer.py` = 1 during both
  runs, and the live value moved 4 → 0 on the real btdongle board.
- *The 23 green tests are not vacuous*: they run and pass identically on unmutated
  code, and the same 23 do go red under mutations of the **gate** logic they
  actually cover. Their green here is genuine — for the question they ask.
- *Restore is clean*: after `mv composer.py.orig composer.py`, `grep -c MUTANT1` = 0,
  `git diff --quiet -- composer.py` rc=**0** (byte-identical to `bb8347a`), and the
  full suite returns **Ran 29, OK**.

## Root cause (mechanism, not blame)

`readability_gate(route_stats, spec)` takes a plain data structure. That is good
design — it makes the gate testable without a KiCad install. The consequence is
that a fixture **is** a valid `route_stats`, so a test built on one exercises the
entire gate and **zero percent** of the code that produces a `route_stats` in
production.

The seam is invisible from inside the test file. Nothing in `test_readability_gate.py`
before the fix mentioned `composer.py` at all, so a reviewer reading the suite —
including the person who wrote it — sees complete coverage of "the readability
gate". They are right. The unstated word is *which half*.

This is why the pass count is the wrong instrument: **it counts assertions, and
what was missing was a category of input, not a count of them.** Adding a 24th
fixture test would have moved the number and changed nothing.

## What was already fixed

`LiveEmissionTests` (6 tests) was added in the same round. It performs a real
`compose_schematic()` and asserts against the emitted file on disk:

- `len(emit.wire_runs)` == the `(wire` count in the written `.kicad_sch`
- `emit.junctions_emitted` == the `(junction` count in that file
- `drawn_subcircuits` equals a live-measured value, not a constant

Each kills a distinct disabled emission. The suite went **23 → 29**. The two
mutation proofs from round 8 (`drawn_subcircuits` → constant `0`; `wire_runs.append`
→ `return`) both go red against it, and both restored with `cmp` rc=0.

**This BR is filed anyway** because the code fix does not carry the lesson: the
next module with a clean data-structure seam will reproduce it exactly, and the
only warning sign — a high pass count on a well-written suite — is the same signal
that says everything is fine.

## Detection (how to catch this class without waiting for a bug)

Mutate the **producer**, not the consumer, and check the consumer's suite goes red.
If the suite is green, it does not cover the seam, whatever its pass count says.
Concretely, for any module whose tests build their own input:

1. Find where that input is constructed in production (not in the test).
2. Replace the computed field with a constant.
3. Purge `__pycache__` (§6.3 — otherwise a green result is meaningless).
4. Run the suite. **Green ⇒ the seam is untested.**

Step 3 is not optional: a same-length edit inside one second leaves mtime and size
unchanged, CPython reuses the stale bytecode, and the mutant never runs. That
failure looks exactly like a passing test.

## Not measured

- Whether other suites in this repo share the shape. Only
  `test_readability_gate.py` was mutated. `tests/` holds 152 files, and any of them
  that construct their own inputs are candidates — unexamined.
- Whether the 6 live tests cover every emission point, or only the three asserted.
  A fourth emission added later would not be caught by them automatically.
- Cost: `LiveEmissionTests` requires KiCad symbol libraries (`skipUnless(HAS_SYMBOLS)`).
  On a host without them the suite silently drops back to the 23 blind tests —
  **the same failure mode, reintroduced by a skip**. Not addressed here.
