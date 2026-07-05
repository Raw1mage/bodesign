# Spec: capability_refs-first-emitters

## Purpose

保證 C01/C02 emitter 產出的每一筆物理約束（exposed components、connector openings、component heights…）都可回溯到該 stage `01_refs/` SSOT 或使用者親答，且不可回溯的內容永遠無法無聲通過 readiness dod gate——消除 BR_20260704 揭示的「模板/臆造內容拿 dod_ok:true 一路傳到 C04 placement」汙染路徑。

## Requirements

### Requirement: refs gate at emit entry

The system SHALL refuse to emit any C01/C02 constraint package when the stage's `01_refs/` SSOT is missing or empty, raising `RefsGateError(REFS_SSOT_MISSING)` with the offending layer and path, generating no files.

#### Scenario: emit without SSOT

- **WHEN** `emit_c01_rockbox_package` / `emit_c02_enclosure_package` is called on a folder with no `01_refs/` sources
- **THEN** a `RefsGateError` is raised, no artifact file is written, and the error detail names the layer and refs_root

### Requirement: per-item provenance

The system SHALL attach `provenance {kind, source, detail}` to every constraint item, where `kind ∈ {refs, answer, derived}`; caller input without attribution SHALL be marked `derived` (visible), never silently promoted.

#### Scenario: corpus-derived component

- **WHEN** `exposed_components` is inferred from C00 keyword corpus rather than answered/referenced
- **THEN** each inferred item carries `provenance.kind == "derived"` and the package readiness reports it as a provenance gap

### Requirement: readiness provenance gate

The system SHALL set `dod_ok=false` and list `provenance_gaps[]` whenever any constraint item has `kind ∉ {refs, answer}` or a `refs` source that does not resolve under `01_refs/`; existence/shape checks alone SHALL NOT grant dod.

#### Scenario: unattributed component set

- **WHEN** a package's `Interface_Constraints.json` has components present but without resolvable provenance
- **THEN** `c01_readiness` returns `dod_ok:false` with each gap named (previously returned true — BR_20260704 §5b)

### Requirement: no emitter-synthesized variant naming

The system SHALL NOT inject architecture-assumption strings (variant/archetype slugs) into product_name or artifact filenames; slugs derive from sanitized product_name only.

#### Scenario: visual package filename

- **WHEN** `c01_emit_id_visual_package` writes its artifacts
- **THEN** filenames contain no archetype/variant token beyond the sanitized product_name

## Acceptance Checks

- [ ] BR §5a: rerun emitters against a clean SSOT fixture → output contains no unattributed items; every item resolves
- [ ] BR §5b: package with components but no provenance → `dod_ok:false` (regression test asserts the OLD behavior is dead)
- [ ] BR §5c: legacy flows with refs fixtures added → full test suite green, v1 consumers unbroken
