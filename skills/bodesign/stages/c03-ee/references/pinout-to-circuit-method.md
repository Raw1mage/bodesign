# C03 method — from chip pinout data to a circuit

**What this is.** The *reasoning method* that C03 turns on most: how to go from a chip's extracted
**pinout** to a complete, correct **design spec** (the `spec` that `bodesign_compose_schematic`
consumes). `ee-design-advisory.md` is the component *knowledge* (what topology / what value); this is
the *synthesis process* (how to reason a whole circuit out of the datasheet). It is the C03 analogue
of C01's reduction lens and C02's geometry-authoring loop — and it is the most AI-heavy part of the
stage, because it is reasoning, not a tool call.

**The spine — generation is not correctness, and nothing is invented.** The method produces the
`spec`; the MCP builds it; **the KiCad analyzer + the datasheets engine verify it** (GUIDE SOP
steps 3–5). Every connection must trace to a datasheet requirement, a manufacturer reference design,
or a named EE decision. A pin whose obligation you cannot resolve is a **documented gap / question to
the user** — never a guessed connection (`../../../references/honesty-model.md` rule 6).

## The loop

1. **Ingest the real pinout** — from the datasheets engine's extraction
   (`datasheets/extracted/<MPN>.json`), not from eyeballing a package drawing. If the part isn't
   extracted yet, sync it (GUIDE SOP step 3) or ask — don't guess a pin function.
2. **Classify every pin** (next section) — each class carries a *mandatory support obligation*.
3. **Ground in the reference design** — start from the datasheet's typical-application circuit; it
   already encodes the required passives, regulator compensation, and recommended decoupling. A
   deviation is a *decision with a reason*, not a default.
4. **Discharge each pin's obligation** — add the support each class requires (below).
5. **Complete each interface** — instantiate the standard support set per bus/peripheral.
6. **Allocate pins against the mux table** — `bodesign_pin_allocation`; a function isn't available on
   every pin. This closes the spec and produces the C05 GPIO map.
7. **Build → verify** — `compose_schematic` places+nets; resolve its `unresolved_pins`; then the
   analyzer + datasheets confirm correctness. Generation ≠ correctness.

## Classify every pin — each class is an obligation, not a label

| Pin class | Mandatory obligation (trace to datasheet) |
|---|---|
| **Power** (VDD/VCC/AVDD/VBAT) | decoupling cascade *per pin*, closest-cap-first (see advisory); bulk per rail; respect max ripple |
| **Ground / exposed pad** | connect every GND; thermal-via array under the pad; AGND/DGND partition if the datasheet asks |
| **Clock** (XTAL/OSC) | load caps to the datasheet **CL** (`C ≈ 2·CL − C_stray`); crystal keepout/guard |
| **Reset / EN** | pull to the defined state; RC or supervisor IC; honour power-up **sequencing** order |
| **Boot / strapping / config** | pull to the **exact** state the datasheet's boot/strap table requires — a floating strap = undefined boot, the C03 equivalent of the floating-PSRAM disaster |
| **Analog reference** (VREF/VRES) | reference filter cap; sometimes a dedicated quiet LDO |
| **IO / GPIO** | allocate per interface; add default-state pulls where the bus/idle needs them |
| **High-speed / differential / RF** (USB DP-DM, MIPI, RF) | ESD, controlled-Z + termination per the SI requirements (advisory § SI); antenna keepout from C01/C02 |
| **NC / DNC / reserved** | follow the datasheet literally — NC = leave open; *reserved/DNC* may need a specific tie. Don't assume; if unstated, ask |

The classification is the design. A pin you can't classify from the datasheet is the question you
take to the user — it is *not* a pin you leave floating to look finished.

## Complete each interface — standard support sets

For every interface the architecture calls for, instantiate its known support (values from the
datasheet / bus spec, not invented):

- **I²C** → pull-ups sized to bus speed + capacitance; one pair per bus.
- **SPI / parallel** → series termination on fast lines (advisory § termination).
- **USB** → ESD array; HS → 90 Ω differential + series; respect DP/DM length-match (→ C04).
- **UART / level-crossing IO** → level shift + ESD where domains differ.
- **Power front-end** → input protection (reverse/TVS/fuse) → regulator + its reference passives →
  sequencing + EN/PG logic; size from the `Power_Tree.md` budget.
- **Crystal / oscillator** → load caps (CL), series R if the datasheet specifies.

## Close the loop honestly

The synthesis produced a *spec*; it is `draft` until the analyzer (with datasheets synced) verifies
it and an EE owner signs off. Carry every support component's **provenance** (datasheet section /
reference design / decision). Resolve `unresolved_pins` before declaring capture done. Boot-strap and
power/ground obligations are the silent killers — verify them explicitly, the way C04 learned to fail
hard on unconnected copper rather than report "COMPLETE".
