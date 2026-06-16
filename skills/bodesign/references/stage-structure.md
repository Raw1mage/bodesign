# Stage folder structure — deliverables at the root, support material in two subfolders

Every stage produces a pile of files: client inputs, generated intermediates, the real
deliverables, and explanatory notes. The reader who opens a stage folder should **see the
deliverables immediately** — what this stage actually hands downstream — and only have to step into
a subfolder for the messier supporting material. So every `cXX-*/` stage folder is organised as
**the deliverables sitting flat at the stage root, plus two numbered support buckets**:

```
cXX-<name>/
├── README.md / CHANGELOG.md   ← the stage's meta record (project-execution log / index, not a deliverable)
├── <deliverables…>            ← every clean output flat at the root: spec/handoff docs, .json bridges,
│                                  engineering files, a viewable PNG  (one glance = what this stage delivered)
├── 01_refs/                   reference — external inputs this stage CONSUMES
└── 02_build/                  build     — intermediate/derived products + build workspaces (garbage-collectable)
```

> **Convention (changed 2026-06-16):** deliverables live **at the stage root**, not in a `03_output/`
> bucket. Rationale: a reader entering the folder should see the deliverables first; supporting clutter
> (consumed inputs, intermediates) is what gets pushed into subfolders. This also matches what the
> bodesign **MCP tools already emit** (flat, at the stage root) — `03_output/` was only ever a
> skill-doc convention that required a manual reconcile step. **Legacy:** the `thesmart_products/rockbox/`
> and `openmv/` tracks predate this and still use the old `03_output/` layout; new work uses flat.

## What goes where

| Location | Put here | Examples |
|---|---|---|
| **stage root** | **The stage's `README.md`/`CHANGELOG.md` (meta/index) AND every clean deliverable** downstream consumes — spec/handoff **docs** (`.md`), structured-data bridges (`.json`), the real engineering files, and a viewable `.png` so the result can be eyeballed without opening CAD/EDA. The README is named distinctly, so deliverables vs the index stay clear. | `README.md`; `Architecture_and_BOM.md`, `Functional_Spec.md`, `*_Handoff*.md`, `Interface_Constraints.json`, `Pin_Map_Bridge.json`, `.kicad_sch`, BOM, Gerbers, STEP, a render/preview PNG, a `.docx` |
| **`01_refs/`** | **External reference source** the stage reads but did not produce — anything consumed as input. PDFs, datasheets, client requirement specs, a reference design, a constraint export consumed from an earlier stage. | requirement `.pdf`/`.docx`, `datasheets/`, an upstream `Mechanical_Constraint_Export.json` mirror |
| **`02_build/`** | **Intermediate & derived** artifacts produced on the way to the deliverables. **Transient — a later garbage-collection pass keeps only what has lasting value.** | analyzer runs (`analysis/`), schematic viewers (`.jrl`/`.opj`), granular per-layer copper PNGs, debug overlays + scripts, working state (`answer_state.json`), docx body sources |

### The recurring judgment calls (decide consistently)

- **Spec / handoff / SOP docs are deliverables → stage root**, even though they are markdown. The
  README/CHANGELOG are also at the root but are the *meta* layer (an index/log about the stage), not
  deliverables. "Is this a thing I hand downstream?" yes → a deliverable at the root; "is this a
  log/index about my own work?" → `README.md`.
- **Structured-data deliverables (`.json` bridges, BOM/netlist tables) → stage root.**
- **Deliverables must be eyeball-able.** Mechanical → a render/`.glb`+viewer or PNG; circuit/PCB →
  a schematic/board/copper PNG. If only a binary deliverable exists, generate a preview (the MCP's
  `render_board_model` / `render_gerber_preview` / a board render) so the result is viewable.
- **External input vs. stage deliverable.** A client requirement `.docx`/`.pdf` is *consumed input*
  → `01_refs/`. A doc the stage *authors as its output* (spec, handoff, SOP) → stage root.
- **Generated previews/intermediates → `02_build/`**; the showcase result PNG → stage root.

## One canonical owner per cross-stage artifact — consume by reference, never re-copy

The worst structural failure mode is the same data living in three stages and drifting (or
propagating a bug). Each shared artifact has **exactly one owning stage** that produces the
canonical copy at its root; every downstream stage that needs it **references that path** and records
the provenance, rather than holding an editable duplicate:

- **Mechanical constraints** — owned by **C03** (`c03-ee/Mechanical_Constraint_Export.json`).
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
  PNG, the fab outputs) are *copied* to the **stage root** as the clean deliverable. Machinery stays
  in `02_build/`; the finished result that downstream consumes sits at the root. (A small,
  self-contained `generated/` of just the viewable deliverables — e.g. rendered SVG/PNG + netlist —
  may instead sit at the root next to the docs that reference it, so `![](generated/…)` links resolve.)

**B. A nested sub-project is a unit that recursively follows this convention.** When a deliverable is
produced by a self-contained sub-project — e.g. an SSOT-driven board *reconstruction* (`ssot/` →
`extracted/` → `C0x` requirement docs → `manufacturable/`) — that sub-project is **one unit**. Place
the whole sub-project under the **owning stage's `02_build/`** (it is *how* that stage's deliverable
was made / its provenance baseline), and surface its final clean outputs at the parent stage's root.
If the reconstruction is the provenance *input* to the stage rather than its own work, `01_refs/` is
the right home instead. Either way the SSOT discipline is preserved, not destroyed.

The litmus test for both: the scheme classifies by **role** (input / machinery / deliverable), and a
subtree keeps that role as a whole — you never have to shred a working directory to obey it.

## Conventions

- The two support buckets are numbered `01_`/`02_` (`refs` / `build`) so they sort ahead of nothing
  and read in workflow order; the names are stable. A support bucket with no content still exists
  (drop a `.gitkeep`) so "no reference inputs" is distinguishable from "someone forgot to file them."
- Generated-from-a-source views carry the `.generated.md` suffix so no one hand-edits a derived file.
- Status vocabulary is shared across stages: `answered` · `drafted` · `blocked` · `accepted-risk` ·
  `external-needed` · `not-run`. Don't invent per-stage synonyms, and don't let two files about the
  same thing disagree (a bring-up checklist that is 1/8 done cannot sit next to a transfer doc that
  says "a board that was physically built").

## Relationship to the Definition of Done

The per-stage **Required deliverables — Definition of Done** block (top of each guide) enumerates
what must exist. "Stage done" = every required artifact is present **at the stage root** (the spec
docs, the bridges, the engineering files, the preview PNG) **or** carries an explicit blocked/not-run
status with a reason + owner. The readiness tools (`bodesign_cXX_readiness`, `package_readiness`)
score it. `02_build/` proves how you got there; the **deliverables at the root** are what you are
accountable for; the root `README.md` indexes and logs it.

The worked-example tracks `thesmart_products/rockbox/` and `openmv/` still show the **legacy
`03_output/`** layout (deliverables in a bucket); the `aiguard/` track shows the current **flat**
layout (deliverables at the stage root). New stages follow the flat layout.
