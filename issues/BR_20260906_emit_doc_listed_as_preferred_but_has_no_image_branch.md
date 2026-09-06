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

## Severity — restated (2026-09-06); this is not a missing-branch ticket

The original framing ("the preferred verb is missing one branch") understates it by
a category. The correct statement is:

> **A verb that the guide names as *preferred* does not support something the
> deliverable *requires*. Every consumer with a figure-bearing deliverable is
> therefore forced out of the sanctioned path — and once they are outside it, no
> bodesign contract governs anything they do.**

The damage is not the absent images. It is that the guide's own routing manufactures
defectors: it names one path, the path cannot carry the payload, and the consumer
necessarily leaves. What they build after leaving is unreviewed, unversioned against
our engines, and invisible to every gate we own. **A capability gap costs one
feature; a preferred-path capability gap costs jurisdiction.**

This is the same chain as
`BR_20260906_no_contract_for_re_rendering_docx_figures_after_kicad_sch_change.md`,
and the causal order between them matters:

1. **(this BR)** the preferred path cannot embed figures → the consumer must route
   figures through *something else*, of their own devising;
2. **(sibling BR)** because that something-else was never a bodesign path, no
   bodesign contract says who re-renders a figure when the `.kicad_sch` changes —
   so nobody owns discovering that a figure has gone stale.

Step 2 is not an independent oversight. **It is the downstream cost of step 1:** we
cannot write a freshness contract for a route we never sanctioned and do not know
the shape of. Fixing the freshness gap without fixing the routing gap writes a
contract for a path nobody is on.

### Upstream causal inference — DOWNGRADED TO UNPROVEN HYPOTHESIS (2026-09-06)

An earlier revision preserved this upstream inference: *because `emit_doc` cannot
embed PNGs, the figures in the delivered `.docx` cannot have come from the preferred
path, so some other undocumented route produced them.* **The conclusion is probably
right but the premise chain is not established, and it is hereby marked unproven.**

Peer duty-officer measurement in `thesmart_products`, re-verified first-hand here
(read-only; `git`-family commands deliberately not used — that repo's index was
recently repaired and its git output is untrusted):

| probe | result | control |
| --- | --- | --- |
| Is `mk_spec.py` a docx assembler? | **No** — `:3` verbatim: *"Project design.py (the electrical SSOT) into per-sheet bodesign compose specs."* | it is a compose-spec projector |
| `.py` files under `04.btdongle/` mentioning `docx` | **1** (`…/sch_gen/mk_sch2.py:122`, and that line is a comment about figure legibility, not assembly) | same grep for `kicad` → **13 files**; negative control `zzznope_marker` → **0** |
| `DELIVERY_NOTES.md` record for `v2.4` | **0 hits** | `v2.1` → **5**; negative control `v9.9` → **0, rc=1** |
| only recorded assembly route | `DELIVERY_NOTES.md:22` — docxmcp native chain (`from_markdown` → `assemble`) | corroborated `:29` |

**Reading:** the consuming repo has no docx-assembling script at all; assembly was
done by direct docxmcp tool calls. So the upstream document plausibly never touched
a bodesign render verb, and **this BR must not be cited as the cause of that case.**

What is unaffected by the above: `doc_emit.py` has zero image handling and
`GUIDE.md:459` prefers it without saying so. That is measured **in this repo**, and
the severity argument in the preceding section rests on it alone — no consumer
incident is required to make a preferred path that cannot carry the payload a
defect.

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
- **Whether this defect had any role in the upstream v2.4 document.** The measured
  evidence (table above) points away from it: no docx-assembling script exists in the
  consuming repo and the only recorded assembly route is docxmcp-native. Marked
  unproven; not investigated further. `DELIVERY_NOTES.md` has no v2.4 entry at all,
  so what produced v2.4 is simply unrecorded.
- **How many consumers have actually defected.** The severity argument above is a
  structural claim ("the preferred path cannot carry the payload, so figure-bearing
  work must leave it"), not a census. No survey of consuming repos was performed.
- Whether any current caller passes image-bearing markdown to `emit_doc` today (no
  call-site survey performed).
- Whether the PDF half of `md → docx+pdf` behaves differently with respect to images.
