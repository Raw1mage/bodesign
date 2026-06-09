# C04 layout judgment — stackup, placement, SI realisation

**What this is.** The *design-intent* layer for C04: how to choose the **stackup**, how to
**place**, and how to **realise** C03's SI requirements — i.e. what to *intend* and what to *ask the
MCP for*. It is distinct from the execution, which is already tool-backed: the bodesign MCP
(`impedance_solve` / `route_net2pcb` / `autoroute` / `pour_planes` / `length_match_bus` / `via_in_pad`
/ `si_check` / `layout_drc_gate` / `emit_fab`) makes copper meet the targets and the KiCad engine
(`analyze_pcb.py`) verifies. This note supplies the judgment *behind* those calls.

**The engine/gate boundary — non-negotiable.** DRC/SI are **tool verdicts, not lab compliance**
(EMC/FCC/CE stay in C06/external labs). **Route only what the netlist gives** — never invent a
connection C03 left unknown. And the lesson this repo paid for: an earlier gate **falsely passed a
board with a floating PSRAM** (footprint pads didn't match the symbol → 24 unnetted pads, gate said
"COMPLETE"). **Never relax a threshold to make a board pass — fix the board or report the warn**
(`../../../references/honesty-model.md` rule 5). Fab outputs are `pending` until the board is frozen.

**Provenance.** The *execution/analysis* KiCad skills crawled were rejected — they overlap or conflict
with the bodesign MCP + KiCad engine. The stackup/placement judgment here is standard PCB-layout
practice tied to C03's SI requirements (`../../c03-ee/references/ee-design-advisory.md`); the **HDI**
section is distilled from `hyndex/Schematics-and-PCB-Skills` (`pcb-specialized-hdi`, IPC-2226/4761).
It is design judgment, not a verified result. For specialised domains beyond HDI (rigid-flex, mmwave,
high-speed, backplane…) the `hyndex` `pcb-specialized-*` / `pcb-theory-*` library is the standing
reference vault — consult it rather than guessing.

## Stackup — choose it from the signals, then hand targets to `impedance_solve`

| Layers | Use when | Assignment |
|---|---|---|
| **2-layer** | simple, low-speed, no controlled-Z, cost-driven | top signal / bottom mostly-GND pour |
| **4-layer** (default for any high-speed or dense board) | controlled-Z needed, BGA/dense, any net over λ/10 | **Sig / GND / PWR / Sig** |
| **6-layer+** | multiple high-speed buses, tight Z control, many power domains | add inner signal layers each adjacent to a plane |

- **Every signal layer must be adjacent to a reference plane** — that plane carries the return
  current. A signal layer with no adjacent plane has no defined return path.
- Put **high-speed signals next to GND**, not next to a power plane.
- Keep the **GND–PWR plane pair close** (thin dielectric) for inter-plane capacitance (decoupling).
- Feed C03's **target Z0 + the chosen dielectric heights** into `impedance_solve`; let it solve the
  trace width — you set the target, the MCP makes copper meet it.

### HDI — when the board goes phone-class (dense BGA, ≤ 0.5 mm pitch)

A standard 4/6-layer board can't escape a fine-pitch BGA; HDI (microvias ≤ 150 µm, fine L/S ≤ 75 µm,
sequential lamination) is the smartphone/wearable regime. Pick the **IPC-2226 type** to the density:

| Type | Structure | Use |
|---|---|---|
| **I (1+N+1)** | microvia one layer each side of the core | moderate density |
| **II (2+N+2)** | two microvia layers per side | denser |
| **Any-layer** | every adjacent pair microvia | **iPhone-class**, highest density, highest cost |

- **Via-in-pad, filled + capped** (IPC-4761 Type VII) is **mandatory for BGA ≤ 0.4 mm pitch**.
- **Staggered microvias > stacked** for reliability; minimise stacked count.
- **BGA escape capability:** 1.0/0.8 mm → 2 traces/channel · 0.65 mm → 1 trace (dog-bone OK) ·
  0.5 mm → 1 trace tight, prefer via-in-pad · **≤ 0.4 mm → via-in-pad mandatory**.
