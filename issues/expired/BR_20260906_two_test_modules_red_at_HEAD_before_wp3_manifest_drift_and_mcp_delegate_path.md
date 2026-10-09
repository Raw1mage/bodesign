# BR_20260906: two test modules were already red at HEAD before WP3 touched anything

- **Status**: open
- **Family**: `G13-harness-disclosure`
- **Filed**: 2026-09-06
- **Filed by**: `ses_f8a707824ffeXcpvN7g4UknjUm` (WP3 handler, plan `c03_delivery_contract_and_engine_seams`)
- **Related**: `BR_20260831a` (`Ran N` — module-did-not-load, module-absent and real-regression share one output)

## 1. Summary

Two test modules fail on a clean HEAD, for reasons unrelated to each other and
unrelated to any current work:

| module | at HEAD | failure |
| --- | --- | --- |
| `tests/test_skill_shipping.py` | `Ran 47 / rc=1 / FAILED (failures=1)` | `:524` — `kicad shadow drift moved: MANIFEST discloses 9 byte-differences, measured 10. Update the MANIFEST figure.` |
| `tests/test_mcp_delegate.py` | `Ran 5 / rc=1 / FAILED (errors=5)` | all five `setUp`s raise `ModuleNotFoundError: No module named 'mcp_delegate'` |

Neither is fixed here. This BR records them so the next agent who sees a red
suite does not spend a round re-deriving that these two are pre-existing.

A third module, `tests/test_landing_gate.py:186`, was red for a **different**
reason (a hand-written path assertion that never matched what the verb writes)
and **was** fixed in the WP3 commit — it is the gate module for `gate.py`, so
leaving it permanently red would have meant shipping `gate.py` changes with no
functioning guard. It is mentioned here only so the three are not confused.

## 2. Measurement — how "pre-existing" was established

Not inferred. For each module the working-tree edit under suspicion was stashed
with an exact pathspec, the module re-run, then the stash popped and the file
compared byte-for-byte against the pre-stash copy:

```
G=skills/bodesign/scripts/gate.py          # and S=services/mcp/server.py
cp "$G" "$G.mine"
git stash push -- "$G"
find . -name __pycache__ -prune -exec rm -rf {} +     # AGENTS.md §6.3
python3 -m unittest tests.<module>
git stash pop
cmp -s "$G" "$G.mine"                       # rc=0 — restored copy is identical
```

| module | with the WP3 edit | with the edit stashed (HEAD) | verdict |
| --- | --- | --- | --- |
| `test_skill_shipping` | `Ran 47 rc=1 failures=1` | `Ran 47 rc=1 failures=1` | pre-existing |
| `test_mcp_delegate` | `Ran 5 rc=1 errors=5` | `Ran 5 rc=1 errors=5` | pre-existing |

`Ran N` was read, not just `rc` — per BR_20260831a, `rc=1` alone cannot separate
"the module regressed" from "the module never loaded". Here N is stable and
non-trivial in both columns, so both modules did load and did run.

`cmp -s` after the pop is the control that the measurement did not damage the
work it was measuring: a stash/pop cycle that silently lost the edit would have
produced the same "pre-existing" reading for the wrong reason.

## 3. Finding #2 — `test_skill_shipping:524`, MANIFEST drift

The assertion compares a byte-difference count disclosed in a MANIFEST against
the count measured live, and demands they agree:

```
AssertionError: 9 != 10 : kicad shadow drift moved:
MANIFEST discloses 9 byte-differences, measured 10. Update the MANIFEST figure.
```

The test is behaving as designed — it is a drift detector, and drift occurred.
What is unresolved is **which side is stale**: whether a tenth legitimate
divergence was introduced and the MANIFEST simply needs the new number, or
whether the tenth divergence is itself the defect. The failure message asks for
the former without establishing it, so applying it blindly would convert a
possible real finding into a documentation edit.

Deciding requires identifying WHICH file is the tenth differing one and when it
diverged — not done here.

## 4. Finding #3 — `test_mcp_delegate`, import path

All five tests die in `setUp` at `tests/test_mcp_delegate.py:10`:

```
self.mod = importlib.import_module("mcp_delegate")
ModuleNotFoundError: No module named 'mcp_delegate'
```

`mcp_delegate` lives under `services/mcp/`. The bootstrap in `tests/__init__.py`
injects `packages/*/` into `sys.path` and `PYTHONPATH` — it does not inject
`services/mcp`. So the module is unimportable under both invocation paths:

```
python3 -m unittest tests.test_mcp_delegate   → Ran 5 rc=1 errors=5
./scripts/run_tests.sh test_mcp_delegate      → Ran 5 rc=1 errors=5
```

The second line matters: `run_tests.sh` is the documented way to run this
suite (AGENTS.md §5), so this is not a "you invoked it wrong" case.

This is the same shape as BR_20260831a. That BR's fix taught the bootstrap about
`packages/*/`, which is where the code under test lived at the time. `services/`
holds importable code too, and nothing told the bootstrap. The disclosure gap is
that a test module which **cannot load at all** reports through the same `rc=1`
as one whose assertions failed — the reader has to open the traceback to learn
that zero assertions ever ran.

## 5. Why family `G13-harness-disclosure`

Neither finding is a defect in product code. Both are cases where the harness
holds the distinguishing information and does not surface it:

- #2: the harness knows exactly which file is the tenth difference; the message
  reports only the count, and phrases the remedy ("Update the MANIFEST figure")
  as though the answer were already settled.
- #3: the harness knows the import failed in `setUp` before any assertion ran;
  the summary line is `FAILED (errors=5)`, which a reader scanning output reads
  as five failing tests rather than one unimportable module.

## 6. Cost already incurred

A permanently-red module stops being evidence. While `test_landing_gate` was red
(fixed in the WP3 commit), any NEW `gate.py` regression would have surfaced as
the same `Ran 20 rc=1 failures=1` and been indistinguishable from the known
failure. The same is true today of `test_skill_shipping` for the skill-shipping
surface and `test_mcp_delegate` for the delegate surface: both are currently
guarding nothing.

## 7. Not measured

- Which file constitutes the tenth byte-difference in #2, and whether it is
  legitimate. Without that, no ruling is possible on whether the MANIFEST figure
  or the shadow tree is the thing to change.
- Whether adding `services/mcp` to the `tests/__init__.py` bootstrap makes #3's
  five tests pass or merely lets them run and then fail. "It will import" and
  "it will pass" are different claims and only the first is supported here.
- Whether other `services/*` subtrees have test modules with the same latent
  import problem — only `test_mcp_delegate` was observed.
