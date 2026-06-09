# C02 mechanical-design advisory — DFM, tolerancing, materials

**What this is.** A compact *advisory knowledge* layer for the C02 ME consultant role: design-for-
manufacture rules of thumb, tolerance-stack method, a material quick-reference, and the scoping
questions to ask before generating any CAD. It is **reference knowledge, not authority** — it does
**not** move the C02 boundary. `me_approved` stays `false`; final DFM, tolerance, draft/undercut,
strength, waterproofing, thermal, and manufacturability sign-off remain the **ME / fab vendor's**
(`../GUIDE.md` § "What C02 does *not* own"). Treat every number below as a *starting* rule of thumb
to confirm with the vendor / printer operator — never as a decided value (honesty rules 1, 4, 6 in
`../../../references/honesty-model.md`).

**Provenance.** The design principles and exit-criteria heuristics are distilled from the external
`mechanical-design-engineer` skill (theNeoAI, `Haibarakiku/awesome-skills`); the FDM/SLA print-rule,
fit-tolerance and fastener numbers are distilled from the `openscad` hardware skill
(`mattpainter701/my-claude-setup`); the injection-moulding / casting / CNC / sheet-metal / tolerance-
cost numbers are distilled from the `dfm-review` skill (`a5c-ai/babysitter`); the IP / sealing
figures are distilled from the `enclosure-designer` skill (`majiayu000/claude-skill-registry`) plus
standard sealing practice; material notes are standard engineering common knowledge. All are widely-published rules of thumb, not measurements or
vendor commitments — confirm against the actual printer/process/vendor before relying on any one.

## Three design principles (the part worth keeping)

1. **Manufacturability before tolerancing.** Design the geometry for the chosen process *first*.
   A well-designed part with loose tolerances beats a poorly-designed part with tight tolerances —
   tightening tolerances to rescue bad geometry is wasted effort (and cost).
2. **GD&T controls *function*, not geometry.** Every tolerance/datum must map to a measurable
   functional requirement. **If you cannot say how it would be inspected, do not specify it.**
3. **Variation is inevitable and quantifiable.** At volume, dimensional scatter compounds — plan for
   it mathematically (tolerance stack, Cpk), not experimentally after tooling is cut.

## Scope it before you model — gate questions for C02-pre

Ask these *before* committing geometry; the answers decide which rules of thumb apply and what stays
`engineering_pending` (feed them into `Mechanical_Assumptions.md` § Prototype Intent):

1. **Process** — home FDM/SLA prototype, soft-tooling (EVT/DVT), or production injection moulding?
   (The wall/draft/clearance rules differ per process; see below.)
2. **Volume** — one-off / pilot / high-volume? Volume is what justifies tooling and tolerance cost.
3. **Structural / environment** — drop, load, sealing/IP, temperature? (Strength/waterproof/thermal
   validation is a vendor/lab gate, honesty rule 4 — record the target, never a pass.)
4. **Assembly & tooling access** — lid/base split, screw vs snap-fit, serviceability, can the tool
   open (undercuts)?
5. **Compliance** — UL/IEC 62368-1 flammability, RoHS, any agency mark? (External gates.)

A question with no answer is a `constraint_status.pending[]` entry with an owner — not a guessed
default.

## DFM rules of thumb — advisory, vendor confirms

### Injection moulding (from the source skill + standard practice)

| Feature | Rule of thumb | Why |
|---|---|---|
| Wall thickness | **Uniform 1.5–4 mm**; any transition **< 25 %** thickness change | Non-uniform walls → sink marks, warp, uneven cooling |
| Draft angle | **0.5–1° per side** minimum along pull; textured: **+1° per 0.025 mm** texture depth | Lets the part eject without drag/scuffing |
| Ribs | Thickness **50–75 % of the adjoining wall** (≤ 60 % is the conservative show-surface rule); height **< 3× wall**; spacing **> 2× wall** | Thicker/closer ribs sink-mark the show surface |
| Bosses | Wall **50–75 % of the base wall**; gusset, don't thicken; outer Ø ≈ 2× screw Ø | Same sink/void reason as ribs |
| Living hinge | Thin (0.2–0.5 mm), PP/PE; design for flex, not rigidity | Material- and geometry-specific; prototype it |
| Radii | Fillet internal corners (≥ 0.5× wall) | Sharp corners = stress risers + flow problems |

### FDM / SLA prototype (bodesign's printable-draft track)

**Print-geometry limits** (FDM, 0.4 mm nozzle unless noted):

