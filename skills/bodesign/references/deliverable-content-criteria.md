# Deliverable content criteria — is this document good enough to hand over?

**What this is.** The **acceptance criteria** for bodesign's *document* deliverables — HDD, CE
technical file, ICD, design review package, manufacturing-transfer package (and the PRD, which
already had half of this). The subject of every clause below is **one finished document about to
leave the building**, not a stage that has work to do.

**Why it exists.** Every other review artefact in this skill has a board, a schematic, or a stage as
its subject. `stages/c04-layout/references/layout-review-method.md` reviews *a board*;
`SKILL.md` § "Pre-implementation design review" reviews *a design intent*; each stage's
"Required deliverables — Definition of Done" checks *file existence plus placeholder strings*
(`../SKILL.md:144-154`). None of them answers "this .docx is generated, structurally complete, and
free of `TBC` — is its **content** worth reading?" A generated document passes every existing gate
while saying nothing. That gap is what this file closes.

**SOP vs criteria — the distinction this file lives or dies on.** A stage GUIDE tells you *how to
produce* the document. This file tells you *whether the produced document is good enough*. If a
clause here reads like an instruction to an author ("write the power tree first"), it is in the
wrong file. Every clause here must be applicable by a reader who has **only the finished document**
and the project tree, and who did not write it.

**This file references, it does not restate.** The judgment machinery — forced-find, the finding
schema, severity levels, the verdict vocabulary — already exists in
`../stages/c04-layout/references/layout-review-method.md`. Content-layer honesty rules already exist
in `honesty-model.md`. This file **points at them and adds the per-document content rows they never
covered**. If you find yourself copying a paragraph from either, stop: two copies of one fact drift
silently, and the drift is invisible until someone acts on the stale one.

---

## 0. How to run a content review (the borrowed machinery)

Borrowed verbatim by reference — do not re-implement:

| Machinery | Where it is defined | Applies here how |
|---|---|---|
| Forced-find contract (≥2 candidate concerns; zero findings **and** zero ruled-out is itself a review defect) | `../stages/c04-layout/references/layout-review-method.md:30-45` | A document review that returns "looks complete" with no ruled-out candidates has not been done |
| Finding schema (`rule_ref` + `evidence_source` mandatory; a finding without both is a hunch) | `../stages/c04-layout/references/layout-review-method.md:76-103` | `rule_ref` here = the criterion id below (e.g. `HDD-C3`); `evidence_source` = the document section + the project file that should have backed it |
| Severity four-level scale — **critical / major / minor / info**, no fifth level | `../stages/c04-layout/references/layout-review-method.md:105-116` | Per-criterion severity is fixed in the tables below |
| Verdict vocabulary APPROVE / APPROVE_WITH_CONCERNS / REJECT | `../stages/c04-layout/references/layout-review-method.md:130-143` | Same three; a REJECT is cleared by fixing the document's content, never by relabelling the criterion |
| Independent multi-pass, dedup by category | `../stages/c04-layout/references/layout-review-method.md:64-74`, `:118-128` | Optional here; use for documents that leave the company |

**Severity meaning in a document context** (same four names, same ordering, mapped to the document
gate instead of the DRC gate):

| Severity | In a document | Effect |
|---|---|---|
| **critical** | The document makes a claim it is not entitled to make (see § 6), or a human gate has been declared satisfied by the generator | Document may **not** be handed over. REJECT. |
| **major** | A required content row is absent, or present but carries no evidence anchor | Handover blocked until filled or honestly marked `pending`/`not-run` with a reason and owner (`honesty-model.md:18-21`) |
| **minor** | Content present and anchored but thin, inconsistent formatting of anchors, ordering nits | Documented, does not block |
| **info** | Improvement suggestion | No gate effect |

