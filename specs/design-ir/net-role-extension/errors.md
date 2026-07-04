# Errors: design-ir_net-role-extension

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| ROLE_PROVENANCE_MISSING | `set_net_role` called with a non-None role but no `EvidenceRef` | `ValueError("role requires role_evidence provenance")` | Supply the schematic net-class / user-annotation source anchor, or leave role None |
| ROLE_OUT_OF_ENUM | Supplied role token not in the closed enum | role left `None` (fail-fast, no raise on the mapping path; no-guess) | Correct the net-class mapping table, or accept None (checker skips role-gated check) |
| NETCLASS_UNMAPPED | `map_netclass_to_role` given a net-class absent from the explicit table | returns `None` (no heuristic fallback) | Add the class→role row to the mapping table with provenance |
| ROLE_QUERY_UNKNOWN_ROLE | `nets_with_role` called with a role token outside the closed enum | `ValueError("unknown role: <token>")` | Query with a valid closed-enum role value |
