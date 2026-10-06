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

### Requirement: R13 IC-centric presentation and intent (DD-16)

PresentationPlan SHALL separate page composition from electrical identity and account
for every applicable IC/connector pin, unit, hidden/stacked pin and NC on its home
view. Local support connections SHALL be visible; remote labels require declared
destinations and explicit exceptions. User-approved module-book view mappings are
retained without creating extra physical instances. Agent drafts are not approval.

#### Scenario: Page composition changes
- **WHEN** a new producer or partition is proposed
- **THEN** a baseline-bound ChangeProposal preserves physical-instance/pin/net identities and locks; both native conformance and independent intent comprehension are checked.

### Requirement: R14 C00-C04 stage-bound delivery (DD-17..20)

Each stage SHALL publish the human/machine artifact sets, invariant declaration,
producer identity, deterministic evidence, blind review and non-claims specified
in design.md DD-17..20 and closure anchors. All files SHALL share one revision-bound
manifest and NN.<stage>-<name>-vN naming under R-G. Stage acceptance requires both
engineering coverage and intelligible views; neither axis substitutes for the other.

#### Scenario: Attractive but unverified output
- **WHEN** an image is accepted but mesh printability, copper/export connectivity or other required checks are missing
- **THEN** preserve the visual verdict and report engineering acceptance blocked/indeterminate, never manufacture a release approval.

### Requirement: R15 Upstream order and renderer decision

Output order SHALL be C03 closure, C04, C02, C01, then C00 document check; upstream
C00 requirements and C01/C02 geometry constraints SHALL be validated before C04.
The known D1 footprint conflict SHALL block this board's C04 entry until resolved
by its owning project. Blender selection SHALL follow the DD-9 gate in design.md;
no renderer is chosen by absence of an earlier evaluation or by silent fallback.

#### Scenario: Missing C04 prerequisite or renderer clearance
- **WHEN** footprint/outline/connector/envelope authority conflicts, or required renderer permission/runtime evidence is absent
- **THEN** report the specific blocker and owner; do not invent geometry, install a substitute, or equate review exports with fabrication authorization.

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

### R-H acceptance additions (target checks, not completion claims)

- [ ] AC20: DD-16 plan/native comparison accounts for all physical-instance pins and approved view mappings; blind intent review identifies function, local support and remote destinations without reconstructing fragmented chips. Traceability and intent remain separate axes.
- [ ] AC21: C03 closure preserves the accepted module book and baseline; ERC findings are adjudicated, BOM coverage recorded, and overview names identify J1/U1/U2. Pin-group equality alone is not electrical approval.
- [ ] AC22: C04 entry records resolved D1 footprint/pad mapping and frozen upstream requirements, geometry and stackup; final filled-board DRC, actual copper connectivity and export parity have explicit coverage. Every copper layer has a bound human render and independent review. Missing Gerber checks cannot pass by PCB DRC alone.
- [ ] AC23: C02 real per-part STL passes declared mesh/scale/wall/clearance checks and qualified print-profile/slicer checks; exploded/section review explains assembly and interfaces. Unmeasured physical fit and production properties remain non-claims.
- [ ] AC24: C01 scene/assets/material tokens/views conform to the approved ID brief with source hashes; blind review recovers product use and interface/appearance intent. No electrical, physical CMF or manufacturability approval is inferred.
- [ ] AC25: Blender/pyrender decision records exact licences/assets/dependencies, authorized-host headless feasibility and measured costs/reproducibility against predeclared budgets on matched subjects. Selection is explicit; neither passing means blocked.
- [ ] AC26: C00 PRD DOCX and human PDF have source/decision/requirement coverage and cross-stage consistency plus readable rendering; requirements were available before dependent work, not deferred until document closure.
- [ ] AC27: Each stage's NN-vN human/machine set has one manifest, exact reviewer and checker subjects, preserved history, explicit non-claims and separate release approval; no packaging or S4 commit authorization is inferred.
