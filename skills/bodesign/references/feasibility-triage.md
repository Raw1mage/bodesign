# Feasibility triage — how far can bodesign take *this* product?

The promise is "give C00, get C01–C04". The honest qualifier is **how far** C04 goes, and that is
decided almost entirely by whether KiCad + the bodesign MCP can actually **route** the board. This
file is the rubric that reads a product's complexity **up front** (C00→C01, refined at C03) and sets
the **C04 completion target** — so the user knows from the start what they will get, instead of
discovering the wall at C04.

Run it as code: `classify_product_feasibility(...)` in `bodesign_workflow_core.feasibility` returns the
tier, the target, and the **drivers** (which signals forced it). The tier is set by the **hardest
driver** — one HDI-class constraint pulls the whole product to Tier 3 no matter how simple the rest is.

## The signals (from C00 estimate, then firm from the C03 component set)

`layer_count` · `finest_bga_pitch_mm` · `hdi_required` · `high_speed_nets` (DDR/USB3/MIPI/SerDes) ·
`rf` · `component_count` + `board_area_mm2` (density). Unknown signals don't push the tier; the verdict
carries `confidence: estimate` (C00) or `firm` (C03).

## The tiers — what bodesign actually delivers at C04

| Tier | Triggers (worst wins) | C04 delivery |
|---|---|---|
| **1 · fab-ready** | ≤4 layer, ≥0.65 mm pitch, no/low high-speed, no RF | **A gated, DRC/SI-clean, fab-ready board package** — KiCad + MCP route + gate. |
| **2 · routed-draft** | 0.5 mm pitch · 6–7 layer · 1–15 controlled-Z nets · RF · very dense | MCP routes most; **critical nets need human/pro SI sign-off** before fab. |
| **3 · concept+constraints → pro-EDA** | HDI/any-layer · ≤0.4 mm pitch · ≥8 layer · ≥16 high-speed nets | **Architecture + stackup + floorplan intent + full SI constraint set**; HDI/DDR/RF routing handed to Allegro/Xpedition + human SI + HDI fab. |

The realistic sweet spot for fully-autonomous C00→C04 is **Tier 1–2**. Tier 3 (phone-class) is
honestly a concept+constraints deliverable — bodesign does the design thinking, the routing wall is
named and handed off cleanly, not faked.

## Declare it up front — the honest half of "give C00"

Run the triage at **C00→C01** on the available estimate and **state the tier and C04 target in the
C01 handoff / the package README**: *"This is assessed Tier N — bodesign will deliver `<target>`."*
Re-run it at **C03** once the real component set (and its finest BGA pitch / high-speed count) is
known; the tier can rise (confidence `firm`). A tier that rises at C03 is itself a signal to re-set
the expectation, not a surprise to bury.

## When the tier clashes with what the user wants — it's a reconciliation

If the user expects a **fab-ready** board (Tier 1) but the product classifies **Tier 3**, that gap is
a cross-stage tension → **emit a reconciliation record** (`cross-stage-reconciliation.md`): the
`finding` is the tier mismatch, the `options` are the levers that *lower* the tier (simplify the
feature set / drop the high-speed bus / use a module/SoM that hides the HDI inside a pre-routed part /
accept Tier-3 concept delivery / bring pro-EDA), routed to **C00/C01** (`affected_downstream_layers`)
to decide with the user. bodesign never quietly downgrades the delivery or pretends it can route a
phone — it surfaces the choice early, while it is cheap.

## Why this is the binding constraint, not C03 method

The C03 design methods (`pinout-to-circuit-method.md`, `ee-design-advisory.md`) scale to phone-class
*design*. What does not scale is C04 *routing* on KiCad + the MCP. So the tier is a statement about
**C04 routability**, and the highest-leverage way to raise the bodesign-completion fraction for hard
products is a clean C04→pro-EDA handoff (the SI constraint set as a standard export), not more C03
knowledge.
