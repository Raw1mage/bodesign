# BR_20260906 — `render_companion`'s `.kicad_sch` branch emits PDF only, while its verb description promises `(pdf/png)`

- **Status**: OPEN
- **Family**: `mcp-verb-contract` (the description makes a claim the implementation cannot satisfy on the named input type)
- **Component**: `packages/reverse-core/bodesign_reverse_core/companion_render.py:45-52`, `services/mcp/server.py:1245`
- **Filed**: 2026-09-06 (bodesign-side fanout of a guest report)
- **Upstream**: `/home/pkcs12/products/thesmart_products/issues/BR_20260906_c03_schematic_chain_delivered_label_stub_pinout_instead_of_circuit.md` §4 **F-2** (lines 319-330), fanout row **B-3** (`:370`)
- **Related**: `BR_20260906_emit_doc_listed_as_preferred_but_has_no_image_branch.md`, `BR_20260906_no_contract_for_re_rendering_docx_figures_after_kicad_sch_change.md` — the three together are the docx-projection chain

## The defect

The registered verb description, verbatim (`services/mcp/server.py:1245`):

```
"Render a readable companion (pdf/png) for a non-readable engineering file
 (.kicad_sch/.kicad_pcb/gerber)."
```

It names three input types and two output formats, with no statement that the pairing
is partial. The implementation pairs them differently:

| input | formats the code can produce |
| --- | --- |
| `.kicad_sch` | **PDF only** |
| `.kicad_pcb` | **PDF only** |
| gerber | PNG (separate branch) |

So `(pdf/png)` is true of the verb **taken as a whole** and false of **every
individual `.kicad_sch` call** — which is the only reading a caller can act on.

## Measurement (verified first-hand in this repo, 2026-09-06)

```
packages/reverse-core/bodesign_reverse_core/companion_render.py
:45    out_pdf = out_root / f"{source.stem}{'.sch' if ext == '.kicad_sch' else '.pcb'}.pdf"
:47        cmd = [cli, "sch", "export", "pdf", str(source), "-o", str(out_pdf)]
:49        cmd = [cli, "pcb", "export", "pdf", str(source), "-o", str(out_pdf), "--layers", ...]
:51    if out_pdf.exists():
:52        return CompanionResult(str(source), "rendered", str(out_pdf), "kicad-cli")
```

`"pdf"` at `:47` is a literal in the argv list. There is no format parameter on this
path — not defaulted to PDF, **absent**. The output variable is even named `out_pdf`,
so the type is fixed at the point of construction (`:45`), before the branch.

**Controls.**
- `grep -n 'Render a readable companion' services/mcp/server.py` → **1 hit, `:1245`** —
  the description string is really there and really says `(pdf/png)`.
- `grep -c 'Render a zzznope companion' services/mcp/server.py` → **0** — the probe
  returns a true zero, so the hit above is not a matching artefact.

## Why it matters (the measured consequence)

The upstream case needed **PNG**, to embed schematic figures into a `.docx`. The verb's
description says PNG is available. A consumer reading only the description would
select this verb, call it on a `.kicad_sch`, and receive a PDF — at which point the
options are to re-convert downstream (undocumented) or abandon the verb.

Upstream measured that `render_companion` has **zero call sites** in the consuming
repo, and could not determine whether the cause was ① the guide never routed callers
here, ② a caller tried it and found the format unusable, or ③ nobody read it at all.
This BR does not resolve that either — **but ② is only possible because of this
defect**, and it is the one cause that is fixable from inside bodesign.

## Two repair directions (NOT adjudicated)

1. **Correct the description** — state the pairing (`pdf for .kicad_sch/.kicad_pcb,
   png for gerber`). Cheap, honest, and removes the false affordance immediately. Does
   not give the consumer what they needed.
2. **Implement PNG for the sch branch** — `kicad-cli sch export svg` followed by a
   raster step is the path `GUIDE.md:164` already documents for
   `render_hybrid_sch.sh` (`kicad-cli svg --exclude-drawing-sheet → white PNG →
   autocrop`), so the capability exists in this repo; it is simply not wired into
   this verb.

These are not exclusive, and (1) should not wait for (2): while the description
overstates, every caller that reads it is misinformed.

## Not measured

- Whether any current caller depends on `render_companion` returning a `.pdf`
  extension specifically (a format parameter defaulting to PDF would be safe; changing
  the default would not).
- Whether `kicad-cli sch export svg` is available in the shipped container image. The
  PDF path's `cli` resolution was not traced.
- Whether `bodesign_c00_emit_prd_docx` / the docxmcp bridge offers a PNG path that
  makes this verb unnecessary for the docx use case — the upstream report explicitly
  flags that branch as unexamined, and it stays unexamined here.
