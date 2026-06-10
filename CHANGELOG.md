# Changelog

All notable changes to bodesign are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); the source of truth for design
rationale is the plan-builder specs under `specs/`.

## [Unreleased]

### Added — persistent server-side Component Vault (SQLite + FTS5, 8 layers)
- `packages/component-kb` gains `storage.py` + `repository.py`: a durable vault under
  `BODESIGN_VAULT_DIR` (docker named volume `bodesign-vault`) with WAL SQLite,
  `user_version` migrations v1–v5, content-addressed blob store, and fail-fast
  startup (missing dir / corrupt DB → VAULT-E001/E002, never silently rebuilt).
- Eight knowledge layers: identity (canonical MPN + aliases, explicit absent),
  documents (sha256 dedup + version chains + mandatory provenance), chunks
  (doc-core adapter + FTS5 BM25 search with page anchors; extractor upgrades mark
  stale, never delete), spec EAV (field_path registry, min/typ/max + condition
  coexistence, `verified`-needs-evidence enforced by trigger), EDA assets
  (symbol/footprint verification ladder unverified→pin-checked→drc-passed with
  provenance per rung), app knowledge (4 payload types, evidence-gated trust),
  append-only audit log (trigger-enforced), usage/sourcing (cross-project
  occurrence aggregation, point-in-time sourcing snapshots, substitutions).
- API surface: 4 MCP tools (`bodesign_vault_ingest/query/spec_check/queue`) and
  5 HTTP routes share the thin `services/mcp/vault_api.py` layer; `spec_check`
  consults the server vault first and marks verdict origin
  (`server-vault` | `client-cache`) while keeping four-state semantics.
- Client-cache import (`import_client_cache`): always unverified with
  `client-cache-import` provenance; conflicts keep both sides (VAULT-E903).
- Consumers: `kicad_emit.vault_symbol` / `footprint_map.vault_footprint` query
  the vault via duck-typed repository and return explicit absent — no guessing.
- Tests: `tests/test_vault_{storage,chunks,specs,api,usage,eda}.py` — 105 new
  vault tests; full suite 132/132 green. Spec: `plans/feature_component_vault/`.

### Fixed — workers topology silently reverted to monolith on rebuild
- `mcpctl.sh` only knew `docker-compose.yml` (monolith), so any `rebuild`/`restart`
  dropped the opt-in `docker-compose.workers.yml` split (heavy CAD/EDA dep isolation,
  core + me/ee workers) and orphaned the worker containers — a silent regression.
- Added a **sticky `BODESIGN_WORKERS` mode** (mirrors `BODESIGN_DEV`): once started with
  `BODESIGN_WORKERS=1`, a `.run/.workers` marker keeps every later `restart`/`rebuild` in
  workers mode; `BODESIGN_WORKERS=0` reverts to the monolith. `status` now reports the mode
  + per-worker health; all `up` calls use `--remove-orphans` so switching modes stays clean.

### Added — C00→C04 judgment layer, recursive reconciliation, feasibility triage
- Per-stage **design-judgment references** — the "how to think" layer the agent reads,
  distinct from the execution engines/MCP. C01: reduction-lens + Ashby material selection
  + design-for-disassembly. C02: DFM/DFA/tolerance/material + IP-sealing advisory, and a
  geometry-authoring (inspect-don't-visualise) loop. C03: EE-design advisory (regulator
  selection, decoupling, the SI requirement numbers, thermal, RF, power-sequencing) and a
  **pinout→circuit synthesis method** (classify every pin's obligation, ground in the
  reference design). C04: stackup/placement, HDI (IPC-2226), SI realisation.
- **Cross-stage reconciliation** ([`references/cross-stage-reconciliation.md`](skills/bodesign/references/cross-stage-reconciliation.md)) —
  area / thermal / height budgets and C06 verdict-fails route *back* to the owning stage,
  reusing the existing `BlockerReturn` primitive (`return_blocker`/`list_blockers`/
  `ingest_blocker`). `assess_package_readiness` now surfaces unresolved blockers and blocks
  the milestone all-clear — machine-enforced, not memory-dependent.
