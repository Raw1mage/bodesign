# PCB layout rules compendium — the deterministic-rule knowledge base behind C04/C06

**What this is.** A consolidated, numeric, machine-checkability-tagged rule base for PCB
placement, routing, stackup, grounding/PI, EMC and DFM — distilled from a web crawl of
vendor/EE/standards sources (JLCPCB & PCBWay capability tables, Sierra Circuits, AtlasPCB,
PCBSync, FastTurn, Cadence/Allegro via graser.com.tw, ipcb.tw, wonderfulpcb, globalwellpcba,
IPC canon: 2221/2226/2141/2152/6012/7351/A-610). It is the **rule vault** the deterministic
gates draw on — every rule carries a **number** (where one exists), a **machine-checkable?**
verdict, and a **bodesign stage map** (C03 EE / C04 layout / C06 verify / C07 mfg / Tier-3
handoff).

> **Boundary (non-negotiable, same as the honesty model).** These are *design rules*, not lab
> compliance. A rule's `machine-checkable: yes` means a DRC/geometry script **can** verify it —
> it does **not** mean bodesign already checks it. DRC/SI/EMC verdicts are tool outputs; EMC/
> FCC/CE stay in C06/external labs. Many rules need **annotations only C03 can supply**
> (current-per-net, voltage-per-net, target-Z-per-net, skew-budget-per-bus) — those are
> C03→C04 handoff data, **not layout-inferable**, and if missing must **fail fast**, never be
> guessed (no-silent-fallback).

**How to read the tables.** `MC` = machine-checkable (Y / partial / N). `Stage` = owning
bodesign stage. `Tier` = common (any beginner guide teaches it) vs specialist (needs a
standard/experience). Numbers anchored to JLCPCB are that fab's **published** capability
(2025/26) — a concrete, real reference tier bodesign already has `jlcpcb`/`pcbway` skills for;
treat other fabs' minimums as their own published tables, not universal law.

> **Provenance discipline (Engineer-Mode SPEC-REF gate).** Every number here carries one of
> three provenance grades — **do not read them as interchangeable**:
> - **`[primary: <std §>]`** — traced to the primary standard, value-for-value (e.g. a row in
>   `standards-compliance.md` verified against the IPC PDF). Use directly.
> - **`[fab: <vendor>]`** — a named fab's published capability table. Real, but that fab's, not
>   universal law.
> - **`[rot]`** — rule-of-thumb / curve-fit / heuristic. A design starting point, **not** a
>   verifiable spec value. Never write a `[rot]` number into a DRC gate or a fab/送廠 doc as if
>   it were a standard clause.
>
> Where a primary table already exists in `standards-compliance.md`, **this file does not restate
> the numbers** — it points there (single source of truth). Restating invites drift, and a
> restated number that silently conflates table columns is exactly the HV-spacing defect this
> convention was added to kill (see R20).

---

## 1. Component placement (C04 — `Placement_Constraints.md`)

