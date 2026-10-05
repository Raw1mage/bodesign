# P0.1 Baseline Version & Entrypoint Inventory

**Milestone**: Phase 1 (P0 Baseline Inventory, Suite Classification & Corpus Setup)  
**Task**: P0.1 / Section 1.1 in [tasks.md](file:///home/pkcs12/projects/bodesign/plans/eda-bridge_unified-collaborative-rebuild/tasks.md)  
**Date**: 2026-10-06  
**Status**: Completed (Reconciled with Astra Architecture Review)  
**Rule Compliance**: Inventory-only phase. Zero package installations, zero AGPL code ingestion, zero code file mutations, zero commits or resets.

---

## 1. Pinned Source & Runtime Identity

### 1.1 Source Repository Identity
- **Monorepo Root**: `/home/pkcs12/projects/bodesign`
- **Pinned HEAD SHA**: `16ed19219e6d3961c860410ccb3d48b228165d08` (`16ed192`)
- **Shared Working Tree Manifest (`git status --porcelain`, no pathspec)**:

```text
Dirty Tracked Files (26 M):
 M .specbase/events.sqlite
 M .specbase/index.sqlite
 M .specbase/ragbase.sqlite
 M AGENTS.md
 M mcp.json
 M packages/shared/bodesign_shared/paths.py
 M plans/c03_delivery_contract_and_engine_seams/README.en.md
 M plans/eda-bridge_multi-sheet-subsystem-schematics/.state.json
 M plans/eda-bridge_multi-sheet-subsystem-schematics/README.en.md
 M plans/eda-bridge_multi-sheet-subsystem-schematics/data-schema.json
 M plans/eda-bridge_multi-sheet-subsystem-schematics/design.md
 M plans/eda-bridge_multi-sheet-subsystem-schematics/errors.md
 M plans/eda-bridge_multi-sheet-subsystem-schematics/grafcet.json
 M plans/eda-bridge_multi-sheet-subsystem-schematics/handoff.md
 M plans/eda-bridge_multi-sheet-subsystem-schematics/idef0.json
 M plans/eda-bridge_multi-sheet-subsystem-schematics/observability.md
 M plans/eda-bridge_multi-sheet-subsystem-schematics/proposal.md
 M plans/eda-bridge_multi-sheet-subsystem-schematics/sequence.json
 M plans/eda-bridge_multi-sheet-subsystem-schematics/spec.md
 M plans/eda-bridge_multi-sheet-subsystem-schematics/tasks.md
 M plans/eda-bridge_multi-sheet-subsystem-schematics/test-vectors.json
 M services/mcp/server.py
 M skills/bodesign/engines/kicad/references/config-reference.md
 M skills/bodesign/scripts/gate.py
 M specs/architecture.md
 M specs/product/pcb_ai_viewer/spec.md

Untracked Entries (53 ??):
?? .claude/
?? .specbase/retros/
?? bogus_out
?? ctrlf
?? deploy/
?? docs/events/event_20260908_partition-comparison-and-a-guard-that-measured-the-wrong-fragment.md
?? docs/events/event_20260908_round45_replica_implementation.md
?? docs/research/report_20261004_c03_lint_qa_structural_review.md
?? docs/runbooks/
?? experiments/aiguard_c01/
?? experiments/aiguard_c03_compose/
?? experiments/aiguard_c03_fix/
?? experiments/aiguard_c03_verify/
?? experiments/aiguard_c04/
?? experiments/btdongle_multisheet_e2e.py
?? experiments/c01_colortest/
?? experiments/c01_v31_render/
?? experiments/c01_v3_render/
?? experiments/c02_me_build/
?? experiments/round46_page_extent_probe.py
?? experiments/round46_replica_wire_probe.py
?? experiments/round46_wire_label_coexist_probe.py
?? issues/BR_20261001_bound_mcp_dependency_upper_limit.md
?? issues/assets_20260706_c03_session/_m4_conflict_probe.py
?? issues/assets_20260706_c03_session/export_ccm_svg.py
?? issues/assets_20260706_c03_session/export_full_board_png.py
?? issues/assets_20260706_c03_session/gen_product.py
?? p1.out
?? p2.out
?? p3.out
?? p4.out
?? packages/eda-bridge/bodesign_eda_bridge/hierarchical.py
?? packages/eda-bridge/bodesign_eda_bridge/partition.py
?? packages/eda-bridge/bodesign_eda_bridge/replica_fidelity.py
?? plans/eda-bridge_c04-route-place-quality/
?? plans/eda-bridge_layered-pipeline/
?? plans/eda-bridge_scale-coherence/
?? plans/eda-bridge_unified-collaborative-rebuild/
?? plans/eda_drafting-rulebook-first/
?? plans/eda_draftsman-v2/artifacts/
?? plans/infra_dockerlab-migration-and-structural-review/
?? plans/template_bodesign-pcb/
?? plans/template_c-stage-delivery/
?? ragbase/ragbase
?? scripts/sync_kb.sh
?? skills/bodesign/engines/kicad/scripts/schemdraw_templates/
?? specs/aiguard_refs-ssot-build/
?? specs/eda-bridge_occupancy-ledger/
?? specs/workflow_c03-stage-entry-gate/
?? tests/test_check_c03.py
?? tests/test_dd14_text_graphics_clearance.py
?? tests/test_dd16_flag_vertical_stack.py
?? tests/test_dd24_flag_uniform_x.py
?? tests/test_dd28_cross_component_occupancy.py
?? tests/test_dd31_pitch_align_main_chip.py
?? tests/test_mcp_emit_multisheet.py
?? tests/test_multisheet_emit.py
?? tests/test_multisheet_global_label_link.py
?? tests/test_replica_emit.py
?? tests/test_replica_fidelity.py
?? tests/test_schemdraw_templates.py
?? tests/test_sheet_name_validation.py
?? tests/test_sheet_partition.py
?? vpg
```

### 1.2 Served Runtime Identity
- **Production Server Endpoint**: Remote DockerLab host CT105 (`http://192.168.100.141:8177/mcp/`)
- **Docker Image Tag & Digest**: `registore.thesmart.cc/bodesign:v0.3.0-dockerlab`
- **Served Tool Count**: **61 tools** in the served runtime container (`registore.thesmart.cc/bodesign:v0.3.0-dockerlab`).  
  *(Note: The local monorepo source tree currently registers 62 tools due to the uncommitted local addition of `bodesign_design_suggest` in `services/mcp/server.py`).*

---

## 2. Toolchain & Environment Freeze

Measured directly on the host development machine (`/home/pkcs12/projects/bodesign`):

| Tool / Runtime | Measured Version | Location / Source | Availability Status | Notes |
|---|---|---|---|---|
| **Python** | `3.12.3` | `/usr/bin/python3` | Available on host | Base runtime for pure-python core packages |
| **Git** | `2.43.0` | `/usr/bin/git` | Available on host | Monorepo VCS |
| **KiCad CLI** | `9.0.9` | `/usr/bin/kicad-cli` | Available on host | Headless schematic/netlist/ERC/DRC/gerber exporter |
| **KiCad Python (`pcbnew`)** | `9.0.9-9.0.9~ubuntu24.04.1` | Python 3 binding | Available on host | Board layout manipulation & DRC Python bindings |
| **ngspice** | `ngspice-42` (KLU solver) | `/usr/bin/ngspice` | Available on host | Analog subcircuit simulation & SI check backend |
| **LibreOffice** | `24.2.7.2` | `/usr/bin/libreoffice` | Available on host | Headless document (docx -> pdf) conversion companion |
| **Java Runtime** | `OpenJDK 21.0.12.1` | `/usr/bin/java` | Available on host | Required for Freerouting JAR execution |
| **kiutils** | Absent | Python site-packages | **Missing on host** | KiCad schematic parser library; present in EE worker image |
| **LibreDWG (`dxf2dwg`/`dwg2dxf`)** | Absent | `/usr/bin/dxf2dwg` | **Missing on host** | Local CAD drawing conversion; present in worker image |
| **OpenSCAD** | Absent | `/usr/bin/openscad` | **Missing on host** | CSG mechanical CAD renderer; present in ME worker image |
| **build123d / OCP** | Absent | Python site-packages | **Missing on host** | Boundary representation / STEP kernel; present in ME worker |

---

## 3. MCP Server Formal Delivery Entrypoints

Inspected from [`services/mcp/server.py`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py).  
The local server codebase defines **62 formal tools** divided across 3 execution groups:
- **Core (28 tools)**: Lightweight / pure-python operations, planning, readiness, constraint assembly, vault, and doc export.
- **EE (27 tools)**: Electronics engineering operations requiring KiCad (`kicad-cli`, `pcbnew`), `ngspice`, or `atopile`.
- **ME (7 tools)**: Mechanical engineering operations requiring OpenSCAD, build123d, or 3D rendering kernels.

### 3.1 Core Group (28 Tools)
1. [`bodesign_init`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L50): Self-describing usage doctrine and organism orientation.
2. [`bodesign_declare_circuit`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L234): C03 topology declaration layer (pure-python net declaration).
3. [`bodesign_emit_multisheet`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L202): Hierarchical multi-sheet schematic emitter (root + leaf `.kicad_sch`).
4. [`bodesign_check_c03`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L604): C03->C04 stage-entry deterministic gate.
5. [`bodesign_design_suggest`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L588): Evidence-backed draft suggestion for pin allocation / connectivity.
6. [`bodesign_prd_bom_crosscheck`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L542): C00->C03 requirements-to-BOM fulfillment gate.
7. [`bodesign_verify_netlist_fidelity`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L547): Electrical-axis gate comparing spec net partition with emitted KiCad netlist.
8. [`bodesign_readability_gate`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L563): Form-axis gate scoring schematic readability (junctions, stubs, subcircuits).
9. [`bodesign_render_gerber_preview`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L776): Pure-python Gerber layer preview rendering.
10. [`bodesign_spice_model_card`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L469): Datasheet-grounded SPICE model card generator.
11. [`bodesign_emit_doc`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L279): Markdown deliverable conversion to docx and pdf.
12. [`bodesign_c00_emit_prd_docx`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L284): PRD document renderer.
13. [`bodesign_c01_generate_concept_image`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L337): Concept visual asset generation hook.
14. [`bodesign_dxf_to_dwg`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L782): DXF to DWG conversion wrapper (gates on LibreDWG).
15. [`bodesign_dwg_to_dxf`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L788): DWG to DXF conversion wrapper (gates on LibreDWG).
16. [`bodesign_mcp_call`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L650): MCP-to-MCP delegation bridge.
17. [`bodesign_stage_dir`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L620): Directory tree staging in workspace.
18. [`bodesign_workspace_inspect`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L625): Workspace token and filesystem inspection.
19. [`bodesign_vault_ingest`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L425): Component Vault ingestion.
20. [`bodesign_vault_query`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L429): Component Vault querying by MPN or keyword.
21. [`bodesign_vault_spec_check`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L433): Component spec verification against Component Vault.
22. [`bodesign_vault_queue`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L439): Component knowledge queue audit.
23. [`bodesign_vault_diagnostics`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L444): Component Vault diagnostic probes.
24. [`bodesign_kb_query`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L1081): PCB domain knowledge base search (read-only).
25. [`bodesign_kb_get`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L1133): PCB domain knowledge base single object retrieval (read-only).
26. [`bodesign_cache_provision`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L918): Deliverable cache provision.
27. [`bodesign_cache_export`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L949): Deliverable cache export to host path.
28. [`bodesign_cache_close`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L963): Deliverable cache closing and cleanup.

### 3.2 EE Group (27 Tools)
1. [`bodesign_emit_symbol`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L158): Generate KiCad `.kicad_sym` from pin list.
2. [`bodesign_compose_schematic`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L165): Compose flat schematic from design spec.
3. [`bodesign_emit_layout`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L256): Place footprints via `pcbnew` and render SVG.
4. [`bodesign_emit_fab`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L267): Export gerbers, drill, pos, STEP, PDF fab package.
5. [`bodesign_simulate`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L464): Analog circuit simulation via `ngspice`.
6. [`bodesign_analyze_emc`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L513): EMC pre-compliance analysis on schematic + PCB.
7. [`bodesign_analyze_thermal`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L518): Thermal hotspot analysis.
8. [`bodesign_analyzer_selfcheck`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L449): Self-check for analysis engines.
9. [`bodesign_export_bom`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L523): Grouped BOM CSV export.
10. [`bodesign_export_netlist`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L537): KiCad netlist export via `kicad-cli`.
11. [`bodesign_render_companion`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L274): Render schematic visual companion (PDF/PNG).
12. [`bodesign_route_net2pcb`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L655): Build netted `.kicad_pcb` from KiCad netlist.
13. [`bodesign_via_in_pad`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L667): BGA via-in-pad fanout generator.
14. [`bodesign_pour_planes`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L673): Copper plane pouring and stitching vias.
15. [`bodesign_widen_bus_tracks`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L683): Bus trace widening.
16. [`bodesign_apply_pad_intrinsic_overrides`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L706): Package-intrinsic pad clearance overrides.
17. [`bodesign_length_match_bus`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L689): Bus serpentine length matching.
18. [`bodesign_layout_drc_gate`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L695): Native KiCad DRC violation evaluation.
19. [`bodesign_clean_micro_stubs`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L701): Clean routing micro-stubs below threshold.
20. [`bodesign_si_check`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L713): High-speed signal integrity check via ngspice.
21. [`bodesign_autoroute`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L722): Freerouting autoroute invocation.
22. [`bodesign_autoroute_preflight`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L751): Pre-route feasibility and capacity probe.
23. [`bodesign_placement_preflight`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L734): Placement density and overlap probe.
24. [`bodesign_bga_escape_capacity`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L742): BGA escape layer capacity calculator.
25. [`bodesign_component_search`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L756): LCSC / EasyEDA component search.
26. [`bodesign_component_fetch`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L761): Authoritative KiCad symbol and footprint fetcher.
27. [`bodesign_ato_build`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L248): Atopile `.ato` circuit compilation.

### 3.3 ME Group (7 Tools)
1. [`bodesign_c02_export_stl`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L342): Export STL enclosure from OpenSCAD.
2. [`bodesign_c02_export_skp`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L347): Honest unavailable gate for SketchUp SKP export.
3. [`bodesign_c02_export_step`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L352): Export STEP model via build123d CAD kernel.
4. [`bodesign_render_board_model`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L358): Render 3D board model (glTF / GLB).
5. [`bodesign_c02_render_enclosure`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L365): Render enclosure STL with camera views.
6. [`bodesign_c02_voice_to_design`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L373): Voice transcript to parametric CAD pipeline.
7. [`bodesign_c02_project_svg`](file:///home/pkcs12/projects/bodesign/services/mcp/server.py#L397): Project 3D enclosure STL to 2D technical drawing SVG.

---

## 4. External Reference Clones Inventory

Located in scratch directory `/home/pkcs12/.cache/scratch/`:

| Repository Slug | Remote URL | Git Commit SHA | Commit Date | Author | Declared License (Text/Header) | License File Status | Copy / Dependency Permission Status (DD-9) |
|---|---|---|---|---|---|---|---|
| **`kicad-mcp-server`** | `https://github.com/mixelpixx/KiCAD-MCP-Server` | `cbb59a6203997f5e916be7e0480d63fe5519134a` | 2026-10-01 | mixelpixx | `MIT License` (c) 2024 mixelpixx | `LICENSE` (1066 B) | **No blanket copy/dependency permission**. Schema and tool convention reference only; clean-room native implementation; no clone dependency. |
| **`kicad-happy`** | `https://github.com/aklofas/kicad-happy` | `78b8f02e70af5a29aef99ebd66b0d3538fb6010c` | 2026-10-04 | Andrew Klofas | `MIT License` (c) 2025 Andrew Klofas | `LICENSE` (1070 B) | **No blanket copy/dependency permission**. Upstream source of original analyzer rules; compare bundled ancestry before importing; any selective extraction requires explicit notice preservation; no clone runtime dependency. |
| **`mcp-server-solidworks`** | `https://github.com/eyfel/mcp-server-solidworks` | `7d50f43c81b5a9c26575bbe87b2af9b853f2f9d9` | 2026-10-05 | Çağatay Bakan | `GNU AFFERO GENERAL PUBLIC LICENSE Version 3, 19 November 2007` (c) 2007 Free Software Foundation | `LICENSE` (34523 B) | **STRICTLY QUARANTINED (NO PERMISSION)**. Zero code copying, zero schema/class ingestion. Concept-only reference; AGPL boundaries enforced by DD-9 and DD-10. |
| **`onshape-mcp`** | `https://github.com/hedless/onshape-mcp` | `a9c2a5efbcebdf79d6d010184bff22658e7abfa6` | 2026-09-10 | Damond Hedley | `MIT License` (declared in `README.md` & `pyproject.toml`) | Declared in `README.md` & `pyproject.toml` | **No blanket copy/dependency permission**. Conceptual reference for assembly mate and feature-tree patterns; clean-room design-ir implementation; no clone runtime dependency. |
| **`fusion360-mcp-server`** | `https://github.com/faust-machines/fusion360-mcp-server` | `ba8560f321656aa493cdc775bc2fa7b2e7d8f005` | 2026-09-16 | July Hata | `MIT License` (c) 2025 Faust Network, Inc. | `LICENSE` (1076 B) | **No blanket copy/dependency permission**. Conceptual reference for headless command execution; no clone runtime dependency. |

### Legal & Boundary Invariants
- **DD-9 Authority Boundary**: Declaration of an open-source license (such as MIT) does **NOT** constitute permission to copy code into `bodesign` or install external MCP clones. DD-9 explicitly mandates that `bodesign` will not install five competing MCP servers.
- **AGPL Quarantine**: `mcp-server-solidworks` is GNU AGPLv3. Under DD-9 and DD-10, no code, classes, or schemas may be copied into `bodesign`. Only high-level conceptual ideas (such as feature parameterization) may inform independent clean-room specifications.
- **Attribution Preservation**: Where approved algorithmic logic is selectively adapted (e.g. sexp parsing), upstream attribution and copyright notices must be preserved verbatim.

---

## 5. Bundled Happy / KiCad Code Inventory

**Audited Population**: Regular Source Files Only (Excluding Directories and `__pycache__`)  
Inspected at [`skills/bodesign/engines/kicad/scripts/`](file:///home/pkcs12/projects/bodesign/skills/bodesign/engines/kicad/scripts/) vs upstream [`/home/pkcs12/.cache/scratch/kicad-happy/skills/kicad/scripts/`](file:///home/pkcs12/.cache/scratch/kicad-happy/skills/kicad/scripts/):

- **Bundled regular source files**: **37 files** (excludes directory `schemdraw_templates/` [5 template files] and `__pycache__`)
- **Upstream regular source files**: **41 files** (excludes directory `envelopes/`)
- **Common regular source files**: **31 files** (8 byte-identical, 23 modified)
- **Files unique to bundled regular source files (6)**:
  1. `host_from_pinmap.py`: Pin mapping generator from host definitions
  2. `netlist_to_kicad_sch.py`: Netlist to KiCad schematic generator
  3. `netlist_to_schematic.py`: Netlist conversion adapter
  4. `netlistsvg_analog_skin.svg`: SVG skin for analog schematics
  5. `render_hybrid_sch.sh`: Shell script for hybrid schematic rendering
  6. `symbol_4edge.py`: 4-edge symbol placement helper
- **Files unique to upstream regular source files (10)**:
  1. `analyzer_envelope.py`: Envelope calculation additions in v2.3.0
  2. `bus_resolver.py`: Bus naming resolver
  3. `capability_mode.py`: Capability mode negotiation
  4. `check_report_sections.py`: Report section structural checker
  5. `gen_output_schema_md.py`: Documentation generator
  6. `inputs_builder.py`: Context inputs builder
  7. `lookup_detectors.py`: Component lookup detectors
  8. `lookup_helpers.py`: Component lookup helpers
  9. `run_id.py`: Run identifier generator
  10. `schema_codec.py`: Codec for finding schema
- **Identical regular source files between bundled and upstream (8)**:
  - `.gitignore`
  - `cross_verify.py`
  - `detection_schema.py`
  - `detector_helpers.py`
  - `export_issues.py`
  - `methodology_gerbers.md`
  - `methodology_pcb.md`
  - `sexp_parser.py`
- **Key Modifications in Bundled Engine (23 regular source files)**:
  - [`validation_detectors.py`](file:///home/pkcs12/projects/bodesign/skills/bodesign/engines/kicad/scripts/validation_detectors.py): Contains bodesign's **PC-001 passive completeness gate** (`validate_passive_completeness`, DD-1 / BR_20260723), providing deterministic decoupling verification on IC power pins.
  - [`domain_detectors.py`](file:///home/pkcs12/projects/bodesign/skills/bodesign/engines/kicad/scripts/domain_detectors.py): Contains vacuous-pass fixes (BR_20260731) preventing false green verdicts on empty RF networks.
  - [`finding_schema.py`](file:///home/pkcs12/projects/bodesign/skills/bodesign/engines/kicad/scripts/finding_schema.py) and [`kicad_types.py`](file:///home/pkcs12/projects/bodesign/skills/bodesign/engines/kicad/scripts/kicad_types.py): Extended with bodesign-specific finding categories and provenance metadata.
