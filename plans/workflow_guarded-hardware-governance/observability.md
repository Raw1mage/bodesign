# Observability: workflow_guarded-hardware-governance

## Events

- `governance.state_transition`: Emitted whenever a micro-state successfully advances (`from_state`, `to_state`, `receipt_digest`).
- `governance.transition_blocked`: Emitted when an advance call is rejected due to gate failure or missing prerequisites (`attempted_state`, `missing_gate`, `error_code`).
- `governance.block_applied`: Emitted when a verified circuit block is expanded into the project netlist (`block_id`, `ports`, `injected_components_count`).
- `governance.tidy_executed`: Emitted when geometric tidy runs (`action`, `elements_modified`, `clearance_violations_resolved`).
- `governance.drc_crop_generated`: Emitted when DRC failure triggers bounding box image extraction (`violation_id`, `coords`, `crop_path`).

## Metrics

- `governance_transition_success_ratio`: Ratio of successful state advances vs rejected attempts.
- `c03_gate_pass_latency_ms`: Duration of `check_c03` execution and receipt generation.
- `tidy_overlap_elimination_rate`: Percentage of silkscreen-to-pad overlaps successfully cleared automatically by `silk_tidy`.
- `agent_reconciliation_cycles_count`: Number of iterations needed for the agent to resolve DRC or gate failures before state locking.