| # | Rule | Number | Why | MC | Stage | Tier |
|---|---|---|---|---|---|---|
| P1 | Partition analog/digital/RF/power | qualitative; each domain its own region + ground area | digital switching noise pollutes analog | partial | C04 (intent from C03) | common |
| P2 | Functional grouping (shorten nets) | related parts clustered | shorter traces → less R/delay/crosstalk | N | C04 | common |
| P3 | Placement order: connectors → power → precision (osc/sensor) → rest | 4-step order | connectors anchor the outline; precision parts land last in the quiet zone | N | C04 | common |
| P4 | Precision/noise-sensitive parts away from HF + switchers | qualitative (check spacing to switcher/RF) | oscillators/sensors are supply-noise sensitive | partial | C04 | common |
| P5 | High-speed parts (CPU/RAM) near their connector/each other | "shortest trace"; cluster clock/DDR group | short nets → less delay/reflection/EMI | Y (net length, spacing) | C04 (bounded by C03 SI list) | common |
| P6 | Decoupling cap hard against IC power pin | 1 cap per power pin; HF cap **< 5 mm** to pin, closest wins | minimise supply-loop inductance | Y (cap→pin dist, per-pin coverage) | C04 place / C03 BOM | common |
| P7 | Heat sources (reg/MOSFET/high-I) at board edge / airflow | qualitative (check dist to edge) | promote heat spreading | partial | C04 + C02 thermal | common |
| P8 | Thermal-via array under QFN/BGA exposed pad | `[rot]` **~1 via / 100 mW**; via Ø0.2–0.3 mm, pitch 1.0–1.2 mm — starting point, NOT a spec; real sizing = package θJA/θJC from the part's datasheet + board copper | conduct heat pad→inner/back copper | Y (via count / power) | C04 | specialist |
| P9 | Copper pour as heat spreader + flood empty area | fill unused area | spreads heat, lowers GND-Z, cuts loop area → less EMI | Y (pour coverage, copper balance) | C04 | common |
| P10 | Heat-sensitive parts (electrolytics) away from heat | qualitative | high temp shortens electrolytic life | partial | C04 | common |
| P11 | Same-type parts same orientation (R/C/diode) | align rotation | faster assembly, fewer pick-place errors, no bridging | Y (rotation consistency) | C04 DFA / C07 | common |
| P12 | No courtyard overlap; each part its clear zone | IPC-7351 courtyard excess 0.25 mm (density A); 0.15 mm (B); 0.5 mm (C) — **secondary-source values, not yet confirmed against the primary 7351B document** (see `standards-compliance.md` §Courtyard caveat) | overlap → un-assemblable / rejected | Y (courtyard overlap = std DRC) | C04 + C07 | specialist |
| P13 | Prefer single-side SMD (top-dominant) | count double-side parts | single-side reflow = simpler/cheaper | Y | C04 | common |
| P14 | Mounting-hole keepout (no trace/copper intrusion) | keepout ≈ screw-head r + 0.5 mm; ≥1–2 mm ring | prevent short / assembly interference | Y (hole keepout) | C04 (from C02) | common |
| P15 | Crystal/oscillator: shortest traces, ground under, guard ring | load traces **< 10 mm**, solid GND under, guard ring + stitching vias | osc is loudest EMI source + most sensitive | Y (trace len, GND completeness) | C04 (realise C03 SI) | specialist |
| P16 | Connector/LED/button/antenna at edge keepouts | per C01/C02 keepout; antenna: no copper under, clearance around | align to enclosure openings; antenna needs clearance to stay tuned | Y (part in assigned keepout) | C04 (from C01/C02) | common |
| P17 | Test-point placement & access | TP Ø ≥1 mm, pitch ≥2.54 mm, single-side preferred | ICT/flying-probe needs reliable contact | Y (TP Ø/pitch/side) | C04 DFT + C07 | specialist |
| P18 | Fiducials | **≥3 global** fiducials, asymmetric at corners; local fiducial for fine-pitch; Ø1 mm + 2 mm clearance | SMT machine-vision alignment | Y (count/pos/clearance) | C04 + C07 | specialist |

## 2. Routing & signal integrity (C04 route → C06 verify)

