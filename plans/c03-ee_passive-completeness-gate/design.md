# Design: c03-ee_passive-completeness-gate

## Context

C03 (EE) ships schematics through `compose_schematic` → `analyze_schematic` → `check_c03`.
A consumer produced a full schematic set that was pure pinout placement: active ICs
(STM32N657, flash/PSRAM, radio) with **zero** support passives. It passed every gate —
ERC ok, fidelity ok, `analyze_schematic` no `high` finding, `check_c03` PASS — because no
gate asserts "does each active IC carry its mandatory passives". The obligation table
(`stages/c03-ee/references/pinout-to-circuit-method.md`, 9 pin classes) is load-bearing
prose with no machine backstop. This is the C03 analogue of C04's floating-copper false
pass. This change installs that backstop.

## Goals / Non-Goals

**Goals**

- HARD FAIL a composed schematic where an active IC's power rails carry zero decoupling.
- Support an explicit, provenance-carrying waiver so honest interface-subset /
  reverse-engineered baselines PASS with the waiver **recorded** (never silent).
- Reuse existing analyzer infrastructure (net map, comp classifier, decoupling walk);
  add no new knowledge — the gate is a machine projection of the existing obligation table.

**Non-Goals**

- Not rewriting the method doc (correct and complete).
- Not making `compose_schematic` refuse to place bare pins (partial schematics are legit).
- Not verifying value correctness / SI — PC-001 asserts *presence* of decoupling, not sizing.
- Not blocking on pulls / termination / load-caps (WARN only — see DD-2).

## Decisions

- **DD-1 (seam): PC-001 = a new `validate_passive_completeness` detector in
  `validation_detectors.py`, wired into `analyze_schematic.py`'s `analyze_signal_paths`.**
  Rejected the composer seam (`compose_schematic(passive_completeness=…)`): the composer has
  NO ref-type classification and NO rail/power-net detection — it consumes only raw
  `REF.PIN→net` mapping, so the walk would have to re-implement classification that already
  exists in the analyzer. Rejected `check_c03` R5: `check_c03` operates on the BOM CSV, not
  schematic topology — it cannot see whether a decoupling cap is *connected* to a rail.
  The analyzer already has, at analyze time: per-ref pin→net map (`ctx.nets`, `ctx.pin_net`),
  `comp["type"]` ref classifier (`classify_component` → `"ic"` for U/A), per-pin electrical
  type, rail/power-net detection (`ctx.is_power_net` / `ctx.is_ground` / `rail_voltages` /
  net_classifications), AND an existing `detect_decoupling` walk that already computes per-rail
  cap totals. PC-001 reuses those primitives; it rides the standard `make_finding` envelope
  (`severity='error'`, `confidence='deterministic'`, `evidence_source='topology'`) and merges
  into `results["validation_findings"]`.

- **DD-2 (policy — USER-adjudicated): mandatory obligation scope = DECOUPLING-ONLY.**
  The blocking PC-001 error fires when an active IC (comp `type` ∈ {`ic`}) with ≥1 power pin
  has **zero** decoupling capacitance on any of its power rails. Unmet pulls / termination /
  load caps → `severity='warning'` (heuristic; pin-class certainty is not reliably reachable
  from netlist alone). Tightest false-positive control; ships exactly the invariant the BR
  names (STM32N657 zero-cap). BR mandates gate *policy* is a human decision — escalated,
  user chose this (Recommended) option.

- **DD-3 (policy — USER-adjudicated): waiver = sidecar file + per-gap match.**
  A committed sidecar `passive_waivers.json` (next to the `.kicad_sch`, sibling of the
  honest-subset `Netlist_Status.md` path) lists each waived gap:
  `{ "ref": "U1", "obligation": "decoupling", "source": "...", "reason": "...", "scope": "..." }`.
  The gate matches each detected `passive_gap` against the waiver list on `(ref, obligation)`:
  a matched gap is **recorded as `waived` in the report and downgraded from blocking to info**
  (visible, provenance carried, NOT suppressed); an unmatched gap stays a blocking error.
  A waiver never flips a `human_approved` field. Missing sidecar = no waivers (all gaps block).
  Malformed sidecar = fail-fast (typed error), never silently ignored.

## Risks / Trade-offs

- **False positive on a legitimately-decoupled-but-oddly-named rail** — mitigation: reuse the
  analyzer's existing `is_power_net` / `rail_voltages` detection (already battle-tested by
  `detect_decoupling`), do not invent new rail heuristics.
- **Decoupling-only misses boot/strap floating (a real killer)** — accepted trade-off (DD-2):
  strap detection is heuristic and out-of-scope for this gate; captured as a WARN, and a
  follow-up `extend` can add a strapping obligation once its detection is reliable.
- **Waiver becomes a rubber stamp** — mitigation: per-gap match (not global flag), provenance
  fields required, waived gaps stay visible in the report; a reviewer sees exactly what was
  waived and why. `passive_waivers.json` is committed → shows up in review diffs.

## Critical Files

- `skills/bodesign/engines/kicad/scripts/validation_detectors.py` — new
  `validate_passive_completeness(ctx)` detector (the PC-001 walk + waiver match).
- `skills/bodesign/engines/kicad/scripts/analyze_schematic.py` — import + dispatch the new
  detector in `analyze_signal_paths`, merge into `validation_findings`.
- `skills/bodesign/engines/kicad/scripts/signal_detectors.py:1172` `detect_decoupling` —
  reference for the per-rail cap walk PC-001 mirrors.
- `skills/bodesign/engines/kicad/scripts/finding_schema.py` — `make_finding` envelope PC-001 uses.
- `skills/bodesign/engines/kicad/scripts/kicad_utils.py:428` `classify_component` — ref→type.
- `tests/` — new fixtures (pinout-only FAIL, decoupled PASS, waiver PASS) + regression.
