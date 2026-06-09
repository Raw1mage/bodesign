# C01 ID — industrial-design direction & interface constraints

## Purpose & scope

C01 turns the product vision from C00 into **design direction** and **measurable interface
constraints** that the rest of the lifecycle can build on. Concretely it owns four decisions
and one bridge:

1. **Design Direction** — form archetype, usage posture, primary user-facing surface, visual tone.
2. **CMF Direction** — colour / material / finish intent + the environment rationale behind it.
3. **Display / UI-UX Requirements** — the user-visible *status model* (display, LED, button,
   buzzer, app), plus the minimum set of product states the UI must resolve.
4. **Interface_Constraints.json** — the machine-readable bridge that turns ID intent into
   constraints ME (C02), EE (C03), Layout (C04) and FW/UX (C05) can consume.
5. **Handoff_to_ID_Designer.md** — the explicit boundary doc that hands the package to a human.

**What C01 does *not* own — the honest boundary.** bodesign authors **direction and
constraints, not final art**. C01 does not produce final `.ai`/`.svg` source artwork, an
approved CMF sample board, final pixel UI mockups, CAD, renders, or any sign-off. Those belong
to a **human ID designer** and the product owner. Every C01 artifact is `draft`/`drafted` until
that human approves it, and the handoff doc states this plainly. Treat C01 as *"the smallest
honest substitute for a designer's brief"* — enough to unblock C02–C05, not a pretence of
finished design. This boundary is non-negotiable; see *Honesty notes* below.

## Required deliverables — Definition of Done

Produce **all five** core artifacts in this stage before you report C01 done or hand off (see SKILL.md
§ "Definition of Done"). Each exists on disk **or** carries an explicit `draft`/`blocked` status with a
reason — silent absence is not allowed. (C01 artifacts stay `draft` until a human ID designer approves;
that is an honest status, not a missing deliverable.)

| # | Required artifact | File |
|---|---|---|
| 1 | Design direction | `Design_Direction.md` |
| 2 | CMF direction | `CMF_Direction.md` (or `CMF/CMF_Direction.md`) |
| 3 | Display UI/UX requirements (status model) | `UIUX_Requirements.md` (or `Display UIUX/UIUX_Requirements.md`) |
| 4 | Interface constraints (machine bridge) | `Interface_Constraints.json` |
| 5 | ID-designer handoff | `Handoff_to_ID_Designer.md` |

**Self-verify:** run `bodesign_c01_readiness` (`folder`) and pass the step-7 self-check before
declaring the gate. Model: `thesmart_products/rockbox/c01-id/`.

## Inputs (from upstream C00)

You consume the C00 PRD package (`stages/c00-prd/GUIDE.md` produces it). Read these specifically:

- **Product vision & overview** — what the product is, who the target user is, the one-line
  pitch. (PRD §"公司願景/商業策略" and §"專案總覽".) This sets the *visual tone* and primary face.
- **ID / mechanical requirements** — the PRD's ID/機構 section: enclosure material intent,
  rough dimensions (marked "final per ID"), mounting/usage posture, environment (IP rating, drop,
  temperature), and the list of **user-facing features** (camera opening, status LED, button,
  USB-C / connector edge-exit, antenna keepout zone, privacy shutter, etc.). This is the seed for
  your exposed-component list.
- **Electrical requirements (visible interfaces only)** — from the EE section you extract just the
  *user-visible* electrical interfaces: connectors, display, LEDs, buttons, sensors with a path to
  the outside (camera/MIC/antenna). You do **not** design the electronics here.
- **C00 handoff / readiness** — check the C00 handoff report's downstream gate (`C01/C02`). If C00
  flagged `C01/C02: blocked` on a named field (e.g. assumptions/constraints unresolved), record
  that as a `pending` input rather than inventing the missing answer.

If an input you need is absent from the PRD, that is a **question for the user or the ID designer**
— capture it as an open decision, do not back-fill a plausible value (honesty rule 6).

