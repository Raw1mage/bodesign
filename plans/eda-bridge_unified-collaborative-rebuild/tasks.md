# Tasks: Unified Collaborative Rebuild

This is the approved target master queue. Child tasks remain with their current owners. No implementation task is authorized by this file alone. Planning completion is separate from implementation progress.

## 0. Planning baseline (Astra)

- Draft 0.1 is staged: user intent, scope and delegation in proposal.md.
- Draft 0.2 is staged: target contracts and predecessor dependencies in spec.md and design.md.
- [x] 0.3 Complete IDEF0/GRAFCET, sequence, schema, test vectors, errors and observability before designed-state promotion — artifact: idef0.json, grafcet.json, sequence.json, data-schema.json, test-vectors.json, errors.md, observability.md, design-validation.md
- [x] 0.4 Obtain duty-officer review of architecture decisions, dependency boundaries and initial dispatch scope — artifact: design.md, handoff.md
- [x] 0.5 Integrate and validate the external-reference amendment — artifact: reference-evaluation.md, reference-validation.md, design.md, spec.md, data-schema.json, idef0.json, test-vectors.json
- [x] 0.6 Obtain officer acceptance of DD-9..DD-12 and explicit release of the P0 dispatch HOLD — artifact: design.md, handoff.md, reference-validation.md

## 1. P0 Baseline (Gemini implementation preparation; Astra review)

- [x] 1.1 Freeze source, library and toolchain versions; enumerate formal entrypoints and capability scopes — artifact: baseline-inventory.md
- [x] 1.2 Run narrow existing tests then the full suite; classify failures, skips and toolchain gaps without masking them — artifact: baseline-test-report.md
- [x] 1.3 Define authorized corpus: power/interface, MCU/sensor, btdongle, human-edited and expected-refusal cases; record data-access permissions — artifact: corpus-inventory.md
- [x] 1.4 Reconcile legacy readability thresholds with native measurements before adopting new thresholds; do not retroactively relabel failed acceptance as passed — artifact: readability-reconciliation.md

P0.1 also inventories reference revisions/licenses and existing bundled Happy code;
P0.3 includes authorized mechanical models and supported CAD/backend availability.
These are inventory-only additions, not permission to install vendor software,
copy AGPL code, upload designs or add cloud credentials.

## 2. P1 Shared contracts (depends on P0)

- [ ] 2.1 Specify and implement artifact/revision, coverage/verdict, proposal/conflict and approval contracts via compatibility adapters.
- [ ] 2.2 Prove stale evidence and changed baselines are rejected; preserve raw checker output.
- [ ] 2.3 Compare MCP and landing domain results and exit/status semantics on identical inputs.
- [ ] 2.4 Implement versioned feature/frame/anchor, adoption and CAD-job contracts; license clearance precedes any selective extraction.

## 3. P2 C03 vertical delivery (depends on P1 and child receipts)

- [ ] 3.1 Consume reviewed seam-promotion receipt from the collaborative plan; do not duplicate its active worker tasks.
- [ ] 3.2 Bind supported functional blocks and existing motifs to circuit/presentation separation.
- [ ] 3.3 Integrate multi-sheet and C03 evidence through the formal entrypoint; obtain outstanding child-plan acceptance rather than copying checkmarks.
- [ ] 3.4 Resolve or explicitly bound PC-001 coverage and waiver behavior; test empty, isolated and NC cases.
- [ ] 3.5 Deliver same-revision schematic/netlist/BOM/library/companion bundle with separate electrical and form results.
- [ ] 3.6 Converge reused-sheet annotation and S-expression codec with native-version tests; preserve upstream MIT notices where code is extracted.
- [ ] 3.7 Converge pure analysis and sourced physical calculations; reject missing defaults and map DS findings into explicit release policy.

## 4. P3 Human round-trip (depends on P2)

- [ ] 4.1 Declare supported edit classes and preserve existing pinning guarantees.
- [ ] 4.2 Test baseline conflict, unsupported edit, repeated generation and human-position retention through the formal path.

## 5. P4 Bounded C04 (depends on P2; edit application also depends on P3)

- [ ] 5.1 Freeze supported board class and mechanical/stackup constraints before choosing benchmarks.
- [ ] 5.2 Reuse placement/routing/plane adapters; verify fixed-object retention and native DRC on final board bytes.
- [ ] 5.3 Verify release denial for missing checks, stale artifacts and absent approval.
- [ ] 5.4 Compile bounded enclosure feature DAG via existing ME backend; verify board/frame/anchor lineage and combined exact mechanical evidence.
- [ ] 5.5 Bind DSN/SES jobs to board revisions and prove supported hole-clearance cases with native DRC.

Optional cloud/workstation CAD, reverse reconstruction and sheet metal require
separate scoped approval after local P4; they are not implied implementation tasks.

## 6. P5 Migration (depends on P3/P4)

- [ ] 6.1 Run a second real-project delivery and semantic compatibility comparisons.
- [ ] 6.2 Obtain explicit cutover approval, publish version/rollback procedure and synchronize current architecture.
- [ ] 6.3 Retain legacy data and user worktrees; retire entrypoints only by a separately approved migration decision.
