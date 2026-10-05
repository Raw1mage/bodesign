# Observability: Unified Collaborative Rebuild

## Events

The target events in errors.md carry request_id, module, outcome, reason/code,
subject_manifest_sha256 (or explicit unavailable), dependency versions,
required/examined/omitted IDs, raw-result references and duration when executed.
Store event provenance in the client-owned evidence package; worker caches are
disposable. Do not log credentials, full private documents or unscoped host paths.

- input.*: freeze source permissions, intent revision and input gaps.
- candidate.*: record actual files, native library versions and generation result.
- verification.*: record independent axes, coverage and freshness; preserve raw output.
- proposal.conflict: record expected/current baseline and refused operation IDs.
- release.*: record exact approval reference, current dependency comparison and outcome.
- capability.receipt: record formal entrypoint, corpus revision, limitations and child receipt.
- reference.assessed: record upstream commit, license anchors, integration mode and evidence limits.
- feature.resolved: record feature/node IDs, anchor revision/cardinality and execution receipt.
- mechanical.checked: record combined manifest, frame, pair population, exact backend, clearance and numerical tolerance separately.
- cad.job: record request/payload digest, baseline, queue/main-thread state and resulting revision; unknown is distinct from cancelled.

These are design event names. P0 measures existing observability; P1 implements
the uniform contract. Historical evidence is imported with its original scope,
not rewritten as a new run.

## Metrics

| Metric | Definition | Interpretation boundary |
| --- | --- | --- |
| coverage_fraction | examined applicable objects / expected applicable objects | Zero denominator is undefined, not 100 percent |
| omitted_objects | Exact expected minus examined IDs grouped by reason | Count alone cannot identify coverage |
| electrical_differences | Split, fusion, missing node and wired NC axes | Never combined with readability into one score |
| form_measurements | Native artifact geometry against approved corpus thresholds | Not an electrical verdict; subject hash required |
| stale_evidence | Records whose subject/dependencies differ | Any required stale record blocks release |
| source_writes_on_conflict | Changed scoped paths after refused patch | Must be zero; check whole scoped manifest |
| formal_path_completion | Completed supported corpus cases / attempted cases | Expose not-run and failed cases separately |
| adapter_divergence | Domain outcome/semantic differences for identical inputs | Transport formatting excluded, user geometry retained |

## Evidence and Acceptance

P0 receipts record commands, raw stdout/stderr, exit status, test count, skips,
versions and source snapshot; no clean-suite claim from exit status alone.
Each test-vector result links an execution receipt and source permissions.
The vectors in this package are specifications, all initially not-run.
Missing tools are observable blockers, not repaired by changing host configuration
under this plan. Implementation release requires duty-officer acceptance; plan
design validation alone authorizes no engineering or manufacturing claim.
