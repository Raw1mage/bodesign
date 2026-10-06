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

## Presentation Authority Amendment (2026-10-06)

This section supersedes the officer draft's DD-13..15 wording where it differs.
DD-1..12 retain their IDs and scope. User-authorized developers for this amendment
are Fable 5.1 and Astra 6; this is a scoped exception to DD-8, not a fleet-wide change.
The paused slice-A working tree is preserved. No further local router repair rounds
are authorized; legacy N=1 compatibility is pinned by snapshot under DD-7, not reset
to an older commit. S1-S3 are implementation work, not completed by this design.

### DD-13: Explicit presentation authority, not an automatic fallback chain

Priority is human draft > explicitly selected layered engine > explicitly selected
legacy compatibility. A supplied human baseline cannot be bypassed after an import
failure. Engine failure cannot fall back to the legacy router or label-only wiring.
Human-authored placements, wire geometry, text, styles, UUIDs and sheet structure
are authoritative presentation, but not automatic electrical or readability approval.
An engine candidate is editable native KiCad and may be explicitly adopted by the
human as a new human baseline. Existing human objects then remain protected.

**S2 formal ingestion contract:** extend the existing `emit_multisheet` application
entrypoint with a scoped `presentation_baseline` manifest: complete root/leaf
`.kicad_sch` set, root path, per-file hashes, declared circuit revision, required
library dependencies and pinned object IDs. Validate local relative sheet references,
unique identities and native version support; missing sheets, ambiguous instance
mapping or unavailable dependencies refuse before writes. No unrestricted host paths.
Default mode is inspect/derive: preserve every input file byte-for-byte and produce
netlist, BOM, ERC, companions, readability and reconciliation evidence separately.

The agent may PROPOSE missing values/footprints, annotation or label completion,
but not apply them under a generic 'repetitive work' permission. Each mutation needs
a P1 ChangeProposal naming baseline hash, object UUID/field, supported edit class,
before/after value, approval and affected checks. Apply only to a separate candidate
with the baseline check and write under the same guard. Untouched files and native
object byte spans are retained; if the editor cannot preserve unknown syntax and
unchanged spans, that edit class is unsupported. Rendering is read-only. No automatic
sheet repartition, renumbering, library replacement, page fitting or relocation of
human objects. New objects need explicit addition permission and collision checks;
the agent may not move existing objects to make room. Changed source => conflict.

Native-export topology mismatch creates a reconciliation ChangeProposal referencing
declared circuit and native manifests, with fused/split/missing/NC/isolated differences.
Neither topology wins silently. Missing pins or connections are proposals, not an
automatic repair. Human input fixture remains pending user supply/permission; a
synthetic fixture proves only the ingestion contract, not real-user acceptance.

### DD-14: Reviewer-aligned instrument with explicit calibration limits

Read native objects, pin geometry and exported net identity together with the native
SVG's visible geometry. Bind all three to exact sheet hashes and renderer version,
viewBox/unit transform, stroke/text extents and declared viewing scale. Raster-only
or unmatched assets cannot establish semantic classes. Missing mapping/geometry is
indeterminate, never zero defects. This instrument models cited failure classes;
it is not claimed to be equivalent to all human perception.

Classes (a)-(f), each with expected/examined/omitted object populations:
- (a) Junction ambiguity: normalized incident branches, segment interiors and pin
  tips versus native junction semantics; flag misleading dot-on-pin placement with
  an evidence region. Raw wire-end count is not a valid degree calculation.
- (b) Cross-net contact and crossing ambiguity: distinguish native shorts from
  electrically separate crossings that visually suggest contact, with OR without
  dots. Same-net T branches with missing visible junctions are a separate finding.
- (c) Local wired-path completeness: declared intra-sheet required pin pairs must
  have visible wire paths, not labels alone. K and eligible nets are explicit policy;
  power symbols, cross-sheet continuations, NC and display-only replicas have named
  applicability/exemption records, never a blanket label prohibition.
- (d) Series-path legibility: compare declared terminal roles, native net partition
  and normalized drawn-wire paths (labels excluded). Distinguish actual bypass from
  apparent continuity/near-contact across a series device. Electrical equality alone
  cannot establish perceptual success; unresolved ambiguity requests human review.
- (e) Foreign-net collinear/near-collinear corridors and pin-row proximity: use
  rendered stroke width and explicit clearance, including segments ending on pin
  rows; distinguish true overlap from visually unresolved separation.
- (f) Text/graphics clearance, clipping, legible scale and occupied page area:
  report units and denominators excluding frame/title block. Bounding-box page-use
  alone is not quality (one long wire can inflate it). 50% is a calibration candidate,
  not an approved universal floor. Reuse child tests only if their population matches.

