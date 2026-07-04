# C04 layout review method — forced-find, multi-pass, dedup, and the report templates

**What this is.** The *review discipline* for C04: how to run a rigorous layout / stackup / DRC
review so it does not collapse into "looks good to me", how to record findings in a shape that
**deduplicates** across passes and reviewers, and the **report templates** for the layout-review and
stackup deliverables. It is the method layer that sits *on top of* the numeric rule base
(`../../../references/pcb-layout-rules-compendium.md` — the thresholds) and the design-intent layer
(`stackup-and-placement.md` — what to intend). This note tells you *how to review*, not *what the
numbers are*.

**Where it fits in the existing gates — read this first.** bodesign already has two review/verify
mechanisms; this method **feeds** them, it does not replace them:

- **G2 pre-implementation design review** (`../../../SKILL.md` § "Pre-implementation design review")
  is a *scenario walkthrough* before validation (power-sequencing, reset chain, I²C address, level
  compat, diff-pair topology) with an `APPROVE/APPROVE_WITH_CONCERNS/REJECT` verdict persisted to
  `_design_review/design_review.json`. The forced-find + dedup discipline here is **how to conduct
  that walkthrough rigorously** and how to structure the concerns it records.
- **The C04 gate** (`bodesign_layout_drc_gate` + `c04_readiness`) is the *deterministic* verdict on a
  built board (copper/unconnected/unmapped-pad/SI). This review method is the *human/LLM judgment*
  pass that runs **against the design intent and the placed/routed board** — it never substitutes for
  the deterministic gate, and it may **never** relax a gate threshold to make a finding go away (the
  floating-PSRAM lesson, `../../../references/honesty-model.md` rule 5).

Every finding this method produces is a *design-review judgment*, honestly labelled — never a DRC
pass, an SI verdict, or a lab-compliance claim. Those stay tool/lab outputs.

---

## 1. Forced-find prompting — kill "looks good to me"

The dominant failure mode of any review is a reviewer skimming the board and approving without deep
analysis. Counter it with a **forced-find** contract on every review pass:

> **You MUST surface at least 2 candidate concerns across the review categories below, even if the
> design appears correct. For each, either explain why it is a genuine concern, OR explicitly state
> why the apparent issue is actually acceptable (with the evidence that makes it acceptable).**

The "explain why it's actually fine" escape is deliberate: it forces the reviewer to *look* and
*reason*, not to rubber-stamp. A pass that returns zero findings **and** zero ruled-out candidates is
itself a review defect — it means the reviewer did not engage.

This is the same premise-before-fix discipline the debug cost-ordering rule uses
(`../../../SKILL.md` § "Debug cost-ordering discipline"): a ruled-out candidate needs an
`evidence_ref`, not a hand-wave.

## 2. Review categories — all five must be examined

Across all passes of a review, **every** applicable category below must be examined by at least one
reviewer. Each maps to the rule base for its thresholds:

| # | Category | What it covers | Threshold source |
|---|---|---|---|
| 1 | **Placement quality** | component proximity, thermal zones, signal-flow direction, decoupling-at-pin, keepouts | compendium §1 (P1–P18) |
| 2 | **Routing integrity** | impedance, length-match, return paths, current capacity, crosstalk, via usage | compendium §2 (R1–R21) |
| 3 | **Stackup compliance** | impedance targets met, reference-plane adjacency, symmetry/copper balance | compendium §3 (S1–S9) + `stackup-and-placement.md` |
| 4 | **DRC cleanliness** | violation count, severity distribution, waiver quality, false-COMPLETE class (filled-pad / pad-overlap) | compendium §6 (D1–D16) + the C04 gate |
| 5 | **Manufacturing readiness** | trace/space vs fab capability, via sizes/aspect ratio, copper-to-edge, panelization | compendium §6 + `jlcpcb`/`pcbway` skills |

Skipping an *applicable* category is a review defect, not a shortcut. A category that genuinely does
not apply (e.g. no high-speed bus → length-match sub-items) is marked **N/A with a one-line reason**,
never silently dropped (honesty model — silent absence is forbidden).

## 3. Independent multi-pass reviews

For high-stakes boards, run the review as **multiple independent passes**:

