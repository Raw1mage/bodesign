# Errors: c03_pc001_coverage_and_waiver_sidecar

<!-- plan-builder:scaffold — replace every <placeholder>, then delete this line -->

## Outcome Codomain

Every functional module declares the COMPLETE set of states it can leave behind.
Mandatory classes: `ok` / `failed` / `not-run` — these are the three a bare
status collapses. `empty` (ran, produced nothing) and `indeterminate` (ran,
cannot decide) must be ADDRESSED: give a value, or a row with
`n/a (<reason>)` stating the module cannot produce it.

Every outcome names the site that emits it. An outcome nobody emits is a comment.

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| <module> | 0 | ok | <what succeeded> | <file:line or event name> |
| <module> | 1 | failed | <what failed> | <file:line or event name> |
| <module> | 2 | empty | <ran, nothing to report> | <file:line or event name> |
| <module> | -1 | not-run | <guard/precondition that skipped it> | <file:line or event name> |
| <module> | n/a (<reason>) | indeterminate | <why it cannot be undecidable> | n/a (<reason>) |

## Error Catalogue

The `failed` region of the codomain above, in detail.

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| <placeholder_error_code> | <when it fires> | <error message / exit code> | <how caller recovers> |
