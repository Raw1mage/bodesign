# Observability: c03_delivery_contract_and_engine_seams

## Events

- `c03.netlist_freeze.checked` — emitted by the WP1 freeze check on every stage
  scan, carrying `status`, the `.net` path, and the recorded vs on-disk `sha256`.
  Emitted on pass as well as fail: a check that only speaks when it fails is
  indistinguishable from one that never ran.
- `c03.pc001.evaluated` — emitted by the relocated PC-001 detector, carrying
  `status` and the count of active ICs classified. A zero count is emitted, not
  suppressed, so `empty` stays distinguishable from `ok`.
- `gate.packages.resolved` — emitted once per `gate.py` invocation, carrying
  `packages_resolved`, `packages_root` (which candidate answered), and
  `packages_error.code` when unresolved. Already partly present at
  `gate.py:845-861`; WP3 adds `packages_root` provenance.
- `fidelity.verified` — emitted by `bodesign_verify_netlist_fidelity`, carrying
  `status`, `nets_parsed`, the length of each of the five difference fields, and
  `unreadable_paths`. `nets_parsed` rides every event so a reader can tell a real
  pass from an empty read without opening the report.
- `design_suggest.answered` — emitted per invocation, carrying `status`,
  `pin_class`, and `evidence.kb_object` when a rule fired. A `no-rule` outcome
  emits the class that had no anchor, which is the input for widening coverage.
- `readability.scored` — emitted per gate run, carrying `status`, `gate_axis`,
  `does_not_authorize`, the measurement block, and `corpus`. Emitted on pass so a
  form pass cannot be quoted without its disclaimer.

## Metrics

- `c03_netlist_freeze_status{stage}` — distribution over
  `ok|failed|not-run|empty|indeterminate`. The interesting number is not the pass
  rate but the `not-run` count: stages predating the contract.
- `fidelity_nets_parsed{run}` — the count itself, not a boolean. A run reporting
  `status=ok` with `nets_parsed=0` is impossible by DD-06, so a nonzero tally of
  such runs would be a defect in the status resolver rather than in the design.
- `fidelity_nc_wired_count{run}` — declared-NC pins found connected. Tracked
  separately from `fused_count` because the two have different fixes; a single
  combined "divergence count" would reproduce the defect WP4 exists to remove.
- `gate_verb_not_run_total{verb}` — verbs that returned `not-run` because
  `packages_resolved=false`. A rising value is a deployment problem, not a design
  problem, and must not be read as verb failure.
- `design_suggest_no_rule_total{pin_class}` — per-class tally of uncovered
  requests. This is the coverage backlog measured from demand rather than guessed.
- `readability_threshold_margin{metric,corpus}` — distance from each threshold,
  tagged with the corpus that produced it. Tagging is load-bearing: BR_20260905
  §8.5.5 measured a synthetic corpus reporting a near-miss where the real board
  passed comfortably, so an untagged margin is not comparable across runs.
