# Spec: feature_eda-mcp-toolchain

## Purpose

Promote the validated OpenMV C04 host-side EDA scripts into first-class bodesign MCP tools with typed I/O, correct execution-group routing (core vs EE worker), fail-fast behaviour on missing dependencies, and a real socket-level callable path — without overfitting to one board or claiming fabrication readiness.

## Requirements

### Requirement: Pure impedance solving in core

`bodesign_impedance_solve` derives microstrip/differential class geometry from an explicit stackup and impedance targets, in the core group (no `pcbnew`).

#### Scenario: Single-ended and differential targets

- **GIVEN** a stackup `{dielectric_height_mm, er, copper_thickness_mm}` and targets including a 50Ω single-ended class and a 90Ω differential class with `gap_mm`
- **WHEN** `bodesign_impedance_solve` runs
- **THEN** it returns per-class `width_mm` (+ `gap_mm` for diff), `actual_ohm`, `ps_per_mm`, and a fab-confirmation warning, with no fabricated stackup defaults

### Requirement: Board-mutating tools route to the EE worker

`bodesign_widen_bus_tracks` and `bodesign_length_match_bus` mutate a `.kicad_pcb` via `pcbnew` and must execute in the EE worker, never faking results in core.

#### Scenario: EE worker unavailable

- **GIVEN** no EE worker is configured in a slim deployment
- **WHEN** an EE board tool is called
- **THEN** it fails fast (`ok:false`) and never fabricates a routed/tuned board

#### Scenario: Clearance-safe mutation writes a new path

- **GIVEN** an input board and target width/budget
- **WHEN** the tool runs in the EE worker
- **THEN** it writes a new output path, returns it, and reports per-net structured results (widened/kept, lengths, spread, within_budget)

### Requirement: Gerber preview is review evidence, fail-fast on unsupported modes

`bodesign_render_gerber_preview` renders a single Gerber layer for review; it must not fabricate composite/stack renders it cannot produce.

#### Scenario: Composite/stack mode without a safe renderer

- **GIVEN** the core has no safe multilayer compositing renderer
- **WHEN** preview is called in composite/front/stack mode
- **THEN** it returns an explicit `render-unavailable` state, not a decorative fallback image

### Requirement: Tools are callable through the real MCP server path

The new tools must be reachable via the real MCP JSON-RPC protocol, not just direct `run_tool` calls.

#### Scenario: Socket-level list + call roundtrip

- **GIVEN** an MCP client connected to `server.py --transport stdio`
- **WHEN** it runs initialize → list_tools → call_tool
- **THEN** all four new C04 tools are listed and `bodesign_impedance_solve` returns a structured result over the protocol

## Acceptance Checks

- Direct unit tests pass for pure impedance math, tool grouping, and the new tools' schemas (19 ok, 1 skipped).
- Socket-level smoke (`tests.test_mcp_server.test_socket_level_list_and_call_smoke`) passes in an MCP-SDK env and skips on the bare host.
- EE tools fail fast without a worker; mutating tools write+return a new path.
- `bodesign_render_gerber_preview` returns `render-unavailable` for unsupported modes.
- `specs/architecture.md` reflects current C04 MCP coverage and boundaries.
