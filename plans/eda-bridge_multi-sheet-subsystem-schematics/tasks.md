# Tasks: eda-bridge_multi-sheet-subsystem-schematics

<!-- plan-builder:scaffold — replace every <placeholder>, then delete this line -->

> **Every `- [x]` must name a machine-verifiable artifact.** Ticking a box is a
> claim made by whoever ticked it; it carries no evidence on its own. Close each
> task with an `artifact:` field so the gate can check the claim:
>
> | form | example |
> |---|---|
> | file | `artifact: packages/lib/src/tools.ts` |
> | code anchor | `artifact: packages/lib/src/tools.ts:158` |
> | file INSIDE this package | `artifact: design.md` |
> | registered verb | `artifact: verb:plan_closeout` |
> | several | `artifact: a/b.ts, verb:spec_tick_task` |
> | genuinely none | `artifact: none (decision only — see DD-3)` |
>
> **Name a file inside THIS package by its bare name** (`design.md`), not by
> the repo path (`plans/<slug>/design.md`). The gate resolves a claim against
> the repo root first and then against the package directory, so the bare form
> keeps working after `plan_graduate` moves the package from `/plans/` to
> `/specs/` — the repo-path form names the old location and dies there.
> (graduate now rewrites such claims for you, but writing them move-invariant
> in the first place is one less thing to repair.)
>
> It goes at the END of the checkbox line — the SAME line, not the next one:
>
> ```
> - [x] 1.1 Fix the off-by-one in the row parser — artifact: packages/lib/src/parse.ts:42
> ```
>
> `plan-validate` warns on an unnamed or non-existent artifact; `plan_closeout`
> blocks. Use `none` honestly rather than naming a file that does not exist —
> a broken claim blocks on EVERY package, an honest `none` never does.
>
> **The `verb:` form needs the verb registry — in a non-node repo it blocks
> this package from ever reaching verified.** The gate reads
> `packages/lib/src/tools.ts` under the nearest ancestor holding BOTH `.git`
> and `package.json`. Without it the claim is UNADJUDICATED, not "wrong" — and
> the gate will not call that a pass, so `plan-promote … --to verified` refuses.
> **In a non-node repo name a path instead** (or `none (<reason>)`): the refusal
> is on the KIND of claim, so only changing the kind clears it — rewording the
> task around a `verb:` will not.

## 1. <placeholder phase name>

- [ ] 1.1 <placeholder task — concrete, verifiable slice> — artifact: <path|path:line|verb:name>
