# Spec: Unified Collaborative Rebuild

## Purpose

Propose observable contracts for a reference-grounded, editable and verifiable engineering delivery. These are target requirements, not claims about current implementation. Existing approved child work continues under its own scope.

## Requirements

### Requirement: R1 Explicit authority and reconciliation

The system SHALL distinguish desired intent, current native implementation, derived representations and frozen release evidence.

#### Scenario: Native edits differ from intent
- **WHEN** an imported KiCad revision changes connectivity or component identity
- **THEN** a reconciliation proposal identifies differences; neither source is silently overwritten and prior evidence is marked stale where affected.

### Requirement: R2 Evidence-backed functional circuit blocks

The system SHALL preserve reference-grounded synthesis and disclose missing applicability/parameter evidence. Graphical motifs SHALL NOT confer electrical approval.

#### Scenario: Missing circuit prerequisite
- **WHEN** a required parameter or reference applicability condition is unknown
- **THEN** generation reports the missing prerequisite or an explicitly unapproved candidate, never a verified design.

### Requirement: R3 One formal delivery application path

MCP and landing adapters SHALL reach shared use cases, with explicit local/worker execution and versioned compatibility behavior.

#### Scenario: Formal C03 delivery
- **WHEN** a supported circuit is submitted through the documented MCP entrypoint
- **THEN** schematic, exported netlist, BOM, library manifest and readable companion refer to the same candidate revision; native export fidelity and ERC results accompany it.

### Requirement: R4 Artifact-bound verification

Each result SHALL identify subject hashes, tool/rule versions, execution status, verdict, expected/examined coverage, omissions and source evidence. Human approval SHALL be a separate record.

#### Scenario: Empty or incomplete examination
- **WHEN** a checker cannot examine required objects or its tool is absent
- **THEN** it returns not-run or indeterminate with scope and reason; an empty finding list cannot establish pass.

### Requirement: R5 Preserve human changes

Change proposals SHALL bind a baseline revision and supported edit classes. Conflicts SHALL stop application before writing.

#### Scenario: Concurrent human edit
- **WHEN** the baseline changes after a proposal or a pinned object would move
- **THEN** the operation reports a conflict and leaves the native source unchanged.

### Requirement: R6 Bounded C04 and release

The system SHALL declare supported board classes and consume frozen mechanical constraints. Release SHALL require validation and explicit approval bound to the final artifact manifest.

#### Scenario: Post-validation board change
- **WHEN** board bytes change after verification or approval
- **THEN** the previous release authorization is not reusable; required checks and approval must be renewed.

### Requirement: R7 Honest lifecycle and capability status

Capability readiness SHALL report formal entrypoint, supported scope, evidence and limitations independently of plan lifecycle, file existence and document completion.

#### Scenario: Partial predecessor completion
- **WHEN** a child plan has completed some tasks but lacks end-to-end evidence
- **THEN** the master reports partial or unmeasured capability, not completed delivery.

### Requirement: R8 Traceable external adoption

Each reused capability SHALL record upstream revision, source anchors, license,
integration mode and unmeasured limits. Code extraction requires attribution and
license compatibility review. Missing permission SHALL block copying, not invite
a relabeled derivative. Vendor data and application terms are separate constraints.

#### Scenario: Advertised capability differs from source
- **WHEN** a README claims HMAC, exact interference or release guarantees not shown by the inspected code
- **THEN** adoption uses the measured boundary; unresolved claims stay unverified and cannot authorize release.

### Requirement: R9 Revision-bound ECAD-MCAD feature compilation

The bridge SHALL link native board exports to a bounded feature DAG using explicit
units, frames, stable identities, evidence and revision-bound anchors. Cycles,
ambiguous anchors and unsupported operations SHALL fail before publishing a candidate.

#### Scenario: Connector or enclosure anchor changes
- **WHEN** source geometry changes or an anchor resolves to multiple faces
- **THEN** compilation refuses or requests reconciliation; it never chooses the first face or silently moves a frozen connector.

### Requirement: R10 Honest mechanical interference evidence

Mechanical release checks SHALL disclose expected pairs, model coverage, required
clearance, numerical tolerance, allowed contacts and algorithm/backend identity.
AABB overlap SHALL NOT be described as exact collision or clearance certification.

#### Scenario: Exact geometry is unavailable
- **WHEN** only bounding boxes exist or a required component solid is missing
- **THEN** the report is partial/indeterminate for exact verification and release is blocked where that check is required.

### Requirement: R11 Evidence-backed analysis and bounded CAD jobs

Numeric engineering claims SHALL require applicable topology and sourced inputs;
assumptions SHALL be explicit. External CAD jobs SHALL preserve baseline, request
identity and uncertain execution outcomes without retrying unknown mutations.

#### Scenario: CAD request times out after starting
- **WHEN** the caller loses confirmation after native execution started
- **THEN** outcome remains unknown, client source is not claimed restored, and read-back reconciliation precedes any new mutation.

### Requirement: R12 Presentation authority and calibrated readability

The system SHALL select human baseline, layered engine or legacy compatibility
explicitly. Human presentation is immutable unless an approved baseline-bound
ChangeProposal authorizes named edits. Import or engine failure SHALL NOT select a
lower-priority source. Readability SHALL bind native semantic identities to rendered
geometry and report DD-14 classes (a)-(f), unknowns and calibration independently
from electrical correctness. Engine output SHALL remain editable native KiCad.