S1 calibration requires a hash-pinned CP1-CP3 manifest with nine reviewer decisions
and localized class labels. Every archived rejection must remain non-passing with
matching evidence, not merely a generic NO. Missing historical native/render pairs
are unmeasured calibration cells, not recreated archives. Include independently
reviewed acceptable examples for each applicable class and paired corrected cases
so an always-NO detector cannot pass. Freeze policy/tolerances before evaluation;
report per-class false positives/negatives and omissions, not just total agreement.
Uncalibrated classes cannot authorize PASS. Fresh-eyes review remains the final
delivery gate; S1 does not replace it or weaken electrical fidelity. Master DD-14
is distinct from child-plan DD-14/DD-16 and child visual AC-14.

### DD-15: Adopt ELK layered through a bounded EE adapter

Recommendation: `elkjs` ELK layered with orthogonal edge routing, fixed-side/fixed
position ports and explicit node dimensions. Use it as a pinned external dependency,
not copied algorithm source. Upstream package metadata observed on 2026-10-06
declares `EPL-2.0 OR GPL-3.0-or-later`; select the EPL-2.0 option subject to grant/notice
review, exact package version/integrity and transitive license clearance before shipping.
Do not adopt netlistsvg as the native emitter. Graphviz ortho is not the selected
engine: this seam needs symbol-port and label constraints, not only box-to-box edges.
No engine is assumed to guarantee readable electrical diagrams before S3 measures it.

Evidence inspected: `https://raw.githubusercontent.com/kieler/elkjs/master/package.json`
(reported 0.13.0, moving branch, NOT a frozen dependency selection);
`https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html`
documents orthogonal routing with arbitrary port constraints and compound graphs;
`https://graphviz.org/docs/attrs/splines/` explicitly states ortho does not handle
ports or, in dot, edge labels. S3 must pin and test the actual chosen release.

Core owns schemas and policy; the existing EE worker runs bounded Node/elkjs jobs
and native KiCad export/render. `Dockerfile.ee` will need a pinned Node runtime and
lockfile-based production dependency layer. Record image-size/build/startup deltas
in S3 rather than inventing a cost estimate; no new JVM, service or listening port.
The inspected `Dockerfile.ee:22-23,91` already installs Java for freerouting but
does not explicitly install Node; this is Dockerfile evidence, not a live-image probe.
No runtime download or network lookup. Timeout/unsupported graph yields explicit
failure. Installation and Docker edits belong to officer-dispatched S3, not this plan.

**Exact seam (working tree inspected 2026-10-06):** in
`hierarchical.emit_hierarchical_schematic`, replace ONLY the engine-mode
`auto_layout`/`layout_sheet` block immediately before `emit_kicad_schematic`
(currently lines 1334-1369). Resolve the final rendered symbol dimensions and pin
positions first, including scale/unit stacking, so later scaling cannot move ports.
Pass one validated presentation solution containing poses, per-net edge sections,
junctions and label anchors. In `emit_kicad_schematic`, engine mode consumes it
instead of the motif/legacy routing loop beginning at `motif_ground_points`
(currently line 1837), including the two-pin route at 1908 and bus route at 1974.
Reuse native wire/junction serialization and run bookkeeping, not `_guard_route`
as a post-engine repair. Grid quantization and validation occur before serialization;
invalid quantized routes fail, not locally reroute. Human mode bypasses this emitter
for retained native objects entirely.

Motifs are rigid compound nodes with exposed fixed ports and preserved internal
wires. Map canonical net hyperedges explicitly; routing junctions are presentation
objects, not new circuit devices. All body/pin/text extents are layout constraints;
native render + S1 checks still verify the result. Engine coordinates cannot move
human locks. Existing post-emission `fit_page`, continuation insertion, replica
annotation and instance-path rewriting must be suppressed for human bytes or
represented in the engine candidate before final hash/render checks, never mutate
an already validated solution invisibly.

S3 acceptance is one usbc candidate through the formal path, exact native topology,
calibrated S1 report and an independent readable-leaf verdict. It is a checkpoint,
not evidence for five leaves or all layouts. S4 in the officer draft is a separate
commit decision, NOT task 3.3d or permission to commit. Task 3.3d retains the original
five-leaf deliverable; source preservation and nine historical NO results remain.

## Approved R-B / R-H integration (2026-10-07)

Authority: `amendment-presentation-authority-20261006.md` §3.1 R-B through R-H,
§3.2 and its user approval note. DD-1..15 are unchanged. The following decisions
are approved target contracts, not implementation or release evidence.

### DD-16: PresentationPlan and IC-centric design comprehension

Circuit identity and page composition have separate authority. A versioned
PresentationPlan declares page roles/order, home pages, complete pin/unit coverage,
local-support relationships, interfaces, intent references and human locks. Import
legacy sheet fields explicitly as a baseline; never silently repartition them.
ICs/connectors have complete, intelligible pin coverage without an arbitrary pin-count
threshold. Off-page labels cannot hide local support relationships. Exceptions need
named targets, justification and explicit approval. Preserve physical instance identity
and account for multi-unit, hidden/stacked and NC pins. Later approved R-D'/R-E/R-F
module-book views may reference one physical instance through explicit identity mapping;
they are not cloned electrical instances. Preserve the accepted five-home-page book.
Agent hand drafting is a producer, not human approval. Intent comprehension is reviewed
separately from traceability and instrument calibration; historical ACCEPTs retain scope.

