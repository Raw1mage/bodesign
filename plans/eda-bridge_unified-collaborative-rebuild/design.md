# Design: Unified Collaborative Rebuild

## Context

The review used the shared working tree around HEAD cf4f4d5, not a clean released snapshot. `architecture.md` mixes historical IR authority and native-KiCad restrictions with current compute workers. `composer.py` uses EmitComponent/EmitNet while design-ir defines BoardDesign. October collaborative work is valuable but incomplete. No test or live-service results were produced by this review.

## Goals / Non-Goals

**Goals**: a trustworthy formal delivery path, explicit model authority, preservation of human edits, evidence-bound readiness and incremental reuse.

**Non-Goals**: a universal IR, more microservices, wholesale emitter replacement, or deleting old experimental work.

## Decisions

All eight decisions were approved by the incumbent through BRNS-CONFIRM
topic=rebuild-plan-rewrite on 2026-10-06. Approval establishes the target baseline,
not a claim of implementation. P0 dispatch follows designed-state promotion.

- DD-1 (approved): requirements/intent own desired behavior; native KiCad files own the current implementation; frozen netlists describe a particular electrical release. Differences create explicit reconciliation work, never silent overwrite.
- DD-2 (approved): separate circuit topology, schematic presentation and PCB constraints. Stable object IDs and source anchors link them. Rendering cannot change circuit topology; native exported connectivity is compared after emission.
- DD-3 (approved): functional circuit blocks declare applicability, topology, required companions, parameters and source evidence. Graphical motifs only arrange an existing circuit; they cannot certify applicability.
- DD-4 (approved): MCP and landing adapters call shared application use cases. Compute placement remains core/EE/ME according to dependencies. Skills describe decisions and workflow; runtime engines migrate incrementally to versioned packages.
- DD-5 (approved): verification records bind subject hashes, tool/rule versions, execution status, verdict, coverage and omissions. Approval is separate and bound to the exact release manifest.
- DD-6 (approved): human changes use baseline-aware proposals with declared supported edit classes. Changed baselines stop application; unsupported edits fail explicitly. Initial support does not imply arbitrary KiCad round-trip.
- DD-7 (approved): keep compatible behavior until dual-run comparison and a named cutover decision. Compare semantics, not random IDs or timestamps; preserve intentional user geometry and raw evidence.
- DD-8 (approved): Astra plans/reviews; Gemini implements under duty-officer dispatch. This design grants no blanket implementation authority.

## Target Boundaries

1. Ingress: scoped client snapshots and pinned source/library manifests.
2. Domain: requirement/intent graph, resolved circuit, schematic presentation and physical constraints.
3. Application: ingest, propose, build candidate, verify, reconcile and prepare release.
4. Adapters: KiCad, routing, SPICE, vault, document rendering and storage exchange.
5. Evidence: immutable subject references, coverage records and explicit approval.

Client source stays authoritative; compute caches are disposable. Remote workers receive scoped manifests, not unrestricted host paths. Changes to a source/library/tool/rule invalidate affected evidence. Keep existing transport boundaries; security/authentication changes require their own approved scope.

## Functional Model and Transition Semantics

- A1 resolves scoped inputs, applicability and pinned dependencies.
- A2 builds an isolated candidate through shared application use cases and EDA adapters.
- A3 verifies exact candidate bytes and discloses each independent axis and omitted population.
- A4 authorizes an exact release or reports refusal while preserving client sources.

These are application contract seams, not a mandate for four new services. Each
leaf is bounded by the schemas, outcomes and vectors in this package; existing
adapters and child-plan algorithms remain below those seams. Further algorithmic
decomposition belongs to their owning implementation plans, not duplicated here.

GRAFCET step 3 waits when approval is absent and the baseline remains valid.
`baseline_changed` is the complement of `baseline_unchanged`; `evidence_stale`
includes unknown freshness; `approval_mismatch` is evaluated only for a received
approval. Required checks pass only when every applicable check passes and every
non-applicable check has explicit justification. Coverage is complete only when
all required object IDs are accounted for. No timeout synthesizes approval.
Steps 4 and 5 wait for a new/corrected request before returning to input resolution;
they do not silently retry an unchanged request. Application/release uses a
concurrency guard for baseline check plus apply; immutable candidate bytes and
approval are rechecked inside that guard.