| Feature | Rule of thumb | Why |
|---|---|---|
| Min wall | **1.2 mm** (3 perimeters @ 0.4 mm nozzle); SLA ≥ 1 mm | Thinner walls are fragile / fail to print |
| Min feature | **0.8 mm** | Below this the nozzle can't resolve it |
| Max overhang | **45° from vertical**, no support; beyond → support or reorient | Steeper overhangs sag |
| Max bridge | **15 mm** (PLA), **10 mm** (PETG) | Longer unsupported spans droop |
| Min horizontal hole | **3 mm**, teardrop-shaped | Round XY holes print small + oval; teardrop self-supports |
| Layer height | **0.2 mm** standard, **0.12 mm** for detail | — |
| Orientation | Lay the show / sealing face flat; load **across** layers, not along | FDM is weakest along Z layer lines |
| Edge | **0.5 mm chamfer** on bed-contact edges | Counters elephant-foot |
| Snap-fit | Validate deflection on the real material; FDM snaps fatigue fast | Layer adhesion ≠ moulded toughness |

**Fits & clearances** (add to nominal — printers over-extrude, nominal-to-nominal jams):

| Fit | Allowance |
|---|---|
| Press-fit hole | **+0.1 mm** over shaft Ø |
| Sliding fit (lid, cover) | **+0.3 mm per side** |
| Snap-fit clearance | **+0.2 mm** |
| Lid lip default | **0.3 mm** tolerance gap |

**Fasteners into plastic / 3D print:**

| Fastener | Hole |
|---|---|
| M3 screw clearance | **3.2 mm** |
| M3 self-tap into plastic | **2.5 mm** |
| M3 heat-set insert | **4.0 mm** Ø × **5.5 mm** deep |

These map straight into `Print_Settings.md` (material, wall, clearance, orientation, support,
tolerance) and the `Enclosure.scad` parameters (`wall`, `clearance`, `lid_clearance`). Two OpenSCAD
authoring gotchas worth carrying: extend every boolean cut **0.1 mm past** each surface (flush cuts
fail silently), and keep ≥ 0.1 mm overlap between internal features and the shell (no floating
bodies). Libraries **BOSL2** (rounding/threads/attachables) and **NopSCADlib** (real-part
"vitamins" for fit-check + BOM) accelerate this — optional, not required.

### Other processes — vendor territory, for the handoff conversation

C02 prototypes in FDM/SLA and specs for injection moulding, but a metal bracket or sheet-metal
chassis may enter at the vendor stage. Carry these so the `Vendor_Handoff.md` discussion is grounded
(the vendor still owns the final call):

| Process | Key numbers |
|---|---|
| **CNC machining** | Tolerance ±0.025 mm (milling) / ±0.013 mm (turning); drill L/D < 5; internal corner radius = tool radius (no sharp internal corners); min wall 1–2 mm (steel) |
| **Casting** | Draft 1–3° external / 2–5° internal; wall 3–5 mm (sand) / 2–3 mm (die); internal corners R > 3 mm, external R > 1 mm; shrinkage ~1.2–2 % (alloy-dependent) |
| **Sheet metal** | Bend radius 0.5× thickness (soft) / 1–2× (hard); flange > 4× thickness and > 3 mm; hole-to-edge > 2× thickness + bend radius |

## Design for assembly (DFA) — feeds `Assembly_Notes.md`

DFM asks "can this part be made?"; DFA asks "can the product be put together cheaply and correctly?"
The standard moves, in priority order:

- **Minimise part count.** Every part is an interface, a tolerance, and a failure mode. Consolidate
  where a single moulded feature can replace a separate part (integral boss/clip/standoff instead of
  a glued-in insert). Fewest parts that still meet function wins.
- **Self-locating / self-fixturing features.** Locating pins, lips, and chamfered lead-ins so a part
  drops into one position only — no "hold it while you screw" steps.
- **Top-down (Z-axis) assembly.** Stack parts along one axis under gravity; avoid re-orienting the
  product mid-build or fastening from multiple directions.
- **Minimise and standardise fasteners.** Snap-fits and integral catches over screws where service
  allows; one screw size over three; standard over proprietary (ties to the DfD/repair direction
  carried from C01).
- **Poka-yoke (mistake-proofing).** Make wrong assembly physically impossible — asymmetric mounting
  holes / connector keep-outs so a board or lid only fits the right way round.
- **Access in the assembled state.** Verify fasteners, connectors, and test points are reachable
  *after* assembly — late discovery here forces a redesign. Define the **assembly sequence**
  (order-of-build) and flag any step needing a fixture.

These map straight into `Assembly_Notes.md` (lid/base split, screw vs snap-fit, battery/cable access,
assembly order) — and the `Enclosure.scad` features (`mounting_markers()`, lid lip, snap clips).

