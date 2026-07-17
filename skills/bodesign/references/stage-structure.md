# Stage folder structure — deliverables at the root, support material in two subfolders

Every stage produces a pile of files: client inputs, generated intermediates, the real
deliverables, and explanatory notes. The reader who opens a stage folder should **see the
deliverables immediately** — what this stage actually hands downstream — and only have to step into
a subfolder for the messier supporting material. So every `cXX-*/` stage folder is organised as
**the deliverables sitting flat at the stage root, plus two numbered support buckets**:

```
cXX-<name>/
├── README.md / CHANGELOG.md   ← the stage's meta record (project-execution log / index, not a deliverable)
├── <human-facing deliverables…> ← what a HUMAN reviews, flat at the root: C0N_*.docx documents, the
│                                  engineering files a person opens, a viewable PNG/PPTX
├── 01_refs/                   reference — external inputs this stage CONSUMES
├── 02_build/                  build     — intermediate/derived products + build workspaces (garbage-collectable)
└── 03_output/                 output    — AI/machine-facing deliverables: generated .md reports + .json
                                           bridges that downstream tools and agents consume (humans don't read raw md/json)
```

> **Convention (changed 2026-07-17, audience split — supersedes 2026-06-16 "everything flat"):**
> deliverables are split by **AUDIENCE**, owner-ruled. **Human-facing deliverables** — the `C0N_*.docx`
> documents and the viewable PNG/render — live **flat at the stage root**: a reader opening the folder
> sees what the stage delivered without stepping into any bucket. Humans don't read raw `.md`/`.json`,
> so **AI/machine-facing deliverables** — generated `.md` reports, `.json` bridges, machine-readable
> tables — live in **`03_output/`**, consumed by downstream tools/agents by path. Cross-stage
> `_consumed_from` references point into the owner's `03_output/`
> (e.g. `../C01-ID/03_output/Interface_Constraints.json`).
> History: the pre-2026-06-16 layout buried ALL deliverables (incl. the human-reviewed ones) in
> `03_output/`; the 2026-06-16 rule over-corrected to "everything flat" and left the root littered with
> machine-only md/json. This audience split is the stable resolution. **Legacy = migration debt, not a
> permanent exemption.** The `thesmart_products/rockbox/` and `openmv/` tracks may still carry the
> OLD-semantics `03_output/` (every deliverable in the bucket, no `C0N_*.docx` at the root) — whenever
> you do real work in a legacy stage, migrate it to the current contract. The `aiguard/` track is the
> reference implementation. Do **not** cite "legacy" to justify leaving a freshly-touched stage
> non-compliant.