| # | Rule | Number | Why | MC | Stage | Tier |
|---|---|---|---|---|---|---|
| R1 | Trace width vs current | `[rot]` external ~**1 A / 20 mil** (10 °C rise, 1 oz) — a shorthand of the **IPC-2221 Figure 6-4 chart**, NOT an IPC-2152 clause; the internal "half of external" factor is undocumented lore (see `standards-compliance.md` §Current Carrying Capacity caveats). Precise sizing: use the chart/curve-fit there | I²R heating; undersized trace overheats/opens | Y (needs C03 current/net) | C03 current → C04 width; C06 | common |
| R2 | Min track/space vs copper weight (JLCPCB) | 1 oz **0.10/0.10 mm**; 2 oz 0.16; 2.5 oz 0.20; 3.5 oz 0.25; 4.5 oz 0.30 mm; width tol **±20 %** | heavier copper etches wider | Y | C04 DRC | common |
| R3 | Power/GND traces wide + short + parallel | widen to current; parallel traces split current | minimise IR drop, stable supply | partial | C04 | common |
| R4 | No 90° corners — use 45° / arcs | replace right angle with two 45° | Z discontinuity → reflection; acid-trap etch risk (low speed = cosmetic/DFM) | Y (90° vertex detect) | C04 | common |
| R5 | No acute (<90°) acid traps | avoid <90° copper angles | etchant pools → over-etch → open | Y (acute-angle detect) | C04 | common |
| R6 | 3W crosstalk rule | centre-centre **≥ 3× width** → ~70 % field contained; 10W → 98 % | limits parallel-trace coupling | Y (parallel-run spacing) | C04 / C06 | common |
| R7 | Ground guard trace between critical parallels | grounded trace + via-stitched | shunts coupled field to GND; **unstitched guard is worse than none** | partial (guard + stitch pitch) | C04 / C06 | specialist |
| R8 | Adjacent-layer orthogonality | route adjacent signal layers 90° apart (top H / next V) | minimise inter-layer coupling | Y (dominant dir per layer) | C04 | common |
| R9 | Controlled impedance targets | SE **50 Ω**; USB **90 Ω** diff; Ethernet/MIPI/LVDS **100 Ω**; CAN **120 Ω**; HDMI 100 Ω; PCIe 85 Ω; JLCPCB tol **±10 %** | mismatch → reflection/attenuation/timing | Y (width-from-stackup solver + tol) | C03 names → C04 `impedance_solve` → C06 `si_check` | specialist |
| R10 | High-speed net over continuous adjacent plane | 0 crossings of a plane gap/split/slot | return current follows trace on nearest plane; gap → loop antenna | Y (plane-continuity-under-trace) | C04 / C06 | specialist |
| R11 | Layer-change return via | GND stitch via next to signal via when transition crosses reference planes; keep both layers on same GND | low-inductance return across transition | Y (stitch-via near signal-via) | C04 | specialist |
| R12 | Minimise vias on high-speed nets | fewer = less L/stub; HDI → blind/buried/µvia (JLCPCB std: blind/buried NOT supported) | via L + stub resonance degrade edges | Y (via count / net) | C04 | specialist |
| R13 | Via stub / backdrill | JLCPCB backdrill through 0.2–0.5 mm, drill +0.2 mm, dielectric-to-next ≥0.15 mm | leftover via stub resonates/reflects | partial (stub from stackup) | C04 | specialist |
| R14 | Diff-pair symmetry & constant gap | equal length, symmetric, constant gap (set by target diff-Z), same layer | asymmetry → mode conversion → EMI/SI loss | Y (gap constancy + parallelism) | C04 | specialist |
| R15 | Intra-pair skew (P/N match) | **≤ 5 mil (0.13 mm)**; ≤2–3 mil for multi-Gbps; match at skew source | ΔL → common-mode conversion | Y (per-pair ΔL) | C04 | specialist |
| R16 | Inter-pair / bus length match | DDR byte-lane tens of mil; USB2 ≤ few mm; serpentine bends ≥ width, obey 3W to self; ps budget | setup/hold across parallel bus | Y (group ΔL/Δps vs budget) | C03 budget → C04 `length_match_bus` → C06 | specialist |
| R17 | No dangling (floating) trace | 0 one-end-unconnected tracks | antenna effect: radiates/receives EMI | Y (dangling-endpoint detect) | C04 (ERC-ish) | common |
| R18 | No self-loop across layers | no net loops back on itself via vias/layers | self-loop = radiating loop antenna | Y (cycle detect per net) | C04 | common |
| R19 | Minimum loop area (signal + return) | keep enclosed area as small as possible | loop area ∝ radiated emission & susceptibility | partial (needs return-path geom) | C04 / C06 | specialist |
| R20 | Min spacing per voltage (IPC-2221 Table 6-1) | **`[primary]` — do NOT read numbers off this row.** The full, column-correct table (B1 internal / B2 external-uncoated / B3 high-alt / B4 coated / A5–A7 assembly, incl. the primary-verified `>500 V` per-volt adders) lives in `engines/kicad/references/standards-compliance.md` §Conductor Spacing. Pick the column that matches the board condition (bare outer = **B2**, inner = B1, coated/assembled = B4/A5–A7). | insufficient gap → arc/breakdown | Y (net-net spacing vs voltage, per correct column) | C03 voltage → C04 spacing DRC | common→specialist (HV) |
| R21 | Same-net & pad/via clearances (JLCPCB) | same-net 0.25 mm; pad-track 0.1 mm; via-track 0.2 mm; PTH-track 0.28 mm (0.35 rec); SMD pad-pad diff-net 0.15 mm | below fab resolution → shorts/scrap | Y (DRC) | C04 | common |

## 3. Stackup & transmission-line (C04)

