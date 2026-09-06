# BR_20260906 — no documented fallback ladder when `compose_schematic` is rejected by the fidelity gate

- **Status**: OPEN
- **Family**: `bodesign-kb` (knowledge gap — the engine behaves as designed; what is missing is the documented outlet)
- **Component**: KB (`bodesign/.specbase/ragbase.sqlite`), `skills/bodesign/stages/c03-ee/GUIDE.md`, `skills/bodesign/SKILL.md`
- **Filed**: 2026-09-06 (bodesign-side fanout of a guest report)
- **Upstream**: `/home/pkcs12/products/thesmart_products/issues/BR_20260906_c03_schematic_chain_delivered_label_stub_pinout_instead_of_circuit.md` §4 **F-1** (lines 293-317), fanout row **B-2** (`:369`)
- **Related**: this repo's `plans/c03_delivery_contract_and_engine_seams` **DD-10**; KB `tooling-failmodes.failure-mode.fix-lands-on-parallel-pipeline-off-delivery-path`; RCA §10 root causes B/D

## The gap

The fidelity gate is documented: `SKILL.md:457-463` and `GUIDE.md:488` both say to run
with `fidelity=True` and that a mismatch raises `FidelityError` and fails loud. That
half is fine and works.

**What happens next is undocumented.** A consumer whose compose is rejected has no
written outlet: no ladder of sanctioned degradations, no statement of what is
permissible to hand-roll, no "stop and ship with a limitations note" rule visible at
the point of failure. The nearest thing is a general delivery-contract clause
(`SKILL.md:378-403`: *if a gap plausibly needs >2 rounds of engine change, STOP
delegating … ship with an honest limitations note*) which is about **delegation
budget**, not about **what to do with the drawing that still has to exist.**

The measured consequence upstream: a handler reported the defect to the engine owner
**and** hand-rolled a substitute drawing. Both actions at once, and nothing in the
documentation told it that the second was out of bounds.

## Measurement (re-run 2026-09-06 in this repo, not transcribed)

`bun gate.ts ragbase_query --repo /home/pkcs12/projects/bodesign`, English terms ≥3
chars. Reported as `repo=N user=N`:

| query | result | reading |
| --- | --- | --- |
| `hand-roll` | **repo=0 user=0** | no KB object addresses whether hand-rolling is permitted |
| `engine defect` | repo=1 user=0 | the single hit is `concept.honesty-provenance-model` ("Honesty & provenance model") — a general principle, **not** a fallback procedure |
| `fallback ladder` | repo=0 user=1 | the single hit is `agent-orchestration.issue.tool-loading-regression-umbrella` — a tool-loading BR, unrelated to schematic fidelity |

**Controls** (same probe, same call shape):

| control | result | what it rules out |
| --- | --- | --- |
| `fidelity` | repo=5 user=5 | the store is reachable and this topic IS represented — the zeros above are content, not connectivity |
| `compose_schematic` | repo=5 user=1 | same |
| `zzznope` | **repo=0 user=0** | the probe can return a true zero, so a zero means something |

Both a real absence and a live store are demonstrated in the same run, so the zeros
are load-bearing.

**Corpus side:** `grep -rn 'FidelityError' skills/` → **1 mention in 1 file**. The
exception that gates the whole delivery path is named exactly once across the skill
corpus, at the place that raises it — and nowhere that tells a reader what to do
about it.

### Discrepancy with the upstream report — stated, not smoothed

The mother BR recorded `engine defect` → n=0 and `fallback ladder` (as a concept) as
absent. I measure **1** and **1** respectively. The difference does not change the
conclusion — neither hit is a fallback procedure, as the titles above show — but the
numbers are not identical and the reader should not be told they were. Likely causes:
a different query tier selection, or KB objects added between the two runs. Not
investigated.

## Why this is a KB gap and not a handler error

