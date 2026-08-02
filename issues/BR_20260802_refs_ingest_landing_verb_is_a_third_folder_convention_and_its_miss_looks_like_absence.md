# BR — `refs_ingest` landing verb is a THIRD `folder` convention, and its miss is indistinguishable from a genuinely-absent stage

- **Filed**: 2026-08-02
- **Status**: OPEN — **not fixed** (fixing it re-widens the scope of the readiness-contract work that adjudicated *internal* paths only)
- **Severity**: medium-high — it is on the **landing plane** (a user/agent calls it directly)
- **Family**: G13-harness-disclosure / 缺席態與失敗態共用同一個輸出
- **Owner**: bodesign refs-first paradigm (`refs_gate.py`, `skills/bodesign/scripts/gate.py`)
- **Related**: `BR_20260719_c01_readiness_folder_arg_double_prefix.md`,
  `BR_20260719_c02_readiness_provenance_root_and_dod_surface.md`
  (the same disease; those two were adjudicated and fixed for the **internal** call paths on 2026-08-02)
- **Scheduled**: not scheduled — deliberately deferred by the adjudicating coordinator
  (`ses_04db7a1c5ffelvbxyLP1p6xlRH`, round 3) so the contract fix could land with a stable boundary

---

## 1. One sentence

After the 2026-08-02 contract fix, `folder` means **product root** everywhere in the internal
code paths — but the `refs_ingest` landing verb still means **stage dir**, and when a caller
obeys the new contract the verb returns `root_visible=false`, which is byte-identical to what
it returns for a path that does not exist at all.

---

## 2. The three conventions, side by side (measured, not inferred)

Fixture: `<W>/prod/C02-ME/01_refs/C02_dimensions.md` (one real refs source, product root = `<W>/prod`).

| # | Entry point | What it wants in `folder` | Passing **product root** | Passing **stage dir** |
|---|---|---|---|---|
| 1 | `require_refs(folder, layer)` — production, `refs_gate.py:260` | **product root** (stage derived from `layer` via `stage_folder_for`) | ✅ `visible=True sources=1`<br>`refs_root=<W>/prod/C02-ME/01_refs` | ✗ double prefix |
| 2 | emitters, e.g. `emit_c02_enclosure_package(out_dir=…)` — `c02_me_package.py:263` | **product root** (`root = Path(out_dir)`, then `require_refs(root, "C02")`, then `C02_OUTPUTS` rel_paths) | ✅ consistent with #1 | ✗ |
| 3 | **`gate.py refs_ingest --arg folder=…`** → `ingest_refs(a["folder"])` — `gate.py:319,363` | **stage dir** (`ingest_refs` appends `01_refs` to whatever it is given) | ❌ `visible=False sources=0`<br>`refs_root=<W>/prod/01_refs` | ✅ `visible=True sources=1` |

`ingest_refs` itself is **not** the defect — its docstring is honest
(`"may point either at the stage folder … or directly at an 01_refs directory"`), and its
strict `root / REFS_DIRNAME` resolution was a deliberate anti-fallback fix (review F7).
The defect is that `refs_ingest` **exposes that raw primitive on the landing plane under the
same parameter name (`folder`) that now means something else in every other entry point.**

---

## 3. The part that makes it a G13 (why it will not be noticed)

```
folder = <product_root>          -> visible=False sources=0 refs_root=<W>/prod/01_refs
folder = <product_root>/ZZZ-NOPE -> visible=False sources=0 refs_root=<W>/prod/ZZZ-NOPE/01_refs   <-- CONTROL
folder = <product_root>/C02-ME   -> visible=True  sources=1                                        <-- discriminating
```

Row 1 is a caller **correctly obeying the new contract**. Row 2 is a path that **does not exist**.
The only difference between them is the echoed `refs_root` string — the two boolean/count fields a
caller actually branches on (`root_visible`, `source_count`) are **identical**.

So the failure mode reads as: *"this product has no refs — I should go decompose the datasheets."*
That is precisely the shape the original two BRs were filed for; it survived on the landing plane.

**And it is reachable without passing `folder` at all** (`--repo` supplies the default):

```
$ gate.py refs_ingest --repo <W>/prod
{"ok": true, … "refs_root": "<W>/prod/01_refs", "root_visible": false, "source_count": 0, …}
```

`ok:true` + a clean empty manifest for a product that has a fully populated `C02-ME/01_refs/`.

---

## 4. Why it was NOT fixed in the same pass

The 2026-08-02 adjudication (`[BRNS-REPLY] round 3`) scoped the contract to **internal code paths**
and explicitly ruled: *"file BR, do not fix — fixing it would widen the scope by another round."*
That ruling is sound: `refs_ingest` is a landing verb with unknown external callers, and the
`ingest_refs` dual-acceptance is load-bearing for callers that legitimately hold an `01_refs` path.

Documenting the **decision** rather than only the defect, per the coordinator's own standing rule
that a deferred item must be distinguishable from an unexamined one.

---

## 5. Candidate fixes (not chosen — for whoever picks this up)

1. **Align the verb, not the primitive.** `_v_refs_ingest` takes `folder` (product root) + a new
   required `layer`, and calls `require_refs(folder, layer)`. Keeps `ingest_refs` as-is for the
   direct-`01_refs` callers. Cost: a breaking arg change on a landing verb.
2. **Rename the arg.** `refs_ingest --arg refs_root=…`, so the landing plane stops using the word
   `folder` for a thing that is not a product root. Cheapest; fixes the *naming* half only.
3. **Make the miss loud.** When the resolved `refs_root` is absent BUT a sibling
   `<folder>/<C0x>/01_refs` exists, emit a named warning
   (`looks_like_product_root_passed_to_stage_arg`). Fixes the *indistinguishability* half —
   the part that actually costs debugging hours — without any signature change.

(1) and (3) are complementary. (3) alone would already have made this BR unnecessary.

---

## 6. Observation, NOT actionable here — orphan `<aiguard>/01_refs/`

In the user's product repo (`thesmart_products`, **not** bodesign) there is a one-file
`<aiguard>/01_refs/` directory at the **product root**, whose single file differs by md5 from the
stage-level copy under `C02-ME/01_refs/`.

Assessment: **suspected residue grown to feed the pre-fix gate** — before 2026-08-02,
`require_refs` resolved `01_refs` against the product root, so a product-root copy was the only
way to satisfy it. After the fix, the stage copy is authoritative and this one is dead weight
whose md5 divergence makes it an active hazard (two SSOTs, silently different).

**Not touched, and must not be touched from here** — it is in the user's product repo.
Needs product-owner confirmation before removal.

---

## 7. Evidence provenance

All rows in §2 and §3 measured 2026-08-02 on this worktree with the readiness-contract fix applied,
against an XDG-private fixture (`$XDG_RUNTIME_DIR/refsconv/`), with a bogus-path control in every
run. The control is what establishes that row 1's `visible=False` carries no information —
without it, row 1 alone reads like a legitimate "no refs here".