| # | Rule | Number | Why | MC | Stage | Tier |
|---|---|---|---|---|---|---|
| S1 | Every signal layer adjacent to a reference plane | dielectric 4–8 mil for controlled-Z; ≥15 dB radiated-emission gain vs routed grounds | return current needs an adjacent plane under the trace | Y (stackup adjacency) | C04 | common |
| S2 | 4-layer default | **Sig / GND / PWR / Sig** (HS on top by GND) | both outer layers referenced; GND-PWR pair = inter-plane C | Y | C04 | common |
| S3 | 6-layer assignment | **Sig / GND / Sig / PWR / GND / Sig** | two well-referenced inner signal layers | Y | C04 | common |
| S4 | High-speed next to GND not PWR | net-class → layer mapping | GND is a cleaner/lower-Z return than a switching PWR plane | partial | C04 | specialist |
| S5 | Symmetric/balanced stackup | mirror dielectric + copper about centreline; copper balance ±10 %/pair | asymmetry warps on reflow (CTE + copper imbalance) | Y (layer-pair compare) | C04 + C07 | specialist |
| S6 | Close GND–PWR plane pair | dielectric **0.05–0.1 mm** (≤10 mil "close"; ~40 mil "wide" barely decouples) | thin dielectric → high plane capacitance (best HF decoupling) | Y (plane-pair dielectric) | C04 | specialist |
| S7 | Plane copper weight vs rail current | signal 1 oz; high-current GND/PWR **2 oz**; size to IPC-2152 | keep IR drop / plane R in budget | Y (compute) | C04 | common |
| S8 | λ/10 rule (treat as T-line) | length > λ/10 of highest sig freq (f_knee ≈ 0.35/t_rise; FR-4 λ≈(11.8/√εr)/f_GHz in) → controlled-Z; rule: t_rise < 2× prop-delay → T-line | below λ/10 lumped is fine; above, reflections dominate | Y (length vs freq/edge) | C03 flags → C04 routes | common |
| S9 | FR-4 propagation delay | `[rot]` ≈ **150–180 ps/in (6–7 ps/mm)** microstrip; ~180 ps/in stripline — assumes εr≈4.2 FR-4; delay scales with √εr, so re-derive per actual stackup/laminate before converting length↔ps | convert length-match tolerance ↔ ps skew | Y (length→delay) | C04 | common |

## 4. Grounding & power integrity (C03 topology + C04 layout + C06 verify)