**Absence is not automatically a finding.** A row that is honestly marked with a status **and a
reason and an owner** is compliant — that is the honesty model's explicit escape
(`honesty-model.md:18-21`, `../SKILL.md:94-99`). A row that is *silently* absent, or present as a
fluent paragraph with nothing behind it, is a finding at the severity in its table.

---

## 1. The three tests every criterion below had to pass

Stated so you can extend this file without diluting it, and so you can reject a criterion someone
adds later.

1. **Document-subject test.** Can the criterion be applied by someone holding only the finished
   document and the project tree? If it needs to know *how the document was produced*, it is an SOP
   line, not a criterion. **This permits running a deterministic query** against the project tree
   (a readiness verb, `list_blockers`, a netlist export) — what it forbids is a criterion that can
   only be settled by asking the author what they intended.
2. **Two-reviewer test.** Would two independent reviewers reach the **same verdict** on the same
   document? "Content must be substantial" fails. "Every entry in the interface list names a
   direction and a voltage level, or is marked `unknown` with a reason" passes.
3. **Human-gate test.** If a criterion would require the reviewer to judge *sufficiency of
   engineering intent* rather than presence-and-anchoring of content, it does **not** become a vague
   criterion — it becomes a **human DECIDE node** (§ 5) and is named as one. There is no third
   option, and no path by which an AI declares a human gate satisfied (`AGENTS.md` 天條 2;
   `honesty-model.md:23-26`).

**Anchor.** Several criteria below require an *evidence anchor*. An evidence anchor is one of the
five bases enumerated in `../engines/kicad/references/report-generation.md:43-47`
(datasheet-verified / extraction-verified / raw-file verified / analyzer-derived / inference-only),
carried in the document text or its companion JSON. "Inference-only" **is** a valid anchor — it is
an honest label, and it is exactly what the same file forbids calling "verified" (`:49`). An
unanchored engineering claim is what fails, not a modestly-labelled one.

---

## 2. Criteria by deliverable

Each table: the content row, the auditable form of "present", and the severity when it is missing
without an honest status. Rows marked **H** are human DECIDE nodes — see § 5; a generator may fill
the surrounding text but may never mark the row satisfied.

### 2.1 HDD — Hardware Design Document

Generation spec (which analyzer feeds which section): `../engines/kidoc/references/report-hdd.md`.
That file says nothing about content adequacy; this table does.

| id | Content row | Auditable form of "present" | Missing ⇒ |
|---|---|---|---|
| HDD-C1 | **Design intent per subsystem** | Each of {power, clocking, reset, each bus in the Signal Interfaces section} has ≥1 sentence stating *why this topology*, not only *what it is*. A section that only restates the generated table is not intent. | major |
| HDD-C2 | **Every electrical value anchored** | Each numeric electrical claim (rail voltage, current budget, divider ratio, filter corner, thermal margin) carries an anchor per § 1. Values reproduced from analyzer output count as `analyzer-derived`. | critical if the claim is presented as verified without one (`../engines/kicad/references/report-generation.md:49`); otherwise major |
| HDD-C3 | **Power budget closes** | The power section's per-rail load total is stated and compared against the source's rating; a delta is either ≤ the stated headroom or is an open item with an owner. A table of rails with no total is not a budget. | major |
| HDD-C4 | **Skipped analyses disclosed** | Every section whose data source was absent appears with a `not-run`/`no data` status **and the reason**, per `../engines/kicad/references/report-generation.md:51-55` "Skipped Analysis Disclosure" and `honesty-model.md:18-21`. Silent omission of a section listed in `../engines/kidoc/references/report-hdd.md:11-81`. | major |
| HDD-C5 | **Compliance section claims only targets** | The Compliance and Standards section lists standards as *targets/plan*; no standard is written as met/passed. See `honesty-model.md:23-26` and `../stages/c06-verify/GUIDE.md:20-26`. | critical if any is written as passed |
| HDD-C6 | **Reader can act** | The Test and Debug section names, for each debug interface, what is exposed and how to reach it (connector ref or test-point net). A generic paragraph naming no refdes fails. | minor |
| HDD-C7 **H** | **Is this design sound?** | Not decidable from the document. Human EE owner. See § 5. | — |

