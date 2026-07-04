# Spec: quality_tool-generalization

## Purpose

Establish and enforce a generality bar for the bodesign MCP tool layer: no shipped tool may silently apply a board-specific or process-specific assumption on a non-reference board. Every such assumption must be either caller-overridable or explicitly reported. Remediate the two tools that currently violate this silently.

## Requirements

### Requirement: Repeatable generality check

The suite must have a documented, repeatable check that flags any shipped tool whose behaviour depends on a board/process constant that is neither caller-overridable nor reported in its result.

#### Scenario: New tool added with a baked-in board constant

- **GIVEN** a contributor adds a tool that hardcodes a board-specific value (e.g. a refdes, a stackup constant, a fixed layer set)
- **WHEN** the generality check runs (checklist + lint/test)
- **THEN** the check flags the constant and names it, and the tool cannot pass the bar until the value is exposed as an input or echoed in the result

#### Scenario: Universal physics constant is not flagged

- **GIVEN** a tool uses a universal constant (speed of light, copper resistivity, a closed-form microstrip coefficient)
- **WHEN** the generality check runs
- **THEN** the constant is NOT flagged, because it is board-independent physics, not a board/process assumption

### Requirement: No silent connector-mapping overfit (H1)

`route_net2pcb` must not silently skip connector pin mapping based on a hardcoded refdes.

#### Scenario: USB-C connector is not refdes J1

- **GIVEN** a board whose USB-C connector is refdes J5 (not J1)
- **WHEN** `route_net2pcb` runs without an explicit connector pinmap
- **THEN** the result reports that the built-in USB-C mapping was not applied to J5 (in `unmapped_connectors`), rather than silently producing a board with an unmapped connector and no signal

#### Scenario: Caller supplies an explicit connector pinmap

- **GIVEN** a caller passes `connectors = {"J5": {"VBUS": ["A4","A9","B4","B9"], ...}}`
- **WHEN** `route_net2pcb` runs
- **THEN** the supplied pinmap is applied to J5 and the result lists J5 under `applied_pinmaps`

### Requirement: No hidden SI assumptions (H2)

`si_check` must expose its driver/load/edge/threshold assumptions as optional inputs, consistent with its already-exposed `z0`/`rs`/`vdd`.

#### Scenario: Caller overrides driver impedance and load capacitance

- **GIVEN** a non-STM32 driver with `rdrv=33` and `cload=5e-12`
- **WHEN** `si_check` runs with those inputs
- **THEN** the simulation uses the supplied values and the result echoes the effective `rdrv`, `cload`, `edge_ns`, and thresholds used

#### Scenario: Caller omits SI assumptions

- **GIVEN** a caller passes only the board and nets
- **WHEN** `si_check` runs
- **THEN** it uses the documented STM32-class-CMOS reference defaults (numerically unchanged from today) AND the result reports those defaults as the effective values, so the verdict is interpretable

## Acceptance Checks

- A generality-check artifact exists and is runnable/repeatable; it correctly flags a planted board-specific constant and does not flag a planted universal-physics constant.
- H1: a regression test runs `route_net2pcb` on a non-J1 USB-C board and asserts the result reports the unmapped connector (no silent no-op); a second test asserts an explicit pinmap is applied and reported.
- H2: a regression test runs `si_check` with overridden `rdrv`/`cload` and asserts the effective values are used and echoed; a second asserts omitted inputs fall back to documented defaults that are reported in the result.
- Both fixed tools still fail-fast (`ok:false`) on genuinely missing required inputs and remain EE-worker-routed where they touch `pcbnew`.
- `specs/architecture.md` records the EDA-bridge generality contract.