> **Convention (changed 2026-06-19):** **document deliverables are delivered as `.docx`**, not `.md`.
> The editable Markdown is an **intermediate source** that lives in `02_build/` (e.g.
> `02_build/<Doc>.docx.body.md`); docxmcp assembles it into the `.docx` deliverable at the stage root.
> Author/edit content in the `.md` under `02_build/`, then (re)assemble the `.docx`. **No ad-hoc deliverable
> subfolders** — the only sanctioned subfolders are `01_refs/`, `02_build/`, and `03_output/`. (So a
> `schematics/` folder for schematic PNGs is wrong — viewable PNGs go at the stage root; machine-readable
> exports go in `03_output/`.) One additional sanctioned dot-folder: **`.history/`** — version backups
> and retired/superseded assets (retirement is never deletion; everything reversible). This is the
> fleet-wide specbase convention (owner ruling 2026-07-17); do not use per-project synonyms like
> `superseded/` or a root-level `old/`.
> Files a professional tool *needs* in a specific tree (a KiCad project's own `generated/` workspace, a
> routing tool's relative-path bundle) stay as that tool requires under `02_build/` — see "Complex
> stages" below; the **viewable result** (PNG/PDF) is copied flat to the root.

> **Convention (changed 2026-06-23): the human-facing `.docx` deliverable carries a `C0N_` stage prefix,
> is self-contained, and is the only `.md`-vs-`.docx` split rule.** Three sub-rules, all mandatory for
> C00–C07:
>
> 1. **`C0N_` filename prefix on every human-facing deliverable.** A document a person reads to review
>    the stage is named `C0N_<中文Title>.docx` (e.g. `C00_產品需求規格書.docx`, `C03_電路設計文件.docx`,
>    `C04_疊層.docx`). The prefix makes the owning stage unambiguous when files are collected across a
>    portfolio. This applies to the `.docx` documents and the human-facing structured exports a reviewer
>    opens (`C03_BOM.csv`, `C03_Pin_Allocation.csv`); it does **not** rename machine-readable bridges
>    consumed by downstream tools (`Interface_Constraints.json`, `Pin_Map_Bridge.json`,
>    `Mechanical_Constraints.json`, `.kicad_sch`, Gerbers, STEP) — those keep their tool-contract names so
>    cross-stage `_consumed_from` references don't break. `README.md`/`CHANGELOG.md` are meta, no prefix.
>
> 2. **Each deliverable `.docx` is self-contained.** A stage may legitimately ship *several* `C0N_` docx
>    (different audiences/purposes — e.g. C00 = `C00_產品需求規格書` + `C00_射頻需求規格書` +
>    `C00_交付移交報告`), but **every one must stand alone**: the figures, tables, and explanatory prose
>    that document needs are **embedded inside the `.docx`** (via docxmcp `![](…){width=…}` image embeds
>    and Word tables), not left as loose `.png`/`.md` a reader must hunt for. "Integrated into one docx"
>    means self-contained, **not** "fold every document into a single file." The litmus test: a reviewer
>    opening one `C0N_*.docx` sees that document's complete picture —图、表、说明 — without opening the
>    package folder.
>
> 3. **`.md`/`.json` never sits at the stage root (except `README.md`/`CHANGELOG.md`) — route by role.**
>    The editable *source* of a docx (the body the assembler consumes) and working notes are
>    intermediates → `02_build/`. A generated `.md`/`.json` that downstream tools or agents CONSUME as a
>    deliverable (`*.generated.md`, machine handoff/readiness reports, `Interface_Constraints.json`-class
>    bridges) is an AI-facing deliverable → `03_output/`. A stage root littered with
>    `Project_Requirements.md` / `*.generated.md` next to its docx is a **defect** — file each by role
>    and keep only the assembled `C0N_*.docx` (+ viewable PNG) at the root.
>
> **Language:** the `.docx` document deliverable is written in **繁體中文 (Traditional Chinese)** —
> translate the `.md` source if it is in English or 簡體中文 before assembling. The `.md` intermediate
> may stay in whatever working language it was authored in (it is not the deliverable). `README.md` /
> `CHANGELOG.md` are meta (not deliverables) and need not be translated. This applies to **all C00–C07
> stages**.

## What goes where

| Location | Put here | Examples |
|---|---|---|
| **stage root** | **The stage's `README.md`/`CHANGELOG.md` (meta/index) AND the human-facing deliverables** — document deliverables as **`.docx`** (the editable `.md` source stays in `02_build/`), the engineering files a human opens in their native tool, and a viewable `.png` so the result can be eyeballed. Flat — no ad-hoc subfolders. | `README.md`; `C00_產品需求規格書.docx`, `*_Handoff*.docx` (docx), `.kicad_sch`, Gerbers, STEP, `C0N_BOM.csv` (reviewer-facing), a render/preview PNG |
| **`01_refs/`** | **External reference source** the stage reads but did not produce — anything consumed as input. PDFs, datasheets, client requirement specs, a reference design, a constraint export consumed from an earlier stage. | requirement `.pdf`/`.docx`, `datasheets/`, an upstream `Mechanical_Constraint_Export.json` mirror |
| **`02_build/`** | **Intermediate & derived** artifacts produced on the way to the deliverables. **Transient — a later garbage-collection pass keeps only what has lasting value.** | analyzer runs (`analysis/`), schematic viewers (`.jrl`/`.opj`), granular per-layer copper PNGs, debug overlays + scripts, docx body sources |
| **`.history/`** | **Version backups & retired assets** — superseded deliverables, pre-revision snapshots. Zero-deletion, fully reversible. | retired `answer_state_YYYYMMDD_*.json`, old docx/pptx versions, obsoleted SSOT files |
| **`03_output/`** | **AI/machine-facing deliverables** downstream tools and agents consume by path — generated `.md` reports, `.json` bridges, machine tables. Humans review the `.docx` at the root; machines read here. **No AI-facing `.json` stays at the stage root** — `answer_state.json` / `Verification_Summary.json` class state files live here too (tool resolvers prefer `03_output/`, root only as legacy fallback). | `03_output/answer_state.json`, `Project_Requirements.generated.md`, `C00_Handoff_Report.md`, `Capability_Gap_Table.md`, `Interface_Constraints.json`, `Pin_Map_Bridge.json`, `Mechanical_Constraint_Export.json`, netlist exports |

### The recurring judgment calls (decide consistently)

- **Document deliverables ship as `.docx` at the stage root; their Markdown is an intermediate source in
  `02_build/`.** Author/edit the content in the `.md` (under `02_build/`), then docxmcp-assemble the
  `.docx` to the root — the `.md` is *how you wrote it*, the `.docx` is *what you deliver*. The
  README/CHANGELOG stay at the root as the *meta* layer (Markdown is fine for them — they are an
  index/log, not deliverables). "Is this a document I hand downstream?" yes → `.docx` at the root, `.md`
  in `02_build/`; "is this a log/index about my own work?" → `README.md` (stays `.md` at root).
- **No ad-hoc subfolders.** The only sanctioned subfolders are `01_refs/`, `02_build/`, `03_output/`.
  Don't create a `schematics/`, `docs/`, `figures/` bucket — human-facing PNGs / `.docx` / engineering
  files go flat at the root; machine-facing `.md`/`.json` go in `03_output/`.
- **Structured-data deliverables (`.json` bridges, generated `.md`, machine tables) → `03_output/`.**
- **Deliverables must be eyeball-able.** Mechanical → a render/`.glb`+viewer or PNG; circuit/PCB →
  a schematic/board/copper PNG. If only a binary deliverable exists, generate a preview (the MCP's
  `render_board_model` / `render_gerber_preview` / a board render) so the result is viewable.
- **External input vs. stage deliverable.** A client requirement `.docx`/`.pdf` is *consumed input*
  → `01_refs/`. A doc the stage *authors as its output* (spec, handoff, SOP) → stage root.
- **Generated previews/intermediates → `02_build/`**; the showcase result PNG → stage root.

## Producing the `.docx` deliverable from the `.md` source (the standard recipe)

The `.md` (in `02_build/`) is the editable source; the `.docx` at the stage root is the deliverable.
To (re)generate a stage-root `.docx` in the **house style + 繁體中文** via docxmcp:

1. **House template** — decompose any existing house `.docx` (`docxmcp_document action=decompose`).
   You get a package with `template/` (styles/numbering/theme) + a `body.md` + `next_args.assemble`.
   Upload it under an **ASCII filename** first (a CJK stem breaks the `doc_dir` path arg).
2. **Translate + inject** — translate the source `.md` to **繁體中文**, then replace the package's
   `body.md` with that content. **Bundle any referenced images** into the package (next to `body.md`,
   matching the `![](name.png)` paths) or they render as "[image not found]".
3. **Assemble** — `docxmcp_document action=assemble` with the package `doc_dir`; the `.docx` inherits
   the house numbering (壹、/ 一、/（一）) and styles. Download it to the **stage root**; move the source
   `.md` into `02_build/`.

Never hand-edit OOXML; if docxmcp can't assemble, stop and report (don't fall back to LibreOffice/pandoc
as the delivery path — soffice is fine only for a read-only render check).

