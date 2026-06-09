# Stage folder structure — docs at root + three numbered buckets

Every stage produces a pile of files: client inputs, generated intermediates, the real
deliverables, and explanatory notes. Left flat at the stage root they become unsearchable and the
"what did this stage actually deliver?" question gets impossible to answer — which is exactly the
ambiguity that lets deliverables silently go missing. So every `cXX-*/` stage folder is organised
as **a meta record at the root + three numbered buckets**, ordered by when they are used:

```
cXX-<name>/
├── README.md / CHANGELOG.md   ← ONLY the stage's meta record (project-execution log, not a deliverable)
├── 01_refs/                   reference    — external inputs this stage CONSUMES
├── 02_build/                  build        — intermediate/derived products + build workspaces (garbage-collectable)
└── 03_output/                 deliverables — every clean output, incl. spec/handoff docs + a viewable PNG
```

## What goes where

| Location | Put here | Examples |
|---|---|---|
| **root** (no bucket) | **Only the stage's `README.md` / `CHANGELOG.md`** — a project-execution record that indexes the stage and logs progress. This is **not** a deliverable; it is the navigation/meta layer. Nothing else lives loose at the root. | `README.md` (what this stage is, what's in `03_output/`, status), `CHANGELOG.md` |
| **`01_refs/`** | **External reference source** the stage reads but did not produce — anything consumed as input. PDFs, datasheets, client requirement specs, a reference design, a constraint export consumed from an earlier stage. | requirement `.pdf`/`.docx`, `datasheets/`, an upstream `Mechanical_Constraint_Export.json` mirror |
| **`02_build/`** | **Intermediate & derived** artifacts produced on the way to the deliverables. **Transient — a later garbage-collection pass keeps only what has lasting value.** | analyzer runs (`analysis/`), schematic viewers (`.jrl`/`.opj`), granular per-layer copper PNGs, debug overlays + scripts, working state (`answer_state.json`) |
| **`03_output/`** | **Every clean deliverable** downstream consumes — the spec/handoff **docs** (`.md`), the structured-data bridges (`.json`), **and** the real engineering files. **Whether mechanical or circuit, include a viewable `.png` (or a viewer) so the preliminary result can be eyeballed without opening CAD/EDA.** | `Architecture_and_BOM.md`, `Functional_Spec.md`, `*_Handoff*.md`, `Interface_Constraints.json`, `Pin_Map_Bridge.json`, schematic `.DSN`/`.kicad_sch`, BOM, Gerbers, firmware source, STEP, a render/preview PNG |

### The recurring judgment calls (decide consistently)

- **Spec / handoff / SOP docs are deliverables → `03_output/`**, even though they are markdown. The
  only docs at the **root** are `README.md` / `CHANGELOG.md` (the execution record about the stage),
  which are *not* deliverables. "Is this a thing I hand downstream?" yes → `03_output/`; "is this a
  log/index about my own work?" → root.
- **Structured-data deliverables (`.json` bridges, BOM/netlist tables) → `03_output/`.**
- **`03_output/` must be eyeball-able.** Mechanical → a render/`.glb`+viewer or PNG; circuit/PCB →
  a schematic/board/copper PNG. If only a binary deliverable exists, generate a preview (the MCP's
  `render_board_model` / `render_gerber_preview` / a board render) so the result is viewable.
- **External input vs. stage deliverable.** A client requirement `.docx`/`.pdf` is *consumed input*
  → `01_refs/`. A doc the stage *authors as its output* (spec, handoff, SOP) → `03_output/`.
- **Generated previews/intermediates → `02_build/`**; the showcase result PNG → `03_output/`.

## One canonical owner per cross-stage artifact — consume by reference, never re-copy

The worst structural failure mode is the same data living in three stages and drifting (or
propagating a bug). Each shared artifact has **exactly one owning stage** that produces the
canonical copy in its `03_output/`; every downstream stage that needs it **references that path**
and records the provenance, rather than holding an editable duplicate:

- **Mechanical constraints** — owned by **C03** (`c03-ee/03_output/Mechanical_Constraint_Export.json`).
  C02 and C04 consume it (`01_refs/` mirror or a `_consumed_from` pointer) and add only their own
  stage-specific fields. Fix the data in the C03 export and re-consume; never hand-edit a mirror.
- **Pin/GPIO map** — owned by **C03**; C05's `Pin_Map_Bridge.json` derives from it (zero invented pins).
- **PRD targets** (cost/qty/cert) — owned by **C00**; C07 cites them, does not restate-as-truth.

If you find yourself editing the same array in two stages, stop: pick the owner, make the others
reference it, and leave a `_consumed_from` note.

## Complex stages — build workspaces and nested sub-projects

A real engineering stage is rarely a handful of loose files. Two recurring shapes must fit the
convention without an exception — they extend it, they don't break it:

**A. Self-contained build workspaces move as one unit into `02_build/`.** A directory that bundles
its own scripts + intermediates + generated outputs (e.g. a routing `generated/` tree with
`build.sh`/`check.sh`, a layout's `routed/` + tooling) is *machinery*, not a deliverable — it goes
**whole** into `02_build/` so its internal relative paths stay valid. Two rules:
- If relocating the subtree changes a script's self-location depth (a `cd "$TD/../.."` that now
  points one level off), **fix the script's root-finding** — never leave a broken tool behind.
- The **final, shippable artifacts** the workspace produces (the Gerber package, the board render
  PNG, the fab outputs) are *copied* into `03_output/` as the clean deliverable. Machinery stays in
  `02_build/`; the finished result that downstream consumes lives in `03_output/`.

**B. A nested sub-project is a unit that recursively follows this convention.** When a deliverable is
produced by a self-contained sub-project — e.g. an SSOT-driven board *reconstruction* (`ssot/` →
`extracted/` → `C0x` requirement docs → `manufacturable/`) — that sub-project is **one unit** and
applies the same layout *inside itself* (its `ssot/` is its refs, `extracted/`+`tools/` are its
build, its requirement docs + `manufacturable/` are its output). Do **not** flatten its deliberate
pipeline into the parent's three buckets. Place the whole sub-project under the **owning stage's
`02_build/`** (it is *how* that stage's deliverable was made / its provenance baseline), and surface
its final clean outputs in the parent stage's `03_output/`. If the reconstruction is the provenance
*input* to the stage rather than its own work, `01_refs/` is the right home instead. Either way the
SSOT discipline is preserved, not destroyed.

The litmus test for both: the bucket scheme classifies by **role** (input / machinery / deliverable),
and a subtree keeps that role as a whole — you never have to shred a working directory to obey it.

## Conventions

- Buckets are numbered `01_`/`02_`/`03_` so they sort in workflow order; the names are stable
  (`refs` / `build` / `output`). A bucket with no content still exists (drop a `.gitkeep`) so the
  shape is uniform and "no reference inputs" is distinguishable from "someone forgot to file them."
- Generated-from-a-source views carry the `.generated.md` suffix so no one hand-edits a derived file.
- Status vocabulary is shared across stages: `answered` · `drafted` · `blocked` · `accepted-risk` ·
  `external-needed` · `not-run`. Don't invent per-stage synonyms, and don't let two files about the
  same thing disagree (a bring-up checklist that is 1/8 done cannot sit next to a transfer doc that
  says "a board that was physically built").

## Relationship to the Definition of Done

The per-stage **Required deliverables — Definition of Done** block (top of each guide) enumerates
what must exist. "Stage done" = every required artifact is present in **`03_output/`** (the spec
docs, the bridges, the engineering files, the preview PNG) **or** carries an explicit blocked/not-run
status with a reason + owner. The readiness tools (`bodesign_cXX_readiness`, `package_readiness`)
score it. `02_build/` proves how you got there; `03_output/` is what you are accountable for; the
root `README.md` just indexes and logs it.

The worked-example project `thesmart_products/rockbox/` is organised exactly this way — read any
stage there to see it populated.