## Tolerance stack — method, not magic

- **Worst-case** (sum of all tolerances): guarantees fit-up but is conservative/expensive. Use for
  small assemblies, safety-critical fits, or low volume where Cpk data doesn't exist.
- **RSS (root-sum-square)** (√Σtol²): statistically realistic for many-part stacks at volume; lets
  you open individual tolerances. Use when you have/expect process-capability data.
- Always identify the **critical dimension chain** (what must fit: PCB-in-pocket, connector-to-
  opening, lid-to-base) and stack *that*, not every dimension.
- Per principle 2: only place a tolerance where you can name the inspection. The rest is nominal.

**Tolerance costs money — open it unless function needs it.** Each tighter band roughly multiplies
machining/moulding cost; quote this when a `Vendor_Handoff.md` asks for a tolerance:

| Class | Cost vs standard |
|---|---|
| Standard ±0.5 mm | 1× |
| Precision ±0.1 mm | 2–3× |
| Close ±0.025 mm | 5–10× |
| Very close ±0.01 mm | 10–20× |

## Material quick-reference — enclosures

| Material | Use when | Watch |
|---|---|---|
| **ABS** | General enclosure, low cost, easy to print/mould | Low UV/heat resistance; not for outdoor/hot |
| **PC** | Impact + heat + clarity (windows, light pipes) | Notch-sensitive; needs generous radii |
| **PC-ABS** | Tougher than ABS, more processable than PC | Cost between the two |
| **PA (nylon)** | Living hinges, wear, snap-fits | Hygroscopic — dries/dimension shifts |
| **PETG** | Tough FDM prototype, some chemical resistance | Stringy to print; softer than ABS |
| **PPS / glass-filled** | High-temp, chemical, structural | Specialist moulding; vendor territory |

RF/antenna keepout zones (carried from C01/C03) **must** stay non-metallic — note the material
constraint in `Mechanical_Constraints.json`, don't silently pick a metallised finish.

## Sealing & IP — design *for* the target, never claim the test

The product carries an IP target from C00; C02 designs the enclosure *toward* it. **IP validation is
an external ingress-test gate** (honesty rule 4) — mark the design `design-for-IPxx, unverified`,
never "IP67 passed".

**IP code** — first digit = solids (6 = dust-tight), second = water: **4** splash · **5** jets ·
**6** powerful jets · **7** immersion ≤ 1 m / 30 min · **8** continuous immersion. Pick the strategy
from the *second* digit:

| Target | Sealing approach |
|---|---|
| **IPx4 (splash)** | Tight tongue-and-groove / lip lid joint; membrane or recessed buttons; louvre/labyrinth over any vent. Gasket optional. |
| **IPx5–6 (jets)** | **Continuous compressed gasket** in a groove (silicone / EPDM O-ring or moulded-in bead); IP-rated or gasketed connectors; PG7/PG9 cable glands (+ silicone). |
| **IPx7–8 (immersion)** | Compressed gasket **or** a permanent seal (ultrasonic weld / over-mould); potted cable entries; conformal-coat the PCB as a second line of defence. |

**Gasket / groove heuristics:** the seal must be a **continuous loop** — no gaps, full-radius
corners (sharp corners leak). Size the groove so the gasket is squeezed **~15–30 %** (compression
set). Don't trust screws alone for IPx5+: keep screw spacing close enough that compression stays
**even** all the way round. Permanent IPx7 → weld/over-mould rather than a serviceable gasket
(this trades against the DfD/repair direction from C01 — flag the conflict, don't silently pick).

**Pressure equalisation (where sealing meets heat).** A *sealed* box that also heats/cools cycles
its internal pressure — that pumps air (and eventually water) past the seal. For a sealed enclosure
with a warm load, add a **Gore/PTFE breathable vent** (passes air, blocks liquid). Whether to vent
at all, where, and the pattern, is a **trade between IP, thermal, acoustics and looks** — a designer
/ thermal-engine call, not a default. If C00/the user/the thermal engine hasn't decided it, raise it
as an `engineering_pending` item and **ask** — don't assume a vent pattern (honesty rule 6).

## Exit-criteria heuristics (the *vendor's* gate, recorded — not asserted by C02)

The source skill's design-review exit bar is a useful *target to hand the vendor*, not something
C02 certifies: **all DFM issues closed · DFMEA RPN < 100 · FOS > 1.5**. In bodesign these belong in
`Vendor_Handoff.md` as the acceptance bar the vendor's refined STEP must meet — C02 records the
target and `me_approved` stays `false` until a named ME signs against it (honesty rules 3, 4).
