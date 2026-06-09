# C02 geometry authoring & inspection loop

**What this is.** The *method* for getting `Enclosure.scad` (and the build123d STEP) geometrically
**correct** — distinct from `mechanical-design-advisory.md`, which is the *numbers* (DFM/tolerance/
material). This is "how to author and verify the shape", and it is the geometry-authoring corollary
of `../../../references/honesty-model.md`: **don't claim a fit-critical model is right until evidence
says so.**

**Provenance.** Distilled (method only) from the `3d-cad-skill` (`aresbit/MateBot`) — chosen because
it runs the *same stack as C02* (OpenSCAD + build123d, STL/STEP/3MF) and shares bodesign's
inspect-don't-assert discipline.

## Core rule

**Do not trust mental visualisation of 3D geometry.** Write the parametric code, produce *evidence*,
inspect it, then revise. A model that "compiles" is not a model that is correct.

## The loop

1. Produce the **smallest correct parametric skeleton** — top-level parameters first; separate base
   body / cutouts / mounts; delay fillets, chamfers, text, cosmetics until the base is right.
2. **Generate evidence** (see below).
3. Compare evidence against the constraints (the `Mechanical_Constraints.json` envelope, openings,
   keepouts).
4. **Name the specific defect** — not "looks off" but "USB-C cutout is 1.2 mm too high".
5. Apply the **smallest plausible fix** — change one parameter/operation, re-inspect, compare to the
   previous result. Avoid broad rewrites unless the part architecture is clearly wrong.
6. Repeat until remaining uncertainty is **minor and explicit** (recorded as an assumption/pending).

## Generating evidence — including when there is no renderer

`openscad` is frequently absent on the authoring machine (see `../GUIDE.md` environment-honesty box).
You can still inspect — the point is *deterministic evidence*, not necessarily a picture:

- **If render/screenshot is available:** check silhouette + proportions from multiple angles after
  every meaningful change.
- **If not (headless):** use **explicit dimension calculations** (compute and print
  `case_width/height/depth` and every opening's edge position), **bounding-box checks** (does the
  computed envelope match the constraint envelope?), **section reasoning** (walk the box-in-box
  `difference()` and confirm wall = outer − inner on each axis), and **orthographic/projection**
  output where the toolchain allows. The `.scad` should `echo` its computed sizes so the numbers are
  inspectable without a render.

## What to inspect

| Layer | Check |
|---|---|
| **Global form** | proportions, symmetry/centering, major-feature orientation, silhouette matches intent |
| **Functional geometry** | hole Ø + placement, wall thickness, slot widths + insertion paths, lid/fastener/mating clearances, contact/support surfaces |
| **Fabrication risk** | thin/fragile members, unsupported bridges + overhangs (> 45°), internal voids that can't be cleaned/printed, sharp internal corners needing a radius |

(The fabrication-risk numbers — overhang 45°, bridge 15/10 mm, min wall 1.2 mm — live in
`mechanical-design-advisory.md` § FDM/SLA.)

## Diagnosing problems

- Whole part looks wrong → inspect **coordinate-system choices + base dimensions** first.
- One feature drifts → inspect its **local transforms + subtraction volumes**.
- Symmetry off → replace duplicated magic numbers with **mirrored parameters**.
- Exported mesh/STEP fails → **simplify booleans**, check for coplanar or zero-thickness geometry
  (extend cuts 0.1 mm past each surface — see advisory note).
- Part hard to revise → **refactor repeated dimensions into named parameters** before continuing.

## Modeling style (reinforces "all variables from constraints, no magic numbers")

- Named parameter for **every** critical dimension; group related ops into small modules.
- Keep `difference()`/`union()`/`intersection()` operands readable and spatially local; don't bury
  key dimensions in nested transforms.
- When debugging, **isolate one body or subtraction volume at a time**.
- build123d: separate sketch from 3D feature; name workplanes; fillets/chamfers are late-stage.
- Prefer deterministic geometry over clever compact code.

## Reporting (the honesty closer)

When reporting a geometry pass, state three things concretely: **what changed**, **what evidence
verified it**, **what remains uncertain**. And the hard rule — the C02 corollary of honesty rule 5:

> **Do not claim a fit-critical model is correct unless it has been verified by render evidence,
> explicit dimension checks, or user-provided measurements.**

Unverified fit stays an explicit assumption in `Mechanical_Assumptions.md`, never a silent "done".
