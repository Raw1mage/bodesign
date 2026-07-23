# Proposal: c03-ee_passive-completeness-gate

## Why

- A project consumer (thesmart_products / aiguard C03) produced a full schematic set via the
  C03 flow that was **pure pinout placement with no circuit design**: STM32N657 with zero
  decoupling, memory buses with zero pull-ups / series termination, radio with zero matching —
  a board that cannot physically work. Yet it passed **every** current C03 machine gate: ERC
  passed, fidelity passed, `analyze_schematic` raised no `high` finding, `check_c03` gate=PASS.
- The method (`stages/c03-ee/references/pinout-to-circuit-method.md`, the 9-class per-pin
  obligation table) and the tools (`compose_schematic` / `analyze_schematic` / `check_c03`) are
  **both present and complete**. The gap is the **enforcement seam**: nothing mechanically
  rejects a `spec`/schematic that skipped step 2→5 of the documented method. The method is
  load-bearing prose with no machine backstop.
- This is the direct C03 analogue of the C04 floating-copper lesson: a gate that passes a board
  with an unsupported active device is a **false pass**. C04 learned to HARD FAIL on floating
  copper; C03 has no equivalent for floating/naked active parts.

## Original Requirement Wording (Baseline)

- Consumer: 「你真的只是把所有的元件純 pinout 畫出來。但是完全沒有電路設計。」
- BR invariant: "An active IC (U/Q with power pins) that carries zero decoupling — and, per its
  pin classes, zero required pulls / termination / load caps — is a HARD FAIL (or an
  explicitly-justified waiver), not a silent PASS."

## Requirement Revision History

- 2026-07-23: initial draft created via plan-init.ts (from BR_20260723).

## Effective Requirement Description

1. Install a **passive-completeness gate**: a deterministic machine projection of the 9-class
   obligation table onto a composed schematic that HARD FAILs when an active IC carries none of
   its mandatory support passives (minimally: decoupling on power rails).
2. The gate must support an **explicit, provenance-carrying waiver** so an honest
   interface-subset / reverse-engineered baseline can declare a documented gap and PASS —
   **never a silent pass**; the waiver must be recorded in the report.
3. The gate is grounded in the existing obligation SSOT (`pinout-to-circuit-method.md`), not new
   knowledge. Gate thresholds are NEVER relaxed to pass (check_c04 floating-PSRAM lesson).

## Scope

### IN
- A passive-completeness check + structured `passive_gaps[]` output naming (ref, obligation).
- An explicit waiver mechanism carrying provenance (source, reason, scope).
- Wiring the gate into the chosen seam (adjudicated in design.md).
- BR validation plan: pinout-only fixture FAIL, decoupled fixture PASS, waiver fixture PASS,
  existing tests green, aiguard `02_mcu_core` before/after.

### OUT
- Rewriting the method doc (it is correct and complete — it needs a backstop, not a rewrite).
- Making `compose_schematic` refuse to place bare pins (some intermediate / interface-subset
  schematics legitimately are partial — honest-subset path stays valid).
- Changing ERC / fidelity (blind to *absent* support by design; not the bug).

## Non-Goals

- Full electrical correctness verification (value sizing, SI). This gate asserts *presence* of
  mandatory support, not that every value is optimal.
- Auto-inserting missing passives (composer builds what the spec says; the gate reports gaps).

## Constraints

- No silent fallback (repo hard rule §2.1). Missing evidence → fail fast + explicit gap list.
- Deterministic, pure, no LLM in the gate path (mirrors check_c03/check_c04 design).
- Waiver may never flip a human-approval field or silently suppress a finding.

## What Changes

- One of the three C03 gate seams gains a passive-completeness check (seam chosen in design.md).
- A waiver schema + recording path is added.
- New tests + fixtures.

## Capabilities

### New Capabilities
- passive-completeness gate: projects the obligation table onto a composed schematic; HARD FAIL
  on unsupported active ICs unless an explicit provenance-carrying waiver covers the gap.

### Modified Capabilities
- C03 stage-entry / analysis gate: now also asserts active-IC support presence, closing the
  pinout-only false-pass class.

## Impact

- `packages/eda-bridge/bodesign_eda_bridge/composer.py` OR
  `skills/bodesign/engines/kicad/scripts/analyze_schematic.py` OR
  `packages/workflow-core/bodesign_workflow_core/check_c03.py` (seam decided in design.md).
- Tests: `tests/test_*` + new fixtures.
- Consumers reading the C03 gate report (new `passive_gaps[]` / waiver fields).
- Docs: `specs/architecture.md` C03 section.