### The "one-pass" recipe: stage visual + self-contained `C0N_` docx (verified 2026-06-23)

This is the executable SOP behind the self-contained-docx rule (§Convention 2026-06-23). The
orchestrator AI is the glue between bodesign-emit and docxmcp-assemble — bodesign emits the *content*,
the stage's render tool emits the *figure*, docxmcp assembles the *embedded-image docx*. There is **no
bodesign→docxmcp container wiring**; the AI drives both MCPs. Per stage:

1. **Emit content** — run the stage's bodesign emitter (`c00_emit_prd` / schematic / layout / …) to get
   the markdown body + structured data. The `.md` is the body *source*, not the deliverable.
2. **Generate the stage's eyeball figure** (the visual a reviewer scans), using the sanctioned host tool
   for that stage — **not** a decorative placeholder:
   - **C00 architecture** — `drawmiat` C4/IDEF0 if its raster is complete; if drawmiat's C4 SVG renders
     degenerate (legend-only, <2KB — a known render defect), fall back to a hand-authored Graphviz `dot`
     (`dot -Tpng -Gdpi=150` + `-Tpdf`), grounded on `answer_state.json` subsystems. Verify node count in
     the SVG before trusting it.
   - **C03 schematics** — `kicad-cli sch export pdf` (per subsystem `.kicad_sch` under
     `02_build/generated/sch*`) → `pdftoppm -png -r 150` for the quick-view PNG. Both PDF (vector
     deliverable) + PNG (eyeball) land at the stage root, `C03_原理圖_<sub>.{pdf,png}`.
   - **C04 PCB** — surface the routed board renders from `02_build/.../routed/<board>/renders/*.png` to
     the stage root as `C04_PCB圖_<board>.png`; or `render_gerber_preview` for a fab-grade copper preview.
   - **C01 ID** — convert the ID-native SVGs (`Ai file/*_ID_skeleton.svg`, `Display UI_UX/*.svg`) to PNG
     via `cairosvg` (host has the py lib) for docx embedding.
   - **C02 enclosure six-view** — `c02_export_stl` → `c02_render_enclosure`; **blocked if openscad
     absent** (record the honest boundary in the docx, do not fabricate a render).
