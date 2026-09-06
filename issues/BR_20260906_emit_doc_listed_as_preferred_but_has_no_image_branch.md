# BR_20260906 — `bodesign_emit_doc` is the guide's preferred render path but has no image branch

- **Status**: OPEN
- **Family**: `skill-guide-contract` (the guide names a preferred path whose capability boundary is undeclared)
- **Component**: `packages/reverse-core/bodesign_reverse_core/doc_emit.py`, `skills/bodesign/stages/c03-ee/GUIDE.md:459`
- **Filed**: 2026-09-06 (bodesign-side fanout of a guest report)
- **Upstream**: `/home/pkcs12/products/thesmart_products/issues/BR_20260906_c03_schematic_chain_delivered_label_stub_pinout_instead_of_circuit.md` **S6** (lines 201-212), fanout row **B-4** (`:371`)
- **Related**: `BR_20260906_render_companion_kicad_sch_branch_emits_pdf_only_despite_pdf_png_description.md`, `BR_20260906_no_contract_for_re_rendering_docx_figures_after_kicad_sch_change.md` — same docx-projection chain

## The defect

`skills/bodesign/stages/c03-ee/GUIDE.md:459` reads, verbatim:

```
5. **Render path.** Prefer `bodesign_emit_doc` (md → docx+pdf) when the worker has LibreOffice;
```

C03's deliverable is a document that **must embed schematic figures**. The preferred
verb cannot embed an image at all — not "does it poorly", not "needs a flag":
`doc_emit.py`'s markdown→HTML converter has no `![...]` branch, so an image in the
source markdown is silently not carried into the `.docx`.

The guide states the preference without stating the boundary. A reader following it
for a figure-bearing deliverable is routed, by the guide, to a path that structurally
cannot produce the deliverable — and the failure is silent, because a document
missing its figures still renders and still opens.

## Measurement (verified first-hand in this repo, 2026-09-06)

`packages/reverse-core/bodesign_reverse_core/doc_emit.py`, whole file = **134 lines**:

| probe | count | reading |
| --- | --- | --- |
| `![` \| `image` \| `.png` \| `figure` | **0** | no image handling of any kind |
| CONTROL — `def ` (function definitions) | **3** | the file was really read; a zero probe is not an unreadable file |
| CONTROL — `table` \| `html` | **20** | this converter DOES have feature branches — it handles tables and HTML — so the image zero is a specific absence, not an empty file |

The second control is the load-bearing one: it shows the module implements
markdown features selectively, so "no image branch" is a design boundary rather
than "this module does nothing".

`GUIDE.md` mentions `emit_doc` at exactly **one** line (`:459`), the one quoted above.
There is no accompanying capability note anywhere in that file.

*(Line-number note: upstream cited `GUIDE.md:421` for this text. WP1 rewrote that
file and the line is now `:459`. Content verified identical; the anchor was
re-measured rather than copied.)*

## Why the silence is the defect

An image that fails to convert produces no error, no warning, and no diff in the
verb's return shape. The `.docx` is produced, LibreOffice reports success, and the
figures are simply absent — so **"the document was generated" and "the document
contains its figures" share one output.** A consumer discovers the gap only by
opening the file and looking, which is exactly the check that gets skipped when a
pipeline reports success.

Upstream's inference from this is worth preserving: because `emit_doc` cannot embed
PNGs, the figures in the delivered `.docx` **cannot have come from the preferred
path** — some other, undocumented route produced them, and that route is where no
figure-freshness check exists (see the sibling BR).

## Three repair directions (NOT adjudicated)

1. **Declare the boundary in the guide** — one clause at `:459` saying the preferred
   path carries no images, and naming what to use when the deliverable has figures.
   Cheapest; removes the misrouting immediately.
2. **Make the omission loud** — have `doc_emit` detect `![...]` in its input and
   return a typed refusal (or a named warning) rather than dropping it. This is the
   fix that closes the shared-output problem, independent of (1).
3. **Implement an image branch** — largest, and only worth doing if `emit_doc` is
   meant to be the figure-bearing path rather than the prose path.

(2) is separable from the others and is the one that stops the failure being silent.

## Not measured

- Which route actually produced the figures in the upstream `.docx`.
  `bodesign_c00_emit_prd_docx` (`server.py:1250`) and the docxmcp bridge were flagged
  unexamined upstream and remain unexamined here. **If the intended figure path is
  one of those, this BR's fix is (1) alone — the guide should point there.**
- Whether any current caller passes image-bearing markdown to `emit_doc` today (no
  call-site survey performed).
- Whether the PDF half of `md → docx+pdf` behaves differently with respect to images.
