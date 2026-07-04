# Spec: gerber-core_copper-geometry-parser

## Purpose

Provide a pure-python, zero-pcbnew copper-geometry parser in `gerber-core` that
turns already-parsed gerber copper-layer artifacts into computable, net-attributed
geometry primitives (polygon / track / pad / plane) and answers deterministic
geometry queries — edge-to-edge copper spacing, point-to-copper distance, and plane
coverage — each carrying geometry provenance. It gives the verify-checker
clearance/creepage/銅距 T-B controls the measurable quantities they need, while
honestly skipping curve primitives and failing fast (never silently) on a missing or
unparseable copper layer, so no clearance number is ever fabricated.

## Requirements

### Requirement: Net-attributed copper geometry primitives

The parser SHALL materialize the already-parsed gerber copper layer into computable
primitives (polygon / track / pad / plane) with coordinates and connected-copper-island
net attribution, extending `gerber-core` without rewriting its existing summary-level
capability, and without any pcbnew / KiCad-mutating dependency.

#### Scenario: copper layer materialized into primitives

- **WHEN** a caller requests copper-geometry parsing of a parsed gerber copper layer
  artifact that contains D01/D03 geometry
- **THEN** the parser returns a set of geometry primitives, each with coordinates and a
  connected-copper-island net identifier, with curve primitives (arc/circle/curve)
  marked `curve` and excluded from linear distance math

### Requirement: Deterministic geometry queries with provenance

The parser SHALL answer edge-to-edge copper spacing, point-to-copper distance, and
plane-coverage queries deterministically (byte-identical output for identical input),
and each result SHALL carry geometry provenance (source layers, participating primitive
refs, skipped curves, algorithm) aligned with the `ValidationEvidence`
`source_anchor` / `threshold_provenance` convention.

#### Scenario: edge-to-edge spacing query

- **WHEN** a checker queries the minimum edge-to-edge copper spacing between two
  net-attributed primitive groups
- **THEN** the parser returns the distance (mm) together with provenance listing the
  source layers, the participating primitive ids, any skipped curve primitives, and the
  algorithm used — never a bare float

### Requirement: Fail-fast on missing or uncomputable geometry

The parser SHALL fail fast with an explicit missing-items list when the copper layer is
absent, present but yields zero D01/D03 geometry, or the primitive set required by a
query is empty. It SHALL NOT return empty, zero, or an optimistic value that a caller
could misread as "safe".

#### Scenario: missing copper layer

- **WHEN** the requested copper layer is missing or contains no drawable geometry
- **THEN** the parser returns an explicit error result carrying `missing_items[]`, and
  the caller (verify-checker) must treat the check as `unverifiable`, not pass

#### Scenario: curve primitive not chord-approximated

- **WHEN** the geometry relevant to a clearance query includes an arc/circle/curve
  primitive
- **THEN** the primitive is disclosed in the result's `skipped_curves[]` and is NOT
  chord-approximated into a fabricated clearance number (absent an explicit
  tessellation contract)

## Acceptance Checks

- [ ] Parsing a copper layer with D01/D03 geometry yields net-attributed primitives
      (polygon/track/pad/plane) with coordinates; curves marked and excluded.
- [ ] Edge-to-edge spacing / point-to-copper / plane-coverage queries return
      byte-identical results across repeated runs on identical input.
- [ ] Every query result carries provenance (source_layers / primitive_refs /
      skipped_curves / algorithm).
- [ ] A missing or empty copper layer produces an explicit `missing_items[]` error, not
      an empty/zero/`inf` silent result.
- [ ] No pcbnew / KiCad-mutating import is introduced into the core parser path.