`data-schema.json` is a normative field/invariant contract, not executable JSON
Schema. P1 implements serialization and invariant enforcement. `test-vectors.json`
contains specified acceptance cases, all not-run; no implementation result is
implied by design validation. IDEF0 and GRAFCET JSON are the model deliverables;
rendered artwork is not part of this planning handoff.

## Dependency and Ownership Map

| Existing package | Reuse / outstanding dependency | Master milestone |
|---|---|---|
| specs/product/pcb_ai_viewer | Product intent and native-editor boundary | P0/P1 |
| specs/feature/doc-package-scaffold | Ratified C00-C07 coordination and draft scope | All |
| plans/c03_delivery_contract_and_engine_seams | Frozen netlist, fidelity, form/electrical separation; do not edit dirty README | P1/P2 |
| plans/c03_pc001_coverage_and_waiver_sidecar | Coverage and waiver gap; 9/16 historical case is not full coverage | P2 |
| plans/eda-bridge_multi-sheet-subsystem-schematics | Existing leaf emission and outstanding real-board geometry evidence; protected dirty tree | P2 |
| plans/eda-bridge_human-ai-collaborative-system | Motifs, typography and pinning; active seams worker owns tasks 1.1/1.2 | P2/P3 |
| specs/quality/deterministic-preplacement | Reuse bounded placement algorithms; synthetic evidence is not all-board proof | P4 |

Child owners retain their tasks. Master acceptance consumes versioned receipts with tested scope, not copied checkmarks. Archived plans are historical references, never completion evidence.

## Risks / Trade-offs

Reference reuse adds license, vendor-version and geometry-coverage risks. The
matrix below and the amendment risks section bound those risks explicitly.

## External Reference Amendment

The source-pinned adoption matrix is `reference-evaluation.md`. The officer ratified
DD-9 through DD-12, R8-R11 and AC10-AC15 in BRNS-CONFIRM
topic=external-reference-ingestion on 2026-10-06 and explicitly released the P0 HOLD.
The amendment validation is recorded separately in reference-validation.md.
Numbering clarification: the acceptance message labels typed calculations DD-10
and Feature Graph DD-11; the frozen design below uses DD-10 for Feature Graph and
DD-11 for exact interference. Preserve these stable IDs. Typed calculations remain
accepted under R11 and the adoption matrix; AC13 explicitly retains exact checking.
This is a cross-reference correction, not a change to the accepted scope.

- DD-9: reuse selected MIT annotation/escaping algorithms and existing analyzer
  assets through native seams; do not install five competing MCP servers. Resolve
  license/version/notice requirements before copying any code. No SolidPilot AGPL
  implementation/schema import or Onshape clone dependency is approved.
- DD-10: own a small Feature Graph contract in design-ir, with deterministic
  compilation to existing ME adapters. Learn the feature-level abstraction, not
  SolidPilot's source. Start with enclosure/boss/cutout operations; reject unsupported
  ribs, sheet-metal or reverse reconstruction rather than substituting geometry.
- DD-11: collision checking is two-stage: conservative bounds select pairs;
  validated solids and an exact geometry backend adjudicate overlap and minimum
  clearance. Geometry omissions, unresolved tolerances or unavailable exact checks
  remain indeterminate, never an AABB-derived mechanical PASS.
- DD-12: optional cloud/workstation adapters consume revision-bound execution jobs.
  Authentication, data-egress permission, vendor entitlement and versioned capability
  discovery are prerequisites. Native CAD main-thread queues track unknown outcomes;
  timeouts never mean rollback and do not authorize automatic duplicate mutation.

### ECAD-MCAD Contract and Ownership

1. **A1 / design-ir + eda-bridge:** freeze the native board manifest and export a
   STEP assembly plus outline, mounting holes, connector poses, component solids,
   height/keepout coverage and connector insertion/service envelopes. Every export
   names its source hash and tool version. Missing 3D models remain omitted IDs.
