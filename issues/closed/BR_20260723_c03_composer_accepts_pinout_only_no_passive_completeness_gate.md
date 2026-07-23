# BR_20260723 — C03 composer/analyzer accept a "pinout-only" schematic: no passive-completeness gate

**Reporter:** project consumer (`thesmart_products`, aiguard C03 track)
**Component:** `packages/eda-bridge/bodesign_eda_bridge/composer.py` (`compose_schematic`) +
`engines/kicad/scripts/analyze_schematic.py` + `packages/workflow-core/bodesign_workflow_core/check_c03.py`
**Severity:** high (ships a non-functional board that passes every current gate)
**Fix venue:** NEW session rooted in `/home/pkcs12/projects/bodesign`

---

## Symptom (verbatim consumer observation)

A consumer used the C03 flow to produce aiguard schematics. Every page rendered, ERC passed,
`analyze_schematic` raised no connectivity `high` finding — yet the user opened them and said:

> 「你真的只是把所有的元件純 pinout 畫出來。但是完全沒有電路設計。」

Measured over the entire `03.aiguard/C03-EE` schematic set (real pages, probe/scale dirs excluded):

| metric | count | expected for ~15 ICs |
|---|---|---|
| R (resistors) | **3** | ~50–150 |
| C (capacitors) | **34** | ~80–200 |
| L (inductors) | **4** | a few |

Per-page (the smoking gun — active ICs with **zero** support passives):

| page | U | R | C | L |
|---|---|---|---|---|
| `02_mcu_core` (STM32N657) | 1 | **0** | **0** | **0** |
| `03_memory` (flash+PSRAM) | 3 | **0** | **0** | **0** |
| `04_wireless` | 1 | **0** | 1 | **0** |

A STM32N657 with **zero decoupling caps**, memory buses with **zero pull-ups / series
termination**, a radio with **zero matching** — this board cannot physically work, yet it is
`gate: PASS` on every current C03 machine gate.

## Root cause (consumer-side RCA — mechanism, not just symptom)

**This is NOT missing KB and NOT missing tooling.** Both are present and complete:

- **Method exists:** `stages/c03-ee/references/pinout-to-circuit-method.md` fully specifies the
  7-step loop and the 9-class per-pin *obligation* table (Power→decoupling, Boot/strap→defined
  pull, Clock→load caps, etc.). Line 46 even names this exact failure:
  > "The classification is the design. A pin you can't classify from the datasheet is the question
  > you take to the user — **it is not a pin you leave floating to look finished.**"
- **Tool exists:** `compose_schematic` places+nets R/C/L from a `spec`; `analyze_schematic`
  detects subcircuits; `check_c03` gates readiness.

**The gap is the enforcement seam, not the knowledge.** The method says "discharge every power
pin's decoupling obligation", but **nothing mechanically rejects a `spec` that skipped it**.
`compose_schematic` faithfully builds whatever `spec` it's handed — hand it a pinout-only spec
(pins → global labels, no support passives) and it emits a clean, ERC-passing, fidelity-OK
schematic. `analyze_schematic`'s connectivity gates (PP-001/RS-002/NT-001) fire on *broken*
nets, not on *absent* support networks. `check_c03` gates BOM schema / readiness / drawability /
SSOT — none of them assert "does each active IC carry its mandatory passives".

So an agent (or a hurried human) can satisfy every gate while having skipped step 2→5 of the
documented method. **The method is load-bearing prose with no machine backstop** — exactly the
class of failure C04 already learned to fail-hard on (floating copper → HARD FAIL, not
"COMPLETE"). C03 has no equivalent for floating/naked active parts.

This is a direct analogue of the *floating-PSRAM* case that motivated `check_c04`'s strict
thresholds: a gate that passes a board with an unsupported active device is a false pass.

## Fix proposal (a passive-completeness gate — implementation is bodesign's call)

The consumer is **not** prescribing the API; these are the shape options bodesign should
adjudicate. The invariant to install:

> **An active IC (U/Q with power pins) that carries zero decoupling — and, per its pin classes,
> zero required pulls / termination / load caps — is a HARD FAIL (or an explicitly-justified
> waiver), not a silent PASS.**

Candidate seams (pick per bodesign's architecture):

1. **`compose_schematic(..., passive_completeness=True)`** — after placement, walk each active
   ref; for every power pin assert ≥1 decoupling cap on its rail within the sheet; for every pin
   whose class in the obligation table mandates support, assert that support exists. Return a
   structured `passive_gaps[]` (ref, pin, class, missing-obligation) analogous to
   `unresolved_pins`. This is the earliest, most fail-loud seam.
2. **`analyze_schematic` new rule (e.g. `PC-001`, `high`)** — "active IC with no decoupling /
   unmet pin-class obligation". Rides the existing finding envelope (confidence + evidence_source),
   so consumers already know how to read it.
3. **`check_c03` R5 (passive-completeness)** — roll the above into the C03→C04 entry gate so a
   pinout-only board is refused C04 entry the same way an R4 SSOT conflict is.

Grounding: the obligation source-of-truth already exists in
`pinout-to-circuit-method.md` (the 9-class table) — the gate is a machine projection of that
table onto a composed schematic, not new knowledge.

## Explicitly NOT bugs (do not "fix" these)

- **`compose_schematic` building whatever spec it's given** is correct behavior — the gate belongs
  at a validation seam, not by making the composer refuse to place bare pins (some intermediate /
  interface-subset schematics legitimately are partial; see `Netlist_Status.md` honest-subset path).
- **The method doc** is correct and complete; it does not need rewriting — it needs a machine backstop.
- **ERC / fidelity passing** is not the bug; they are blind to *absent* support by design. The bug
  is that no *other* gate covers it.
- Honest interface-subset / reverse-engineered baselines must remain able to declare a documented
  gap (`Netlist_Status.md`) and pass with a waiver — the gate must support an explicit,
  provenance-carrying waiver, not force passives onto a deliberately-partial deliverable.

## Validation plan

1. Unit: a pinout-only fixture (active IC, power pins, zero passives) → gate FAILs with
   `passive_gaps`/`PC-001` naming the ref+obligation.
2. Unit: a properly-decoupled fixture → gate PASSes.
3. Unit: an honest interface-subset with a documented-gap waiver → gate PASSes with the waiver
   recorded (no silent pass).
4. Regression: existing `test_composer.py` / `test_check_c03.py` still green.
5. Real-board: re-run against the aiguard `02_mcu_core` before/after the consumer adds
   decoupling — FAIL before, PASS after.

## Relay

`sender_session_id` = (this session). On completion inject back:
- done → `[BRNS-DONE sender=<S> br=c03-passive-completeness status=shipped commit=<sha>]`
- blocked → `[BRNS-BLOCKED sender=<S> br=c03-passive-completeness reason=<one-line>]`

Bounded agent-to-agent Q only for pure implementation trade-offs (≤2–3 rounds); anything touching
gate *policy* (what counts as a mandatory obligation, waiver semantics) escalates to the user.
