# Observability: gerber-core_copper-geometry-parser

## Events

- `build_copper_geometry` logs one line per source layer materialized
  (`layer=<x> primitives=<n> curves_skipped=<k> islands=<m>`) — makes the curve-skip
  boundary and island count visible.
- A fail-fast raise logs `copper_geometry: <reason> missing_items=<list>` before raising,
  so the no-silent-fallback trip is auditable.
- Query functions are pure and emit no side-effect events (determinism); the provenance
  block in each result is the observability surface.

## Metrics

- `primitives_total` / `curves_skipped` per geometry build — coverage-completeness signal.
- `islands_count` — connected-copper island count (sanity vs expected net count).
- Per-query `skipped_curves_len` — how often a clearance answer is partial (backlog signal
  for a future tessellation contract, NOT a silent approximation).