2. **A1 / design-ir:** normalize the board-to-enclosure frame explicitly: mm,
   right-handed axes, declared origin and board normal, rigid 4x4 transform. The
   adapter converts vendor units/axes; reject undeclared units, reflection or invalid
   scale. Exported geometry and constraints must share the same revision/frame.
3. **A2 / design-ir + existing ME worker:** compile an acyclic Feature Graph in
   topological order. Nodes carry stable IDs, operation, typed parameters, input
   references, constraints and evidence. Board-linked bosses/cutouts consume anchors
   by semantic role plus object ID and source revision, never a naked face index.
   Resolve exactly one entity or fail. Re-resolve after every relevant native edit.
4. **A2 / adapter:** build in an isolated candidate document. Do not mutate the
   approved enclosure. Persist per-operation receipts; unsupported or failed
   operations stop the job. Discarding an isolated candidate is not a claim that
   an external CAD transaction rolled back.
5. **A3 / ME checker + workflow-core:** assemble board, enclosure and service
   envelopes; enumerate expected pairs, explicit allowed contacts and clearances.
   AABB is broad-phase only. Exact overlap/distance tests carry kernel version,
   model coverage, numeric tolerance and required physical clearance separately.
   Contact/fastener allowances are declared, not blanket collision suppression.
6. **A4 / workflow-core:** bind mechanical evidence and human approval to both board
   and enclosure manifests. A board/component/connector, enclosure, frame, clearance
   policy or geometry-dependency change invalidates affected checks. Proposed
   adjustments flow back as ChangeProposal; C04 cannot relocate a C02-frozen port.

`packages/design-ir` owns exchange contracts; `packages/eda-bridge` owns native
ECAD parsing/export and adapter boundaries; existing workflow-core C02 logic and
ME worker own feature execution; workflow-core owns evidence/approval policy.
This adds no unconditional proprietary runtime dependency or new service.

### Calculation and External Execution Limits

Power-tree structure may be inferred with disclosed uncertainty. Numeric checks
require source-bound inputs: Vout=Vref*(1+Rtop/Rbottom) only for the applicable
feedback topology; fc=1/(2*pi*R*C) only for its first-order model;
CL=C1*C2/(C1+C2)+Cstray only with explicit parasitic assumptions. These equations
do not certify stability, thermal budget or ESD immunity. Missing values stay
missing, rather than adopting upstream keyword current or stray-capacitance defaults.

External mutation jobs require request ID, baseline, capability revision and receipt.
State is queued/running/succeeded/failed/cancelled-before-start/unknown. Only pending
jobs can be cancelled without side effects. A lost response while running is unknown;
read back the native revision and resolve it before any retry. No hardcoded upstream
port, raw unauthenticated TCP bridge or secret-bearing log is part of this design.

## Amendment Risks / Trade-offs

- Contract work can become a second framework: require one real formal-entrypoint slice before further abstraction.
- A single benchmark can overfit drawing rules: use small power/interface, MCU/sensor, btdongle, human-edited and expected-refusal cases.
- Concurrent work can move the baseline: freeze inputs and record commits plus working-tree digests before comparison.
- Full sync is expensive: ship declared edit classes first; do not suppress unsupported geometry.
- Estimate: 12-16 weeks with two developers and recurring EE review, subject to P0 measurements; not a delivery commitment.
- Optional vendor adapters and reverse/sheet-metal work are excluded from that estimate; P0 must re-estimate the local mechanical bridge increment.

## Critical Files

- `specs/architecture.md` — current-state authority; update only after decisions/implementation are adopted.
- `packages/design-ir/bodesign_design_ir/contracts.py` — present BoardDesign representation.
- `packages/eda-bridge/bodesign_eda_bridge/composer.py` — existing compose path.
- `packages/workflow-core/bodesign_workflow_core/validation_evidence.py` — current evidence adapter contract.
- `services/mcp/server.py` — formal delivery entrypoints and worker routing.
