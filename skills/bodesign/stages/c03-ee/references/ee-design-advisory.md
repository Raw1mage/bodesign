# C03 EE design advisory — power, decoupling, SI requirements, thermal, RF

**What this is.** The *design-side* judgment layer for C03: the heuristics for **what to put in the
schematic** — regulator topology, decoupling strategy, the signal-integrity *numbers* C04 must hit,
thermal sizing, RF budget. It is the EE analogue of C02's `mechanical-design-advisory.md`.

**What it is NOT — the engine boundary.** These are *starting* design heuristics, not verified
findings. C03 has an execution engine (`../../../engines/kicad/`): you **run the analyzer and carry
its `confidence`/`evidence_source`**, you do not assert a value because a rule of thumb gave it. The
`datasheets` engine confirms the actual part specs; **SPICE/EMC verdicts belong to C06** (you name
the plan, never claim a pass — honesty rules 3, 4). A heuristic here tells you what to *try* and what
*requirement* to hand C04; the engine and the datasheet tell you what is *true*.

**Provenance.** Distilled from the `ee` hardware skill (`mattpainter701/my-claude-setup`, same author
as the OpenSCAD/KiCad skills already used) plus standard EE practice; the speed-tier table draws on
`drandyhaas/KiCadRoutingTools`; the power-sequencing rules from `jonaschen/ai-bsp-knowledge-skill-sets`
(boot-debug-expert); the RF/antenna integration rules from `hyndex/Schematics-and-PCB-Skills`
(`pcb-specialized-rf`); the area-budget margin discipline from `amoslee2026/Babel` (bb-prd) and the
area-as-constraint pattern from `Arcadia-1/analog-agents` + `chuanseng-ng/digital-chip-design-agents`.
All are published rules of thumb, not measurements.

> **Specialised-domain reference vault.** For phone-class and beyond, the
> `hyndex/Schematics-and-PCB-Skills` library is a standing per-domain knowledge base — `pcb-theory-*`
> (signal-/power-integrity, grounding, emi-emc, thermal, isolation, creepage) and `pcb-specialized-*`
> (hdi, rf, mmwave, high-speed, rigid-flex, mixed-signal, precision-analog, bms, wearable, …) plus a
> `refdesign-*` reference-design workflow that mirrors the pinout→circuit method's
> "ground in the reference design". A given product picks the relevant few; consult it for a domain
> this advisory doesn't cover rather than guessing.

## Power tree & regulator selection

| Topology | Use when | Watch |
|---|---|---|
| **LDO** (linear) | low noise, dropout < 0.5 V, < ~500 mA, noise-sensitive analog/RF | dissipates `(Vin−Vout)·I` as heat → check θJA (below) |
| **Buck** (step-down) | efficiency at higher current / large Vin−Vout | switching node noise; layout-critical |
| **Boost** (step-up) | Vout > Vin | inductor current, RHP zero in control loop |

**Switcher layout rules (a C03 requirement you hand C04):** short/fat traces on the switching (Lx)
node; input cap right at Vin pin; **GND plane under the switcher**; keep Lx away from the feedback
resistors. State these as constraints in the mechanical/SI export — C04 realises them.

**Power budget** — build the rail table (`rail | V | I | P`) before choosing parts; sum per rail,
add margin, and let it drive regulator current rating + thermal. This is `Power_Tree.md`'s core.

**Power sequencing (mandatory on CMOS SoCs — wrong order = latch-up).** A reverse-biased well diode
triggers the parasitic PNPN thyristor; the fix is order, not luck. Default safe order, **up**:
`VDD_CORE → VDD_SRAM → VDD_IO → VDD_ANA` (core first, analogue last); **down** is the reverse, and
**assert isolation clamps before any rail drops** (else bus contention on restore). Always confirm
the *actual* order against the SoC/PMIC datasheet — it overrides this default. Each rail also needs
its **hold-time** and **brownout/monotonic-ramp** spec met. Reference: JEDEC **JESD78E** (latch-up).
This is a power-tree *requirement*; the analyzer's EN/PG-chain check verifies it, you author it.

## Passives: decoupling & derating