- **Match the fab tier to the design rules** *first* (the #1 HDI mistake is designing beyond what the
  chosen fab can build); design a **microvia cross-section test coupon**; budget yield + cost.
- Thin HDI dielectrics need a **field-solver** for impedance (the engine/MCP `impedance_solve`).
- Standards: IPC-2226 (HDI design), IPC-4761 (via protection), IPC-6012 (qual), IPC-7351 (lands).

## Placement — partition before you route

> **Fit was already estimated in C03.** C03's area-budget check
> (`../../c03-ee/references/ee-design-advisory.md` § "Area budget") gave an early "does the set fit
> the C02 outline?" verdict. C04 placement is the **real test** of it — if the board won't actually
> pack within the outline + keepouts, that's a finding to escalate back (HDI, more layers, both
> sides, larger outline), not a threshold to quietly stretch.

- **Partition by power / noise / thermal domain.** Keep switchers (and their hot Lx loop) away from
  analog/RF; group each power domain; keep the C03 switcher-layout rules (input cap at Vin, GND under
  the switcher, Lx away from feedback).
- **Decoupling caps at the IC power pins** — C03's cascade (bulk→mid→HF→ultra-HF) only works if
  placement honours closest-cap-to-pin, minimum loop area. This is a *placement* decision, not a BOM
  one.
- **Thermal:** spread heat sources; array thermal vias under QFN/BGA exposed pads (C03's ~1 via per
  100 mW); keep hot parts away from the battery and temp-sensitive components.
- **Edges/openings:** connectors, LEDs, buttons, antenna land at the faces/keepouts C01/C02 set —
  honour the `Mechanical_Constraint_Export.json` keepouts; flag any collision back, don't route over
  it.

### Height budget — do the tall parts fit the enclosure depth? (cross-stage)

The third instance of the same reconciliation pattern (`../../../references/cross-stage-reconciliation.md`),
and a real phone/thin-product killer. As you place, check the **Z** dimension, not just X-Y:

- **Available depth** = C02's internal enclosure depth at each region (it may vary — a battery pocket
  vs a board zone), from `Mechanical_Constraints.json`'s component-height envelope.
- **Required height** = the tallest part in that region (connector, electrolytic, shield can, BGA
  stack, board-to-board stack), from the `datasheets`/BOM package height.
- If a part overflows the local depth → **emit a `height` reconciliation record**. Levers per stage:
  relocate the tall part to a deeper region / other side (**C04**) · lower-profile part (**C03**) ·
  deeper enclosure or local boss/pocket (**C02**) · accept a bump in the industrial design (**C01/C00**).

Tall parts also drive placement: keep them off the side that mates against the display/lid, and away
from regions C02 marked thin.

## Realising C03's SI requirements

C03 hands the *numbers* (`ee-design-advisory.md` § SI); C04 makes copper meet them:

- **Return-path continuity:** never route a high-speed net across a reference-plane split; **via-stitch
  at every layer transition**. `si_check` flags violations — but design for it, don't rely on the
  check to catch a bad plan.
- **Controlled-Z nets** → `impedance_solve` against C03's target Z0.
- **Length-match groups** (DDR, differential, source-synchronous) → `length_match_bus` to C03's
  tolerance.
- **Crosstalk:** keep the **3W** edge-to-edge spacing; route the worst offenders as differential
  pairs / with guard traces.
- **Termination** placement per C03's per-net spec (series at source / parallel at load).

## Done = gated, not "looks routed"

Run `layout_drc_gate` honestly (copper + unconnected = hard fail; unmapped-pad gate on) and
`c04_readiness`. A board is a **draft** until it passes; passing means the gate parsed real DRC, not
that the render looks clean. Hand frozen outputs to C07 — `emit_fab` produces gerbers, but they stay
`pending` against the freeze gate that owns them.

**And — C04 may not declare done while an `open` cross-stage reconciliation it is named in is
unresolved** (`../../../references/cross-stage-reconciliation.md`): a DRC-clean board sitting on an
unresolved area or thermal overage is the same false-COMPLETE the floating-PSRAM gate produced.
Placement is also the **real test** of C03's area/thermal estimates — if reality diverges, update the
record (resolve it, or escalate to the next lever's stage), don't quietly stretch the outline.
