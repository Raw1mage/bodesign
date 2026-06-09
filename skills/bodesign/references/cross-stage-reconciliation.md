# Cross-stage reconciliation — turning "escalate back" into a tracked state

bodesign runs mostly **forward** (C00→C07), but some constraints can only be checked by combining
facts that several stages own — and when such a check **fails**, the honest response is to send work
*back upstream*, not to quietly proceed. This file defines the **state convention** that makes that
feedback explicit and trackable, so a cross-stage failure becomes a recorded, actionable signal
rather than a sentence buried in a doc. It is the first concrete rung of the co-design *iteration*
loop.

## The rule

When a stage computes a **cross-stage budget** and it does not close, it MUST emit an open
**reconciliation record** — never absorb the overage silently (this is honesty rule 6, exclude-
rather-than-guess, applied across stages). The record names the quantified delta, who owns the levers,
the escalation options routed to their stages, and which stage must act next. It stays `open` until a
named stage changes something and records the resolution — or a **human** marks it `accepted_risk`
(AI never accepts a cross-stage risk alone, the same gate as `me_approved`/external compliance).

## This is the existing `BlockerReturn` primitive — not a new scheme

The orchestration engine already has the mechanism: `bodesign_workflow_core.orchestration` provides
**`return_blocker`** (emit), **`list_blockers(folder, unresolved_only=True)`** (scan), and
**`ingest_blocker`** (resolve) — persisted as JSON with IDs and a log. A reconciliation record **is** a
`BlockerReturn`; use that API rather than inventing a parallel store. Field mapping:

| reconciliation | `BlockerReturn` |
|---|---|
| `finding` | `summary` + `evidence` |
| `owners` / `must_act` (the stage to act) | `affected_downstream_layers` (+ `affected_c00_fields` if it reaches C00) |
| `escalation_options` | `options` |
| `recommended_owner` (the owner *type*: `downstream_agent` re-does it · `user` decides · `external_expert` vendor) | `recommended_owner` |
| `status` open/resolved/accepted_risk | `resolved` + `resolution` + `proposed_state` |
| `initiated_by` | `source_layer` |

So "emit a reconciliation record" = `return_blocker(...)`; "an open record blocks done" =
`list_blockers(unresolved_only=True)` returns one naming this stage as `recommended_owner`; "resolve"
= `ingest_blocker(...)` (which already refuses an empty/auto resolution — honesty-aligned).

## The record (the `BlockerReturn` fields, illustrated)

Carry these in the stage's machine bridge (e.g. `Mechanical_Constraint_Export.json` /
`Mechanical_Constraints.json`) under `cross_stage_reconciliation[]`:

```json
{
  "budget": "thermal",                 // area | thermal | height | power | cost | …
  "status": "open",                    // open | resolved | accepted_risk
  "initiated_by": "C03",
  "finding": "ΣPdiss 4.2 W exceeds enclosure dissipation envelope ~2.8 W by ~1.4 W (50%)",
  "owners": ["C02 enclosure", "C04 copper/placement", "C03 part selection"],
  "escalation_options": [
    { "action": "spread/relocate heat sources + thermal-via arrays", "stage": "C04" },
    { "action": "vent the enclosure (trades IP — see sealing×heat)", "stage": "C02" },
    { "action": "lower-Pdiss / higher-efficiency part",             "stage": "C03" },
    { "action": "larger enclosure surface / different form",        "stage": "C02/C00" }
  ],
  "must_act": "C02",                   // the stage to re-evaluate next
  "resolution": null                   // {by_stage, what_changed, when} when status→resolved
}
```

## How it makes the pipeline iterative

An `open` record is a **re-run signal** for the stage named in `must_act`: that stage re-evaluates
with the new pressure, applies a lever (or hands to the next option's stage), and either flips the
record to `resolved` (recording what changed) or escalates further. A downstream stage **must not
declare its gate done while an `open` reconciliation it is named in remains unresolved** — a routed
board on top of an unresolved thermal overage is exactly the kind of false-COMPLETE the C04
floating-PSRAM lesson forbids.

> Orchestration note: the automatic re-run of `must_act` may not exist yet — today the record is the
> honest, trackable trigger a human (or a future orchestrator) acts on. Defining the state is the
> prerequisite for ever automating the loop; emitting it is mandatory regardless.

## Two trigger directions — the recursion has both halves

The **same record** is emitted from two places, and routes the same way:

- **Forward (design-time budget overflows).** A stage computes a budget from facts several stages own
  and it doesn't close — area, thermal, height. Initiated as the design is built (C03/C04/C02).
- **Backward (verify-time verdict fails).** C06 runs a tool and gets `warn`/`fail` — an SI overshoot,
  an EMC margin, a DRC unconnected, a thermal verdict. C06 **does not fix it** (it doesn't own the
  artifact) — it **routes** it: emits a reconciliation record naming the owning design stage in
  `must_act`. The fail becomes a tracked, routed signal instead of a dead-line in a report.

Both halves obey one hard rule from the C04 floating-PSRAM lesson: the `must_act` stage resolves by
**fixing the design**, never by relaxing the threshold to make the number/verdict pass.

## Current reconciliation points

| Trigger | Dir | Initiated | Owners (levers) | Check |
|---|---|---|---|---|
| **area** | fwd | C03 | C02 outline · C04 stackup/2-sided · C03 parts | `../stages/c03-ee/references/ee-design-advisory.md` § "Area budget" |
| **thermal** | fwd+bwd | C03 / C06 | C02 enclosure(vent/surface) · C04 copper/vias/spread · C03 Pdiss | `../stages/c03-ee/references/ee-design-advisory.md` § "Thermal budget" |
| **height** | fwd | C04 / C02 | C02 enclosure depth · C04 placement/part-Z · C03 package | `../stages/c04-layout/references/stackup-and-placement.md` § "Height budget" |
| **si / emc / drc** | bwd | C06 | C04 route/stackup · C03 SI requirement / part | C06 GUIDE (verdict → record) |

Extend this table as new triggers are added (power-source capacity, cost ceiling). Each follows the
same record + iteration rule above. Triggers often **couple** — venting for thermal trades against IP
(C02 advisory § Sealing & IP) — so one escalation option may open a *second* record; that is correct,
not a bug.
