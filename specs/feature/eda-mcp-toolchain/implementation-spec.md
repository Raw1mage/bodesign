# EDA MCP Toolchain Integration Spec

## Goal

Convert the validated OpenMV/STM32N657 C00-C07 intermediate artifacts and C04 host-side EDA scripts into first-class bodesign MCP/workflow capabilities where they proved reusable, so future agents can execute the real product-development workflow through typed calls instead of ad-hoc shell scripts and loose generated files.

This plan captures the practical lesson from the first end-to-end board run: the useful unit of reuse is not a single via-in-pad helper. The immediate MCP gap is the deterministic C04 toolchain, but the plan must first inventory C00-C07 derived scripts, JSON bridges, generated package files, verification summaries, and handoff artifacts so reusable capabilities are promoted at the right layer.

## Scope

### In

- Promote remaining validated scripts into importable `bodesign_eda_bridge` functions.
- Inventory C00-C07 generated artifacts and intermediate scripts before implementation.
- Classify each artifact as MCP tool, workflow-core primitive, package template, evidence record, fixture, or one-off output.
- Register MCP handlers and schemas in `services/mcp/server.py`.
- Route every `pcbnew`/KiCad-dependent tool to the EE worker through `_EE_GROUP_TOOLS`.
- Keep pure math impedance solving in core unless future stackup data requires EE context.
- Preserve fail-fast behavior: missing dependencies return explicit unavailable/error states, not fabricated success.
- Add direct unit tests and at least one socket-level smoke path for the new MCP tools.
- Record empirical limitations discovered during the OpenMV/STM32N657 run.

### Out

- No claim that generated boards are fabrication-ready without DRC/SI/user approval.
- No silent fallback from EE worker to core for `pcbnew` tools.
- No separate `meander` MCP tool; its simpler strategy is subsumed by bus length matching if needed.
- No durable server-owned project storage or direct save-back workflow changes.

## Existing Baseline

The previous integration already landed these MCP tools:

- `bodesign_route_net2pcb`: KiCad netlist to netted `.kicad_pcb`.
- `bodesign_via_in_pad`: fine-pitch BGA via-in-pad fanout.
- `bodesign_pour_planes`: copper zones and GND stitching vias.
- `bodesign_layout_drc_gate`: copper/unconnected hard gate plus silkscreen warning split.
- `bodesign_si_check`: ngspice transmission-line SI gate.
- `bodesign_autoroute`: Freerouting-backed autoroute with explicit unavailable state.

## Required C00-C07 Inventory Pass

Before implementing more C04 tools, perform a stage-by-stage inventory of the OpenMV run outputs:

- C00: PRD / product-requirement package artifacts, answer state, downstream work packets, and approval/readiness summaries.
- C01: industrial-design interface constraints, CMF/UI handoff artifacts, preference evidence, and user-facing package outputs.
- C02: mechanical constraints, OpenSCAD/enclosure artifacts, print/vendor handoff files, and export-unavailable gates.
- C03: EE schematic/netlist outputs, mechanical constraint exports, pin/package bridges, and netlist/BOM intermediates.
- C04: layout constraints, KiCad PCB/routing scripts, impedance/length/SI/DRC reports, Gerber/drill/render outputs.
- C05: firmware pin-map bridge, SW/FW spec artifacts, generated interface contracts, and test hooks.
- C06: verification summaries, validation reports, DRC/SI/manufacturing gates, and readiness rollups.
- C07: release/manufacturing/vendor package artifacts if present; if absent, record the gap explicitly.

Each item must be mapped to one of: `already-integrated`, `promote-to-mcp`, `promote-to-workflow-core`, `template/package-output`, `fixture/evidence-only`, `discard-one-off`, or `blocked-needs-decision`.

## New Tool Candidates

### `bodesign_impedance_solve`

- Source: `openmv/C04-Layout/generated/tools/impedance.py`.
- Purpose: solve microstrip/differential trace geometry from stackup and impedance targets.
- Inputs: `stackup`, `targets`.
- Outputs: class map with `width_mm`, optional `gap_mm`, `actual_ohm`, `ps_per_mm`.
- Execution group: core.
- Risk: closed-form estimates are guidance only; fab solver confirmation remains required.