### 2.2 CE technical file

Generation spec: `../engines/kidoc/references/report-ce.md`. Defaults there (EN 55032 / EN 55035 /
EN 62368-1 / EN IEC 63000, `:31-33`) are *defaults*, not findings of applicability.

| id | Content row | Auditable form of "present" | Missing ⇒ |
|---|---|---|---|
| CE-C1 | **Nothing is declared conformant** | The Declaration of Conformity section is a *template with the signature block unsigned*, and no directive is stated as met. Any "complies with" written as fact. | **critical** — this is the single highest-risk row in the whole file (`honesty-model.md:23-26`; `../stages/c06-verify/GUIDE.md:20-22`) |
| CE-C2 | **Directive applicability justified** | Each directive in the mapping table has a one-line reason it applies or does not (e.g. "RED: applies — BLE module U7"; "RED: N/A — no radio in BOM"). An auto-populated table with no reasons fails; N/A must carry a reason, same rule as `../stages/c04-layout/references/layout-review-method.md:60-62`. | major |
| CE-C3 | **Standards list is scoped, not defaulted** | Each harmonized standard is either tied to a product characteristic, or explicitly labelled as the tool default pending review. A default silently presented as a selection. | major |
| CE-C4 | **Risk assessment rows are populated or open** | Each hazard row (electrical shock / overheating / EMI / ESD / mechanical) has a risk level *with its basis*, or is an explicitly open cell with an owner. `../engines/kidoc/references/report-ce.md:37` leaves unfilled cells by design — an unfilled cell that is not marked open reads as "assessed, low". | major |
| CE-C5 | **EMC/thermal figures labelled as analysis, not test** | Any EMC or thermal number states it came from the analyzer, not a lab. | critical if presented as lab data |
| CE-C6 **H** | **Is the file complete for submission?** | Regulatory judgment. Human / compliance owner. See § 5. | — |

### 2.3 ICD — Interface Control Document

Generation spec: `../engines/kidoc/references/report-icd.md`.

| id | Content row | Auditable form of "present" | Missing ⇒ |
|---|---|---|---|
| ICD-C1 | **Every signal has direction and level** | For each row in every connector's signal table: direction (in/out/bidir) and voltage level are given, or the cell says `unknown` with the reason. An ICD whose value is consumed by the other side of the interface cannot leave these blank. | major |
| ICD-C2 | **Placeholders are visible as placeholders** | `../engines/kidoc/references/report-icd.md:29-31` and `:40` generate narrative *placeholders* for protocol/timing and voltage min/max. Each such placeholder still bearing generated wording is marked `TBD` + owner, or removed. A fluent placeholder paragraph left in as if it were content. | major |
| ICD-C3 | **Connector identity is unambiguous** | Each connector entry gives refdes **and** MPN or a mating-part reference. "USB-C connector" alone does not let the other side build to it. | major |
| ICD-C4 | **Protocol/timing stated or scoped out** | For each bus, either the timing-relevant parameters are given, or the ICD states that this interface is specified elsewhere and names where. Silence. | major |
| ICD-C5 | **Pin numbering matches the source** | Connector pin numbers in the document are traceable to the schematic/pinmap export, not renumbered for readability. Verify against the C03 pinmap. | critical if they diverge |
| ICD-C6 **H** | **Is this interface agreed with the counterparty?** | Two-party agreement. Human. See § 5. | — |

### 2.4 Design review package

Generation spec: `../engines/kidoc/references/report-design-review.md`. **Read `:57-60` first**: the
Action Items section's data source is literally `config (pre-seeded template row)`. The package can
therefore be generated complete, formatted, placeholder-free, and contain **no actual review**.
That is the exact failure this file exists for.

