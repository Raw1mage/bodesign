---
slug: concept/honesty-provenance-model
title: Honesty & provenance model (the soul of bodesign)
layer: ragbase
type: concept
confidence: verified
---
# Honesty & provenance model (the soul of bodesign)

A design package has value only because a reader can **trust** it. Seven rules override convenience, deadlines, and the urge to look finished:

1. **Never fabricate** an approval, verdict, measurement, fab output, certification, or a pin/net/value not derived from a real source. A truthful `pending` beats a false `complete`.
2. **State provenance** — every non-trivial fact traces to a datasheet (page/section), a published reference, an extracted netlist, or a tool run. The KiCad engine attaches `confidence` + `evidence_source` to every finding; preserve it.
3. **Mark the unproven** with an explicit status (`draft`/`pending`/`not-run`/`assumption`) **and a reason** — a status without a reason is itself a defect.
4. **External gates stay external** — EVT/DVT, FCC/CE/CISPR/IEC 62368-1, RoHS/REACH, ESD are decided by an external lab or physical build; record target+plan, never mark passed.
5. **Show reliability, don't assert it** — "269/269 nets matched a known-good reference" beats "robust, production-ready". Cross-check against a control group and report the delta both ways (extras AND missing).
6. **Document honest boundaries; exclude rather than guess** — missing source data is recorded as a source-data limit and left out, never back-filled.
7. **Respect provenance vaults** — proprietary/borrowed source lives in gitignored vaults; never commit it, never copy it into a deliverable.

Litmus test: *"If the reader fabricated the board tomorrow and checked this claim, would it hold?"* If not, downgrade and name what's missing.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/honesty/model/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.honesty.model.md]] @ honesty-model.md: seven rules + per-stage + litmus test — source_weight 1

## Related

- → `constrains` [[workflow/c00-prd|C00 PRD — author the product requirements contract]]
- → `constrains` [[workflow/c03-ee|C03 EE — design definition → schematic → BOM → netlist → bridges]]
- → `constrains` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]
- → `constrains` [[workflow/c06-verify|C06 Verify — evidence → honest pass/warn/fail verdicts]]
- → `constrains` [[workflow/c07-mfg|C07 MFG — manufacturing-transfer readiness]]
- ← `references` [[concept/impl-ir-source-of-truth|BoardDesign IR as Source of Truth]]

