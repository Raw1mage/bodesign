# Observability: quality_tool-generalization

## Events

- `generality_check_run` — the checklist/lint executed over the shipped tool layer; payload: tools scanned, flags raised, physics-allow-list hits skipped.
- `hotspot_remediated` — an overfit hotspot (H1–H5) moved from flagged to overridable/reported; payload: hotspot id, tool, remediation kind.
- `connector_mapping_reported` — H1: `route_net2pcb` emitted `applied_pinmaps`/`unmapped_connectors`; payload: counts per category (the signal that the silent no-op is gone).
- `si_defaults_echoed` — H2: `si_check` reported `result.effective`; payload: whether values were caller-supplied or documented defaults.
- `fabrication_blocked` — a fix stopped rather than inventing a board/process default; payload: which value, which tool.
- `ee_worker_unavailable` — a `pcbnew` regression could not run; payload: tool, recorded as env blocker (not a fake pass).

## Metrics

- **silent_overfit_count** — number of shipped tools where a board/process constant affects behaviour without being overridable or reported. Target: 0 for the silent-failure set {H1,H2}; this is the plan's headline success metric.
- **hotspots_remediated / hotspots_total** — progress against H1–H5 (H3–H5 may defer to a follow-up slice).
- **generality_lint_flags** — count of lint warnings over the tool layer; trend to 0 for in-scope tools, watched for new regressions.
- **regression_tests_passing** — H1/H2 non-OpenMV-board tests + fail-fast tests green; gate for `verified`.
- **backward_compat_drift** — count of tools whose default-path output changed vs the OpenMV baseline. Target: 0 (DD-3 invariant).