| id | Content row | Auditable form of "present" | Missing ⇒ |
|---|---|---|---|
| DR-C1 | **A review actually happened** | The Action Items / findings table contains ≥1 row whose text is not the pre-seeded template row, **or** an explicit statement that the review found nothing together with the ruled-out candidates that prove engagement (`../stages/c04-layout/references/layout-review-method.md:30-45`). A package carrying only the seeded row. | **critical** |
| DR-C2 | **Findings carry `rule_ref` + `evidence_source`** | Per `../stages/c04-layout/references/layout-review-method.md:98-103`. A finding with neither is a hunch and must be grounded or dropped. | major |
| DR-C3 | **Applicable G2 scenarios all appear** | Each of the five minimum scenarios in `../SKILL.md:334-341` (power sequencing / reset chain / I²C address / level compatibility / diff-pair topology) is present with a conclusion, or marked N/A **with a one-line reason** (`../stages/c04-layout/references/layout-review-method.md:60-62`). | major |
| DR-C4 | **Verdict matches the findings** | An `APPROVE` while a ≥ major finding is open, or an `APPROVE_WITH_CONCERNS` whose concerns are not carried as findings ≥ major, is a contradiction (`../SKILL.md:344-350`). | critical |
| DR-C5 | **Action items are assigned** | Each action item has an owner and a state. Un-owned items disappear. | major |
| DR-C6 **H** | **Approve / reject** | The verdict itself. Human reviewer of record. See § 5. | — |

### 2.5 Manufacturing transfer package

Generation spec: `../engines/kidoc/references/report-manufacturing.md`. Note `:36-39` (Assembly
Instructions, data source **none — narrative placeholder**) and `:41-44` (Production Test
Procedures, **pre-seeded checklist**): two whole sections are generated with no project data in
them at all.

| id | Content row | Auditable form of "present" | Missing ⇒ |
|---|---|---|---|
| MFG-C1 | **Fab parameters are chosen, not defaulted** | `../engines/kidoc/references/report-manufacturing.md:31-34` supplies defaults (1.6 mm, 1 oz, HASL/ENIG, IPC Class 2). Each such parameter is either tied to a design requirement / the C04 stackup, or explicitly labelled as an unreviewed tool default. A default silently presented as a specification. | major |
| MFG-C2 | **Assembly instructions are project-specific** | The section names at least the project's sensitive parts (moisture-sensitive, hand-solder, shielding cans, connectors requiring fixtures) — or states that none exist. | major |
| MFG-C3 | **Test procedures have pass/fail criteria** | Each of the checklist steps has a criterion a factory operator can apply (a measurable value, an expected LED state, a programming return code), or is marked TBD with an owner. A step with no criterion is not a test. | major |

| MFG-C4 | **BOM rows are orderable** | Every non-DNP row has an MPN or an explicit "customer-supplied"/"to be sourced" marker. | major |
| MFG-C5 | **No claim of a built board** | The package describes *pre-fabrication readiness*; nothing is written as produced, tested or yielded (`honesty-model.md:54-55`). | critical if violated |
| MFG-C6 **H** | **Release to manufacturing** | Human + the fab-release gate (`AGENTS.md` 天條 3). See § 5. | — |

### 2.6 PRD — the row that already existed

C00 already carries content criteria; they are **not** restated here. Use them directly:

- Field state vocabulary + "a status without a reason is a defect" —
  `../stages/c00-prd/GUIDE.md:182-194`.
- **Objectives must be verifiable**: "Each objective must be verifiable: state its acceptance
  criterion and how it's measured … A goal with no measurable criterion is `drafted`, not
  `answered`" — `../stages/c00-prd/GUIDE.md:219-221`. This is the shape every criterion in this
  file imitates.
- Six cross-cutting dimensions per requirement (what/why-not-how, priority & scope, measurable
  success, provenance, risk+mitigation+owner, target ≠ result) —
  `../stages/c00-prd/references/prd-interview-guide.md:41-48`.