| # | Rule | Number | Why | MC | Stage | Tier |
|---|---|---|---|---|---|---|
| G1 | **Do NOT split analog/digital ground (default)** | 1 solid unbroken plane; partition by *placement*, split ONLY for galvanic isolation | a moat forces return detours + becomes a slot antenna — manufactures the EMI it aimed to kill (Henry Ott) | partial (detect split Y; judge legitimacy N) | C03 topology + C04 | **specialist (counter-intuitive)** |
| G2 | AGND/DGND joined at the converter | tie at device, same plane, shortest per datasheet | impedance between pins couples *more* digital noise into analog | partial | C03 | specialist |
| G3 | Star (single-point) ground only ≤~1 MHz | star for LF/audio/DC/precision; multipoint plane >~1 MHz | star forces HF return to a distant node → loop antenna | N (topology intent) | C03 | specialist |
| G4 | Bridge a deliberate split correctly | stitch cap ~0.1 µF (A/D boundary); 2200 pF/2 kV across isolation; single controlled net-tie; gap ≥ IPC-2221 creepage | HF return path without a DC short across domains | partial | C03 + C04 | specialist |
| G5 | No signal crosses a plane split/slot/void | 0 HS/clock traces over a reference gap | return detours around slot → big loop + slot antenna ~λ/2 | Y (trace vs plane-void) | C04 / C06 | common |
| G6 | Return via ≤ 50 mil of every layer-changing signal via | **≤50 mil (1.27 mm)**; 30 mil for ≥10 Gbps; 2 flanking vias ≥5 Gbps | short cross-plane return path; 20–30 dB EMI cut | Y (nearest GND via to signal via) | C04 / C06 | specialist |
| G7 | Copper pour completeness / no floating islands | every island tied with ≥1 via or removed; solid > mesh on HS layers | floating copper = antenna/resonator | Y (island detect / unconnected-copper DRC) | C04 / C06 | common |
| G8 | Solid reference (no cutouts) under connectors | 0 voids under USB/HDMI/Ethernet footprints | void raises common-mode noise at I/O boundary | Y (plane continuity in footprint bbox) | C04 / C06 | common |
| G9 | 20H rule (plane-edge setback) | recess PWR-plane edge **20 × H** (H = PWR-GND dielectric); ~1 mm practical; 70 % field @20H, 98 % @100H | contain fringing field → less edge radiation (modest, nice-to-have) | Y (PWR outline offset ≥20·H, needs H) | C04 | specialist |
| G10 | Stitching-via spacing ≤ λ/20 | λ/20 @ f_max: 7.5 mm@1 GHz, 2.5 mm@3 GHz, 1.5 mm@5 GHz, 0.75 mm@10 GHz; general 5–10 mm | keeps inter-via gap non-radiating + breaks cavity resonance | Y (max nn-spacing in fence ≤ λ/20) | C04 / C06 | specialist |
| G11 | Edge via-fence setback | λ/20 pitch, **50–100 mil (1.3–2.5 mm)** from edge, continuous around cutouts; 10–20 dB edge-radiation cut | forces plane-pair V→0 at edge | Y (perimeter ring + spacing + edge dist) | C04 / C06 | specialist |
| G12 | PDN target impedance | **Z_target = ΔV / I_transient** (the formula is the rule). Worked examples — NOT real rail targets, recompute per rail from C03 specs: 1.0 V/5 %/10 A → 5 mΩ; 0.9 V/3 %/25 A → 1.1 mΩ; 3.3 V/5 %/1 A → 165 mΩ | Ohm's-law ceiling so worst-case current step stays in ripple budget | Y (compute per rail from C03) | C03 EE | specialist |
| G13 | Flat Z below target to knee freq | Z ≤ Z_target DC → **f_knee ≈ 0.35/t_rise** (not just spot freqs) | little energy above knee; spot pass can spike between caps | N (needs PDN sim) | C06 PI sim | specialist |
| G14 | Decap cascade values | HF **0.01–0.1 µF** (0402/0201) at pins; mid **1 µF**; bulk **10–100 µF** at VRM; bulk = 2–10× local | each value owns a band centred on its SRF | partial (band coverage per rail Y) | C03 | common |
| G15 | HF cap placement distance by freq | small HF cap **≤10 mm** of pin (100 MHz); 1 nF ~touching; ≤λ/20 of switching edge; bulk 100 µF ~10 cm OK | placement is a frequency/propagation problem | Y (cap→power-pin dist by value) | C04 / C06 | common |
| G16 | Minimise decap mounting loop inductance | vias in/adjacent to cap pad, **no trace between pad and via**; via-in-pad under BGA; mounting adds 0.5–2 nH | loop inductance, not nominal value, sets HF effectiveness | Y (trace-stub pad→via > threshold) | C04 / C06 | specialist |
| G17 | Fewer distinct decap values, more in parallel | avoid scattered decade; multiples of same value; 2 identical < ESL of 1; don't chase lowest ESR (ESR damps) | 2 dissimilar values form a parallel-LC anti-resonance peak | partial (count values per rail Y; true peak = sim) | C03 | specialist (counter-intuitive) |
| G18 | Per-rail decoupling set | each power net ≥1 decap set | rails differ in current demand + target-Z | Y (per power net ≥1 decap) | C03 / C06 | common |
| G19 | Cavity-resonance suppression | stitch a 100×100 mm cavity into 20×20 mm sub-cavities → lowest mode 750 MHz → 3.75 GHz | smaller sub-cavities push resonances above signal band | Y (compute lowest mode vs f_max) | C04 / C06 | specialist |

## 5. RF-specific (mostly Tier-3 handoff — bodesign does NOT auto-route on KiCad)

| # | Rule | Number | Why | MC | Stage | Tier |
|---|---|---|---|---|---|---|
| RF1 | RF 50 Ω trace + grounded coplanar waveguide | 50 Ω SE, GND pour both sides at defined gap + stitching vias | tight, shielded, well-referenced RF path | partial | **Tier-3 handoff** | specialist |
| RF2 | Antenna keepout | no copper (trace/pour/plane) in vendor keepout; often several mm all sides + full height | nearby copper detunes antenna | Y (copper-in-keepout) | C04 enforce, route Tier-3 | specialist |
| RF3 | RF ground stitching density | stitch RF pour ≤ λ/20 pitch | prevents pour becoming a resonant patch | Y | Tier-3 | specialist |
| RF4 | Guard trace/ring (RF/sensitive) | grounded, stitched ≤ λ/20 (~5 mm); unstitched = worse than none | nearer return + shield | partial | C04 / Tier-3 | specialist |