- **Decoupling cascade**, placed closest-cap-to-pin first, minimise loop area:
  **bulk 10–100 µF + mid 1–10 µF + HF 100 nF + ultra-HF 10 nF**.
- **Cap dielectric:** **X7R** for decoupling (±15 %, −80 % at rated V); **X5R** for bulk/low-cost;
  **avoid Y5V** for power (+22/−82 %). Use caps at **≤ 50 % rated voltage** (X7R loses ~20 % C at
  50 %) — check the datasheet derating curve.
- **SRF:** above self-resonance a cap is inductive. 0402 MLCC SRF ≈ 200–600 MHz, 0201 ≈ 1–3 GHz —
  the smaller package decouples higher frequencies, hence the cascade.
- **Resistor derating:** P_rated × 0.5 at 70 °C, linear to 0 at T_max.
- **MOSFET:** Rds(on) roughly **doubles 25 → 125 °C** — derate gate drive and loss accordingly.

## Area budget — will the chosen component set fit the board?

bodesign already holds both halves of this; the missing piece was tying them together into an
explicit **fit check** *before* C04 tries to place. Do it as soon as the component set is chosen:

- **Available area** = C02's provisional `board_outline` (back-derived from the C00 enclosure
  envelope), ×2 if components go on both sides.
- **Required area** = Σ(component footprint areas, from the `datasheets`/BOM) × a **packing factor**
  + connector/keepout area + routing channels. Packing rules of thumb: simple board ~40–60 %
  component-area utilisation, dense ~70 %, phone-class pushes higher only via stacking (PoP/SiP).
- **Reserve ≥ 10 % area margin** (routing + assembly clearance + tolerance) — the area analogue of
  the power-budget margin; if `required > available − margin`, it does **not** fit.

**If it doesn't fit — the escalation ladder (this is the co-design feedback loop in miniature):**
shrink passives (0402 → 0201 → 01005) · denser package (QFN → WLCSP/BGA) · go **HDI / any-layer**
(→ C04 stackup) · use both sides / more layers · collapse to a **module/SiP** · or push back to
**C00/C02 for a larger outline**. Pick with the user — don't silently assume it packs.

This is an **early feasibility estimate, not a placed board** — C04's actual placement is the real
test. A "won't fit" result **emits an `area` reconciliation record**
(`../../../references/cross-stage-reconciliation.md`): quantified delta, the ladder above routed per
stage, and a `must_act` for who re-evaluates — surfaced now, not discovered after C04 fails to place.
An `open` area record means the board is not "done" until it resolves.

## Signal-integrity *requirements* — the numbers C03 hands C04

C03 derives these; **C04 realises them** (its MCP `impedance_solve` / `length_match_bus` / `si_check`
make copper meet them). Hand them over in `Mechanical_Constraint_Export.json` / the SI requirement set.

- **When is a net "high-speed"?** Treat a trace as a transmission line when **length > λ/10 at the
  knee frequency** (knee ≈ 0.35 / t_r). Quick tiers by interface: **ultra-high > 1 GHz** (t_r ~0.3 ns,
  DDR/SerDes/LVDS), **high 100 MHz–1 GHz** (~1 ns), **medium 10–100 MHz** (~3 ns), **low < 10 MHz**.
  Only the nets that cross the λ/10 threshold need controlled-Z / length-match / termination.
- **Target Z0** (microstrip over a plane): `Z0 ≈ (87/√(εr+1.41))·ln(5.98H/(0.8W+T))`; FR4 εr ≈ 4.2,
  εr_eff ≈ 3.0. Use **stripline** for tight control (fully enclosed, no dispersion). Hand C04 the
  target Z0 + the stackup height assumption, not a trace width — width is C04's to solve.
- **Return paths:** **never split the reference plane under a high-speed net** (a split forces the
  return current around the gap → loop antenna); if a split is unavoidable, bridge it with a cap;
  **via-stitch** at every layer transition to carry the return. These are SI *rules* for C04.
- **Crosstalk:** **3W rule** — edge-to-edge spacing ≥ 3× trace width; reduce parallel run length;
  guard traces / differential pairs for the worst offenders.
- **Termination:** series R = Z0 at source (point-to-point); parallel R = Z0 to GND at load
  (multi-drop); AC termination = R + series cap (DC-blocking). Specify which, where, per net class.

