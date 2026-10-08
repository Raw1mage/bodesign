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
- [ ] 3.3a S1: Implement DD-14 instrument and calibrated classes (a)-(f); meet AC16 with pinned rejected and accepted examples, explicit missing archive cells and no router edits. Fable 5.1 under officer dispatch.
- [ ] 3.3b S2: Implement explicit human-draft baseline ingestion and approved patch/reconciliation boundary through the formal entrypoint; meet AC17. Authorized human fixture pending; no automatic repartition or restyling.
- [ ] 3.3c S3: Spike pinned/license-cleared elkjs layered in the EE worker at the DD-15 presentation-solution seam; meet AC18 on usbc without legacy fallback. Requires S1 calibration for acceptance.
- [ ] 3.3d Deliver all five human-viewable subsystem leaves through the formal entrypoint; meet AC19 and obtain child visual/electrical acceptance, not copied checkmarks. 3.5 packages the same validated revision.
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

## 7. Approved R-B / R-H delivery queue (DD-16..20, 2026-10-07)

This queue extends rather than checks off sections 2–6. Source: amendment §3.1 R-B
and §3.2 with its approval note. C03 module-book closure is officer-reported;
its pin-group equality and visual reviews do not complete electrical closure.
Only C03 close-out is currently dispatched to Sonnet. Other implementation needs
separate allocation; build-host and S4 commit decisions remain unchanged.

- [ ] 7.1 Materialize DD-16 PresentationPlan and intent-review contract with complete pin/unit/NC accounting, approved module views, local-support relationships, exception approvals and baseline mappings; consume existing book evidence without re-partitioning or relabelling earlier reviews.
- [x] 7.2 Close C03: adjudicate ERC findings, export/check same-revision BOM coverage, update overview block names to J1/U1/U2 and bind module-book/native/netlist/data evidence. Owner: dispatched Sonnet producer; acceptance AC21, no duplicate implementation here. Officer-verified 2026-10-07: manifest root `ff8115dc…` (352 entries, 0 non-OK), 07–11 page files byte-unchanged (mtime 03:43 < run 04:38), ERC 336 rows (REAL 1: PWR_FLAG declared in design.py:308 but absent from every sheet), BOM 45 refs missing 0 / extra 0 / mismatch 1 (D1 SOT-363 vs SSOT SOT-886), 00.overview-v5 + book PDF v8 (6 pages). Remainder as ChangeProposals: 11.j1_usb-v4 (D1 footprint), PWR_FLAG on VBUS_CON/VBUS, page-specific wire-UUID seeds (46/63 UUIDs duplicated across pages). Blind review of 00 v5 not yet run.
- [x] 7.3 Before C04, verify C00 requirements and frozen C01/C02 envelope, board outline, connector faces, stackup and qualified footprint/pad mapping. Resolve the D1 SOT-363/SOT886 BR with thesmart_products duty officer ses_eed1fb0b6ffelFUGhmXVSGcp3z and consume its verified resolution. Unresolved D1 or upstream conflicts BLOCK this board's C04 entry (R15, AC22). Officer-verified 2026-10-07: `c04-entry-freeze-20261007.md` §1–3 (freeze set, chain contract, PO-1..4 sandbox assumptions under R-I/R-J); D1 lifted to SOT-886 in `design.py` (thesmart_products commit still user-pending).
- [x] 7.4 C04 / DD-20: propose and obtain placement approval; retain locks, generate actual copper-layer views plus editable PCB/Gerber/drill set; measure final DRC, copper connectivity and export parity separately; independently review intent/placement and exact layer views (AC22). Reuse section 5 work, not a second routing implementation. Officer-verified 2026-10-08 (freeze §4.5–4.9): v4 board `eb5ed99c…` + gerbers-v4 + four copper PNG + composite + stack PDF; placement gate GATE-01..07 and gerber gate G-01..04 ok=true; routing gate R-01..R-08 under Power_High 0.26 ruling with one residual (GND 0.2<0.3 F.Cu, 9 segments). Not claimed: native DRC on final bytes, export parity.
- [x] 7.5 C02 / DD-19: consume the frozen board/constraint revision through OpenSCAD/build123d in ME; deliver per-part STL and assembly/section views, mesh/wall/clearance and declared-process slicer checks; disclose physical-print limits (AC23). Reuse 5.4 and DD-10/11. Officer-verified 2026-10-08 (freeze §4.7–4.10, §4.11(b)): v3 STL/STEP + seven views; chain/mesh/view gates all pass; v4 manifest adds `exported_enclosure_mesh_sha256`. Not claimed: slicer/print/strength, fit.
- [ ] 7.6 Blender / DD-9 clearance: pin release and binary/source integrity; inventory tool/addon/dependency/asset licences and obligations; decide renderer ownership, with no optional addon or installation before clearance. No assumed rejection or automatic replacement of pyrender.
- [ ] 7.7 Blender benchmark on an authorized host: freeze matched C01 scenes, view/CMF intent, colour management, seeds/backend and comparison tolerances; measure headless EE-image feasibility, image/build/start/render/memory deltas and blind-review results against pyrender. Decide retain/adopt/blocked against predeclared budgets; ME geometry ownership unchanged (AC25). Host unavailable means BLOCKED, not fabricated metrics.
- [x] 7.8 C01 / DD-18: selected cleared producer emits product/CMF views, editable source/scene and token bindings; verify assets, view coverage and supported geometric conformance, then blind review against frozen ID intent; retain non-approval markers (AC24). Officer-verified 2026-10-08 (freeze §4.11–4.12): pyrender baseline r2, scene gate S-01..S-05 pass (S-01 secondary measured after C02' v4), Review 30 blind 3/3 READ_OK; r3 residual list open (SILVER/KEY separation, LED 3/4, footer overflow). Blender path remains 7.6/7.7.
- [x] 7.9 C00 final document check: deliver NN.c00-prd-vN.docx plus human PDF through the approved document pipeline; check requirements/source/decision coverage, cross-stage consistency and rendered readability. Requirements remain upstream of 7.3, not deferred until this task (AC26). Officer-verified 2026-10-08 (freeze §4.13): `12.c00-prd-v1.{docx,pdf}`, manifest v3, `c00_prd_gate` P-01..P-05 pass, Review 31 blind 3/3. Residual r2 list: empty TOC, header placeholder, title wrap; docxmcp BR filed.
- [x] 7.10 Bind C00–C04 sets under DD-17/R-G human-machine tree separation, NN.<stage>-<name>-vN naming, history and one manifest; record all gate/review omissions and explicit non-claims. Architecture Sync and release approval are separate from document completion (AC27). Officer-verified 2026-10-08: `outputs/btdongle_ms/c00c04_bundle_manifest-v1.json` `645e9a78…` (45 human + 76 machine files measured, 5 stage manifests, 10 gate receipts bound to HEAD `7a16c31`) + `.src/reports/c00c04_omissions-v1.md` `4fe2bec3…` (37 gates, 9 non-claims, 4 open residuals); hashes 674 entries 0 non-OK, root `1027654b…`. Note: bundle `hashes_root` records the pre-rebuild baseline `55b8f2dc…` (a manifest cannot carry its own post-rebuild root); C04 routing receipt ok=false is the declared GND residual, not a bundle defect. Release approval NOT claimed.

Output order: 7.2 → 7.4 → 7.5 → 7.8 → 7.9; 7.3 is a prerequisite to 7.4,
and 7.6–7.7 precede any Blender selection for 7.8. This order never permits
invented upstream geometry, automatic fallback, unapproved fabrication or a commit.
