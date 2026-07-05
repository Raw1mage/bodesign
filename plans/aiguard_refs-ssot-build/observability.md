# Observability: aiguard_refs-ssot-build

## Events

- `refs.freeze.C01` — emitted when C01 manifest is written with status=frozen (+ file count, anchor count)
- `refs.block.<layer>` — emitted per layer marked blocked_missing_source (+ required_authority name)
- `refs.ingest.load` — `refs_ingest` successfully loaded a frozen layer's SSOT
- `refs.ingest.fail_fast` — `require_refs` raised REFS_SSOT_MISSING for a blocked layer (天条1 signal)
- `refs.regression.report` — REGRESSION.md written (+ counts: N pass / M block)

## Metrics

- `refs_layers_frozen` — count of layers with real owner SSOT (target ≥1 = C01)
- `refs_layers_blocked` — count of blocked layers + their required-authority list (honesty gauge)
- `refs_anchors_total` — total page anchors backing frozen values (天条4 traceability)
- `regression_layers_pass` / `regression_layers_block` — per-run chain reach vs fail-fast breadth