- Each pass operates with **independent context** — no access to the findings of other passes. This
  prevents anchoring, where a second reviewer just confirms the first one's list.
- Default **2 passes**; raise for dense/high-speed/safety-relevant boards, lower to 1 for a simple
  2-layer board (record the count and why).
- Passes may be different reviewer instances, or the same reviewer re-run with a **fresh-eyes**
  prompt and no prior finding list in context (the same "fresh-eyes subagent" discipline the pptx/QA
  workflow uses).

## 4. Finding schema — the shape that deduplicates

Every finding MUST be recorded in this structure so findings from multiple passes/reviewers can be
merged deterministically:

```json
{
  "id": "<unique finding id, e.g. RT-003>",
  "severity": "critical | major | minor | info",
  "category": "placement | routing | stackup | drc | manufacturing",
  "component": "<reference designator, or null>",
  "net": "<net name, or null>",
  "board_issue_id": "<board-level issue enum id, or null>",
  "location": "<board coordinates or area description>",
  "description": "<what is wrong — the observed evidence>",
  "fix": "<recommended corrective action>",
  "rule_ref": "<compendium rule id backing this, e.g. R15 / P6 / D10, or null>",
  "confidence": "high | medium | low",
  "evidence_source": "<tool output / file:anchor / datasheet page — where this came from>"
}
```

- `rule_ref`, `confidence`, `evidence_source` are the **bodesign additions** to the base schema —
  they keep every finding traceable to a numeric rule and an evidence source, exactly as the KiCad
  engine labels its own findings (`analyze_pcb.py` carries `confidence` + `evidence_source`; do not
  launder those into bare assertions — GUIDE.md § "Cross-check").
- A finding with no `rule_ref` and no `evidence_source` is a *hunch*, not a finding — either ground
  it or drop it.

### Severity → gate behaviour (align with the deterministic gate, do not diverge)

| Severity | Meaning | Maps to |
|---|---|---|
| **critical** | shorts, opens, clearance on HV nets, floating/unmapped pads | C04 gate HARD FAIL (copper/unconnected/unmapped) |
| **major** | impedance out of tolerance, insufficient annular ring, return-path break, SI fail | gate fail or SI `fail` |
| **minor** | silkscreen overlap, courtyard nit, cosmetic | gate WARN — documented, does not block |
| **info** | advisory / improvement suggestion | noted, no gate effect |

The review's severity language must **match** the gate's fail/warn split — a "minor" finding must not
be something the deterministic gate treats as a hard fail, and vice versa. If the review disagrees
with the gate on severity, that disagreement is itself a finding to escalate, not a reason to relabel.

## 5. Deduplication across passes/reviewers

When merging findings from multiple passes, dedup **deterministically** (do not eyeball it):

- **Component-level findings** → match on `component` (case-insensitive) **+** `category`.
- **Net-level findings** → match on `net` (case-insensitive) **+** `category`.
- **Board-level findings** → match on `category` **+** `board_issue_id` (case-insensitive).

Merged findings **keep the highest severity** of the group and gain `confirmed_by: N` (the number of
independent passes that raised it). A finding confirmed by multiple independent reviewers is a
stronger signal than a lone one — surface `confirmed_by` in the report so the reader can weight it.

## 6. Verdict

The review closes with one verdict, mirroring the G2 contract so it slots into
`_design_review/design_review.json`:

- **APPROVE** — no critical/major open; minors documented.
- **APPROVE_WITH_CONCERNS** — passes, but the concerns MUST appear as findings with severity
  ≥ major so they stay visible downstream (they do not silently vanish).
- **REJECT** — keeps deterministic validation **blocked** until the critical/major findings are
  resolved and re-reviewed. A missing review record blocks validation the same way (`REVIEW_MISSING`)
  — the gate cannot be skipped by simply not reviewing.

A REJECT is never overridden by relaxing a threshold — fix the board, then re-review (honesty model
rule 5; the floating-PSRAM cautionary tale).

---

## 7. Report template — Layout Review Report

Author as the markdown source for the layout-review deliverable; render/store per the stage layout.

