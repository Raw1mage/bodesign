# C00 PRD — Product Requirements (the root of the lifecycle)

The PRD is the contract every downstream stage reads. It fixes **what we're building, why, for whom,
and to which targets** — and it does so *honestly*: an unanswered requirement stays visibly open, an
approval that hasn't happened stays unapproved. C03 reads its constraints here, C07 reads its
cost/quantity/certification targets here, C01/C02 read the ID/ME envelope here. If the PRD lies, every
stage downstream inherits the lie. So this stage is fully specified below — you author the whole thing,
not "go run a skill."

Read `../../references/honesty-model.md` before writing a single field. It overrides everything here.

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

Produce **all** of these in this stage before you report C00 done or hand off (see SKILL.md
§ "Definition of Done"). Each must exist on disk **or** carry an explicit `blocked`/`external-needed`
status with a reason + owner — silent absence is not allowed.

| # | Required artifact | File | Notes |
|---|---|---|---|
| 1 | Answer state | `C00-PRD/answer_state.json` | every gating field `answered` or honestly `accepted-risk`/`external-needed` |
| 2 | Project requirements (PRD) | `C00-PRD/Project_Requirements.md` (`.generated.md`) | the twelve sections; `.docx` optional |
| 3 | RF requirements | `C00-PRD/RF_Requirements.md` (`.generated.md`) | **only if the product has RF**; else mark N/A with reason |
| 4 | Handoff report | `C00-PRD/C00_Handoff_Report.md` | downstream gates (C01/C02/C03/C05/C06) ready/blocked |

**Self-verify:** run `bodesign_c00_readiness` (`folder`) and report which fields/sections are still
open. C00 is not done while any gating section is unanswered without an honest accepted-risk/external
owner. Model: `thesmart_products/rockbox/c00-prd/`.

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

If none of these exist yet, the PRD starts mostly `missing` — that is a legitimate honest state, not a
failure. You fill it by interviewing the owner, not by inventing plausible answers.

## SOP

The PRD is built as an **answer-state model**, then rendered to markdown (the source of truth) and
optionally to `.docx`. Working from a structured answer-state — not free-typing a doc — is what keeps
open items visible and prevents silent default-filling. The real examples
(`thesmart_products/openmv/C00-PRD/`, `thesmart_products/rockbox/c00-prd/`) follow exactly this shape.

### 1. Scaffold the answer-state

Copy `assets/answer_state.template.json` to `<project>/C00-PRD/answer_state.json`. It defines the
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

1. **s01 Business strategy** — `target_customer`, `problem_statement`, `business_goal`, `success_metric`,
   `market_or_use_context`. (`success_metric` typically carries the headline cost & maturity targets.)
2. **s02 Project overall** — `product_summary`, `primary_use_cases`, plus engineering scope and
   build-volume intent (e.g. EVT 50 sets → 500-unit pilot).
3. **s03 Objectives** — the numbered product goals (maturity to DVT, FPS/perf target, cost target, …).
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
   baseline, external-lab certification gates, out-of-scope items, TBC component choices). → feeds
   C01/C02/C03/C06.
10. **s10 Project management** — stage-gate plan (EVT→DVT→pre-MP), sync cadence, change-control loop.
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

| Artifact | Path | Format | Role |
|---|---|---|---|
| Answer-state | `C00-PRD/answer_state.json` | JSON | **Source of truth** — field states, owners, sources, handoff targets |
| Project Requirements | `C00-PRD/Project_Requirements.md` | Markdown | Rendered SoT document (mirrors the answer-state, open items visible) |
| RF Requirements | `C00-PRD/RF_Requirements.md` | Markdown | RF appendix (only if `include_rf`) |
| Handoff report | `C00-PRD/C00_Handoff_Report.md` | Markdown | Readiness %, gates, next blocking question, approval flag |
| PRD .docx | `C00-PRD/Project_Requirements.docx` | docx | Optional, via docxmcp |
| Architecture diagram | `C00-PRD/source/` or inline | SVG/PPTX | Optional, via drawmiat |
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
