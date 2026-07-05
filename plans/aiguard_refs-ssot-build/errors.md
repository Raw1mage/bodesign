# Errors: aiguard_refs-ssot-build

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `REFS_SSOT_MISSING` | `require_refs(folder, layer)` reaches a layer whose `01_refs/<layer>/` is absent or `blocked_missing_source` | `RefsGateError[REFS_SSOT_MISSING]` raised (天条1 fail-fast) | Supply the layer's named `required_authority` owner source, extract to `01_refs/<layer>/`, set manifest `frozen`, re-run |
| `REFS_ANCHOR_MISSING` | A frozen value in `01_refs/C01/*` lacks a `{source, page}` anchor | Validation error at manifest build | Add the page anchor from the real PDF, or drop the un-sourced value (天条4) |
| `REFS_PHANTOM_FILE` | A `blocked_missing_source` layer manifest lists a file in `files[]` | Validation error (天条2 no-fabrication) | Remove the phantom entry; blocked layers keep `files:[]` + status flag only |
| `REFS_SOURCE_ABSENT` | A claimed owner source (e.g. N6_X01 PDF) is not on disk | Build-time error; layer stays blocked | Do NOT invent; record the layer as blocked with the source named in `required_authority` |
| `PDF_EXTRACT_EMPTY` | PDF extraction yields no structured spec for a section | Warning in extract log | Mark that section thin/absent in the JSON; do NOT fabricate detail |
