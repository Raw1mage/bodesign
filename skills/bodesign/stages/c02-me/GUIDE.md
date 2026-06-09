# C02 ME — mechanical / enclosure constraints, parametric model & draft STEP

## Purpose & scope

C02 turns the upstream form-factor and electrical/interface facts into a **mechanical
constraint package** and a **draft enclosure model** that an ME / fab vendor can pick up and
refine. Concretely it owns:

1. **`Mechanical_Constraints.json`** — the machine-readable enclosure contract: component-height
   envelope, connector openings, heat sources, antenna keepouts, battery envelope, ESD/EMC notes,
   provisional board outline + mounting holes, and an explicit `constraint_status` /
   `approval_status` ledger.
2. **`Mechanical_Assumptions.md`** — the human-readable scope, prototype intent, engineering-pending
   list, and the non-approval statement.
3. **`Enclosure.scad`** — a *parametric* OpenSCAD enclosure draft (source of truth for the shape).
4. **A draft STEP** (`Enclosure.step`) — a real ISO-10303 solid for **soft-tooling (EVT/DVT)**,
   produced by build123d/OCP **only if that toolchain is present** (see the environment-honesty box).
5. **Handoff notes** — `Assembly_Notes.md`, `Print_Settings.md`, `STEP_Draft_Handoff.md`,
   `SketchUp_Import_Guide.md`, `Vendor_Handoff.md`.

**What C02 does *not* own — the honest boundary.** bodesign authors **mechanical constraints and a
prototype model, not a manufacturable enclosure**. C02 does **not** produce: production
injection-mould tooling (downstream/external), DFM sign-off, tolerance/draft/undercut approval,
waterproofing/strength/thermal validation, a final vendor-refined STEP, or ME approval. The board
outline it carries is **provisional** — the *authoritative* outline is owned by C04 Layout / ME
(C02 hands a confirmation request *back* to C04). Every C02 artifact is `draft` until a named ME /
vendor signs off; `me_approved` stays `false`.

> **Environment honesty — read before you claim an export.** `openscad`, `build123d`, `OCP`, and
> `cadquery` are frequently **absent** on the authoring machine. Verify first:
> `which openscad` and `python3 -c "import build123d"`. The `.scad` is authored as **source** either
> way. A rendered STL needs `openscad`; a STEP needs build123d/OCP. **If the toolchain is missing,
> ship the `.scad`/emitter as source, mark STL/STEP `not-run` with that reason, and never write a
> `.step`/`.stl` by hand or claim `step_exported: true`.** When build123d *is* present, run
> `assets/emit_step.py` to produce a genuine solid — then it's an honest `draft_unapproved` STEP.

## Required deliverables — Definition of Done

