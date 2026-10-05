# Errors: Unified Collaborative Rebuild

## Outcome Codomain

These are TARGET events, not claims that emit sites are implemented. P1 implements
the named application events; P0 inventories legacy outcomes. `ok` means the
module's own contract succeeded, not overall engineering or manufacturing approval.
A3 reports `ok` only for a complete current pass or evidenced non-applicability.
An executed engineering failure maps to `failed`; missing scope maps to
`indeterminate`; no applicable population without proof maps to `empty`.

| Module | Value | Class | Means | Emitted at |
| --- | --- | --- | --- | --- |
| A1 | ok | ok | Inputs resolved and pinned | target input.resolved |
| A1 | failed | failed | Invalid scope or source structure | target input.refused |
| A1 | not-run | not-run | Permission or prerequisite unavailable | target input.blocked |
| A1 | empty | empty | Accepted snapshot contains no design inputs | target input.empty |
| A1 | indeterminate | indeterminate | Applicability cannot be established | target input.unresolved |
| A2 | ok | ok | Complete isolated candidate manifest | target candidate.built |
| A2 | failed | failed | Native generation or supported-edit contract failed | target candidate.failed |
| A2 | not-run | not-run | Upstream or worker prerequisite unavailable | target candidate.blocked |
| A2 | empty | empty | Worker returned no required artifacts | target candidate.empty |
| A2 | indeterminate | indeterminate | Candidate provenance cannot be resolved | target candidate.unresolved |
| A3 | ok | ok | Complete current pass or proved non-applicability | target verification.completed |
| A3 | failed | failed | Execution failed or engineering verdict failed | target verification.failed |
| A3 | not-run | not-run | Checker did not execute | target verification.blocked |
| A3 | empty | empty | No examined objects without applicability proof | target verification.empty |
| A3 | indeterminate | indeterminate | Partial coverage, stale or undecidable evidence | target verification.unresolved |
| A4 | ok | ok | Exact approved manifest released | target release.authorized |
| A4 | failed | failed | Approval rejected, baseline conflict or manifest mismatch | target release.refused |
| A4 | not-run | not-run | Waiting for approval or required checks | target release.blocked |
| A4 | empty | empty | Release manifest contains no deliverables | target release.empty |
| A4 | indeterminate | indeterminate | Current dependency identity cannot be established | target release.unresolved |

## Error Catalogue

| Code | Condition | Surface | Recovery |
| --- | --- | --- | --- |
| SOURCE_SCOPE_INVALID | Path escapes scoped manifest or permission is invalid | A1 failed, path/gap list | Supply authorized source snapshot |
| PREREQUISITE_MISSING | Required block parameter or applicability evidence absent | A1 not-run/indeterminate with missing fields | Obtain evidence; never guess |
| UNSUPPORTED_EDIT | Edit class outside declared capability | A2 failed, writes=0 | New supported proposal or explicit scope extension |
| TOOL_UNAVAILABLE | Required worker/checker unavailable | A2/A3 not-run with reason | Restore approved toolchain; no substitute verdict |
| ARTIFACT_MISSING | Required file absent from actual candidate | A2 empty/failed | Repair generation; regenerate manifest |
| COVERAGE_INCOMPLETE | Expected objects unexamined | A3 indeterminate and omitted IDs | Resolve omissions or explicitly adjudicate applicability |
| EMPTY_EXAMINATION | Zero examined objects without proof | A3 empty, verdict indeterminate | Supply valid export and population |
| ELECTRICAL_DIVERGENCE | Split/fused/missing/NC mismatch | A3 failed with axis and object IDs | Repair topology/emission then rerun |
| EVIDENCE_STALE | Subject or dependency changed | A3/A4 indeterminate | Rerun affected checks and renew approval |
| BASELINE_CONFLICT | Current native revision differs from proposal | A4 failed, writes=0 | Reconcile and propose against new baseline |
| APPROVAL_REQUIRED | No exact human release approval | A4 not-run | Await explicit decision, never auto-approve |
| APPROVAL_MISMATCH | Approval binds other manifest | A4 failed | Review and approve current manifest |
| OUTCOME_INVALID | Unknown outcome value | Adapter rejects typed payload | Fix producer; no success default |
| REFERENCE_LICENSE_UNCLEARED | Grant, terms or compatibility not cleared | A1 not-run | Obtain approval before copying or dependency installation |
| FEATURE_GRAPH_INVALID | Cycle, dangling reference or unsupported operation | A2 failed | Correct graph or approve supported capability extension |
| ANCHOR_UNRESOLVED | Missing, stale or ambiguous geometric reference | A2 failed | Re-resolve against pinned revision; never choose first face |
| FRAME_INVALID | Missing units, invalid transform or reflection | A1 failed | Supply explicit valid frame and source provenance |
| MECHANICAL_COVERAGE_GAP | Missing solids or exact geometry backend | A3 indeterminate/not-run | Supply models or approved backend; AABB cannot substitute |
| CLEARANCE_VIOLATION | Exact geometry violates declared contact/clearance policy | A3 failed | Reconcile candidate geometry and rerun |
| CAD_OUTCOME_UNKNOWN | Confirmation lost after mutation started | A2 indeterminate | Read back revision; no blind retry or rollback claim |

No raw checker findings are dropped by adaptation. `not-run`, `empty` and
`indeterminate` map to non-success transport/CLI results with the original domain
code retained. P1 freezes numeric CLI mappings before compatibility cutover.