### DD-17: COMMON stage-bound presentation and evidence

C00–C04 delivery is in scope. Each stage binds declaration, candidate, producer/toolchain,
checks and independent review in one manifest. Approved human constraints outrank
machine proposals; changes require baseline-bound ChangeProposal, never fallback.
R-G separates human PNG/PDF/index from machine sources/data/evidence; both use
`NN.<stage>-<name>-vN` with coherent revisions, source identity, visible DRAFT/non-approval
status and preserved history. No directory creation is authorized by this decision.
Review cannot override failed/unmeasured required gates; gates cannot prove comprehension.

### DD-18: C01 product appearance and intent

Deliver product/CMF PNG views and review PDF, plus scene, assets, camera/light/material
recipe and tokens. Preserve sourced ID direction, CMF, face/interface layout and envelope.
Renderer is TBD: pyrender is the explicit baseline pending DD-9 clearance and comparison.
Check source/assets, token assignments, view coverage, render success and geometry-based
dimension/interface conformance. Blind reviewers identify product/use, controls, ports,
status, orientation, apparent finishes and obscured/contradictory features before comparison
with the frozen brief. No electrical, physical CMF, colour-accuracy, ergonomic or
manufacturability approval follows from pixels.

### DD-19: C02 printable enclosure geometry

Deliver enclosure/exploded PNG and section/clearance PDF; machine artifacts are real
per-part STL, parametric source, genuine STEP when available, units and print profile.
OpenSCAD/build123d remain ME producers over the same sourced constraint set: board
envelope/heights, holes, connector faces/openings, walls, clearance, assembly and frames.
Check nonempty valid manifold/watertight mesh, orientation/scale, measured wall/fit/
clearance against thresholds. A printable claim also needs declared process/material/
nozzle/build-volume/orientation and slicer evidence. Blind review asks how parts assemble,
support the board and expose interfaces/access; hidden relations need sections/explosions.
Watertight is not sufficient for printability; no physical print, fit, strength, thermal,
fire/IP or production certification without corresponding evidence.

### DD-20: C04 placement and actual copper presentation

Deliver placement PNG, every declared copper-layer PNG and labelled stack/orientation
PDF from the exact Gerber set; retain editable PCB, Gerber/drill, applicable BOM/CPL and
reports. Freeze C03 pin/net partition, qualified footprint/pad mapping, mechanics,
stackup, net classes and DRC rules. Approved human placement leads; agent proposals and
constrained engines respect locks in existing workers. Final filled-board DRC and actual
copper connectivity must cover unrouted/short/open populations. Bind exports and measure
Gerber parity/connectivity separately; unavailable checks remain unmeasured, never a
preview-derived PASS. Blind reviewers locate ICs/connectors/support, explain visible
power/signal/return organization and identify congestion/access/isolation concerns.
No SI/EMC/thermal, assembly or fabrication guarantee follows from a view. Review export
is not send-to-fab authorization; explicit user approval and deterministic gates remain.

### Closure, renderer decision and dependency order

C03 close-out preserves the module book/native baseline and review scope while adjudicating
ERC, exporting coverage-checked BOM and naming overview blocks J1/U1/U2. C00 delivers
PRD DOCX plus human PDF with requirements/source/decision coverage, cross-stage consistency
and rendered readability checks. Pin-group equality is not complete electrical validation.
Blender clearance under DD-9 pins release/source/binary digest, actual licence obligations,
addons/dependencies/assets/notices and output rights; subprocess use is not blanket clearance.
Evaluate headless `blender -b` on an authorized build host, proposed EE-image costs and
CPU/GPU/EGL/failure behavior; no core heavy dependency or transfer of ME geometry ownership.
Freeze scene/units/cameras/lights/materials/colour/seed/backend; measure reproducibility with
declared tolerance, not an assumed bit-identical GPU render. Compare matched C01 subjects
against pyrender with predeclared quality/operational budgets and blind review. Retain
pyrender if adequate; adopt Blender only on demonstrated benefit and cleared obligations;
neither passes means blocked, not automatic fallback. Renderer ownership is explicit.
Output order: C03 close-out → C04 → C02 → C01 → C00 document check. BEFORE C04,
validate C00 requirements and frozen C01/C02 geometry/ID inputs. Missing/contradictory
footprints, outline, connector faces or envelope block entry; resolve the D1 SOT-363 versus
SOT886 BR before this board enters C04. Owner: thesmart_products duty officer
`ses_eed1fb0b6ffelFUGhmXVSGcp3z`; consume its verified resolution, do not repair it here.
C04 inherits intent, locks and dual-axis review, not schematic partition rules. A spike
proposal needs no new generic ruling, but concrete placement approval and conflict ASK
remain required. Rerouting after human placement is not presumed proven. Build-host,
packaging and user-controlled S4 commit gates remain; only C03 close-out is dispatched.

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
