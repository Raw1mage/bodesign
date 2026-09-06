# Handoff: c03_delivery_contract_and_engine_seams

## Execution Contract

- Deliver WP1..WP6 from `tasks.md` in that order. Done for a WP = every task box
  ticked with a real artifact, its POSITIVE control green, and its NEGATIVE
  control demonstrated to fail before the work (or to go red when the mechanism
  is disabled).
- Every WP handoff note records the measurement AND what was not measured. A WP
  reported without its negative-control result is not done.
- Nothing in this package authorises a commit. The drafting handler does not
  commit; the implementing handler stops at working-tree state and the dispatcher
  adjudicates.

## Required Reads

- `docs/research/rca_20260906_c03_schematic_total_root_cause.md` — root causes
  A–G; §5 (PC-001 landed off the delivery path), §10.3 (fidelity gate),
  §10.4 (projection), §10.6 (root cause G).
- `skills/bodesign/stages/c03-ee/GUIDE.md` — the contract WP1 rewrites.
- `issues/BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm_on_non_label_friendly_topology.md`
  §7 and §8.5 — WP6's thresholds and the false-green counterexample.
- `AGENTS.md` §3.1/§3.2 (two deployment paths), §6.1 (shared worktree),
  §6.3 (`__pycache__` before any mutation proof).
- `packages/eda-bridge/bodesign_eda_bridge/fidelity.py` — WP4's whole surface.
- `specs/architecture.md:100-104` — where C03's terminus is described today.

## Stop Gates In Force

- **Before WP2 lands DD-01 in `specs/architecture.md`** — the adjudication is a
  contract change; the dispatcher confirms the wording before it is written.
- **Before WP3 fixes the contents of its candidate list** — DD-04 fixes the
  mechanism, but which roots are enumerated is a deployment decision the
  dispatcher owns.
- **Before any WP6 threshold is treated as binding** — thresholds are calibrated
  on one board; adopting them as a gate is the dispatcher's call.
- **Any WP whose negative control cannot be made to fail** — stop and report,
  rather than substituting a check with no discriminating power.

## Execution-Ready Checklist

- [ ] Dispatcher has verified and frozen this package
- [ ] DD-01 and DD-02 exist as `spec_record_decision` entries
- [ ] `plan-validate.ts --target-state designed` passes
- [ ] `specbase_diagram_validate` passes for `idef0.json` and `grafcet.json`
- [ ] The acceptance corpus (real btdongle spec, 45 components / 27 nets) is
      reachable from the implementing session
- [ ] The implementing handler has read the shared-worktree rules in AGENTS.md §6.1