#### Scenario: Human draft disagrees with declared circuit
- **WHEN** native export differs from the declared circuit
- **THEN** preserve source bytes, report topology differences and issue a reconciliation proposal; do not reroute, repartition or silently choose either topology.

#### Scenario: Readability instrumentation lacks matching source assets
- **WHEN** archived PNG/SVG cannot be bound to native objects or render transforms
- **THEN** affected class coverage is unmeasured/indeterminate, not zero defects or calibrated PASS.

## Acceptance Checks

- [ ] AC1: P0 records versioned source/library/toolchain baselines and distinguishes existing failures from unavailable prerequisites.
- [ ] AC2: R1/R3 pass a real formal-entrypoint C03 case without a bespoke delivery script.
- [ ] AC3: R2/R4 expected-refusal cases cover missing evidence, absent tool, empty export, partial coverage and stale evidence.
- [ ] AC4: Electrical partition matches expected connectivity; NC and isolated nodes are covered explicitly, not discarded.
- [ ] AC5: Drawing readability is reviewed independently from electrical correctness; thresholds are corpus-specific and approved before comparison.
- [ ] AC6: R5 human-edited and conflict cases preserve source files and pinned objects.
- [ ] AC7: R6 bounded C04 retains fixed mechanical constraints and refuses unapproved or stale releases.
- [ ] AC8: At least one second real project completes the same documented path; this does not imply all-board support.
- [ ] AC9: CLI/MCP adapters preserve failure and no-verdict semantics and produce equivalent domain results on identical pinned inputs.
- [ ] AC10: Reference matrix pins all five source revisions; licenses and deviations are recorded; no restricted source/dependency is imported without clearance.
- [ ] AC11: Reused sheet instances and escaped strings survive native export with unique instance references and unchanged values; version support is demonstrated, not inferred.
- [ ] AC12: ECAD-MCAD cases cover valid frames, missing solids, cycles, ambiguous anchors, connector movement and stale board/enclosure evidence.
- [ ] AC13: AABB false-positive, exact collision, clearance violation and authorized contact are distinguished; exact-unavailable cannot pass required mechanical checks.
- [ ] AC14: Missing Vref/parasitics/ESD rule scope and absent routing counts cannot become numeric defaults or release PASS.
- [ ] AC15: Pending cancellation, running timeout, cloud revision conflict and unsupported CAD capabilities preserve honest outcome and prevent blind replay.
- [ ] AC16 (S1 / 3.3a; corpus amendment approved 2026-10-06): Historical CP1/CP2 cells (6) remain permanently blocked, never passed. The replacement calibration corpus comprises (i) CP3 rejecting cells ×3 (archived, reviewer-adjudicated); (ii) every S3 engine-spike output that receives an independent fresh-eyes review, entered as rejecting or accepting per that review; and (iii) hand-built paired cases (clean/b1 family), entered as accepting only after an independent review, until then labelled `hand-verified, unadjudicated`. AC16 `calibrated` status requires at least one adjudicated rejecting AND at least one independently reviewed accepting entry per class a–e; class f follows its own explicit applicability ruling. Versioned per-class thresholds, populations, false positives/negatives, localized evidence and omissions remain required; no always-NO or raw-wire-end proxy. Fresh-eyes remains the final delivery gate. See [S1 receipt: approved corpus amendment](s1-instrument-receipt.md#approved-ac16-corpus-amendment-2026-10-06).
  - Corpus membership does not certify input provenance: CP3 archived netlist mismatch remains disclosed and its diagnostic findings do not become a verified paired measurement. Calibration records bind the policy, subject/declared-input hashes and independently reviewed evidence; unadjudicated extras are not confirmed false positives.
  - S3 may produce and submit its first leaf for independent review before calibration closes, subject to separate officer dispatch and DD-9 clearance. That leaf is an accepting candidate, not a presumed YES. This removes the dispatch circularity, not AC18's final calibrated-S1 acceptance requirement. Until the per-class conditions are evidenced, calibration remains partial and 3.3a remains unchecked; `verdict_scope="a-e"` does not imply class-f or six-class PASS.
- [ ] AC17 (S2 / 3.3b): Formal entrypoint accepts a complete human native sheet set plus declared circuit and dependencies; inspect/derive leaves every source byte unchanged. Approved candidate patches preserve untouched object spans/UUIDs and pinned geometry. Changed baseline, unsupported syntax/edit, missing sheet or topology disagreement produces refusal/conflict/proposal before mutation. Synthetic cases do not replace the pending authorized human fixture.
- [ ] AC18 (S3 / 3.3c): Pinned/license-cleared elkjs in the EE worker produces one editable usbc leaf through the formal path without legacy routing fallback. Final symbol-port coordinates, quantized routes, labels and native exported topology agree; calibrated S1 plus independent visual review accept the exact native-rendered candidate. Record runtime/image costs and unsupported cases; no five-leaf claim.
- [ ] AC19 (3.3d): All five named subsystem leaves plus root, native files and human-viewable renders are delivered; each has matching final hashes, independent readable-leaf acceptance and separate native electrical/replica fidelity evidence. Prior nine NO verdicts remain historical failures. Existing child visual AC-14 remains required and is not master AC14.
