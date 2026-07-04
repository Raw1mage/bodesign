# Handoff: design-ir_net-role-extension

## Execution Contract

- Deliver: `Net.role` (closed enum, optional, default None) + `Net.role_evidence`
  (EvidenceRef | None) in `packages/design-ir/bodesign_design_ir/contracts.py`, plus a
  `set_net_role` invariant helper, a deterministic `map_netclass_to_role` mapping helper,
  and a `nets_with_role(design, role)` query — all pure-python, zero worker-only deps.
- Done = all tasks in tasks.md checked, new unit tests green, full existing suite green,
  no fabrication (role never inferred from net name), backward-compatible (existing Net
  callers unaffected).

## Required Reads

- `plans/design-ir_net-role-extension/design.md` — DD-1..DD-6 (the contract).
- `packages/design-ir/bodesign_design_ir/contracts.py` — `Net` dataclass to extend.
- `packages/shared/bodesign_shared/contracts.py` — `EvidenceRef` (source_id, target_path,
  confidence, note).
- AGENTS.md §2 (no fabrication / no silent fallback), §5 (test PYTHONPATH incantation).

## Stop Gates In Force

- Cross-spec `extend` into verify-checker registry (DD-6) is OUT OF SCOPE for this plan —
  do NOT flip any T-B binding stub→landed here. This plan delivers the IR contract only.
- No net-name heuristic for role, ever (天條). If tempted, stop.

## Execution-Ready Checklist

- [x] design.md at `designed`, diagrams validated
- [x] EvidenceRef signature confirmed
- [ ] plan at `implementing` before code edits