### `bodesign_widen_bus_tracks`

- Source: `openmv/C04-Layout/generated/tools/widen.py`.
- Purpose: recover high-speed bus traces from neckdown to target width only where clearance-safe.
- Inputs: `in_path`, `out_path`, `nets`, `target_mm`, optional `clearance_mm`.
- Outputs: `board`, `widened`, `kept`, `target_mm`.
- Execution group: EE worker.
- Gate: follow with `bodesign_layout_drc_gate`.

### `bodesign_length_match_bus`

- Source: `openmv/C04-Layout/generated/tools/length_match.py`.
- Purpose: add clearance-aware serpentine detours to tune bus skew.
- Inputs: `in_path`, `out_path`, `nets`, `budget_ps`, `ps_per_mm`, optional `report_path`.
- Outputs: `board`, per-net lengths, `spread_mm`, `spread_ps`, `within_budget`, `tuned`, `total`.
- Execution group: EE worker.
- Gate: follow with `bodesign_layout_drc_gate` and `bodesign_si_check`.

### `bodesign_render_gerber_preview`

- Sources: `gerber_view.py`, `gerber_layer.py`, `gerber_stack.py`.
- Purpose: render manufacturing output for visual review: front assembly view, single layer, or multilayer copper stack.
- Inputs: `gerber_dir`, `out_path`, `mode`, optional `drill_dir`, `layer_glob`.
- Outputs: `image`, `mode`, `rendered_layers`, `skipped`.
- Execution group: core if `gerber`/Cairo dependencies are installed; otherwise explicit dependency blocker.
- Risk: rendering is review evidence, not a DRC substitute.

## End-to-End Workflow

1. `bodesign_impedance_solve` derives initial class widths and delay constants from stackup.
2. `bodesign_route_net2pcb` creates a netted board from KiCad netlist and known placements.
3. `bodesign_via_in_pad` escapes fine-pitch BGA inner balls when an approved POFV process is acceptable.
4. `bodesign_pour_planes` creates reference planes and stitching vias.
5. `bodesign_autoroute` attempts routing with Freerouting.
6. `bodesign_widen_bus_tracks` restores clearance-safe high-speed widths after route/neckdown.
7. `bodesign_length_match_bus` tunes bus skew within the explicit timing budget.
8. `bodesign_si_check` grades selected high-speed nets.
9. `bodesign_layout_drc_gate` blocks copper/unconnected failures.
10. `bodesign_render_gerber_preview` provides final visual review evidence when Gerbers exist.

## Design Constraints

- `pcbnew` must remain isolated to EE worker execution.
- Core must not fake EE worker results if the worker is down.
- Tool outputs must be structured JSON, not stdout-only logs.
- Every mutating board tool must write a new output path and return the path.
- Every validation/gate tool must report counts/statuses usable by an agent without parsing prose.
- The OpenMV scripts are evidence-backed prototypes, but MCP implementations should become importable functions, not shell wrappers.

## Validation Plan

- Direct Python tests for pure impedance solving.
- Fixture-based tests for handler schema registration and tool grouping.
- EE-worker smoke tests for `widen_bus_tracks` and `length_match_bus` on a small routed board fixture.
- Dependency-gated smoke test for Gerber preview; fail explicitly if renderer deps are unavailable.
- Socket-level MCP list/call verification for all new tools before marking the plan verified.

## Open Decisions

- Whether Gerber preview dependencies should live in core, EE, or a later dedicated rendering group.
- Whether length matching should support strategy selection beyond the validated clearance-aware serpentine method.
- Whether impedance class results should be persisted into `BoardDesign IR` constraints in this same slice or a later C04 planning slice.

## Stop Gates

- Stop if EE worker cannot import `pcbnew` for board-mutating tools.
- Stop if a tool requires hidden defaults for stackup, timing budget, or process capability.
- Stop if socket-level MCP execution cannot prove the tool is callable through the real server path.
