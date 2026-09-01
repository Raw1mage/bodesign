# BR_20260901_c02_render_enclosure_token_relative_path_never_resolved

- **Status**: CLOSED — fixed, independently verified, committed and effective in-tree.
- **Fix commit**: `0ada3495774a15c207c0564c6143cf2fa6424c12`
  (`fix(mcp): resolve token-relative stl_path/glb_path on the same frame as preflight`;
  4 files changed, 625 insertions(+), 3 deletions(-)).
  The fix is effective on import — no rebuild, restart or 3R is required for the
  in-repo test surface. A running **container** still serves the pre-fix bytes
  until `./mcpctl.sh restart`; that is a deployment step, not an open defect.
- **Closed**: 2026-09-01 by ses_fa2b0134bffeO73T1So3I6KizD (handler),
  under archive authorization from ses_04db7a1c5ffelvbxyLP1p6xlRH (duty officer).
- **Owner**: ses_04db7a1c5ffelvbxyLP1p6xlRH (dispatcher) / handler session
- **Family**: `G13-harness-disclosure` — success state and failure state sharing one output
- **Related**:
  - `issues/closed/BR_20260804_c02_export_stl_cannot_see_files_staged_into_its_own_token.md`
    — same execution path (`bodesign_c02_*` under a token), same failure class
    ("the tool cannot see a file that is demonstrably inside its own token").
  - AGENTS.md §6.1 / §6.2 / §6.3 — the three recorded instances of
    "success output and disaster output are byte-identical". D2 below is a
    fourth instance of that same shape, in the MCP envelope rather than in a shell.

## 1. Symptom

Same token `tok_4b9f0c2ffab14a8e`, same `doc_dir`. `workspace_inspect` lists
`C02-ME/Enclosure.scad` and `C02-ME/Enclosure.stl`. Then:

```
c02_render_enclosure(token=…, stl_path="C02-ME/Enclosure.stl", out_dir=".", views=[front,iso,rear])
→ ok: true                       ← envelope says success
  result.status: "error"          ← handler says failure
  result.note: "STL not found: C02-ME/Enclosure.stl"
  produced: []
```

Passing the absolute token path instead is rejected by `PREFLIGHT_HOST_ONLY_ABSOLUTE`,
so from the caller's seat there was no accepted spelling of the input at all.

## 2. Reproduction (pre-fix, measured)

```
MEASURE doc_dir      = <sessions>/tok_…
MEASURE handler_saw  = C02-ME/Enclosure.stl        ← bare relative, never resolved
MEASURE envelope_ok  = True
MEASURE inner_status = error
MEASURE inner_note   = STL not found: C02-ME/Enclosure.stl
MEASURE produced     = []
CONTROL file_exists  = True                        ← decisive: the file IS there
```

The control is what makes this a defect report rather than a guess: the file
exists in the token tree, and the tool still said "not found".

## 3. Root cause — TWO independent defects

### D1 — two layers resolved the same argument in different frames

`services/mcp/server.py`:

- `PATH_ARG_KEYS` (line 1451) listed `out_dir` but **not** `stl_path` / `glb_path`.
  The token dispatch loop (line ~1735) therefore rewrote `out_dir` against
  `doc_dir` and handed the handler a **bare relative** `stl_path`.
- `_h_c02_render_enclosure` (line 303) passed that straight to
  `render_enclosure_model`, which does `Path(stl_path)` — resolved against the
  **container CWD**, where nothing exists → `src.exists()` False → `status:"error"`.
- Meanwhile R17.2.4 preflight (`_RENDER_EMIT_ASSET_KEYS`, line 1537) resolved the
  **same argument correctly** against `doc_dir` (`preflight._classify_one`) and
  **passed it**.

So the guard and the dispatcher disagreed about what `"C02-ME/Enclosure.stl"`
means. The call was neither blocked nor served. A guard that resolves a path
differently from the code it guards does not protect that code — it launders it.

`glb_path` (`bodesign_render_board_model`) had the identical latent defect; it is
preflighted on the same map and was equally absent from `PATH_ARG_KEYS`.

### D2 — the envelope hard-coded `ok:true` around any handler return

`run_tool` (line ~1759) built `{"ok": True, "result": handler(args)}` unconditionally.
A handler that declared `status:"error"` still shipped an `ok:true` envelope. Any
caller branching on the envelope — the ordinary thing to do — reads a failure as a
success. This is the AGENTS.md §6.1–6.3 shape (success state and failure state
sharing one output), relocated into the MCP envelope.

D2 is why D1 survived: D1 alone would have produced a visible error.

### D3 (adjacent, found while writing the controls)

`preflight` reported a path that exists but is a **directory** as `unresolved`
— i.e. "not found" about something demonstrably present. Same conflation, smaller
blast radius.

## 4. Fix

| File | Change |
| --- | --- |
| `services/mcp/server.py` | `stl_path`, `glb_path` added to `PATH_ARG_KEYS`. |
| `services/mcp/server.py` | New `_resolve_token_path(doc_dir, raw)` — **one** resolver, sharing preflight's reference frame. Absolute inputs are resolved, not grafted under `doc_dir` (`lstrip('/')` on an absolute path builds a location that exists nowhere). `symbol_dirs` re-pointed at it, so there is now a single implementation. |
| `services/mcp/server.py` | New `_apply_result_status(envelope)`: when the handler declares `status` in `_HANDLER_ERROR_STATUSES` (`{"error"}` — deliberately narrow), `ok` flips to False and `error=TOOL_REPORTED_ERROR` + `message` are lifted. `result_status` is mirrored for **every** dict result. Inner `result` left byte-identical. |
| `services/mcp/preflight.py` | New `REASON_NOT_A_FILE` / `CODE_PREFLIGHT_NOT_A_FILE`; a declared input asset that exists but is not a regular file gets its own code. |
| `tests/test_c02_render_token_path.py` | New, 17 tests. |