## Thermal sizing (design-for; validation is C06/lab)

- **Junction temp:** `Tj = Ta + Pdiss·θJA`, `θJA = θJC + θCS + θSA`. Keep
  **Tj_max − Tj_operating ≥ 10 °C** margin; if exceeded → reduce Pdiss, more copper, heatsink,
  airflow, lower-Rds(on) part.
- **Copper as heatsink:** 1 in² of 1 oz copper ≈ 50–70 °C/W (still air), ~halved at 2 oz.
- **Thermal vias:** each ≈ 3–10 °C/W; array under exposed pads (QFN/BGA), guideline **~1 via per
  100 mW** for QFN. This is a placement/stackup requirement for C04.

### Thermal budget — does the heat dissipate within the enclosure? (cross-stage)

Like the area budget, this only closes by combining facts three stages own — so it is a
**cross-stage reconciliation** (`../../../references/cross-stage-reconciliation.md`). Run it once the
heat sources are known:

- **Heat to remove** = Σ Pdiss from `heat_sources[]` (LDO drop, switcher loss, SoC/RF dissipation).
- **Available dissipation** — from C02's enclosure: surface area × natural-convection coefficient
  (h ≈ 5–10 W/m²·K still air) × allowable ΔT (Ta → max internal), **sealed boxes dissipate far less**
  than vented. **Defer the real number to the thermal engine** (the `datasheets`-fed thermal analyzer)
  — this is the *reconciliation logic*, not a replacement for the sim.
- **Limits that must all hold:** every hot part's `Tj` (above); **external touch temperature**
  (IEC 62368-1 limits by surface material + contact time — handheld continuous contact is strict);
  and the **battery temperature window** (heat sources must not push it past its charge/discharge spec).

**If it doesn't close → emit a `thermal` reconciliation record** (don't silently ship a hot box). The
escalation ladder, routed per stage: spread/relocate heat + thermal-via arrays (**C04**) · vent the
enclosure — **but that trades IP** (**C02**, opens a coupled sealing record) · heatsink/spreader
(**C02/C04**) · lower-Pdiss or higher-efficiency part (**C03**) · larger enclosure surface (**C02/C00**).
The record's `must_act` names who re-evaluates; a hot, unresolved board is not "done".

## RF link budget (for products with an antenna)

- **dB sanity:** 2× = +3 dB, 10× = +10 dB; 0 dBm = 1 mW, +30 dBm = 1 W.
- **Friis NF:** `NF_total = NF1 + (NF2−1)/G1 + …` — the first stage dominates noise.
- **Sensitivity:** `Sens = −174 + 10log(BW) + NF + SNRmin` [dBm].
- **Match (S11):** good return loss < −10 dB; L-network `Q = √(Rs/Rl − 1)`, `BW ≈ f0/Q`.

**Antenna integration** (the RF requirements C04 realises): **50 Ω** single-ended is universal
(diff: 90 Ω USB, 100 Ω Ethernet/MIPI). Antenna **at the board edge**, RF chip **≤ 30 mm** from it,
**no copper or traces under a chip antenna** (any layer). Place an unstuffed **π-matching network**
(DNI initially) and **tune on the first prototype with a VNA** — don't trust the calc. RF rail from
an **LDO, not a switcher** (noise). Fence the RF section with a **via wall at λ/20** (~3 mm at
2.4 GHz; λ on PCB ε_eff 2.5 ≈ 79 mm). Use low-loss laminate (Rogers) above ~3–6 GHz. The antenna
keepout / non-metal-window also travels from C01/C02 — restate impedance + keepout + the ≤30 mm /
no-copper rule into the export so C04 honours it.

## Honesty closer

Every value here is a *design starting point*. Before C03 reports a number as decided: did the
**analyzer** confirm the connectivity/value (with provenance)? did the **datasheet** back the part
spec? is the SI/EMC/thermal claim a *plan* (C06) rather than a *pass*? If not, it stays `draft` /
`pending` with a reason — the heuristic sized it, the engine has not yet verified it
(`../../../references/honesty-model.md` rules 2, 3, 4).