3. **Assemble the embedded-image docx via docxmcp** (the proven token spine):
   - If a house `.docx` exists for the stage: upload it (`POST /files`) → `docxmcp_document
     action=decompose` → pull `template/template.dotx` + `manifest.json` from the token.
   - If none: hand-write a `manifest.json` with `workflow_state: "decomposed"` (NOT `authored` — assemble
     rejects `authored`) + `package_type: "text-document"`.
   - Author `body.md` in **繁體中文** with `![alt](media/<figure>.png){width=…}` embeds; copy the figure(s)
     into `media/`.
   - Tar the **flat** package (`manifest.json` + `body.md` + `template/` + `media/` at the token root —
     NOT nested under a `<stem>/` subdir, which yields `DOCUMENT_DOC_DIR_NOT_FOUND`) → `POST /files`
     (`Content-Type: application/x-tar`) → `docxmcp_document action=assemble doc_dir=<token>
     template=template/template.dotx preview=true`.
4. **Verify the embed, then land** — download `rebuilt.docx`; confirm the figure is embedded
   (`unzip -l rebuilt.docx | grep media/image` shows the PNG at its real byte size — a docx with a broken
   `![]()` ref has zero `word/media/*`). Copy to the stage root as `C0N_<中文Title>.docx`; move the
   source `.md` into `02_build/`.

This loop is fully tool/script-driven (zero hand-patching) and is what "next run, whole line in one go"
means: the AI replays this recipe per stage. The figure-generation step is the only stage-specific part;
the docxmcp assemble spine is identical across C00–C07.

## One canonical owner per cross-stage artifact — consume by reference, never re-copy

The worst structural failure mode is the same data living in three stages and drifting (or
propagating a bug). Each shared artifact has **exactly one owning stage** that produces the
canonical copy at its root; every downstream stage that needs it **references that path** and records
the provenance, rather than holding an editable duplicate:

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
what must exist. "Stage done" = every required artifact is present **at its sanctioned location**
(human-facing at the stage root; machine-facing bridges/reports in `03_output/`) **or** carries an explicit blocked/not-run
status with a reason + owner. The readiness tools (`bodesign_cXX_readiness`, `package_readiness`)
score it. `02_build/` proves how you got there; the **deliverables at the root** are what you are
accountable for; the root `README.md` indexes and logs it.

The worked-example tracks `thesmart_products/rockbox/` and `openmv/` still show the **legacy
`03_output/`** semantics (ALL deliverables in the bucket); the `aiguard/` track shows the current
**audience-split** layout (human-facing docx/PNG at the stage root; AI-facing md/json in `03_output/`).
New stages follow the audience-split layout.