- **Feasibility triage** (`classify_product_feasibility`, `bodesign_workflow_core.feasibility`)
  — classifies a product into a C04 delivery tier (1 fab-ready · 2 routed-draft · 3
  concept+constraints → pro-EDA) by the hardest complexity driver, declared up front at C01
  so "give C00, get C01–C04" is honest per-product; re-run firm at C03.
- **SI constraint handoff** (`emit_si_constraint_export`, `bodesign_workflow_core.si_handoff`)
  — Tier-3 (HDI/DDR/RF) products emit a neutral SI constraint package (JSON source-of-truth
  + CSV net-classes + per-tool import mapping for Allegro / Xpedition / Altium); the routing
  wall becomes a clean pro-EDA handoff. Constraints bodesign did not derive are listed under
  `tbd[]`, never guessed.
- Tests: `test_feasibility`, `test_reconciliation_gate`, `test_si_handoff` (full suite green).

### Added — C04 EDA toolchain (MCP)
- `bodesign_impedance_solve` — pure-core closed-form microstrip/differential class
  widths + delay constants from an explicit stackup (guidance; fab-solver confirmed).
- `bodesign_widen_bus_tracks`, `bodesign_length_match_bus` — clearance-safe bus
  finishing on the EE worker (widen to target width; clearance-aware serpentine
  skew tuning), each writing a new `.kicad_pcb`.
- `bodesign_render_gerber_preview` — real single-layer Gerber raster (gerber-core /
  pygerber); composite/stack modes return explicit `render-unavailable`.
- Graduated spec: [`specs/feature/eda-mcp-toolchain/`](specs/feature/eda-mcp-toolchain/README.md)
  documents the full C04 routing/finishing toolchain; KB-indexed.

### Changed — tool generality (no SILENT overfit)
- `bodesign_route_net2pcb` — connector pin expansion is no longer gated on refdes
  `J1`. Accepts an explicit `connectors` pinmap and otherwise applies the built-in
  USB-C table to any USB-C footprint on any refdes; result reports `applied_pinmaps`
  and `unmapped_connectors` instead of silently skipping.
- `bodesign_si_check` — driver/load/edge/thresholds (`rdrv`/`cload`/`edge_ns`/
  `overshoot_pass_pct`/`overshoot_warn_pct`) are now caller-overridable with
  documented STM32-class-CMOS defaults; result echoes the `effective` values.
- `bodesign_emit_layout` — placement grid + outline margin exposed
  (`board_mm`/`columns`/`place_start_mm`/`place_pitch_mm`/`margin_mm`).
- `bodesign_emit_fab` — PDF layer set exposed via `pdf_layers` (default = 2/4-layer).
- `bodesign_pour_planes` — stitch net + grid/via geometry exposed
  (`stitch_net`/`stitch_pitch_mm`/`stitch_drill_mm`/`stitch_pad_mm`).
- `bodesign_via_in_pad` — JLCPCB-advanced POFV via defaults documented.

### Added — generality contract enforcement
- `docs/generality-check.md` — the no-silent-overfit bar + 5-axis checklist + audit.
- `tests/test_tool_generality.py` — schema-level regression guard asserting each
  tool's board/process assumptions stay caller-overridable or reported.
- Durable socket-level MCP smoke test (`test_socket_level_list_and_call_smoke`):
  real `initialize → list_tools → call_tool` roundtrip over stdio; skips without
  the MCP SDK.

### Fixed
- Repaired a broken HEAD where `impedance.py` and the gerber-preview implementation
  had been left untracked while their wiring was committed (fresh-checkout import
  failure).

### Known limitations
- Real-board EE execution (widen/length-match/route/pour via `pcbnew`) requires the
  EE worker; board-level mutation regression is env-gated. Decision logic is covered
  by pure-helper + schema tests on a bare host.

## Earlier
- `component-kb`: lazy MPN-keyed datasheet vault + RCA spec-audit gate
  (`bodesign_datasheet_register` / `bodesign_spec_check` / `bodesign_rca_spec_audit`)
  — anti-hallucination spec grounding, project-scoped.
- `bodesign_render_board_model` — render a published 3D board model (glTF/.glb,
  incl. Draco) to board-view PNGs.
- Worker split (core / ee / me) via `docker-compose.workers.yml`.
