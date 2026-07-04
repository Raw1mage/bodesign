# Handoff: gerber-core_copper-geometry-parser

## Execution Contract

- Deliver a pure-python, zero-pcbnew `copper_geometry.py` in
  `packages/gerber-core/bodesign_gerber_core/`: primitives (track/pad/polygon/plane/curve)
  with net-island attribution, `build_copper_geometry` (fail-fast on empty), and three
  deterministic queries (edge_to_edge / point_to_copper / plane_coverage) each returning
  a `GeometryQueryResult` with geometry provenance.
- Done = all tasks.md checked, new unit tests green, full existing suite green, no
  fabrication (curves skipped not chord-approximated; missing geometry → explicit
  MissingGeometryError, never empty/0/inf silent pass), backward-compatible (existing
  gerber-core summary API untouched).

## Required Reads

- `plans/gerber-core_copper-geometry-parser/design.md` — DD-1..DD-6.
- `packages/workflow-core/bodesign_workflow_core/checkers/board_outline.py` — the parser
  template: `point_to_segment_distance`, `min_clearance_to_edge`, curve-skip discipline,
  inf-means-caller-fail-fast.
- `packages/gerber-core/bodesign_gerber_core/contracts.py` — existing summary-level
  dataclasses (`GerberGeometrySummary`, `GerberDrawSegment`, `GerberFlash`) to extend not
  rewrite; `parse_gerber_file` output shape.
- AGENTS.md §2 (no fabrication / no silent fallback), §4 (core/worker boundary), §5 (test).

## Stop Gates In Force

- Cross-spec `extend` into verify-checker registry (DD-6) is OUT OF SCOPE — do NOT write
  clearance/creepage checkers or flip T-B stubs here. This plan delivers the parser + query
  API only.
- No chord-approximation of curves (天條). If a query's geometry involves a curve, disclose
  it in skipped_curves, never fabricate a number.

## Execution-Ready Checklist

- [x] design.md at `designed`, diagrams validated
- [x] board_outline.py template + gerber-core contracts confirmed
- [ ] plan at `implementing` before code edits