- `human_approved` stays false until the named owner signs — `../stages/c00-prd/GUIDE.md:301-305`.

Reviewing a PRD's content = applying those, with the severity scale of § 0.

---

## 3. Cross-document criteria (apply to all five)

| id | Content row | Auditable form | Missing ⇒ |
|---|---|---|---|
| X-C1 | **Status vocabulary used, with reasons** | Every unproven item carries `draft`/`pending`/`not-run`/`assumption` **and a reason** (`honesty-model.md:18-21`). A bare label is itself a defect, per that rule. | major |
| X-C2 | **No adjective standing in for evidence** | Claims of quality use a shown quantity, not an adjective. `honesty-model.md:28-31`: "269/269 nets matched a known-good reference" is shown; "robust, production-ready" is empty. Scan the executive summary first — that is where empty adjectives concentrate. **Weak criterion, knowingly kept**: deciding which sentence *is* a quality claim has no criterion of its own, so two reviewers may flag different sets. It is retained because its errors are one-directional — it does not let an empty document through, it only misses some empties. Do not read a clean X-C2 as "no empty claims". | minor, unless the adjective asserts a gate outcome ⇒ critical |
| X-C3 | **Gaps documented, not back-filled** | Where source data was missing, the document records a *source-data limit* rather than a plausible fill (`honesty-model.md:33-36`). A plausible-looking value with no anchor is the failure. | critical |
| X-C4 | **Cross-document numbers agree** | A value appearing in two of these documents (rail voltage, board dimension, component count, connector pin count) is the same value, or the difference is explained. Check ≥3 shared numbers. | major |
| X-C5 | **Open cross-stage blockers surfaced** | If `list_blockers(folder, unresolved_only=True)` names the stage that owns this document, the document says so (`../SKILL.md:101-109`, `cross-stage-reconciliation.md:12-17`). A document that reads clean while an open reconciliation exists is misleading by omission. | major |

---

## 4. Inference-leap patterns — where a sound input becomes an unsound claim

A document can be fully anchored and still wrong, because the **anchor supports a narrower claim
than the sentence makes**. Every pattern below is a place where a legitimate source is stretched by
one step. Reviewing for these is separate from reviewing for anchors: X-C2/X-C3 catch *missing*
evidence; this section catches evidence that is *present but over-read*.

**Already written into this repo** — these are existing SSOT, cited not restated:

| Leap | Rule that forbids it |
|---|---|
| *It was generated* ⇒ *it is correct* | `../stages/c03-ee/references/pinout-to-circuit-method.md:30`, `../stages/c03-ee/references/schematic-drawing-rules.md:104` (`Generation ≠ correctness`); `../SKILL.md:236-239` |
| *A tool returned a verdict* ⇒ *it is certified* | `../stages/c06-verify/GUIDE.md:290`, `:20-26` (`Verdicts ≠ certification`) |
| *A target was committed* ⇒ *it was achieved* | `../stages/c00-prd/references/prd-interview-guide.md:48` (`Target ≠ result`) |
| *The row claims a symbol source* ⇒ *the part is drawn in the schematic* | `../stages/c03-ee/GUIDE.md:484` (R3 vs R5 not interchangeable) |
| *An analyzer produced it* ⇒ *it is verified* | `../engines/kicad/references/report-generation.md:47-49` (`inference-only`; the word "verified" is forbidden for analyzer-only claims) |
| *ERC/DRC passed* ⇒ *the net partition is what was intended* | `../SKILL.md:455-459` and `../stages/c03-ee/GUIDE.md:488` (ERC is blind to collinear-wire net fusion; the fidelity gate is a separate check) |
| *The machine gate is 0* ⇒ *the rendered output is fine* | `../stages/c03-ee/GUIDE.md:489-490` (render-layer QA and a fresh-eyes pass are separate gates) |

**Newly named here** — patterns that pass every existing rule and still yield a false claim. Each is
a *new induction* from this repo's material unless a line reference is given.