**No fallback was added.** Every rejected state fails fast with a code distinct
from every other state. `no-deps` / `no-gl` / `empty` deliberately keep `ok:true`
— those are honest degradation (the tool ran and reported a real boundary), and
folding them into "failed" would be the same conflation in the other direction.

## 5. Verification

**Positive** — the load-bearing assertion is not "no exception" but *the path the
renderer was handed is absolute and `relative_to(doc_dir)` succeeds, and its bytes
equal the staged file's*. A spy renders whatever it is given, so asserting
`status == rendered` alone would have proved nothing.

**Five states, pairwise distinct discriminators** `(ok, error, result_status)`:

| state | ok | error | result_status |
| --- | --- | --- | --- |
| A resolved + rendered | true | — | `rendered` |
| B resolved + renderer failed | false | `TOOL_REPORTED_ERROR` | `error` |
| B2 honest degradation | true | — | `no-gl` |
| C file absent | false | `PREFLIGHT_UNRESOLVED` | — |
| D path is a directory | false | `PREFLIGHT_NOT_A_FILE` | — |
| E traversal | false | `PREFLIGHT_OUT_OF_NAMESPACE` | — |

`produced == []` carries **no** weight: B, C and D all produce nothing. A summary
test collects all six discriminators in one run and asserts they are pairwise
distinct — individual tests can each pass while two states still coincide.

C, D and E additionally assert `spy.calls == []` (the renderer was never reached),
so "rejected at the gate" cannot be confused with "reached the renderer and failed".

**Mutation proof** (the control that matters — do the tests detect the original bug?):

```
new tests vs FIXED tree :  Ran 17, OK
new tests vs HEAD tree  :  Ran 17, FAILED (failures=7, errors=4)   ← 11 detect it
FORGERY CHECK on the HEAD tree:
  grep -n 'PATH_ARG_KEYS = '        → line 1451, no stl_path/glb_path
  grep -c '_apply_result_status'    → 0
  grep -c 'REASON_NOT_A_FILE'       → 0
```

The forgery check rules out "the mutant tree accidentally contained the fix".

**Negative control for the runner itself**: `python3 -m unittest
tests.test_module_that_does_not_exist` → `Ran 1 test / FAILED (errors=1)`, which is
byte-identical in shape to a real regression. Hence every count above is read off
`Ran N`, not off `rc`.

**Adjacent modules** — the 5 failures in `tests.test_mcp_server` and the 8 in
`tests.test_token_store` are **pre-existing**, proven by running the same modules
against a clean `git archive HEAD` extraction: identical failing test names,
identical `FAILED (failures=3, errors=2, skipped=3)`. `test_token_store` fails at
`import token_store` (module path, not behaviour). `test_registry_is_well_formed`
fails on `bodesign_init`, which is served in-process and has no registry handler
by design — untouched by this work.

```
tests.test_c02_render_token_path      Ran 17  OK
tests.test_mcp_r17_r06_conformance    Ran 31  OK
tests.test_model_render               Ran  3  OK (skipped=1)
tests.test_mcp_server                 Ran 49  FAILED — identical at HEAD (pre-existing)
tests.test_token_store                Ran  8  FAILED — identical at HEAD (pre-existing)
```

`__pycache__` cleared before every run (AGENTS.md §6.3: `-B` does not evict an
*existing* stale `.pyc`).

### 5.1 Independent verification (VANS) and commit boundary

The evidence above was produced by the implementing session, so on its own it is
self-attestation. Two things make it load-bearing:

- **VANS** `ses_fa2a1a1edffe9sRNrAA0NwXAXo` — an independent adversarial session,
  not the implementer — verified the change and returned **PASS**. The duty officer
  `ses_04db7a1c5ffelvbxyLP1p6xlRH` read that verdict plus the diff before
  authorizing the commit; authorization was withheld until then.
- **The duty officer independently re-verified the landed commit**
  `0ada3495774a15c207c0564c6143cf2fa6424c12` rather than trusting the report:
  four files matching the authorized list, every numstat row non-`0 0`, the named
  files clean in the worktree, and `.specbase` / `AGENTS.md` absent from the commit.

Commit boundary, measured with a paired control rather than a bare empty result
(an empty `git show -- <pathspec>` is equally what a mistyped pathspec returns):

```
git show --name-only --format='' 0ada349 -- .specbase AGENTS.md   → (empty)
git show --name-only --format='' 0ada349 -- services/mcp
  → services/mcp/preflight.py
    services/mcp/server.py          ← same probe, non-empty on a path that IS there
```

The control is what licenses reading the first line as "genuinely absent" instead
of "the probe never looked". Post-commit re-run: `Ran 51 OK (skipped=1)`.

## 6. Not measured

These remain unmeasured **after** the fix, the VANS PASS and the commit — none of
those three events converts any of them into a verified claim:

- Not exercised against the live container or the real `tok_4b9f0c2ffab14a8e`
  (out of bounds: user token). The renderer boundary is mocked — trimesh/pyrender
  are absent from the lean core, so an end-to-end PNG was never produced here.
  What is proven is the **path contract**, which is where the defect lived.
- The `me`-worker forwarding path (`_forward_to_worker`) forwards **raw** arguments
  and the worker re-runs `run_tool` on the shared session volume, so it goes
  through the same fixed resolver. Not separately exercised — no worker was
  running in this session.
- `bodesign_render_board_model` / `glb_path` is fixed by the same one-line
  registration and is covered by the generalised control
  (`test_control_every_preflighted_asset_key_is_token_resolved`), but has no
  dedicated end-to-end test.
