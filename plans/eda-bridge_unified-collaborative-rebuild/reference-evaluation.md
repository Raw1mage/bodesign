# External Reference Evaluation — 2026-10-06

Read-only source inventory; no upstream tests, CAD applications or external APIs
were run. Source evidence was collected by worker ses_ef2b3b2d0ffecoPL5PnQW9a0bT;
adoption decisions below belong to the architecture lead. Paths below are relative
to the named clone under `/home/pkcs12/.cache/scratch/`. Commit-pinned upstream URLs
remain the provenance when scratch clones disappear. No upstream code was copied.

## Source and License Baseline

| Clone / upstream | Inspected HEAD | License evidence and adoption constraint |
| --- | --- | --- |
| kicad-mcp-server / github.com/mixelpixx/KiCAD-MCP-Server | cbb59a6203997f5e916be7e0480d63fe5519134a | LICENSE:1-21 MIT; retain notice for any extracted code; Node/Python/KiCad server is not a core dependency |
| kicad-happy / github.com/aklofas/kicad-happy | 78b8f02e70af5a29aef99ebd66b0d3538fb6010c | LICENSE:1-21 MIT; compare existing bundled engine ancestry before importing; preserve attribution |
| mcp-server-solidworks / github.com/eyfel/mcp-server-solidworks | 7d50f43c81b5a9c26575bbe87b2af9b853f2f9d9 | LICENSE AGPLv3; compiler/solidworks/pyproject.toml:15 AGPL-3.0-only; no code/schema copying or linking approved; commercial terms require separate agreement |
| onshape-mcp / github.com/hedless/onshape-mcp | a9c2a5efbcebdf79d6d010184bff22658e7abfa6 | README:391-393 says MIT, but searched license files and package metadata do not supply full grant; copying/dependency blocked pending clarification |
| fusion360-mcp-server / github.com/faust-machines/fusion360-mcp-server | ba8560f321656aa493cdc775bc2fa7b2e7d8f005 | LICENSE:1-21 MIT; Fusion SDK/application entitlement and supported build remain separate prerequisites |

License observations are engineering intake, not legal clearance. Adapter isolation
does not itself remove upstream license obligations. No new CAD purchase, cloud
upload or source disclosure is authorized. Existing dependency license compatibility
and notices must be checked before extraction. The native designs below use domain
requirements and documented APIs, not renamed copies of upstream implementation.

## Capability Decisions