| id | Leap | Why it clears the existing rules | What the document must say instead |
|---|---|---|---|
| **L1** | **Datasheet says "supports X"** ⇒ **"X works in this design"** | `AGENTS.md` 天條 4 requires a datasheet-grounded lookup (`bodesign_datasheet_lookup` / `bodesign_vault_spec_check`) behind an electrical claim — and here that lookup was genuinely performed and returned a real page anchor. 天條 4 is satisfied on its own terms; the leap happens *after* it, in what the sentence does with the result. But the datasheet claims a **part capability under the vendor's reference conditions**, while the document claims a **system behaviour** — which additionally depends on the circuit around it, the firmware, and the boot configuration, none of which the datasheet saw. | "U7 datasheet p.12 lists X as a supported mode. Not yet exercised in this design — circuit/firmware/boot config unverified." Hardware instance: a competitor BT module's datasheet states *Classic BT supported*, with **no concurrency performance figures**; "supports Classic BT" does not license "sustains Classic BT concurrently with the rest of the link budget". |
| **L2** | **A capability is listed** ⇒ **it performs adequately** | A listed feature has no performance dimension attached, so no rule about numbers fires. | Name the missing dimension: throughput / concurrency / duty cycle / range / temperature. Absent a number, the claim is `inference-only` (`../engines/kicad/references/report-generation.md:49`). |
| **L3** | **A reference design does it** ⇒ **our derived design does it** | Provenance is real and citable, so rule 2 (`honesty-model.md:13-16`) is satisfied. But a derivative differs by exactly the deltas that were introduced. | State the deltas, then the claim. The `reference_baseline` block (`../SKILL.md:191`) exists to render derived-from / diffs / sourcing-gates for this reason. |
| **L4** | **Component-level rating** ⇒ **system-level rating** | Every component figure is datasheet-anchored, so 天條 4 passes at each row. The leap happens in the *summation*: ratings hold under per-part conditions (25 °C, single-rail, no derating) that do not co-occur in the assembled system. | Present as a per-part table plus a stated assumption set; the system figure is `assumption` until measured (`honesty-model.md:18-21`). |
| **L5** | **The section exists and is well-formed** ⇒ **the underlying analysis ran** | Placeholder/pre-seeded sections generate as complete prose. Existence checks and `TBC` scans both pass. `../engines/kidoc/references/report-manufacturing.md:36-44` and `../engines/kidoc/references/report-design-review.md:57-60` are the documented instances. | Every section states its data source or `not-run` + reason (HDD-C4, DR-C1, MFG-C2/C3). |
| **L6** | **A default value appears in a spec table** ⇒ **it was specified** | Defaults are legitimate tool behaviour (`../engines/kidoc/references/report-manufacturing.md:31-34`, `../engines/kidoc/references/report-ce.md:31-33`) and look identical to decisions in the rendered table. | Mark the provenance of each value: chosen (with source) vs tool default pending review (MFG-C1, CE-C3). |
| **L7** | **No finding was reported** ⇒ **there is no problem** | A zero-finding result is indistinguishable from a review that never engaged — the same absence/failure collision `../stages/c04-layout/references/layout-review-method.md:30-41` addresses with forced-find, and the reason a zero-finding pass with zero ruled-out candidates is itself a defect. | Report what was examined and ruled out, with evidence, not only what was found (DR-C1). |
| **L8** | **An earlier stage marked it done** ⇒ **the claim is still true** | Stage DoD is evaluated once, against the artefacts of that moment; a later change does not retroactively invalidate the recorded status. | Restate downstream claims against the current artefacts, or cite the stage record **with its date/revision**. Cross-check with X-C4. |

**How to use this table in a review.** For each substantive claim in the document, ask: *what is the
narrowest statement the cited evidence supports?* If the sentence says more than that, it is an L-row
finding — severity **critical** when the claim is about a gate, a certification, or a system-level
behaviour; **major** otherwise.

