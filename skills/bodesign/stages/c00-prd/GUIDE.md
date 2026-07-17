# C00 PRD — Product Requirements (the root of the lifecycle)

The PRD is the contract every downstream stage reads. It fixes **what we're building, why, for whom,
and to which targets** — and it does so *honestly*: an unanswered requirement stays visibly open, an
approval that hasn't happened stays unapproved. C03 reads its constraints here, C07 reads its
cost/quantity/certification targets here, C01/C02 read the ID/ME envelope here. If the PRD lies, every
stage downstream inherits the lie. So this stage is fully specified below — you author the whole thing,
not "go run a skill."

Read `../../references/honesty-model.md` before writing a single field. It overrides everything here.

**Write for the next reader, who is an AI agent or a junior engineer.** Every downstream stage — C01…C07 —
consumes this PRD as machine-actionable input, not prose to admire. So be explicit and unambiguous, avoid
unexplained jargon, and give enough detail that a reader with no prior context can act on a field without
guessing. Ambiguity doesn't stay here; it propagates as a wrong decision downstream. (Honesty governs
*whether* a value is asserted; this governs *how clearly* it's stated once it is.)

## Purpose & scope

**This stage owns:**
- Product vision & business strategy (who, what problem, why us).
- Product-level system architecture (the block diagram: compute, memory, power, connectivity, sensors, I/O).
- Requirements split by discipline: ID/ME, electrical (EE), software/firmware.
- The **targets** downstream stages must honour: cost (PCBA + finished-good BOM), quantity (EVT/DVT/MP),
  certification (FCC/CE/NCC/…), schedule milestones.
- Roles & responsibilities, assumptions & constraints, project management cadence, timeline, team roster.
- An optional **RF requirements appendix** when the product has any radio (Wi-Fi/BLE/LTE/NFC/…).

**This stage does NOT own** (these are downstream — record the *requirement/target*, never the result):
- Schematic, BOM line items, netlist, pin assignment → **C03**.
- Enclosure CAD, tolerances, STEP → **C02**. CMF / screen UX detail → **C01**.
- Firmware code or driver implementation → **C05**.
- Any test verdict, bring-up result, or compliance pass → **C06/C07** (and external labs).

## Required deliverables — Definition of Done

> **`readiness_pct: 100` ≠ done.** The readiness tools enforce this table as a machine-checkable
> manifest: the real gate is **`dod_ok: true`** in the readiness output — true only when every row
> below is `present` (or honestly deferred via a `dod_status.json` entry) and no `answered` field is
> fake-complete (a `TBC`/placeholder value). Read the `guide_compliance` block, not the bare percent.

Produce **all** of these in this stage before you report C00 done or hand off (see SKILL.md
§ "Definition of Done"). Each must exist on disk **or** carry an explicit `blocked`/`external-needed`
status with a reason + owner — silent absence is not allowed.

| # | Required artifact | File | Notes |
|---|---|---|---|
| 1 | Answer state | `C00-PRD/03_output/answer_state.json` | every gating field `answered` or honestly `accepted-risk`/`external-needed`; lives in `03_output/` (AI-facing output — tool resolver prefers `03_output/`, root kept as legacy fallback) |
| 2 | Project requirements (PRD) | `C00-PRD/03_output/Project_Requirements.md` (`.generated.md`) | the twelve sections; the human-facing `C00_*.docx` renders from it at the root |
| 3 | RF requirements | `C00-PRD/03_output/RF_Requirements.md` (`.generated.md`) | **only if the product has RF**; else mark N/A with reason |
| 4 | Handoff report | `C00-PRD/03_output/C00_Handoff_Report.md` | downstream gates (C01/C02 · C03 · C05 · C06 · **C07 targets**) ready/blocked |
| 5 | Module breakout 板級切割圖 + 系統方塊圖 | `C00-PRD/C00_模組Breakout.pptx` (+ root PNG) | **human-audit mandatory** — slide1 = board/module partition (channel layer drawn as LINES, not cards); slide2 = MCU-centric functional block diagram from answer_state subsystems (`c03_emit_host_block_diagram` model — absorbs the retired standalone `C00_系統方塊圖.png`, owner ruling 2026-07-17: same-source duplication). Visual mother-source of s04's partition AND C03's functional blocks; MUST be regenerated whenever s04/s05 partition rulings change (a stale breakout is a DoD defect, not cosmetics) |
| 7 | Capability/gap table | `C00-PRD/03_output/Capability_Gap_Table.md` | baseline capability vs net-new, with provenance + downstream owner |
| 8 | Rich-media adjudication ledger | `C00-PRD/01_refs/Adjudication_Ledger.md` | every concept image explicitly adjudicated (§0c); unadjudicated media must not be consumed downstream |

