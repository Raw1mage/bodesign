# Tasks: gerber-core_copper-geometry-parser

## 1. Copper geometry primitives + parser

- [x] 1.1 Add `copper_geometry.py` to `bodesign_gerber_core` with dataclasses: `CopperPrimitive` (id, primitive_type, coords, width, net_island, source_layer, curve_params), `GeometryProvenance`, `MissingGeometryError`, `GeometryQueryResult` — DD-5/data-schema
- [x] 1.2 `build_copper_geometry(tracks, pads, polygons=None, curves=None, source_layer=...)` materializes primitives from already-parsed draw/flash/region input (mirrors board_outline.py consuming parsed edges); curve primitives flagged and excluded from distance math — DD-1/DD-3
- [x] 1.3 Fail-fast: empty input (no tracks/pads/polygons) → raise `MissingGeometryError(reason=zero_geometry, missing_items=[...])`; never return an empty CopperGeometry silently — DD-4
- [x] 1.4 `from_gerber_summary(summary)` adapter building input from `GerberGeometrySummary` draws/flashes (documents that summary sample-limit completeness is an upstream concern)

## 2. Net-island attribution

- [x] 2.1 Deterministic connected-copper-island grouping (union-find over segment endpoints + pad centers within an epsilon); assign `net_island` ids in a stable order — DD Risks (geometric island, not logical net)

## 3. Deterministic geometry queries with provenance

- [x] 3.1 `edge_to_edge(geom, island_a, island_b)` — min point-to-segment distance between two islands' primitives; returns `GeometryQueryResult` with distance_mm + provenance (source_layers/primitive_refs/skipped_curves/algorithm) — DD-2/DD-5
- [x] 3.2 `point_to_copper(geom, px, py)` — min distance from a point to all copper primitives; result + provenance — DD-2
- [x] 3.3 `plane_coverage(geom, px, py)` — ray-casting point-in-polygon over plane/polygon primitives; covered bool + provenance — DD-2
- [x] 3.4 Empty primitive set for a query → `GeometryQueryResult` carrying `MissingGeometryError` (empty_primitive_set), not a 0/inf silent value — DD-4

## 4. Tests + validation

- [x] 4.1 Test: build primitives from synthetic tracks/pads; curves flagged + excluded; deterministic ids
- [x] 4.2 Test: build with empty input → MissingGeometryError(zero_geometry)
- [x] 4.3 Test: net-island grouping merges touching copper, separates disjoint copper
- [x] 4.4 Test: edge_to_edge returns correct min distance + provenance lists skipped curves; byte-identical repeat
- [x] 4.5 Test: point_to_copper + plane_coverage correctness; empty-set query → MissingGeometryError result
- [x] 4.6 Test: no pcbnew import in the module; export API from `bodesign_gerber_core.__init__`
- [x] 4.7 Run full test suite green (AGENTS.md §5 PYTHONPATH incantation)
