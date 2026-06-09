# C01 design-direction method — reduction lens & essential-function framing

**What this is.** A *method scaffold* for reasoning your way to the C01 Design Direction, CMF
Direction, and Visible-Component Intent — not a designer and not final art. Everything it produces is
**rationale and sharper open questions**, which land in C01 artifacts as `draft`/`drafted` fields and
`Open ID Decisions` / `open_decisions[]` entries. It does **not** let you assert a decided form,
colour, or placement; the human boundary in `../GUIDE.md` § "What C01 does *not* own" still holds.

**Provenance.** The reduction lens is distilled (method only) from the external `ind` "industrial
designer" skill (`Everyone-Needs-A-Copilot/codex-copilot`) and the public Dieter Rams / Jony Ive
principles it builds on; the material-selection method is distilled from the `materials-selection`
skill (`majiayu000/claude-skill-registry`, after Ashby's standard method); the design-for-disassembly
heuristics are the transferable principle from a `material-selection` skill
(`Amanbh997/Skills-Architects`, building-specific data dropped). The `ind` persona framing and its
private specialist-routing (`$sd`/`$uxd`/…) are dropped and replaced with bodesign's real downstream
routing. All are published methods/rules of thumb, not decided values.

## The reduction lens — Rams/Ive principles as *constraints*

Treat these as constraints to test a decision against, not adjectives to claim:

- **Usefulness · honesty · longevity · thoroughness · reduction** (Rams), plus **care, material
  honesty, systems thinking, physical-digital harmony** (Ive) — applied *carefully*, as a check.
- **Remove elements until function breaks, then stop.** Reduction is the default; every surviving
  element must earn its place.
- **Reject** fake materials, decorative complexity, and features added only for parity with another
  product.

> **This *is* the bodesign honesty model, applied to form.** Rams' "honesty" and Ive's "material
> honesty" are the same instinct as `../../../references/honesty-model.md`: don't fake a finish,
> don't dress a draft as finished, don't assert what you haven't decided. A removal-audit verdict
> that needs a human to confirm is an **open decision**, not a decided form — exactly as honesty
> rule 6 (exclude rather than guess) demands.

## Workflow — and where each step lands in a C01 artifact

1. **Name the essential job + necessary functions** *before* exploring form. → seeds
   `Design_Direction.md` **Form Direction** (`Form archetype`, `Primary face`) and the one-sentence
   `Visual tone` that ties tone to function. If the essential job isn't clear from C00, that's an
   open decision, not a guess.
2. **Removal audit** — for every exposed component / visible element ask **"what breaks if we remove
   this?"** → drives the **Visible Component Intent** table. A component that survives the audit
   gets a *defensible reason to exist*; one that doesn't becomes an `Open ID Decision` ("is this
   needed, or parity-only?"), never silently kept or cut.
3. **Material / tactile / sonic / first-use decisions** where relevant; reject fake materials. →
   feeds `CMF/CMF_Direction.md` (each finish justified by the **Environment rationale**, not taste).
   Anything not given by C00/user stays the honest `draft/missing` value at status `drafted`.
4. **Map physical ↔ digital reinforcement** — how the enclosure surfaces, LEDs, buttons, buzzer and
   any app reinforce one product story. → sharpens `Display UIUX/UIUX_Requirements.md` (the status
   model) so the physical feedback surface and the firmware state agree.
5. **Longevity · repair · lifecycle · family-system** implications (serviceability, wear, what a
   product line shares). → an explicit lens for `Design_Direction.md` and the CMF wear/thermal
   checks; under-weighted otherwise, genuinely additive here. **Design-for-disassembly heuristics**
   to carry as direction (final call is ME's at C02): prefer **screwed/bolted/snap over glued or
   welded** joints (demountable = repairable + recyclable); keep **fixings accessible** in the
   assembled state; favour **modular/layered** construction so a worn part swaps without scrapping
   the whole; **mark materials** for end-of-life sorting; standard fasteners over proprietary. These
   are *direction* for C02's `Assembly_Notes.md`, not a fixed joint spec.
6. **Route** the survivors and the open questions to bodesign's real downstream, not a persona:
   form/openings/surfaces/mounting → **C02 (ME)**; visible electrical interfaces + antenna → **C03
   (EE)**; preferred faces + keepouts → **C04 (Layout)**; status state labels + interaction →
   **C05 (FW)**; and every unresolved form/CMF/UI call → the **human ID designer** via
   `Handoff_to_ID_Designer.md`.

## Mapping at a glance

| Lens step | C01 artifact it sharpens |
|---|---|
| Essential job before form | `Design_Direction.md` — Form Direction, Visual tone |
| Removal audit ("what breaks if removed?") | Visible Component Intent table + Open ID Decisions |
| Material honesty / reject fake finish | `CMF_Direction.md` — Direction + Environment rationale |
| Physical ↔ digital reinforcement | `UIUX_Requirements.md` — status model |
| Longevity / repair / lifecycle | Design Direction + CMF wear/thermal checks |
| Route survivors + open questions | `Interface_Constraints.json` + `Handoff_to_ID_Designer.md` |

## Material selection for CMF — the Ashby lens (the "M")

CMF's *colour* and *finish* are taste calls for the ID designer; the *material* underneath has a
**defensible, auditable** method. Use it to give `CMF_Direction.md` a rationale that survives
challenge, not a preference. C01 produces material **direction with its reasoning**; the grade-level
pick, supplier samples, and sign-off stay human/ID (honesty rules 1, 4).

**Ashby's five questions** (ask them of the enclosure / any structural part):

1. **Function** — what does it do? (enclosure = contain + protect + present; a clip = spring; a
   window = transmit light/RF.)
2. **Objective** — what to minimise/maximise? (cost, mass, environmental impact — usually cost for a
   consumer enclosure.)
3. **Constraints** — the hard musts: service temperature, impact/drop, UV/outdoor, flammability
   (UL 94), chemical/sweat/skin contact, **RF-transparency** in antenna zones, food/child-contact
   bans (no lead/cadmium/hex-chromium), and **processability** (must injection-mould / 3D-print).
4. **Free variable** — usually the material itself (fix the wall/shape class *first* — don't
   co-optimise geometry and material, it halves clarity).
5. **Performance index** — the property group to maximise. *Derived, not chosen.*

**For enclosures the win is usually constraint-filtering, not an index.** A box isn't
stiffness- or mass-limited, so the real work is step 3: discard anything that fails temperature, UV,
flammability, skin-contact, RF-transparency, or processability — that cuts thousands of candidates to
a handful (typically the ABS / PC / PC-ABS / PA / PETG / PP family already in `../GUIDE.md` § Material
quick-reference). When a part *is* mechanically limited (a thin clip, a structural rib, a
press-spring), the indices below apply.

| Function + objective | Index (maximise) |
|---|---|
| Stiff, light tie / beam / panel | `E/ρ` · `E^½/ρ` · `E^⅓/ρ` |
| Strong, light tie / beam | `σ_f/ρ` · `σ_f^⅔/ρ` |
| Minimum-cost stiff beam | `E^½/(ρ·C_m)` |
| Spring / snap-fit energy density | `σ_f²/E` |
| Thermal-shock resistance | `σ_f/(E·α)` |

*(C_m = cost/kg, α = thermal expansion. The snap-fit index `σ_f²/E` is the useful one for C02's
cantilever clips.)*

**Multi-objective** (cost vs mass vs eco): plot candidates and keep the **Pareto front** — anything
beaten on *both* axes is eliminated without debate; the final pick sits on the front. **Eco is a
material decision masquerading as a process one**: recycled aluminium ≈ 5 % of primary energy,
EAF-scrap steel ≈ 30 % of primary — note recycled-content intent in the CMF direction where it's a
soft objective.

**Method failure modes to avoid** (they map onto bodesign honesty): don't decide on a 2 % property
difference (inside handbook noise → that's a *test*, not a chart call → keep it an open decision);
don't over-constrain early (musts vs wants — push wants into the objective); once a *class* wins,
continue at **grade level** with real data, which is the human/ID + vendor's job, not C01's.

## Honesty guard for this lens

The reduction lens generates **rationale and open questions**, never a decided form or CMF. If a
"remove this?" verdict, a material choice, or a proportion would be the ID designer's call, it stays
in `Open ID Decisions` / `open_decisions[]` at `drafted` with its reason — the lens makes the
*argument* sharper, it does not promote the *status*. Litmus test unchanged (`../GUIDE.md` §
"Honesty notes"): *"If the ID designer opened this tomorrow, would they find this was actually their
decision, or mine?"*