**Self-verify:** run the landing verb `c00_readiness` (`python3 <skill>/scripts/gate.py
c00_readiness --repo <abs-project>` — NOT an MCP tool; see SKILL.md § "Landing / compute routing
contract") and report which fields/sections are still
open. C00 is not done while any gating section is unanswered without an honest accepted-risk/external
owner. Then run two honesty-review passes the readiness tool can't compute: a **boundary check** — no
C03/C05-level detail (schematic, pin assignment, part numbers as *decisions*, firmware code) has leaked
in; the PRD states *what/why*, downstream owns *how* — and an **evidence check** — every asserted value
and capability-table row carries a source; nothing unsupported slipped past `missing`. Model:
`thesmart_products/rockbox/c00-prd/`.

## Inputs (from upstream)

C00 is the head of the chain, so its inputs are external, not from a prior bodesign stage:
- The **product idea or brief** from the user/owner — the raw "what we want to build."
- A **reference design**, if the product is derived from one (aiguard derives from OpenMV N6 /
  STM32N657). When a reference exists, it is the electrical/architecture *baseline* — cite it by path
  and role (e.g. `refs/02.OpenMV` datasheets), and label derived facts as derived. Never paste
  proprietary source out of a provenance vault (`refs/` is gitignored — see `../../../AGENTS.md` if present).
- A **prior-generation PRD or real fabricated board**, if reorganising/archiving one (rockbox is a
  preserve-only archive of a shipped board). In that case copy originals verbatim into `source/` and
  never mutate them; your companions sit alongside and index them.

When a reference design or prior PRD exists, produce a **capability / gap identification table** as part
of discovery: each row a capability the baseline already provides (with its source — datasheet + page or
reference path), its **match level** to this product's need (full / partial / none), and the resulting
**gap** a downstream stage must close (which one). This is what keeps *derived ≠ invented* honest at the
system level — you see at a glance what's inherited vs. net-new, and every inherited claim carries
provenance. A capability row with no source is a defect, same rule as any field. (C00 only *identifies*
the gap; deciding how to close it — the part, the circuit — is C03/C05.)

If none of these exist yet, the PRD starts mostly `missing` — that is a legitimate honest state, not a
failure. You fill it by interviewing the owner, not by inventing plausible answers.

## SOP

The PRD is built as an **answer-state model**, then rendered to markdown (the source of truth) and
optionally to `.docx`. Working from a structured answer-state — not free-typing a doc — is what keeps
open items visible and prevents silent default-filling. The real examples
(`thesmart_products/openmv/C00-PRD/`, `thesmart_products/rockbox/c00-prd/`) follow exactly this shape.

### 0. Ingest the refs SSOT first (refs-first gate)

Before scaffolding anything, run the **`refs_ingest`** landing verb (`folder` = the stage dir or an
explicit `01_refs/` path; via `gate.py`). It scans the stage's `01_refs/` SSOT into a read-only
manifest: sources classified by media type, ranked against the authority order declared in the
baseline file, rich media flagged as unadjudicated. An absent/invisible root comes back
`root_visible: false` with a warning — loud, never a clean empty indistinguishable from a genuinely
empty folder. Two reasons this is step 0, not paperwork:

- **The interview cites by rank.** Step 2's answers carry `source` fields; the manifest's authority
  order is what resolves conflicting sources deterministically — not whichever file you opened
  first.
- **Downstream emitters are refs-gated.** The C00→C01 orchestration handoff and the C01/C02
  emitters refuse to run without the target stage's `01_refs/` SSOT (`RefsGateError
  REFS_SSOT_MISSING`). Preparing the refs tree now is what keeps the pipeline from failing at
  emit time instead of at intake.

### 0b. Decompose document-class refs into `.src` packages (paragraph-level anchors)

`refs_ingest` classifies and ranks, but it does NOT read content — a pptx/pdf authority source
stays an opaque blob to every downstream `source` citation. For each **document-class authority
source** (pptx / pdf / docx ranked in the baseline's authority order), run docxmcp
`document action=decompose` and land the package as a sibling `<stem>.src/` next to the original
inside `01_refs/`, with a short `PROVENANCE.md` (source sha256, decompose date, anchor format):

- pptx → `.src/content_list.json` gives slide-level text anchors (`content_list.json#<index>`).
- pdf → `.src/body.md` carries `<!-- page: N -->` markers (`body.md#page-N`).
- The `.src` is **read-only recon**; the original file stays authoritative. Never rebuild the
  source from its `.src`.

Why: answer-state `source` fields (step 2) can then cite **paragraph/page-level anchors** instead
of a bare filename — that is what makes a later fidelity audit (or a downstream stage's claim
check) mechanically resolvable. Proven in aiguard 0R: the deck-v3 pptx decomposed to 250
addressable slide-text entries; the X01 pdf to page-anchored body text.

### 0c. Adjudicate every rich-media source explicitly (the ledger gate)

`refs_ingest` flags rich media (pdf/pptx/docx/xlsx/image/cad) as `unadjudicated` — but the flag
alone has no teeth: nothing stops a downstream stage from silently citing (or silently IGNORING)
an unadjudicated image. The aiguard C00→C01 shape-break was exactly this failure: the ONE owner
concept image showing the intended product form sat `unadjudicated` for weeks while C01 invented
a different enclosure from nothing.

So: maintain `01_refs/Adjudication_Ledger.md`. One row per rich-media file:

- **nature** — what the artifact IS (appearance vision / board-level sketch / architecture
  diagram / spec document / vendor datasheet / photo reference);
- **verdict** — `adopted` (with a scoped role: what it IS authority for, and what it is NOT) /
  `rejected` / `superseded`;
- **basis** — the owner ruling date or DD number. No basis ⇒ may not be marked `adopted`.

Rule with teeth: **an unadjudicated rich-media source may not be cited as a fact source by
answer-state or any downstream stage** — and conversely, a source adjudicated `adopted` for a
role (e.g. "appearance direction authority") MUST be consumed by the stage owning that role.
Appearance/mechanical-intent images deserve special attention: they are exactly the sources the
text-biased interview flow tends to skip.

### 0d. Two-track stage-root layout (deliverables vs machine outputs)

Keep the stage root flat but classify every artifact into two tracks:

- **deliverables (for humans)**: `.docx` / `.pptx` / `.png` / `.xlsx` / `.pdf` — what an owner
  or vendor opens.
- **outputs (for AI/machines)**: `03_output/answer_state.json`, the `.generated.md` PRD projections,
  the handoff report, refs manifest, adjudication ledger, capability/gap table — what the next stage
  (or the next session) resolves claims against. **No AI-facing JSON/md stays at the stage root**;
  the root is reserved for human deliverables.

`01_refs/` holds external inputs (+ their `.src` packages), `02_build/` holds GC-able
intermediates (incl. docx `body.md` sources), `.history/` holds version backups and retired assets
(project convention, aligned with specbase's `.history/` snapshot rule) — retirement is never
deletion. The stage README states which track each root file belongs to.

### 1. Scaffold the answer-state

Copy `assets/answer_state.template.json` to `<project>/C00-PRD/03_output/answer_state.json`. It defines the
twelve PRD sections (s01–s12) plus the three RF-appendix sections (rf01–rf03), every field initialised
to `missing`. Set `project_name` and `include_rf` (true if the product has any radio).

The allowed field states — and the rule that **a status without a reason is a defect**:

| state | meaning |
|---|---|
| `missing` | not yet answered — the honest default |
| `drafted` | authored by you, not yet confirmed by the owner |
| `answered` | confirmed by the named owner (`source: user` or a cited reference) |
| `external-needed` | can only be filled by an external party (a lab, a vendor, the customer) |
| `blocked` | depends on another field/decision not yet made — name the blocker |
| `accepted-risk` | knowingly left open with owner sign-off — name who accepted it |

Every field also carries `owner`, `source` (where the value came from — `user`, a datasheet+page, a
reference path, a tool run), and `handoff_targets` (which downstream C-stage consumes it).

### 2. Fill the twelve sections by interview (don't fabricate — ask or mark missing)

Drive each field from the owner's answers. Where you can derive a fact from a cited reference (e.g. the
STM32N657 spec from the N6 datasheet), set `answered` with `source` = that reference + page/section. Where
you can't, set `missing`/`external-needed`/`blocked` with a reason — never a guess.

**Batch the high-leverage questions first.** Before drafting, ask the owner the 3–5 questions that unblock
the most fields — problem/goal, core scope, the hard boundaries (what's explicitly *not* in scope), the
headline targets (cost / quantity / certification), and the success metric. Use `AskUserQuestion` with
named options so the owner picks rather than free-types, and fold each answer back as `answered` with
`source: user`. Whatever the owner can't answer yet stays `missing`/`external-needed` — you ask, you don't
invent.

**Use the question catalog.** `references/prd-interview-guide.md` is the field-keyed question bank for this
whole collect-ideas loop — the interview protocol, the six cross-cutting dimensions to hit for every
requirement (what/why-not-how, priority & scope, measurable success, provenance, risk+mitigation+owner,
target≠result), and a per-section question list mapped one-to-one to the answer-state fields so each answer
drops straight in and renders into the docx with no translation step.

1. **s01 Business strategy** — `target_customer`, `problem_statement`, `business_goal`, `success_metric`,
   `market_or_use_context`. (`success_metric` typically carries the headline cost & maturity targets.)
2. **s02 Project overall** — `product_summary`, `primary_use_cases`, plus engineering scope and
   build-volume intent (e.g. EVT 50 sets → 500-unit pilot).
3. **s03 Objectives** — the numbered product goals (maturity to DVT, FPS/perf target, cost target, …).
   Each objective must be **verifiable**: state its acceptance criterion and how it's measured, so C06 can
   write a test against it. A goal with no measurable criterion is `drafted`, not `answered`. → feeds C06.
4. **s04 System architecture** — the product-level block diagram + a short narrative. This is the field
   that most directly seeds C03. Render the diagram with `drawmiat` (C4 / block) or an ASCII block as in
   the real PRDs; capture compute, memory, power chain, connectivity, sensors, I/O.
5. **s05 ID/ME requirements** — enclosure material & tooling, mount/form, dimensions (mark TBD where ID
   hasn't decided), front-face features, buttons/LEDs, ports, antenna keep-out, ingress/drop targets.
   → feeds C01/C02.
6. **s06 Electrical requirements** — application processor, flash/RAM, radios, PHY, camera/sensors,
   power input, charger, regulators, load switches, ESD/TVS, temperature range, ESD spec. Each component
   line should cite its source (reference design / datasheet). → feeds C03.
7. **s07 Software requirements** — on-device behaviour, operating modes, alerting, pairing, OTA/update,
   security, model/data management. → feeds C05.
8. **s08 Roles & responsibility** — discipline → owner → deliverable, for C00–C07. Often
   `external-needed` early (the org hasn't assigned owners) — leave it visibly open.
9. **s09 Assumptions & constraints** — the baseline assumptions and known limits (reference-design
   baseline, external-lab certification gates, out-of-scope items, TBC component choices). Keep this to
   standing assumptions/limits; program **risks** (with mitigation + owner) live in s10's risk register.
   → feeds C01/C02/C03/C06.
10. **s10 Project management** — stage-gate plan (EVT→DVT→pre-MP), sync cadence, change-control loop,
    issue tracking, and the **risk register**: each program risk with likelihood/impact, a mitigation,
    and an owner. A risk with no mitigation or owner is a worry, not a plan — record it `accepted-risk`
    with who signed off, or give it a mitigation (single-source parts, cert-fail risk, schedule slip).
11. **s11 Schedule** — milestone table vs M0 (PRD freeze, schematic+BOM, layout+gerber, EVT, verify,
    DVT). Mark due dates `TBC` until committed — a `drafted` schedule is honest; a fake one is not.
12. **s12 Team roster** — chip/module vendors, ODM/assembly, certification lab. Vendors TBC and lab TBC
    stay `external-needed`.

### 3. Fill the RF appendix (only if `include_rf`)

- **rf01 Product brief** — use case, region, radio standards, antenna context.
- **rf02 Objectives** — RF success criteria, link/range targets, power constraints.
- **rf03 RF specifications** — frequency bands, module/chip, antenna type, **certification_target**
  (FCC/IC/CE/PTCRB/NCC/JATE/TELEC…), test needs. The certification target is a *target only* — never a pass.

### 4. Compute readiness (don't round up)

Readiness = answered fields / total fields, but a stage is only **ready** when its gating sections are
answered. Compute and record:
- Field counts: `total`, `complete`, `partial` (drafted), `blocking` (missing/external-needed/blocked).
- **Document gates** — which document group is ready vs blocked, *naming the blocking sections*
  (e.g. `execution_control: blocked by s08, s10, s11, s12`).
- **Downstream handoff gates** — for each consumer stage, ready or blocked + the blocking sections
  (e.g. `C03: blocked by s09`; `C05: blocked by s08`).

Rockbox's real C00 sits at **74% (blocked)** with 18 blocking fields and roles/management/schedule still
open — and it says so on its face. That is the model: an honest in-progress PRD beats a fake-complete one.

### 5. Render the source-of-truth markdown

Generate `Project_Requirements.md` (and `RF_Requirements.md` if RF) from the answer-state. Every field
renders with its `state`, `owner`, `source`, and `handoff_targets` so **open items stay visible** in the
document, not just in the JSON. Put the status banner at the top (project, readiness %, human_approved,
"generated from answer_state.json; no hidden defaults applied"). `assets/render_prd.py` does this from the
template schema; or author the markdown by hand following the real examples' layout.

Companion accelerators (use to *populate sections*, then fold results back into the answer-state — they
do not replace it):
- `define-problem-statement` → s01 problem framing.
- `foundation-lean-canvas` → s01/s02 business model sanity.
- `discover-market-sizing` / `discover-competitive-analysis` → s01 market context (carry their
  confidence labels through; don't launder a range into a fact).
- `deliver-prd` → a richer PRD narrative for the s01–s07 body.
- `drawmiat` (C4/block) → the s04 architecture diagram.

### 6. Emit optional .docx and the handoff report

- For a `.docx` deliverable, go through the **docxmcp** MCP (Mode A: decompose a template → edit package
  markdown → assemble; or author fresh). Never hand-edit OOXML.
- Write `C00_Handoff_Report.md`: readiness %, blocked/ready, the next blocking question, human_approved
  flag, field counts, document gates, downstream handoff gates. This is the one-glance status the rest of
  the program reads.

### 7. Approval — leave it honestly open until it happens

`human_approved` stays `false` and the PRD stays **draft** until the named owner signs off. Do not flip
it yourself. Record the open approval question explicitly (rockbox's is literally *"Who approves PRD,
circuit, layout, FW spec, verification plan, and factory release?"*). PRD freeze is the C00 gate; until
it's signed, downstream stages may *read* the draft but must treat its targets as provisional.

## Deliverables

Audience-split filing (see `references/stage-structure.md`): human-facing at the stage root; AI/machine-facing in `03_output/`.

| Artifact | Path | Format | Audience / Role |
|---|---|---|---|
| Answer-state | `C00-PRD/03_output/answer_state.json` | JSON | AI — **source of truth** (in `03_output/`; resolver falls back to root for legacy projects) — field states, owners, sources, handoff targets |
| Project Requirements | `C00-PRD/03_output/Project_Requirements.md` | Markdown | AI — rendered SoT document (mirrors the answer-state, open items visible) |
| RF Requirements | `C00-PRD/03_output/RF_Requirements.md` | Markdown | AI — RF appendix (only if `include_rf`) |
| Handoff report | `C00-PRD/03_output/C00_Handoff_Report.md` | Markdown | AI — readiness %, gates, next blocking question, approval flag |
| Capability/gap table | `C00-PRD/03_output/Capability_Gap_Table.md` | Markdown | AI — baseline vs net-new with provenance |
| PRD / 彙編 / 交付報告 .docx | `C00-PRD/C00_*.docx` | docx | **Human** — the review deliverables (繁體中文, self-contained) |
| Module breakout | `C00-PRD/C00_模組Breakout.pptx` (+PNG) | PPTX/PNG | **Human** — s1 board/module partition + s2 functional architecture audit view (one deck, two projections) |
| Adjudication ledger | `C00-PRD/01_refs/Adjudication_Ledger.md` | Markdown | AI+Human — rich-media adjudication record |
| Preserved originals | `c00-prd/source/` | as-received | Archive track only — verbatim, never mutated |

The markdown + JSON are source-of-truth and version-controlled; `.docx`/SVG/PDF are generated and
regenerable. For a derived product, cite the reference by path; for an archive, the originals live under
`source/` and your companions index them.

## Gate / done-criteria

C00 is **genuinely complete (PRD freeze)** only when:
- Every gating section (s01–s12, plus rf01–rf03 if RF) is `answered` — or any open field is an
  *explicitly* `accepted-risk` / `external-needed` with a named owner and reason.
- All **downstream handoff gates** (C01/C02, C03, C05, C06) report ready, with no unnamed blockers.
- `human_approved: true`, set by the named approver — not by you.

Anything short of that is **draft / blocked**, and the handoff report must say so with the % and the
blocking sections. Partial is fine and normal; *fake-complete is the only failure mode that matters.*

## Honesty notes for this stage

Per `../../references/honesty-model.md`:
- **Mark the unproven, with a reason.** Every field carries a state + source; a bare value with no
  provenance is a defect. `missing`/`drafted`/`blocked`/`external-needed`/`accepted-risk` each need a why.
- **Targets are not results.** Cost/quantity/certification entries here are *targets the program commits
  to*, never achievements. Certification (FCC/CE/NCC/PTCRB…) is an external-lab gate — record the target,
  never a pass. C07 will read these targets and is bound by the same rule.
- **Open approvals stay visible.** `human_approved` is false until signed; the readiness % and blocking
  questions surface in the handoff report. Don't silently resolve an approval to make the doc look done.
- **Derived ≠ invented.** When the architecture/EE baseline comes from a reference, label it derived and
  cite the source. When data is genuinely absent (a component not yet chosen), mark it TBC/`missing` —
  exclude rather than guess.
- **Respect the vault.** Don't commit `refs/` content; for an archive track, preserve `source/` verbatim.

## Handoff to C01/C02/C03 (and C05/C06/C07)

Each downstream stage extracts specific sections — wired through the `handoff_targets` on every field, so
a consumer can pull exactly what it needs and see the field's state:

| Consumer | Extracts from C00 | Used for |
|---|---|---|
| **C01 ID** (`../c01-id/GUIDE.md`) | s05 (ID requirements), s02 use-cases, s09 constraints | design direction, CMF, screen UX, interface envelope |
| **C02 ME** (`../c02-me/GUIDE.md`) | s05 (ME: dimensions, mount, ingress/drop, ports, antenna keep-out), s09 | enclosure constraints, STEP/SCAD draft |
| **C03 EE** (`../c03-ee/GUIDE.md`) | s04 architecture, s06 electrical requirements, s09 constraints | design definition, schematic, BOM, netlist, GPIO map |
| **C05 FW** (`../c05-fw/GUIDE.md`) | s07 software requirements, s02 use-cases, s08 owner | firmware functional spec, modes/state machine |
| **C06 Verify** (`../c06-verify/GUIDE.md`) | s03 objectives, s01 success metric, s09 | test plan acceptance criteria, cross-check targets |
| **C07 MFG** (`../c07-mfg/GUIDE.md`) | **cost & quantity targets** (s01/s02/s03), **certification targets** (rf03/s09) | cost gate, build volume, cert plan |

### Mother-source matrix — what C00 must PROVIDE each layer (machine-checkable intent)

The table above says what each consumer *reads*; this matrix says what C00 must have *produced and
kept current* for that read to be possible. Every row is a C00 obligation — if the artifact is stale
relative to a newer owner ruling (DD-N), C00 is NOT done, even if the file exists:

| Consumer | Required mother-source artifacts (beyond the PRD text) | Staleness trigger |
|---|---|---|
| **C01 ID** | s05 ID intent fields; `01_refs/Adjudication_Ledger.md` (adjudicated concept images) | a form-factor ruling (like DD-11) not reflected in s05 / ledger |
| **C02 ME** | s05 envelope/mounting/environment fields; zone/partition logic when the enclosure is multi-zone | enclosure logic change without s05 update |
| **C03 EE** | s04 subsystems + `C00_模組Breakout.pptx` (s1 board partition · s2 functional blocks); s06 electrical fields | any partition or subsystem ruling not re-rendered into BOTH slides |
| **C04 Layout** | (indirect via C03/C02) the breakout's board-count/partition premise; certification target (review severity) | board-partition premise invalidated (e.g. single-board → multi-zone) without a breakout re-issue |
| **C05 FW** | s07 software fields; s06 IC inventory; s08 owner matrix | behaviour/mode ruling not in s07 |
| **C06 Verify** | s03 acceptance criteria; s01 success metric; s09 risks/accepted gaps | acceptance change not in s03 |
| **C07 MFG** | **explicit cost / quantity / certification target fields with `handoff_targets: ["C07"]`** + a C07 gate row in the handoff report | targets exist only as prose in s01–s03 with no C07-tagged field (defect: C07 cannot pull) |

Downstream stages should treat the PRD as authoritative-but-provisional until `human_approved: true`;
if a target changes later, write it back here as a new version (keep a version-history table) so the
contract stays single-sourced.

## Tools & companion skills

- **Engines:** none of the KiCad/kidoc engines are needed to *author* C00 (no schematic/PCB exists yet).
  The doc engine (`../../engines/kidoc/`) is only relevant later when a stage emits a formal PDF.
- **Companion skills (accelerators, fold results back into the answer-state):** `define-problem-statement`,
  `foundation-lean-canvas`, `discover-market-sizing`, `discover-competitive-analysis`, `deliver-prd`,
  `drawmiat`/`miatdiagram` (architecture diagram).
- **Document artifacts:** the **docxmcp** MCP for `.docx`/`.pdf` (never hand-edit OOXML); `xlsx` if a
  target/cost table is wanted as a sheet.
