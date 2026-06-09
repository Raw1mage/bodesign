# Changelog

All notable changes to bodesign are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); the source of truth for design
rationale is the plan-builder specs under `specs/`.

## [Unreleased]

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