```markdown
# Layout Review Report

**Project:** <name>   **Board:** <rev>   **Date:** <ISO 8601>
**Reviewer:** <id>   **Passes:** <N, independent>
**Deterministic gate run:** layout_drc_gate <yes/no> · c04_readiness <yes/no>
**Engine cross-check run:** analyze_pcb.py --full / cross_verify.py <yes/no>

## Board summary
| Parameter | Value |
|-----------|-------|
| Board dimensions | <W×H mm> |
| Layer count | <N> |
| Component count | <N> |
| Net count | <N> |
| Via count | <N> (TH <n>, blind <n>, buried <n>) |
| Min trace/space | <trace>/<space> mm |

## Findings (deduped, all passes)
| ID | Sev | Cat | Comp | Net | rule_ref | conf | Description | Fix | confirmed_by |
|----|-----|-----|------|-----|----------|------|-------------|-----|--------------|
| RT-001 | major | routing | — | DDR_DQ0 | R15 | high | intra-pair skew 9 mil > 5 mil | meander tune | 2 |

## Category scores
| Category | Verdict | Notes |
|----------|---------|-------|
| Placement | PASS/CONCERN/FAIL | |
| Routing | PASS/CONCERN/FAIL | |
| Stackup | PASS/CONCERN/FAIL | |
| DRC | PASS/CONCERN/FAIL | |
| Manufacturing | PASS/CONCERN/FAIL | |

## Deterministic gate cross-reference
<layout_drc_gate verdict: copper N / unconnected N / unmapped N / SI worst=…>
<any review finding that the gate did NOT catch — and why (a gate gap to file), or
 any gate fail the review must explain>

## Verdict: APPROVE / APPROVE_WITH_CONCERNS / REJECT
<rationale; concerns ≥ major listed above stay visible downstream>
```

## 8. Report template — Stackup Specification

```markdown
# Stackup Specification

**Project:** <name>   **Board:** <rev>   **Date:** <ISO 8601>
**Target fab:** <fab if known, else Generic>   **State:** assumption-until-fab-confirmed

## Design requirements
| Parameter | Target | Source (C03 net class / constraint) |
|-----------|--------|-------------------------------------|
| Single-ended Z0 | <Z> Ω | |
| Differential Zdiff | <Z> Ω | |
| Layer count | <N> | density / SI need |
| Board thickness | <T> mm | C02 mechanical |
| Copper weight (outer/inner) | <oz>/<oz> | current/thermal |

## Layer stackup
| Layer | Name | Type | Thickness (mil) | Material | Er | Cu (oz) | Purpose |
|-------|------|------|-----------------|----------|-----|--------|---------|
| 1 | Top | Signal | | | | | microstrip, ref L2 |
| … | | | | | | | |

## Impedance (from impedance_solve, not guessed)
| Trace type | Target Ω | Solved Ω | Width mil | Spacing mil | Ref layer | Margin |
|-----------|----------|----------|-----------|-------------|-----------|--------|

> Widths are design starting points — an `assumption` until confirmed against the chosen fab's
> controlled-impedance solver (GUIDE.md § step 2). State it; do not present them as fab-verified.

## Copper balance & symmetry
| Layer | Coverage % | Symmetric pair Δ | Notes |
|-------|-----------|------------------|-------|
<coverage target >60%; symmetry per compendium S5 — flag warpage risk if unbalanced>

## Manufacturing notes
- min trace/space for this stackup · via drill/aspect ratio · special processing (HDI) · surface finish
```

---

## 9. Provenance

The forced-find + independent-multi-pass + deterministic-dedup discipline and the two report
templates are distilled from the `pcb-layout-engineer` role skill (mcpmarket, v1.0.0). Its numeric
reference tables (stackup/routing/layout guidelines) were **not** imported — they are already
covered, more completely and with machine-checkability tags, by
`../../../references/pcb-layout-rules-compendium.md`; this note takes only the *review method* the
compendium lacked. The method is adapted to bodesign's contracts: findings carry
`rule_ref`/`confidence`/`evidence_source`, severities align to the deterministic C04 gate's fail/warn
split, and the verdict slots into the existing G2 `design_review.json` record — never relaxing a gate
to pass (`../../../references/honesty-model.md` rule 5).