## SOP

This procedure is self-contained: an agent with only the C00 package and this guide can execute it.
Companion skills (named in *Tools*) are accelerators, not prerequisites.

### 1. Ingest & summarise C00

Extract the C00 source summary into a tight paragraph: product, derivation/reference if any,
core function, connectivity, enclosure intent, dimensions, mounting, environment, and the bullet
list of electrical building blocks. This paragraph is reused verbatim in `Design_Direction.md`
(*C00 Source Summary*) and `Handoff_to_ID_Designer.md` (*From C00*) — write it once, well. Keep
the PRD's original language (the real examples are bilingual/Chinese — match the source).

### 2. Author the Design Direction

Create `CMF/`, `Display UIUX/`, and an `Ai file/` (or flat — match the example you are extending)
and write `Design_Direction.md` with:

- **Status block** — `State: AI draft, not final industrial design.`; `Owner:` the named ID
  team/designer or "待指派" if unassigned; `Source: C00-derived visual/human-interface intent.`
- **C00 Source Summary** — the paragraph from step 1.
- **Form Direction** — `Form archetype` (e.g. "rounded-rectangle guard module, wall/desk dual
  mount"), `Usage posture`, `Primary face` (the main user-facing surface and what lives on it),
  `Visual tone` (one defensible sentence tying tone to function — e.g. "matte anti-glare so the
  finish never reflects into the camera").
- **Visible Component Intent** — a table of every exposed component with `Placement Preference`
  and `Decision Status`. Until a human decides placement, the honest value is
  `draft/missing — C01 must ask user or ID designer` at status `drafted`. Do **not** assert a
  specific face/coordinate you have not been given. Run the **removal audit** from
  `references/design-direction-method.md` here — for each component ask "what breaks if we remove
  this?"; a survivor earns a defensible reason, a non-survivor becomes an Open ID Decision
  ("needed, or parity-only?"), never silently kept or cut.
- **Open ID Decisions** — list what genuinely needs human/ID approval (proportions, brand
  treatment, logo/label zones, visual hierarchy). **Ergonomics / human factors** (grip, one-handed
  use, control reach, viewing angle, handedness) belong here too — these are **designer/user
  preference, not something to pre-load or assume an anthropometric value for**. If C00 or the user
  didn't specify, record it as an Open ID Decision and **ask** (honesty rule 6); do not invent a
  hand size or reach envelope to make the direction look complete.

### 3. Author the CMF Direction (`CMF/CMF_Direction.md`)

- **Status** — `State: AI draft, not CMF sample approval.` + owner.
- **Direction** — one CMF-intent sentence (material, finish, key optical/RF surfaces) plus an
  **Environment rationale** that *justifies* it from the PRD environment (IP rating, temp range,
  deployment). The rationale is what makes this a defensible draft rather than a taste assertion.
  For the *material* half, use the Ashby constraint-filter method in
  `references/design-direction-method.md` § "Material selection for CMF" — filter on temp / UV /
  flammability / skin-contact / RF-transparency / processability to a defensible family, and leave
  the grade-level pick + samples to the human ID/vendor.
- **Candidate Routes** — offer 2–3 labelled routes so the human chooses, don't pre-decide:
  e.g. *Clean utility* (neutral/low-gloss, broad acceptance) · *Industrial durable*
  (darker, textured, protected openings) · *Brand-forward* (controlled accent + status zone,
  needs brand approval).
- **Required Human / ID Checks** — material feasibility, supplier samples, cost, wear, thermal
  effect, brand fit. End: "Any route selected here remains `drafted` until ID/owner approval."

### 4. Author the Display / UI-UX Requirements (`Display UIUX/UIUX_Requirements.md`)

This is the **status model** — the contract the UI/firmware must satisfy.

- **Status** block as above.
- **User-Visible Status Model** — describe how each product mode is shown to the user across the
  available surfaces (display content, LED colour/pattern, button gestures, buzzer, app). Be
  concrete and behavioural: "RGB ring: idle = slow-breathing white, armed = solid blue, alarm =
  fast-flash red…; multi-function button: short = arm/disarm, 3 s = pair, 10 s = factory reset."
  Where accessibility matters, state it (e.g. colour-blind-safe via shape+rhythm, not colour alone).
- **Minimum States To Resolve** — a table with columns `State | User Feedback Surface |
  C05 Firmware Dependency | Decision Status`. Always cover at least: *power-on/booting*,
  *normal operation*, *error/fault* (needs an error-code vocabulary), *low-battery/charging*,
  *connectivity/pairing*. The `C05 Firmware Dependency` column is what C05 consumes — name the
  firmware event/state each surface binds to. Add product-specific modes (arm/disarm, OTA, etc.).
- **No-Display Rule** — if the product has no screen, the status model still maps to
  LED/button/buzzer/app behaviour and **must not be silently omitted**. State this explicitly so a
  screenless product still gets an honest UX contract.

To turn the status model into a verifiable state diagram, hand it to **drawmiat** (Grafcet/IEC
60848 or a C4-style state view). C05 will pick this up; producing it here is optional but valued.

### 5. Emit `Interface_Constraints.json` — the bridge

This is the heart of the downstream value. Use schema `bodesign.c01.interface_constraints.v1`
(an asset template lives in `assets/Interface_Constraints.template.json`). Structure:

- top-level: `schema`, `state: "drafted"`, `product_name`, `source`.
- `exposed_components[]` — one object per user-visible component, each with:
  - `name`, `placement_preference` (honest `draft/missing…` until decided), `decision_status`,
    `owner` (e.g. "C00 user + ID designer"),
  - `downstream_targets` — which stages must honour it (e.g. camera → `["C02","C04"]`;
    LED → `["C02","C04","C05"]`; USB-C → `["C02","C03","C04"]`; antenna → `["C03","C04"]`),
  - `risk_notes` — the *measurable* constraint ME/EE/Layout must respect, phrased as a concrete
    failure mode + mitigation. This is what makes the JSON useful: not "looks nice" but
    "camera FOV can be obstructed by enclosure geometry → opening + clearance needed",
    "antenna metal/finish can block RF → keepout + non-metal window required",
    "status LED can be invisible → light pipe / visible face needed".
- `downstream_targets{}` — a per-stage rollup of *what that stage consumes* (C02: form archetype,
  openings, user-facing surfaces, mounting; C03: visible electrical interfaces, antenna
  constraints; C04: preferred faces, keepouts, visibility/RF/acoustic constraints; C05: status
  state labels, button/LED/display/app behaviour).
- `open_decisions[]` — the unresolved items requiring human confirmation.

Every component's `decision_status` is `drafted` and every placement is the honest `draft/missing`
string unless C00 or the user gave you a real placement. The JSON's own `state` is `drafted`.

### 6. Write the ID-designer handoff (`Handoff_to_ID_Designer.md`)

This doc makes the human boundary explicit:

- **Package Status** — "first-pass C01 package; suitable for ID continuation and downstream
  constraint discussion; **not** final `.ai`, CMF board, Display UI/UX, CAD, or sign-off."
- **Feasibility tier (declare it here — the honest half of "give C00")** — run
  `classify_product_feasibility(...)` on the C00 estimate
  (`../../references/feasibility-triage.md`) and state the result plainly: *"Assessed **Tier N** —
  bodesign will deliver `<C04 target>` for this product."* Tier 1–2 → an autonomous C00→C04 path to a
  (near-)fab-ready board; Tier 3 (HDI/phone-class) → concept+constraints with the C04 routing handed
  to pro-EDA. If this tier clashes with what the user expects, that's a reconciliation routed to
  C00/C01 — surface it now, not at the C04 wall. C03 re-runs the triage on the firm component set.
- **From C00** — the source paragraph from step 1.
- **AI Drafted** — bullet the form / posture / primary-face / CMF / UI-status directions you wrote.
- **Human / ID Must Decide** — final proportions & style; CMF route, samples, finish, brand fit;
  exact visible-component treatment & opening placement; whether any conflict with C02–C05 is
  accepted as risk.
- **Downstream Notes** — restate which stage consumes which constraint (mirrors the JSON rollup).

### 7. Self-check before declaring the gate

- Every exposed component in the PRD's user-facing list appears in both the Design Direction table
  and `Interface_Constraints.json`.
- No placement/coordinate/colour is asserted as decided unless C00 or the user gave it.
- Every UI state in the status table names its C05 firmware dependency.
- The JSON validates against the v1 schema and parses (`python3 -m json.tool` on it).
- The handoff doc names the human boundary and lists open decisions.

## Deliverables

Source-of-truth is **markdown + one JSON**; nothing here is "generated/binary". Model on the real
examples (`openmv/C01-ID/`, `rockbox/c01-id/`):

| Artifact | Path (relative to the stage dir) | Role |
|---|---|---|
| Design Direction | `Design_Direction.md` (real example nests it under `Ai file/`) | form / posture / primary face / visual tone / visible-component table |
| CMF Direction | `CMF/CMF_Direction.md` | material/finish intent + environment rationale + candidate routes |
| Display UI/UX | `Display UIUX/UIUX_Requirements.md` | user-visible status model + minimum-states table + no-display rule |
| Interface constraints | `Interface_Constraints.json` | machine-readable bridge to C02/C03/C04/C05 |
| ID-designer handoff | `Handoff_to_ID_Designer.md` | explicit human-boundary + open decisions |

Optional accelerated artifacts (do not fake; mark `draft` if produced): a UX **state diagram**
(drawmiat), low-fidelity **UI mockups** (frontend-design / canvas-design), a **CMF / concept render**
(an ID-native tool such as Vizcom, sketch→render), or a **handoff deck** (pptx via docxmcp). These
supplement — they never replace the five core docs above. **A photoreal render carries extra risk:**
it *looks* decided when the CMF/form is still `drafted`, so label it loudly as an illustrative
concept, keep it routed to *Open ID Decisions*, and never let it promote a status. Ignore any tool's
"must look stunning / avoid boring shapes" mandate — C01 authors defensible *direction*, not chosen art.

A template for the JSON lives in `assets/Interface_Constraints.template.json`.

## Gate / done-criteria

C01 is **genuinely done** (vs still draft) only when:

- All five core artifacts exist and the self-check (step 7) passes.
- `Interface_Constraints.json` validates against `bodesign.c01.interface_constraints.v1` and every
  exposed component carries `downstream_targets` + a concrete `risk_notes` constraint.
- Every `draft`/`drafted`/`pending` status carries a *reason* (an open decision or a named missing
  input), not a bare label.

C01 is **never** "approved/final" from inside bodesign. Final ID, CMF approval, UI sign-off, and
acceptance of any C02–C05 conflict are **human gates** owned by the ID designer / product owner.
The package can be *complete-as-a-draft-brief* and still correctly carry `State: AI draft` — those
are not in tension. Do not upgrade a status to look finished; if the human hasn't signed, it's draft.

## Honesty notes for this stage

Apply `../../references/honesty-model.md` here as follows:

- **Direction, not art (rule 1 & 6).** C01 authors intent and constraints. Where the PRD didn't
  specify a placement, colour, or proportion, the honest value is the explicit
  `draft/missing — C01 must ask user or ID designer` string at status `drafted` — **never** an
  invented coordinate or hex value to make the doc look complete.
- **Provenance (rule 2).** The form/CMF/visible-component intent traces to the C00 PRD; say so
  (the Source Summary + "From C00" blocks are that trace). CMF *Environment rationale* ties each
  finish choice back to a PRD environment requirement so it's defensible, not taste.
- **Status with a reason (rule 3).** Every artifact opens with a `State:` line; every open item
  lands in *Open ID Decisions* / `open_decisions[]` with the reason it's open.
- **Human gate stays human (rule 4-analogue).** ID/CMF/UI sign-off is the C01 equivalent of an
  external gate — bodesign records the *direction* and *who must approve*, and never marks it
  approved itself. The handoff doc is where this boundary is made explicit and visible.
- **Litmus test.** Before writing any placement/finish/state as decided, ask: *"If the ID designer
  opened this tomorrow, would they find this was actually their decision, or mine?"* If it was the
  human's to make, mark it `drafted` and route it to *Human / ID Must Decide*.

## Handoff to C02 (ME), and to C03 / C04 / C05

You export, primarily, **`Interface_Constraints.json`** — the single machine-readable contract —
plus the four direction docs for human context. Downstream consumption:

- **C02 (ME)** — `../c02-me/GUIDE.md` consumes: form archetype, openings, primary/user-facing
  surfaces, mounting & handling assumptions. These seed the enclosure constraints/assumptions doc.
- **C03 (EE)** — `../c03-ee/GUIDE.md` consumes: the set of *visible electrical interfaces*
  (connector/display/button/LED/sensor presence) and antenna constraints, as the interface side of
  the electrical definition.
- **C04 (Layout)** — `../c04-layout/GUIDE.md` consumes: preferred component faces, placement
  keepouts, and visibility / RF / acoustic constraints (from each component's `risk_notes`).
- **C05 (FW)** — `../c05-fw/GUIDE.md` consumes: the status **state labels** and
  button/LED/display/app interaction behaviour from the UI/UX status model → firmware states.

Carry every `drafted` status across the handoff unchanged — a downstream stage may *accept a
conflict as risk*, but only a human can, and that acceptance is recorded back in the handoff doc's
*Human / ID Must Decide* list, not silently resolved.

## Tools & companion skills

- **`references/design-direction-method.md`** — the reduction lens (Rams/Ive as constraints) +
  essential-function framing + the removal audit, mapped onto each C01 artifact. A *method scaffold*
  for reasoning toward Design Direction / CMF / Visible-Component Intent — it sharpens the argument,
  it never promotes a `drafted` status to decided. Use it in SOP steps 2–4.
- **drawmiat** (`mcp__drawmiat__validate_diagram` → `generate_diagram`) — turn the UI/UX status
  model into a Grafcet/IEC-60848 state diagram or C4 view for C05. Validate before generate.
- **frontend-design** / **canvas-design** — low-fidelity UI mockups or a CMF mood board. These are
  *illustrative drafts*, never final art; label them `draft`.
- **Vizcom** (or any sketch→render ID tool) — a CMF / concept render for human discussion, more
  ID-native than the above for *form/material* feel. SaaS-backed (no local capability — it's prompt
  craft over an external canvas); the one transferable nugget is material/lighting prompt precision
  ("anodized aluminium", "frosted glass", explicit lighting) to dodge the plastic-y AI look. Subject
  to the photoreal-render caveat above: illustrative draft only, never a decided CMF, drop its
  "must be stunning" mandate.
- **docxmcp** MCP (`docxmcp_pptx_*`) / **pptx** / **docx** / **pdf** — package the handoff as a
  deck or doc for the ID designer / product owner when a human-facing artifact is wanted.
- **foundation-persona** — if the target user/visual tone is thin in C00, generate an
  evidence-calibrated persona to ground the visual-tone decision (mark assumptions).
- No KiCad/kidoc engine work happens at C01 — those engines (`../../engines/kicad`,
  `../../engines/kidoc`) enter at C03+. C01 stays upstream of any board.
