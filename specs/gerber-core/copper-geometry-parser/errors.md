# Errors: gerber-core_copper-geometry-parser

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| LAYER_ABSENT | Requested copper layer file / input not present | `MissingGeometryError(reason="layer_absent", missing_items=[...])` | Provide the parsed copper layer artifact; caller judges the check unverifiable |
| ZERO_GEOMETRY | Layer present but yields no track/pad/polygon primitives | `MissingGeometryError(reason="zero_geometry", missing_items=[...])` raised by `build_copper_geometry` | Confirm the layer actually has D01/D03 copper; do not treat as empty pass |
| EMPTY_PRIMITIVE_SET | A query targets an island/primitive set that is empty | `GeometryQueryResult` with `error=MissingGeometryError(reason="empty_primitive_set")`, distance_mm None | Caller must judge `unverifiable`, never read as safe clearance |
| CURVE_COVERAGE_INCOMPLETE | Query geometry involves arc/circle/curve primitives (skipped) | result carries non-empty `provenance.skipped_curves`; distance still returned but flagged | Caller notes coverage is partial; do NOT chord-approximate to fill the gap |