The upstream report frames this as an open question with two answers (its §4 F-1
table): either the general clause **is** the answer and the handler failed to apply
it (→ consumer's fault), or the clause does not address the situation at all
(→ bodesign's gap). This BR takes the second reading.

### The ground for taking reading B (revised 2026-09-06 — the earlier ground was rejected)

An earlier revision of this BR justified reading B as chosen *"for the purpose of
having something to fix"*. **That is not a criterion and it has been withdrawn** —
a thing being fixable says nothing about whether it is a defect, and choosing a
reading because it yields work is how a non-defect acquires a repair.

The replacement ground is behavioural and observable: **what a consumer does after
compose is rejected leaves a trace, and the trace is a self-written substitute.**

- Attribution: **peer duty officer testimony from `thesmart_products`** (a GUEST
  read of a consuming repo), re-verified first-hand here by directory listing —
  **not** a bodesign-side measurement of bodesign behaviour.
- The measured trace: `thesmart_products/04.btdongle/C03-EE/02_build/sch_gen/`
  contains a locally authored schematic-generation toolchain at the exact node
  where `compose_schematic` was the sanctioned path — `mk_sch.py`, `mk_sch2.py`,
  `mk_sch_bodesign.py`, `mk_spec.py`, `verify_net.py`, `verify_sch.py`, plus
  `design.py` / `mk_local_syms.py` / `mk_tables.py` / `symlib.py`.
  (Count note: the peer's testimony said "six scripts"; a direct `ls` of that
  directory on 2026-09-06 shows **10** `.py` files. The discrepancy is reported
  rather than smoothed; it does not change the reading, since the claim rests on
  *existence*, not on cardinality.)

The inference: **a KB that has no next step after a rejection has, as its
observable consequence, consumers inventing their own next step — and an invented
next step is governed by no gate at all.** That is a defect in the KB regardless of
whether any particular invented substitute was good or bad.

**Scope boundary (user ruling, 2026-09-06):** the *contents* of those scripts are
explicitly out of scope. The ruling was that they should not have been written at
all — a correct one might be adopted, an incorrect one has no debugging value — so
this BR uses only the fact **that they exist**, and performs no content analysis on
them. Nothing in this BR should be read as a critique of their internals.

### The prior textual argument (retained; it is independent of the above)

`SKILL.md:381`'s stop-loss is about **when to stop asking the engine team for
changes**. It is silent on the question the consumer actually faces — *the deliverable
requires a schematic, the engine refuses to produce an acceptable one, and the
deadline is real.* A rule that does not mention the deliverable cannot be the rule
governing the deliverable.

The counter-reading remains legitimate and the adjudicator may prefer it; in that
case the fix moves to wiring `SKILL.md:381` into the c03-ee SOP so it is visible at
the failure site, which is a smaller change and lands in this same repo.

## What a fix would need to contain (NOT adjudicated)

Enumerated so the gap is concrete, not to prescribe:

1. What degradations are sanctioned, in order (e.g. accept `label` connection style
   with a declared note → accept partial wiring with the unwired nets named → stop).
2. Which of them may reach a customer deliverable and which may not.
3. What must be recorded when one is used, so the drawing carries its own provenance
   rather than looking like a normal output.
4. The stop condition — the point at which the honest answer is "no schematic this
   round".

The absence of (3) is what makes this expensive: a degraded output is
indistinguishable from a good one at the consumer's end, which is the same shape as
`fix-lands-on-parallel-pipeline-off-delivery-path`.

## Not measured

- Whether any handler has ever successfully recovered from a `FidelityError` (no
  ledger search performed).
- Whether the general `SKILL.md:378-403` clause is reachable from the c03-ee stage
  guide by a reader who never opens `SKILL.md` — the navigation question, not the
  content question.
- The upstream report's own §4 F-1 hedge: it explicitly declined to choose between
  its A and B readings. This BR chooses B on the behavioural ground stated above.
  **The "something to fix" justification that previously stood here is withdrawn.**
- **Whether the self-written toolchain in `thesmart_products` was caused by this
  gap.** The scripts' existence at that node is measured; the causal link to the
  fidelity rejection is an inference, not a measurement. No commit-time ordering
  was established (the consuming repo's git index was recently repaired, so git-side
  probes there were deliberately not used).
- Anything about the scripts' contents — out of scope by user ruling, see above.