> **Tier-3 wall (feasibility-triage.md):** RF/antenna/GCPW/mmWave + any-layer HDI + DDR fly-by
> are where bodesign **must not** claim KiCad autorouting. Emit concept + numeric constraints
> (`emit_si_constraint_export`) and hand to professional EDA + human SI. RF1/RF3/RF4 above are
> knowledge for *authoring the constraint handoff*, not for routing.

## 6. DFM / fab constraints (C04 DRC gate + C07 mfg) — JLCPCB published numbers

| # | Rule | Number | MC | Stage |
|---|---|---|---|---|
| D1 | Min track/space | 1 oz 0.10/0.10 mm (0.09 multilayer, 3 mil BGA fanout); 2 oz 0.16; 2.5/3.5/4.5 oz 0.20/0.25/0.30 mm; tol ±20 % | Y | C04 |
| D2 | Min via | hole 0.15 mm / Ø0.25 mm (multilayer); Ø ≥ hole+0.1 mm; preferred hole 0.2 mm | Y | C04 |
| D3 | PTH annular ring | **≥0.20 mm** rec; abs min 0.15 mm (multilayer 1 oz) / 0.18 mm (2-layer) | Y | C04 |
| D4 | NPTH pad annular ring | ≥0.45 mm | Y | C04 |
| D5 | Via aspect ratio (thickness ÷ drill) | standard **≤ 8:1**, 10:1 advanced, 12:1 out-of-spec | Y | C04 |
| D6 | Hole-to-hole spacing | via 0.2 mm; pad hole-to-hole 0.45 mm | Y | C04 |
| D7 | Copper-to-edge | **≥0.2 mm** routed; **≥0.4 mm** V-cut (<0.2 → mask flakes) | Y | C04 |
| D8 | Soldermask dam/bridge | **≥0.10 mm** (colour 1 oz); 0.13 mm black/white; 0.20 mm 2 oz | Y | C04 |
| D9 | Soldermask expansion | 1:1 — **JLCPCB post-2025 LDI process only**; other fabs / older processes expand 0.05–0.1 mm: check that fab's DFM table; ≥0.09 mm to neighbour trace | Y | C04 |
| D10 | **Don't draw pads as filled polygons** | pad must be a real pad primitive | Y | C04 (false-COMPLETE class) |
| D11 | No overlapping pads | 0 pad-pad overlap | Y | C04 (false-COMPLETE class) |
| D12 | Silkscreen | line ≥0.15 mm, text height ≥1.0 mm (40 mil), char W:H 1:6, pad-to-silk ≥0.15 mm, silk off pads | Y | C04 |
| D13 | V-cut | copper ≥0.4 mm from groove, 25° angle, tol ±0.4 mm, min panel 70×70 mm, v-cut spacing ≥2 mm | Y | C07 |
| D14 | Mouse-bite / tab-route | tooling edge ≥3 mm (5 mm SMT), fiducials 1 mm @3.85 mm from edge, mouse-bite Ø0.5–0.8 mm | Y | C07 |
| D15 | Panel spacing | ≥2 mm between boards | Y | C07 |
| D16 | Plated slot | min 0.5 mm (2-layer)/0.35 mm (multilayer); length ≥2× width; NPTH slot ≥1.0 mm | Y | C04/C07 |

> **The "passes DRC but unmanufacturable" class (D10/D11 + ipcb.tw/495).** Filled-block "pads"
> generate no solder-mask opening → uncoated/unsolderable; overlapping pads scrap the board on
> drill; a power plane is a *negative* image so a careless gap shorts power. These are the same
> **false-COMPLETE** family as the floating-PSRAM lesson (honesty-model rule 5) — a naive DRC
> can pass them. Worth encoding as explicit gates.

## 7. Design-flow methodology (C04 process order — Cadence/Allegro tech17)

Not numbers — an **ordering discipline** for the physical-design phase. Encodable as C04 gates:

