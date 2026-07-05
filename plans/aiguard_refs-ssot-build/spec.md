# Spec: aiguard_refs-ssot-build

## Purpose

This spec guarantees that `.work/aiguard/01_refs/` is a consolidated, frozen SSOT for the
aiguard project — harvested from its existing user-authored PRD, its existing layer
constraints, its 2 human-seed PDFs, and its 26-datasheet component vault, then expanded
with real datasheets for PRD-named parts. Existing SSOT is never discarded; immature
`drafted` C00~C04 products are killed and regenerated refs-derived from this frozen SSOT.
`require_refs` consumes it and fail-fasts only on genuinely-absent SSOT.

## Requirements

### Requirement: Existing SSOT is harvested, never discarded

The system SHALL harvest real user-sourced and datasheet-grounded values from aiguard's
existing artifacts into `01_refs/`, and SHALL NOT discard them when regenerating products.

#### Scenario: C00 user PRD is harvested into frozen SSOT

- **WHEN** harvesting C00 from `answer_state.json`
- **THEN** every `source:user` field is extracted into `01_refs/C00/prd.json` anchored to
  its `{document, section_id, field}`, and the layer manifest status is `frozen`

#### Scenario: real values inside an immature product are harvested before regen

- **WHEN** a `drafted` constraint file holds real `source:user`/datasheet-grounded values
  alongside immature derivation
- **THEN** the real values are harvested into `01_refs/` first, and only the immature
  derivation is killed and regenerated (DD-2/DD-7)

### Requirement: SSOT is expandable via real datasheets

The system SHALL reuse vault datasheets and pull new ones to ground electrical/mechanical
values — this is expansion (天条 4), not fabrication (天条 2).

#### Scenario: vault reuse before pull

- **WHEN** a PRD-named part is already in the vault (e.g. BQ24075)
- **THEN** `bodesign_vault_spec_check` links its datasheet spec into the layer's
  `source_anchors[]` as tier=`datasheet`, without re-pulling

#### Scenario: datasheet expansion for a missing part

- **WHEN** a PRD-named part is absent from the vault (e.g. STM32N657L0)
- **THEN** `bodesign_datasheet_lookup` + `bodesign_vault_ingest` pull a real datasheet
  (provenance `01_refs/datasheets/<MPN>.pdf`), every grounded value page-anchored `{MPN,page}`;
  honest rank-0 with no fabricated substring match if none is found

### Requirement: immature products are regenerated refs-derived

The system SHALL kill and regenerate the immature C00~C04 products from the frozen
`01_refs/`, and fail-fast on genuinely-absent SSOT.

#### Scenario: require_refs fail-fasts on genuinely-absent SSOT

- **WHEN** a field has no PRD source, no existing constraint value, and no derivable datasheet
- **THEN** it is `blocked_missing_source` + named `required_authority`, `require_refs` raises
  `RefsGateError[REFS_SSOT_MISSING]` (天条 1), and no phantom file is created (天条 2)

## Acceptance Checks

- [ ] `01_refs/C00/prd.json` holds all `source:user` PRD fields, each `{section_id,field}`-anchored
- [ ] `01_refs/C01..C04` harvested from existing constraints + PDFs; immature derivation dropped
- [ ] Vault reuse links ≥1 already-ingested PRD-named datasheet (e.g. BQ24075) into a layer
- [ ] Datasheet expansion pulls ≥1 PRD-named part absent from the vault, page-anchored
- [ ] `.work/aiguard/C03-EE/` created, grounded from PRD electrical + datasheet SSOT
- [ ] Immature `drafted` C00~C04 products regenerated refs-derived from `01_refs/`
- [ ] `require_refs` fail-fasts on genuinely-absent-SSOT fields (天条 1)
- [ ] `REGRESSION.md` reports per-layer pass/block with SSOT citations