---

## 5. Human DECIDE nodes — what an AI may never mark satisfied

These are not gaps in this file; they are **where judgment legitimately stops being auditable**.
Criterion-3 of § 1 routes anything unauditable here rather than into vague prose. Every one of them
already exists elsewhere in the skill; this is an index with the reason each belongs in this class.

| Node | Defined at | Why it is human, not criterion |
|---|---|---|
| External compliance gates — EVT/DVT, FCC Part 15, CE RED, CISPR/EN 55032, IEC 62368-1, RoHS/REACH, ESD | `honesty-model.md:23-26`; `../stages/c06-verify/GUIDE.md:20-26` | The verdict is produced by an external lab or a physical build. No amount of document content can substitute; recording *target + plan* is the maximum bodesign may do. (Covers HDD-C7 in part, CE-C6, MFG-C6.) |
| `me_approved` (mechanical) | `../stages/c02-me/GUIDE.md:145-147` | Named as **always false** inside bodesign — a human gate by construction. |
| Final ID / CMF / UI sign-off, and acceptance of C02–C05 conflicts | `../stages/c01-id/GUIDE.md:212`, `:261-284` | C01 has a dedicated "Human / ID Must Decide" list; taste, brand fit and proportion are not auditable by criterion. |
| PRD approval (`human_approved`) | `../stages/c00-prd/GUIDE.md:301-305` | Freeze of the requirement baseline; the named owner signs, the generator does not flip the flag. |
| Accepting a cross-stage risk | `cross-stage-reconciliation.md:16-17` | Stated verbatim: *AI never accepts a cross-stage risk alone*. |
| Send-to-fab / release to manufacturing | `AGENTS.md` 天條 3 | Requires deterministic validation **plus** explicit user approval. |
| Design review verdict (DR-C6) | `../SKILL.md:344-353` | The verdict is the reviewer's judgment; the gate only checks that a review happened and produced one. |
| "Is this design sound?" (HDD-C7) | — | Deliberately not written as a criterion: two reviewers would not converge. What *is* auditable is that the intent is stated (HDD-C1) and the values are anchored (HDD-C2); soundness itself is the EE owner's call. |
| "Is the interface agreed?" (ICD-C6) | — | Requires the counterparty's assent, which is not a property of the document. |

**Rule.** A review of any deliverable may report these as *open, with the named owner*. It may never
report them as met, and no criterion in § 2 may be read as implying them. This preserves 天條 2 /
`honesty-model.md` rule 1: a truthful "pending" beats a false "complete".

---

## 6. Where this file is deliberately silent

Stated so a reviewer does not read silence as approval:

- **Engineering correctness.** Nothing here judges whether a topology is the right one. That is
  HDD-C7 / the G2 review / the EE owner.
- **Writing quality.** Style, tone and 繁體中文 phrasing are out of scope; the document-language
  rule lives in `../SKILL.md:81-92`.
- **Documents outside the five (plus PRD).** C01/C02/C05 stage artefacts have their own honesty
  notes in their guides; this file does not generalise to them.
- **Automation.** These criteria are **not** currently machine-checked. `dod_ok` / `guide_compliance`
  (`../SKILL.md:144-154`) checks existence and placeholder strings; that is a different question and
  passing it says nothing about any row above.

---

## 7. Reviewer's one-page procedure

1. Identify the deliverable; open its table in § 2 plus § 3.
2. Apply forced-find (`../stages/c04-layout/references/layout-review-method.md:30-45`) — you must produce ≥2 candidates, found or
   ruled out with evidence.
3. Walk each row; record findings in the schema at `../stages/c04-layout/references/layout-review-method.md:81-96` with `rule_ref` =
   the criterion id and `evidence_source` = document section + the project file that should back it.
