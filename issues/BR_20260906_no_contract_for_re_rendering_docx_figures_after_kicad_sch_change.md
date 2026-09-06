# BR_20260906 — no contract says who re-renders docx figures after a `.kicad_sch` changes

- **Status**: OPEN
- **Family**: `skill-guide-contract` (a required step exists in practice but has no owner in any contract)
- **Component**: `skills/` corpus (stage guides + SKILL.md), specifically `skills/bodesign/stages/c03-ee/GUIDE.md`
- **Filed**: 2026-09-06 (bodesign-side fanout of a guest report)
- **Upstream**: `/home/pkcs12/products/thesmart_products/issues/BR_20260906_c03_schematic_chain_delivered_label_stub_pinout_instead_of_circuit.md` **S5** (lines 192-200), fanout row **B-5** (`:372`)
- **Related**: `BR_20260906_render_companion_kicad_sch_branch_emits_pdf_only_despite_pdf_png_description.md`, `BR_20260906_emit_doc_listed_as_preferred_but_has_no_image_branch.md` — the three form the docx-projection chain: one verb cannot make the format, one verb cannot embed the image, and **nobody owns noticing that the image is stale**

## The gap

A C03 deliverable embeds rendered figures of a `.kicad_sch`. The schematic is
regenerated during normal work. Nothing in the skill corpus says **who is responsible
for re-rendering the figures** when that happens, or by what check a reader would
know the embedded figure no longer matches the source.

`GUIDE.md` requires the rendering layer's QA to pass. It does not say that a
`.kicad_sch` change creates a re-render obligation. So the obligation exists in
reality — the deliverable is wrong without it — and in no document.

**A step with no owner is a step nobody performs**, and its omission produces a
deliverable that looks complete: the figures are present, they are legible, they are
simply of a previous revision. There is no output that differs between "current" and
"stale".

## Measurement (re-run first-hand in this repo, 2026-09-06)

Corpus: `skills/` — **173 files total**, of which **64** are `.md`.

| probe (over `skills/`) | files | reading |
| --- | --- | --- |
| `re-render` \| `rerender` \| `stale figure` \| `figure is stale` \| `re-export the figure` | **2** | see below — neither assigns ownership |
| CONTROL — `compose_schematic` | **6** | the probe traverses the corpus and finds real content |
| CONTROL — `zzznope_never_appears` | **0** | the probe can return a true zero |

The **2** hits, read in full:

1. `skills/bodesign/stages/c00-prd/GUIDE.md:377` — *"any partition or subsystem ruling
   not re-rendered into BOTH slides"*. This is C00, about PPTX slides, and it is a
   gate criterion for a different artefact. It does not reach C03 figures.
2. `skills/bodesign/engines/kidoc/scripts/figures/runner.py:42` — *"force: If True,
   re-render all figures regardless of cache."* This is a **parameter docstring**: it
   documents a capability, not an obligation. It tells you the machine can re-render;
   it does not say when anyone must.

So: **the capability to re-render is documented; the duty to re-render is not.**
Neither hit is a contract, and the count of contracts remains zero.

### Discrepancy with the upstream report — stated, not smoothed

The mother BR recorded **zero** hits over "173 skill files" with a control of 11. I
measure **2** hits with a control of **6**. Both differences are explained by scope,
not by disagreement:

- The 173 figure counts **all** files; my `.md`-only view is 64. Upstream's grep and
  mine did not read the same corpus, and one of my two hits is a `.py` docstring that
  a `.md`-only search would never see.
- The control differs for the same reason (`compose_schematic` appears in more
  non-`.md` files).

**The conclusion is unchanged and is not weakened by the discrepancy** — the two hits
are not counter-examples, as quoted above. But the numbers are not the same and the
next reader should not be told they were.

## What a contract would have to name (NOT adjudicated)

1. **The trigger** — what event creates the obligation (`.kicad_sch` mtime/sha change
   after the last figure export, most plainly).
2. **The owner** — the stage, verb, or role that must act. This is the piece whose
   absence the whole BR is about; a fix that adds a check but no owner reproduces the
   problem one layer up.
3. **The detection** — how staleness is made visible. A figure carrying no provenance
   cannot be adjudicated by anyone downstream, which is why this currently fails
   silently. A recorded source sha beside each exported figure would make "current"
   and "stale" different outputs.
4. **The gate placement** — whether a stale figure blocks delivery or merely warns.

Item (3) is separable and is the one that stops the failure being invisible, whatever
is decided about ownership.

## Not measured

- Whether a re-render obligation exists in a **non-`skills/`** location (this repo's
  `specs/`, `docs/`, or the MCP verb descriptions). Only `skills/` was searched. A
  contract living elsewhere would change the finding from "absent" to "misplaced".
- Whether `kidoc`'s figure cache (`runner.py:42`) already detects source changes
  automatically — if it does, the gap is narrower than stated and the fix is to
  document the existing behaviour rather than build a check. **Not read beyond the
  docstring line.**
- The upstream execution half: which actor swapped the figure set in the delivered
  document. That is the consuming repo's question and is not bodesign's to answer.
