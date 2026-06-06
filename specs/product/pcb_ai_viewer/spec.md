# Spec: bodesign — AI PCB Design Copilot (MCP)

## Purpose

Define the observable contract of bodesign as a standalone **MCP server**: each capability is
an MCP tool over a docxmcp-style token file surface; the system generates the forward-generation
layer and orchestrates the EDA skill suite for the rest, **demonstrating** reliability rather than
asserting it. Effective requirements (`R*`) are in `proposal.md`; decisions (`DD-*`) in `design.md`;
the lifecycle node map (`N1–N19`) + build queue in `tasks.md`.

## Requirements

### Requirement: Read-only ingest
The system SHALL ingest an entire client project tree without modifying any input file.

#### Scenario: Ingest a project folder
- **WHEN** `ingest_project_folder` (or a `/files` tarball upload) runs on a project tree
- **THEN** an index/manifest is produced and every input file is left byte-unchanged

### Requirement: Validated generation
The system SHALL only report a generated symbol/schematic as ready when `kicad-cli` validation passes.

#### Scenario: Schematic emit passes ERC
- **WHEN** `emit_kicad_schematic` emits a schematic and `kicad-cli` ERC is clean
- **THEN** the result is reported ready with the validation evidence

#### Scenario: Invalid pin table is refused
- **WHEN** `emit_kicad_symbol_library_from_pin_table` is given a table whose validation did not pass, or with no rows
- **THEN** it raises rather than emitting a bogus symbol

### Requirement: Demonstrated reliability
The system SHALL cross-check generated output against a known-good control-group reference, with provenance.

#### Scenario: Cross-check reports coverage and gaps
- **WHEN** `reference_crosscheck` compares generated nets to the reference
- **THEN** agreements/divergences are returned with provenance and uncovered nets are flagged as gaps, never passed

### Requirement: Honest verification ladder
The system SHALL return `passed | failed | skipped` (with a reason) for each verify layer and never a false pass.

#### Scenario: SPICE engine absent
- **WHEN** `simulate_schematic` runs with no SPICE engine or no valid skills
- **THEN** it returns `skipped` with the reason, not `failed` and not a false `passed`

### Requirement: Readable companions
The system SHALL pair every non-readable engineering file with a readable companion.

#### Scenario: Companion for an engineering file
- **WHEN** a `.kicad_sch` / gerber / docx-source is emitted
- **THEN** `render_companion` / `emit_document` produces a viewable pdf/png/svg/xlsx alongside it

### Requirement: Readiness compass
The system SHALL compute the next single step from folder contents alone.

#### Scenario: Compute readiness
- **WHEN** `package_readiness` / `gap_report` runs on a package folder
- **THEN** a readiness%, the single next step, and blockers are computed without a separate status file

### Requirement: Fab gate
The system SHALL emit no send-to-fab output without deterministic validation + explicit approval (DD-8).

#### Scenario: Fab output is approval-gated
- **WHEN** fab outputs are requested
- **THEN** they are released only after validation passes and the user explicitly approves

### Requirement: Data isolation
The system SHALL ship no working data; client trees enter only at runtime (token store, TTL-GC'd) or via an external `data_root()`.

#### Scenario: Clean-clone suite is green
- **WHEN** the test suite runs on a clean clone with no `BODESIGN_DATA_DIR`
- **THEN** it is green and data-dependent tests skip via `data_root()` guards

### Requirement: Dual transport
The system SHALL bind UDS (local) + TCP (external) from one process.

#### Scenario: Both transports reachable
- **WHEN** the server starts with `--uds` and `--port`
- **THEN** `/mcp/` and `/healthz` respond on both transports from one process

## Acceptance Checks

- Behaviour ↔ test mapping is enumerated in `test-vectors.json` (TV1–TV14).
- The runtime sequence is in `sequence.json`; failure modes in `errors.md`; operability in `observability.md`.
- Non-functional: deterministic emitters (byte-identical on identical input); generic (STM32 *recognition* allowed, product *recipes* not); one Docker image bundles the toolchain.