1. **Inputs-ready gate (before layout):** 4 inputs must exist — netlist, mechanical outline,
   DFx rules, SI/PI rules. Missing input = fail fast (concurrent design is the #1 rework source).
2. **Rules-as-data:** encode DFx + SI/PI as DRC rules **up front** (Allegro Constraint Manager),
   not post-hoc — design-time enforcement avoids back-end re-spins.
3. **Placement:** full **fanout of every device** + define reusable modules **before** global
   placement; place modules by signal-flow; verify DFx + thermal + assembly at global stage.
4. **Routing in strict order:** rule-review → doc → **stackup** → **plane/power FIRST** →
   intra-module → inter-module *critical* signals → low-speed control/sense → **length-tune LAST**
   → test points → silkscreen. (Power/plane first guarantees current capacity + plans return
   paths; tuning last so you tune against real geometry and don't create cross-split detours.)
5. **Exit gate:** netlist current, **unplaced = 0, unconnected = 0, all rules satisfied** —
   maps directly onto bodesign's honest DRC gate (`layout_drc_gate` copper+unconnected = fail).
6. **Check:** post-layout sim on critical nets (C06), checklist for redundant vias / cross-split,
   tool short/open check (invisible to the eye → must use a tool).

---

## 8. What maps where — the bodesign integration index

**By stage (for the eventual implementation plan):**
- **C03 (EE, names the numbers):** R1 current, R9/R20 targets, G2/G3/G4 ground topology,
  G12 Z_target, G14/G17/G18 decap strategy, S8 λ/10 flag. These are **handoff annotations**
  C04 consumes — if absent, fail fast.
- **C04 (layout, realises + geometric DRC):** all of §1 placement, §2 routing geometry, §3
  stackup, §4 layout-side grounding, §6 DFM, §7 flow. The bulk of machine-checkable rules.
- **C06 (verify):** G13 PDN sim, G17 anti-resonance sim, R10/R19 return-path/loop analysis,
  SI/EMC verdicts. Simulation-tier, not geometry DRC.
- **C07 (mfg):** D13–D16 panelization, IPC-class threshold selection.
- **Tier-3 handoff (bodesign refuses to auto-route):** §5 RF, any-layer HDI, DDR fly-by.

**Highest-value machine-checkable geometry rules for a bodesign DRC/analysis engine** (pure
geometry + a number, no sim): P6/P8/P12/P15/P17/P18, R2/R4/R5/R6/R8/R10/R11/R15/R16/R17/R18/
R21, S1/S5/S6, G5/G6/G7/G8/G9/G10/G11/G15/G16, RF2, all of D1–D16. Several already exist in
the KiCad engine (`analyze_pcb.py` return-path, proximity/crosstalk, edge clearance) — the
**new value** is the consolidated *numeric thresholds* + the false-COMPLETE class (D10/D11).

**Compute-only (need C03 rail specs, no geometry):** R1, G12, G19, S7.
**Require simulation (C06, not DRC):** G13, G17, R19(partial).
**Topology/intent — human/LLM judgement, not auto-verifiable:** G1/G3/G4 legitimacy, P1 intent.

## 9. Sources & honesty notes

- **Fab numbers:** JLCPCB published capability table (2025/26) — the concrete reference tier;
  PCBWay table partly unreachable this crawl, its deltas (6/6 mil default, 0.2 mm min via) not
  re-confirmed. Treat each fab's table as its own, not universal.
- **SI/EMC/grounding:** Sierra Circuits, AtlasPCB, PCBSync, FastTurn + Ott / Johnson-Graham /
  Bogatin-Smith canon. IPC standards (2221/2152/2141/2226/6012/7351/A-610) cited as the
  authority behind numeric rules, not as fetched pages.
- **User-provided sources:** ipcb.tw/468 (3W/20H/loop/orthogonal/open-loop/self-loop/decap),
  ipcb.tw/495 (DFM gotchas: edge clearance, filled-pad, pad overlap), jlcpcb blog + capability,
  graser tech105 (high-speed: no-split-plane, return path, backdrill), graser tech17 (design
  flow), wonderfulpcb + globalwellpcba (beginner placement).
- **Honesty:** YouTube `rULvhr_HLyA` had captions disabled — no content distilled, **not
  fabricated**. `YDjp2NEFB2U` (interactive KiCad tips) distilled separately into
  `kicad-interactive-layout.md`. Numeric "rules of thumb" (λ/10, 20H, prop-delay) are labelled
  as such; nothing dressed as a fab-verified spec.
- This compendium is a **design-rule reference**, not a certification. It supplies the numbers
  the deterministic gates *can* check — wiring each into an actual gate is implementation work
  for the forthcoming plan.
