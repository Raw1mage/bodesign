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
(→ bodesign's gap). This BR takes the second reading, on the following ground:

`SKILL.md:381`'s stop-loss is about **when to stop asking the engine team for
changes**. It is silent on the question the consumer actually faces — *the deliverable
requires a schematic, the engine refuses to produce an acceptable one, and the
deadline is real.* A rule that does not mention the deliverable cannot be the rule
governing the deliverable.

That said, **this framing is a judgement and is not measured.** The counter-reading
is legitimate and the adjudicator may prefer it; in that case the fix moves to
wiring `SKILL.md:381` into the c03-ee SOP so it is visible at the failure site,
which is a smaller change and lands in this same repo.

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
  its A and B readings. This BR chooses B **for the purpose of having something to
  fix**, and says so.
