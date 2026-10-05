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