4. Sweep the substantive claims against § 4.
5. List every § 5 node the document touches as **open, owner named** — never as met.
6. Verdict per `../stages/c04-layout/references/layout-review-method.md:130-143`. A `critical` open ⇒ REJECT; `major` open ⇒
   handover blocked until filled or honestly statused; `minor`/`info` documented.

---

## 8. Provenance

New file (2026-09-03). It adds the *document-content* layer that the existing review machinery never
covered, and it **references rather than copies** every rule it depends on — `honesty-model.md`, the
C04 review method, the C03 gate contract, the C00 PRD field discipline, the kidoc generation specs
and the `report-generation.md` evidence-basis vocabulary all remain the single source of truth for
what they define. The inference-leap table's L1 hardware instance (a BT module datasheet stating
"supports Classic BT" with no concurrency data) is cited by permission of the originating fleet's
duty officer; L2–L8 are induced from this repo's own documented failures where noted.

## 9. How this file's own citations were checked — and how that check failed first

This file is almost entirely `file:line` citations, so the audit of those citations *is* the audit of
the file. That audit had two defects during review (2026-09-03). Both are recorded here because the
next person to extend this file will write the same probe.

**Defect 1 — the probe's corpus was smaller than the probe believed.** Round 1's citation audit
reported `TOTAL_CITATIONS=53 BAD=0`. The `BAD=0` was true *of the corpus the probe built*. That
corpus came from a regex matching `` `path.md:NN` ``, which silently excluded the bare continuation
form `` `:NN` `` used when a citation reuses the preceding path. Actual occurrences: **78**. Five
citations were never examined, and one of them was wrong — report-generation.md line 51 (a section
heading) cited where line 49 (the prohibition on the word "verified") was meant. A
narrowed corpus and a genuinely clean result produce the **same output**: a small number next to
`BAD=0`, which reads as thoroughness.

**Defect 2 — a positional correction applied as a batch translation.** Inserting the entry pointer
added 12 lines to `../SKILL.md` above line 156, so citations below that point needed +12. That offset
was applied to the batch instead of re-resolving each citation against the file. One citation —
`../SKILL.md:144-154`, the `dod_ok` / `guide_compliance` block — sits *above* the insertion and was
already correct; it was pushed to lines 156-166, which is the newly inserted pointer paragraph itself.
The file then cited "go read this file" as its evidence that the existing DoD checks only existence.
A reader following it lands back where they started, and every step of the path looks valid.

**What to do instead, when auditing citations here:**

- **Report the corpus size beside the result.** `BAD=0` alone has no discriminating power; `78
  occurrences / 56 unique / BAD=0` does. A count that cannot state what it counted is not a
  measurement.
- **Enumerate both citation forms** — full `` `path.md:NN` `` and bare `` `:NN` `` (which inherits the
  nearest preceding path on the same line). A bare form with no preceding path is a defect, not
  something to skip.
- **Give the probe a negative control that must fail** — e.g. honesty-model.md with an absurd line
  number, plus a non-existent file. If the probe does not flag both, its clean result means nothing.
  (Written without the `path:line` punctuation on purpose: a live citation here would be a phantom
  the next audit has to explain away, and a checker that cries wolf gets ignored.)
- **Read the target text, not only the line range.** Both defects above passed "file exists and the
  range is in bounds" while pointing at the wrong content.
- **Never batch-translate line numbers after an edit.** Re-resolve each citation against the file:
  citations above an insertion point do not move, and one that was already correct is exactly the one
  a blanket offset will break.
- **Use `wc -l` / line-count comparison to test range validity, never `sed -n 'NNp'`** — `sed` exits 0
  on an out-of-range line and prints nothing, so it cannot distinguish "line absent" from "line
  empty".

The general lesson, stated once: **an audit probe's corpus must itself be audited.** Both defects
are the absence-versus-failure collision this whole file is written against (§ 4, L7), occurring in
the instrument rather than in the document under review — which is where it is hardest to notice,
because a verification tool that under-reports failures still looks like it is working.
