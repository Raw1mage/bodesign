# Tasks: design-ir_net-role-extension

## 1. Net schema extension

- [x] 1.1 Add `role: Literal["power","ground","high_current","rf","signal","differential"] | None = None` to `Net` dataclass (contracts.py), placed after existing fields (slots=True back-compat) — DD-1
- [x] 1.2 Add `role_evidence: EvidenceRef | None = None` to `Net` — DD-3
- [x] 1.3 Export the closed role enum as a reusable symbol (`NET_ROLES` tuple or `NetRole` Literal alias) from `bodesign_design_ir` for callers/validators

## 2. Role provenance invariant + explicit-supply mapping

- [x] 2.1 Add a builder/validator helper `set_net_role(net, role, evidence)` enforcing the invariant `role is not None ⇔ role_evidence is not None`; reject out-of-enum tokens by leaving role None (fail-fast, no-guess) — DD-2/DD-3
- [x] 2.2 Add deterministic net-class → role mapping helper `map_netclass_to_role(netclass, table)` consuming an explicit mapping table (zero net-name heuristic, zero LLM); unmapped class → None — DD-4

## 3. Role-aware query interface

- [x] 3.1 Implement `nets_with_role(design, role)` returning the subset of `design.nets` with `net.role == role`; `role is None` nets always excluded; deterministic, pure-python — DD-5
- [x] 3.2 Export query + helpers from `bodesign_design_ir.__init__`

## 4. Tests + validation

- [x] 4.1 Test: Net with no role → role None, role_evidence None; existing positional/keyword construction unaffected (back-compat)
- [x] 4.2 Test: set_net_role with valid enum + evidence sets both; out-of-enum token → role stays None; role without evidence rejected (invariant)
- [x] 4.3 Test: map_netclass_to_role maps known class, returns None for unmapped (no heuristic)
- [x] 4.4 Test: nets_with_role filters by role, excludes role=None nets, byte-identical across repeated runs
- [x] 4.5 Run full test suite green with the package PYTHONPATH incantation (AGENTS.md §5)