| Capability / evidence | Decision and owner | Limits and acceptance |
| --- | --- | --- |
| Reused hierarchical-sheet annotation: KiCad python/utils/symbol_instances.py:425-503 | Selective MIT extraction/refactor into existing eda-bridge annotation seam; not the entire MCP server | Identity includes sheet-instance path plus symbol UUID; multi-unit packages share package reference only within the correct instance; native export on declared KiCad versions must pass |
| Symmetric escaping: KiCad python/utils/sexpr_format.py:177-194; tests/test_sexpr_escaping.py:49-60 | Selective MIT codec reuse in one eda-bridge S-expression module | Decode once; quotes, literal backslashes, multiline values round-trip; retain notices and test provenance; no parallel codec in skills |
| DSN/SES lifecycle: KiCad python/commands/freerouting.py:716-763,1103,1162 | Native refactor around existing freerouting adapter | Per-job staging is not a security sandbox; use scoped cache, revision-bound DSN/SES, timeouts and explicit cancellation; never import stale SES |
| Hole clearance: same file:233-262,565-576; tests/test_dsn_hole_edge_clearance.py:55-90 | Selective MIT geometry port with native DRC acceptance | Upstream covers near-circular Edge.Cuts in micrometers, not arbitrary cutouts; unsupported units/shapes are disclosed, never silently declared protected |
| JLCPCB/LCSC: python/kicad_interface.py:6229-6273; src/tools/datasheet.ts:80-83 | Direct external catalog adapter through existing component-kb/vault | Explicit live vs cached mode, never silent fallback; catalog terms separate from MIT; 2.5M+ not measured; generated URL is not a retrieved or verified datasheet |
| Pure parser: Happy skills/kicad/scripts/sexp_parser.py:11-100 | Reconcile/reuse existing MIT analyzer, then converge one native parser interface | Parser itself is stdlib-only; full repo is not proven dependency-free; malformed/unsupported syntax produces structured gaps |
| Power topology and physical math: domain_detectors.py:5283-5343; detection_schema.py:49-94; analyze_schematic.py:7660-7732 | Native typed calculations in workflow-core, using design-ir topology and evidence | Preserve formulas, not implicit stray=3pF or keyword current estimates; require Vref, R/C, parasitics, units, conditions and uncertainty; topology alone is not stability proof |
| Connector ESD: domain_detectors.py:2470-2558 | Native workflow-core coverage rules with explicit applicability | Net protection coverage is not IEC immunity; proposed signal:GND >3:1 rule was not located by inventory and needs cited scope/threshold before enforcement |
| DS findings and fab release: analyze_schematic.py:5331-5452; fab_release_gate.py:50-59,403-458 | Native workflow-core release policy, not direct trust in upstream PASS | DS-001 error, DS-002 warning, DS-003 info; missing unrouted count may default to zero upstream. Require per-required-claim evidence and exact artifacts; no guessed zero or 90% blanket permission |
| Feature Graph: SolidPilot cad-planner/contracts/feature-graph.schema.json:3-40; compiler/solidworks/pycompiler/compiler.py:59-99 | Independent bounded design-ir feature DAG; deterministic ME lowering in existing worker | Do not copy AGPL schema/compiler. Keep validate-resolve-lower-execute separation and capability negotiation; CAD failure is not transactional rollback |
| Anchor resolution: compiler/solidworks/pycompiler/resolver.py:17-84 | Native revision-bound anchor contract | Upstream hints are not consumed; geometric anchors promise fresh replay only. Ambiguous/missing faces refuse; do not assume persistent face indices across edits |
| Reverse drawings: cad-planner/drawing/dxf_read.py:2-10; adapters/claude/server.py:1252-1274; README:41,248 | Defer full reverse reconstruction; use existing DXF/DWG adapters for explicit imports | Reader does not infer 3D; DWG path requires SolidWorks. 0.02% is unverified historical README evidence, not an accuracy SLA; dimensions/material density and independent fit tests needed |
| MCP at top: SolidPilot CONTRIBUTING.md:23; adapters/claude/ir_execution_port.py:31-65 | Adopt architecture pattern natively | MCP/CLI invoke shared use cases; internal typed execution ports use existing worker transport, not nested MCP servers |
| Onshape auth/revisions: api/client.py:55-63,107-147; api/partstudio.py:32-76 | Optional direct vendor REST adapter, independently implemented from approved vendor API docs | Inspected code uses Basic, not claimed HMAC; explicit microversion management not evidenced. Select supported auth without fallback; pin immutable revision and prove precondition support before writes |
| Variables/FeatureScript: api/variables.py:73-164; api/featurescript.py:13-64 | Optional vendor adapter after credentials/data-egress approval | Whole-table read-modify-write needs concurrency guard; inspected FeatureScript lambda is read-only, not general persistent feature creation |
| Interference: analysis/interference.py:92-239 | Native broad-phase pruning plus exact worker geometry check | World AABB overlap is candidate selection, not collision proof or clearance certification; exact unavailable => indeterminate |
| CAD main-thread dispatch: Fusion addon/server/event_bridge.py:66-157; socket_server.py:29,82-90 | Native execution-port/job contract; optional licensed workstation adapter | Port 9876 is not adopted; authenticated approved transport and registry allocation required. Queue timeout can cancel pending work, not undo running mutation; unknown outcome prevents blind replay |
| Sheet metal/sketch: Fusion addon/server/command_handler.py:733-782,2992-3075 | Optional direct Fusion API adapter; deferred beyond initial enclosure slice | Require version/capability and explicit stationary-face anchor; never select first planar face silently. Constraint creation does not prove solved/fully constrained sketch |

## Scope and Order

P0 adds source/license inventory and identifies existing bundled Happy overlap.
P1 adds bridge contracts and outcome semantics without proprietary dependencies.
P2 prioritizes escaping/annotation and evidence-backed analyzer convergence.
P4 adds local ECAD-MCAD STEP/enclosure checks through existing ME toolchain.
Cloud/workstation CAD and reverse/sheet-metal adapters are optional follow-on
work, not prerequisites for core delivery. The earlier 12-16 week estimate excludes
these optional integrations and requires P0 re-estimation for the bridge slice.

No upstream tests were executed. Statically present implementation, tests, README
claims and absent evidence are intentionally distinguished throughout this matrix.
