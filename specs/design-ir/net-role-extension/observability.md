# Observability: design-ir_net-role-extension

## Events

- The IR builder mapping path logs one line per net whose class was resolved to a role
  (`netclass=<x> role=<y> source=<anchor>`) and one per unmapped class
  (`netclass=<x> role=None reason=unmapped`) — makes the no-guess boundary visible.
- `nets_with_role` is a pure query and emits no side-effect events (determinism).

## Metrics

- `nets_total` / `nets_with_role` counts per BoardDesign — coverage of role assignment.
- `roles_unmapped` — nets left role=None because their class was absent from the table
  (a backlog signal for extending the mapping table, NOT a silent-pass).
- Per-role histogram (power/ground/high_current/rf/signal/differential) — sanity check
  that the closed enum matches real board content.