Produce **all** of these before you report C02 done or hand off (see SKILL.md § "Definition of
Done"). Each exists on disk **or** carries an explicit `draft`/`pending`/`not-run` status with a
reason + owner — silent absence is not allowed. (`me_approved` stays `false`; that is honest, not a
gap.)

| # | Required artifact | File | Notes |
|---|---|---|---|
| 1 | Mechanical constraints (machine contract) | `Mechanical_Constraints.json` | must parse |
| 2 | Mechanical assumptions | `Mechanical_Assumptions.md` | scope + non-approval statement |
| 3 | Parametric enclosure model (source) | `Enclosure.scad` | always author as source |
| 4 | Enclosure export | `Enclosure.step` / `.stl` / `enclosure_3d/*.glb` | **only if toolchain present**, else `not-run` with reason — never hand-write |
| 5 | Assembly notes | `Assembly_Notes.md` | |
| 6 | Print settings | `Print_Settings.md` | |
| 7 | Vendor handoff | `Vendor_Handoff.md` | |
| 8 | SketchUp import guide | `SketchUp_Import_Guide.md` | |

**Self-verify:** run `bodesign_c02_readiness` (`constraints`/`folder`) and pass the step-8 self-check;
the STEP/STL status in the package must match what actually ran. Model:
`thesmart_products/rockbox/c02-me/`.

## Inputs (from upstream)

C02 consumes three things; rely on the *explicit* values in each and treat absences as pending:

- **C00 form-factor** — enclosure envelope (rough W×H×D), material intent, mounting/usage posture,
  environment targets (IP, drop, temperature). From `../c00-prd/GUIDE.md`. The provisional board
  outline is back-derived from this envelope (inner = outer − 2·wall − 2·clearance).
- **C01 `Interface_Constraints.json`** — `exposed_components[]` with `placement_preference` and the
  per-component `risk_notes` (e.g. "camera FOV obstructed by geometry → opening + clearance",
  "antenna metal blocks RF → keepout + non-metal window"). Each component routed to `"C02"` becomes a
  **connector opening** and/or an **antenna keepout**. From `../c01-id/GUIDE.md`.
- **C03 `Mechanical_Constraint_Export.json`** — the EE export (real example:
  `openmv/C03-EE/03_output/Mechanical_Constraint_Export.json`). It wraps `{ "status": ..., "constraints": {…} }`
  and supplies the *explicit-only* mechanical facts: `component_heights[]`, `connector_openings[]`,
  `heat_sources[]`, `antenna_keepouts[]`, `battery_envelope`, `esd_emc_notes`, and a `source` block
  stating that board outline / mounting / coordinates are **not** C03's to give. From
  `../c03-ee/GUIDE.md`.

If an input you need is absent (no board outline, no component heights, no environment targets),
that is an **engineering-pending item with a named owner** — record it, do not back-fill a guess
(honesty rule 6). The rockbox example does exactly this: with `component_heights: []` and no board
outline, it keeps four `engineering_pending` entries and emits *no* CAD source.

## SOP

This procedure is self-contained: an agent with the three inputs above and this guide can execute
it. Companion skills (named in *Tools*) are accelerators, not prerequisites.

### 1. Ingest C03 export + C01 + C00 into one constraint set

Start from `assets/Mechanical_Constraints.template.json`. Pull the C03 export's `constraints`
object verbatim (it's already provenance-tagged: each height/heat-source carries `source` and
`status: "explicit"`). Then **layer in** the C00/C01 facts:

- `connector_openings[]` — one per C01 exposed component routed to C02 (camera, USB-C, RJ45,
  microSD, LED, button, display window…). Set `preferred_edge` from C01's `placement_preference`;
  set `status: "explicit_without_final_coordinates"` (you know the opening exists, not *where* — that
  is C04's). `owner: "C03 EE / C04 layout / C02 ME"`.
- `antenna_keepouts[]` — one per RF/antenna component; `notes` must state "non-metal enclosure
  material in this zone" so the CMF/material choice is constrained, not just noted.
- `battery_envelope` — carry C03's chemistry; keep capacity/form as `status: "TBC"` + a flagged
  `provisional` guess (clearly labelled as an assumption, never as decided).
- `esd_emc_notes` — copy C03's port-protection notes and **append**: "FCC Part 15 / CE RED are
  external-lab gates" (honesty rule 4 — never imply you can pass them here).

### 2. Set the provisional board outline + mounting holes (clearly provisional)

If C04 has *not* yet produced an authoritative outline, derive a **provisional** one from the C00
envelope and label it as such:

- `board_outline`: `width_mm`/`height_mm` = inner envelope − 2·wall − 2·clearance;
  `status: "provisional — derived from C00 enclosure envelope; final board outline owned by C04
  layout / ME, not final"`, `source: "C00 enclosure envelope (derived, unapproved)"`.
- `mounting_holes[]`: place at inset corners (e.g. 4 mm inset, Ø2.5 mm). These are **placeholders**
  until C04/ME confirms — if you have no basis at all, leave the array empty and add a
  `engineering_pending` entry (`key: "mounting_holes"`, owner `C04 layout / ME`) instead of inventing
  positions.

The real aiguard example carries `board_outline` (60×40, provisional) + four mounting holes; the
rockbox example carries **none** and lists them as pending — both are honest. Match your situation.

### 3. Build the `constraint_status` + `approval_status` ledgers

- `constraint_status.pending[]` — every missing input as `{ key, status: "engineering_pending",
  owner, reason, blocks: [...] }`. `environment_targets` is almost always pending (it blocks
  `compliance_review` + `vendor_handoff`). Add `board_outline` / `component_heights` /
  `mounting_holes` whenever those are absent (as rockbox does).
- `approval_status` — five booleans: `source_ready`, `viewable_draft_ready`, `printable_draft_ready`,
  `vendor_handoff_ready`, `me_approved`. Set each only by what genuinely exists. `me_approved` is
  **always `false`** inside bodesign (it's a human gate). `printable_draft_ready` stays `false` until
  a real STL exists; `source_ready` becomes `true` once the `.scad`/STEP source is written.

Validate the JSON: `python3 -m json.tool Mechanical_Constraints.json >/dev/null`.

### 4. Write `Mechanical_Assumptions.md`

Mirror the real example's sections: **Scope** (what this package is/isn't), **Project Summary**
(one-paragraph product description from C00), **Prototype Intent** (e.g. "EVT soft-tooling PC/ABS;
FDM/SLA to validate volume + opening fit; production injection moulding deferred to DVT" — use the
five scoping gate questions in `references/mechanical-design-advisory.md` § "Scope it before you
model" to pin process/volume/structural/assembly/compliance, and record any unanswered one as
`engineering_pending` rather than a guess),
**Engineering Pending Items** (each `key` from the ledger with its owner + reason), a
**Non-Approval Statement** ("AI/tool output is not production mechanical approval, DFM approval,
waterproofing/strength approval, or tolerance sign-off"), and an **OpenSCAD/STEP Source Status**
note recording exactly which sources exist and which exports are `not-run` and why.

### 5. Author `Enclosure.scad` (parametric source)

Write a parametric OpenSCAD model whose variables are **all** derived from the constraints (no magic
numbers): `board_width`, `board_height`, `max_component_height`, `wall`, `clearance`,
`lid_clearance`, and computed `case_width/height/depth`. Provide modules: `enclosure_shell()`
(a `difference()` box-in-box), `board_placeholder()`, `mounting_markers()`, and an `opening_notes()`
that emits one `//` comment per connector opening (so the placement intent travels with the model).
End with a computed `// Computed case size preview: W x H x D mm` line. Open the file with a comment
block stating it's a **prototype source only — not ME approval, not STEP, not SKP**, and that all
dimensions come from explicit constraints. (See `openmv/C02-ME/03_output/Enclosure.scad` for the exact shape.)

If `which openscad` succeeds, you *may* render a preview/STL (`openscad -o Enclosure.stl
Enclosure.scad`) and then flip `printable_draft_ready` after recording print assumptions. If it
fails, the `.scad` ships as un-rendered source and STL stays `not-run`.

Author it with the **inspect-don't-visualise loop** in `references/geometry-authoring-loop.md`:
smallest correct skeleton first (delay fillets/cosmetics), generate *evidence* after each change,
fix one defect at a time. When `openscad` is absent you still inspect — via the `.scad`'s `echo`'d
computed sizes, bounding-box vs the constraint envelope, and section reasoning — rather than trusting
the shape in your head. Never report a fit-critical model correct without evidence (honesty rule 5).

### 6. Emit the draft STEP — **only if build123d is present**

Verify `python3 -c "import build123d"`. If it succeeds:

```
python3 assets/emit_step.py Mechanical_Constraints.json Enclosure.step
```

This builds a real ISO-10303 shell solid from the same parametric envelope and prints the computed
case size. Then set `STEP_Draft_Handoff.md` to `step_exported: true`, `draft_unapproved`, naming the
toolchain (build123d / OCP / OpenCASCADE). If build123d is **absent**, the script exits non-zero and
writes nothing — leave `step_exported: false` / `not-run` with the reason "build123d/OCP not
installed on this worker", and say so in `STEP_Draft_Handoff.md`. Never fabricate the `.step`.

> Note on the real example: `openmv/C02-ME/03_output/Enclosure.step` is a genuine OpenCASCADE STEP — it was
> produced on a worker that *had* build123d. The fact that this machine currently lacks it does not
> retroactively make that file fake; it means *you* cannot re-export here without the toolchain, and
> must say so rather than overwrite/claim.

### 7. Write the handoff notes (the vendor-facing package)

- **`STEP_Draft_Handoff.md`** — native STEP status (`step_exported`, toolchain, output path,
  `draft_unapproved`), what the ME/vendor must verify and own (wall/tolerance/draft/undercut, fit,
  strength, waterproofing, thermal, DFM), and the explicit limit ("geometry from constraints; does
  not certify manufacturability").
- **`Print_Settings.md`** — printer profile (layer/nozzle/material/technology) **if** an STL exists,
  else the honest "No STL generated by this emitter; printable readiness false until a real STL
  exists" + items to confirm (material, wall, clearance, screw fit, orientation, support, tolerance).
- **`Assembly_Notes.md`** — current assembly status (not finalised), required inputs before CAD
  (PCB outline + mounting from C04, height envelope + connector list from C03, battery/cable/antenna/
  heat map), and "final fastener/catch/adhesive decisions require ME/vendor review".
- **`SketchUp_Import_Guide.md`** — SKP is *not* generated here; state `skp_export_unavailable: true`
  with the reason and the future path (export STL → import to SketchUp). End: "Do not treat this
  guide as proof that an SKP/STL/STEP exists."
- **`Vendor_Handoff.md`** — the request (estimate/refine a prototype enclosure; return CAD/STEP plan,
  assembly approach, DFM risks, quote/timeline), current readiness (mirror `approval_status`), and
  vendor-owned outputs (final/refined `.step`, assembly/exploded view, tolerance/material/structural/
  waterproofing/thermal/DFM sign-off).
- **Optional — a draft dimensioned drawing** (`Enclosure_drawing.svg`/`.dxf`). When build123d is
  present (same gate as the STEP), you *may* project an orthographic technical drawing from the same
  model as a vendor aid (build123d `TechnicalDrawing` / `render_technical_drawing()`; see
  build123d's tech-drawing tutorial). Honesty rules, identical to the model: the **3D model stays the
  one source of truth — the sheet is a projection, never a second geometry source**; default to
  front + top + right views; **dimension only interfaces, clearances, and inspection-critical
  features**; never add a section/datum/label that can't be traced back to the model; mark it
  `draft_unapproved` (GD&T + tolerance sign-off is the vendor's). Absent build123d ⇒ skip it; don't
  hand-draw an SVG.

### 8. Self-check before declaring the gate

- Every C01 component routed to C02 appears as a `connector_opening` or `antenna_keepout`.
- Every C03 explicit height/heat-source is carried with its `source` intact (provenance not laundered).
- No board-outline / mounting / dimension is asserted as *decided* — provisional values say so, and
  truly-absent ones are `engineering_pending` with an owner, not invented.
- The `.scad` variables are all derived from constraints; `opening_notes()` covers every opening.
- STEP/STL status in the JSON and in the handoff docs matches reality (ran ⇒ `true`/path; didn't run
  ⇒ `not-run` + reason). `me_approved` is `false`.
- `python3 -m json.tool Mechanical_Constraints.json` parses.

## Deliverables

Source-of-truth is **markdown + one JSON + the `.scad`**; the `.step`/`.stl` are *generated*
(and conditional on toolchain). Model on the real examples (`openmv/C02-ME/`, `rockbox/c02-me/`):

| Artifact | Path (relative to the stage dir) | Role | SoT vs generated |
|---|---|---|---|
| Mechanical constraints | `Mechanical_Constraints.json` | the enclosure contract + status ledgers | source-of-truth |
| Mechanical assumptions | `Mechanical_Assumptions.md` | scope / intent / pending / non-approval | source-of-truth |
| Parametric model | `Enclosure.scad` | OpenSCAD enclosure source | source-of-truth |
| Draft STEP | `Enclosure.step` | ISO-10303 solid for soft-tooling | **generated** (build123d; conditional) |
| Print STL | `Enclosure.stl` | FDM/SLA mesh | **generated** (openscad; conditional, often `not-run`) |
| STEP handoff | `STEP_Draft_Handoff.md` | STEP status + vendor ownership + limits | source-of-truth |
| Print settings | `Print_Settings.md` | profile or honest "no STL yet" | source-of-truth |
| Assembly notes | `Assembly_Notes.md` | assembly inputs + authority | source-of-truth |
| SketchUp import | `SketchUp_Import_Guide.md` | SKP-unavailable + future path | source-of-truth |
| Vendor handoff | `Vendor_Handoff.md` | request + readiness + vendor-owned outputs | source-of-truth |

For an archival/preserve-only track (like rockbox), a real vendor STEP may already exist under
`source/`; then C02 may *additionally* publish an interactive 3D view (`enclosure_3d/`: a `.glb`
converted from the real STEP via build123d `import_step → export_gltf`, plus a `<model-viewer>`
HTML). Do this **only** from a genuine STEP and label the source — see
`rockbox/c02-me/enclosure_3d/README.md`. Never synthesise a `.glb` to fake a 3D model.

Templates live in `assets/Mechanical_Constraints.template.json` and `assets/emit_step.py`.

## Gate / done-criteria

C02 is **genuinely done** (vs still draft) only when:

- All source-of-truth artifacts exist, the JSON parses, and the self-check (step 8) passes.
- Every `pending`/`draft`/`provisional`/`not-run` status carries a *reason* + *owner*, not a bare label.
- The STEP/STL status in the package matches what actually ran (toolchain verified, not assumed).

C02 is **never** "ME-approved / production-ready / DFM-cleared / waterproof-validated" from inside
bodesign. Those are **human/vendor gates** and `me_approved` stays `false`. Production injection-mould
tooling is downstream/external. A package can be *complete-as-a-draft* and still correctly carry
`State: draft` — that is the honest, expected end state of C02.

## Honesty notes for this stage

Apply `../../references/honesty-model.md` here as follows:

- **Constraints, not a manufacturable enclosure (rules 1 & 6).** Carry explicit C03 values; for
  missing inputs (board outline, heights, mounting, environment) write `engineering_pending` with an
  owner — never invent dimensions to make the model look complete. The rockbox example (no heights,
  no outline → no CAD source, four pendings) is the gold standard for an honest empty package.
- **Provenance (rule 2).** Component heights/heat-sources keep their C03 `source`+`status`; the board
  outline names its derivation ("C00 envelope, derived, unapproved"). Don't launder a derived guess
  into a bare number.
- **Status with a reason (rule 3).** `approval_status` + `constraint_status.pending[]` are the ledger;
  every false/pending entry states why and who owns it.
- **External gates stay external (rule 4).** Waterproofing/strength/thermal/DFM and FCC/CE are
  decided by a physical build / external lab / ME-vendor — record the target and plan, never a pass.
- **Don't claim an export you didn't run (rules 1 & 5).** Verify `which openscad` / `import build123d`
  *before* claiming an STL/STEP. Toolchain absent ⇒ `not-run` + reason; the `.scad` is honest source
  regardless. Show the export by its real output path, don't assert it.
- **Litmus test.** Before marking any mechanical claim better than the evidence, ask: *"If the vendor
  cut soft tooling from this tomorrow, would it hold — and did I actually run the export I'm
  claiming?"* If not, downgrade and name what's missing.

## Handoff — to the vendor, and back to C04 (board-outline confirmation)

- **To the ME / fab vendor:** the whole package above. `Vendor_Handoff.md` + `STEP_Draft_Handoff.md`
  are the entry points; the vendor returns a refined STEP, assembly approach, DFM risks, and a quote.
  Package these into a vendor doc with **docxmcp** / `docx` / `pdf` when a formal handoff is wanted.
- **Back to C04 (Layout) — board-outline confirmation:** the provisional `board_outline` +
  `mounting_holes` are a **request for confirmation**, not a directive. C04 (`../c04-layout/GUIDE.md`)
  owns the authoritative outline; when C04 sets it, update `Mechanical_Constraints.json`
  (`board_outline.status` → confirmed, real coordinates) and re-run `emit_step.py`. Flag any conflict
  (a connector opening that collides with C04's keep-out, a height that overflows the enclosure
  depth) as an open item — only C04/ME can resolve it, and the resolution is recorded, not assumed.
- **To C06 (Verify):** the environment targets and ESD/EMC notes seed the verification plan
  (`../c06-verify/GUIDE.md`); they remain `engineering_pending` until C00/C06 confirms them.
- **Cross-stage reconciliation — C02 is a lever owner.** C02's enclosure holds the levers for the
  **area** and **thermal** budgets (`../../references/cross-stage-reconciliation.md`): the
  `board_outline` (area), and surface area / vent-vs-IP / heatsink (thermal). When C03 emits an `open`
  area or thermal record naming C02 in `must_act`, re-evaluate the enclosure (larger outline, vent —
  which opens a coupled IP record, see § Sealing & IP — or spreader) and record the resolution; don't
  leave it for a downstream stage to absorb.

## Tools & companion skills

- **`references/mechanical-design-advisory.md`** — advisory DFM / DFA / tolerance-stack / material
  rules of thumb (injection-moulding *and* FDM/SLA), the three design principles, and the C02-pre
  scoping gate questions. Knowledge layer for the consultant role — it does **not** move the C02
  boundary; the vendor still owns DFM/tolerance/strength sign-off and `me_approved` stays `false`.
  Feed its numbers into `Print_Settings.md`, the `Enclosure.scad` parameters, and `Vendor_Handoff.md`.
- **`references/geometry-authoring-loop.md`** — the *method* for getting `Enclosure.scad`/STEP
  geometrically correct: the inspect-don't-visualise loop, how to inspect **without a renderer**
  (echo'd sizes, bounding-box, section reasoning), defect diagnosis, and the "no claimed fit without
  evidence" rule. Same stack as C02 (OpenSCAD + build123d). Use it in SOP steps 5–6.
- **build123d / OCP** (`assets/emit_step.py`) — the honest path to a real draft STEP. Requires the
  Python CAD kernel; verify `python3 -c "import build123d"` first. Absent ⇒ STEP `not-run`. The same
  runtime also projects an optional draft **technical drawing** (`TechnicalDrawing`, SVG/DXF) — see
  step 7. Two reusable-module ideas worth growing in `emit_step.py` rather than re-deriving each
  time: parametric **snap-fit hook** and **hinge** generators for lids/clips (cantilever beam +
  catch geometry, watertight single-component).
- **OpenSCAD** (`openscad` CLI) — render `Enclosure.scad` to STL/preview. Verify `which openscad`
  first; frequently absent on the authoring machine.
- **drawmiat** (`mcp__drawmiat__validate_diagram` → `generate_diagram`) — optional assembly/exploded
  flow or an IDEF0 view of the enclosure-assembly process. Validate before generate.
- **docxmcp** MCP (`docxmcp_pptx_*` / `docxmcp_document`) / **docx** / **pdf** / **xlsx** — produce
  the vendor handoff doc, an RFQ, or a tolerance/opening table. Do everything *through* the tools;
  never hand-edit OOXML.
- **Optional product render (CAD → marketing image)** — to turn `Enclosure.scad`/`.stl` into a
  polished "boss/marketing" image (the *viewable* artifact the C02 plan wants), a CAD→AI-render
  pipeline (e.g. CadQuery/OpenSCAD → ComfyUI, after `edhahn/agent-skills` product-illustrator) is an
  option. It needs a running **ComfyUI** server — absent ⇒ skip and rely on the STL preview /
  `enclosure_3d` `.glb` viewer. A render is an **illustrative draft**, label it so; it is not a
  geometry source and never replaces the `.scad`/STEP (honesty rule 5).
- No KiCad/kidoc engine work happens at C02 (those enter at C03+). C02 sits between C01's interface
  constraints and C04's authoritative board outline.
