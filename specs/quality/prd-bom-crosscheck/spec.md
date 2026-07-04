# Spec: quality_prd-bom-crosscheck

## Purpose

保證 C03 產出的 netlist 履約 C00 PRD `main_components` 定義的電路角色集合：每個角色 `present` 或經使用者批准 `substituted`，否則以 BLOCKING 證據拒絕 C04 入口。比對全程確定性，LLM 只參與一次性上游結構化且結果落盤可審計。

## Requirements

### Requirement: Deterministic PRD-BOM crosscheck

The system SHALL provide a pure function `prd_bom_crosscheck(manifest_path, netlist_path)` that produces, for every role in the manifest, a verdict of `present`, `substituted` (with envelope/approval status), or `missing`, plus a BLOCKING list; identical inputs SHALL yield identical outputs.

#### Scenario: CC regulator missing from board

- **WHEN** the manifest contains role `current-regulator` (qty_min 1) and no netlist component matches its patterns nor its allowed-alternative patterns
- **THEN** the verdict is `missing`, the role appears in the BLOCKING list, and the gate result is FAIL

#### Scenario: In-envelope alternative present

- **WHEN** no primary pattern matches but an `allowed_alternatives` pattern matches (e.g. NPN linear sink instead of AL5809)
- **THEN** the verdict is `substituted` with `in_envelope: true` and it is NOT blocking

#### Scenario: Out-of-envelope substitution without approval

- **WHEN** neither primary nor allowed-alternative patterns match and no `approvals[]` entry covers the role
- **THEN** the verdict is `missing` (or `substituted` with `approved: false` when a substitute is declared) and it IS blocking

### Requirement: Fail-fast on missing inputs

The system SHALL raise an explicit error (not a silent pass) when the structured manifest is absent, unparseable, or the netlist file is missing/unreadable.

#### Scenario: Manifest not yet extracted

- **WHEN** `main_components_structured.json` does not exist in the C00 folder
- **THEN** the tool fails with `MANIFEST_MISSING` and instructs extraction + human audit, never skipping the gate

### Requirement: Gate enforcement at C04 entry

The crosscheck verdict SHALL be consumable by C03 readiness such that any BLOCKING item refuses C04 entry until the user either fixes the design or records an approval.

#### Scenario: Gate blocks C04

- **WHEN** the crosscheck report contains ≥1 BLOCKING item
- **THEN** C03 readiness reports the gate as FAIL with the itemized list, and the documented C04 workflow refuses to proceed

## Acceptance Checks

- [ ] E2E LED driver 迴歸：現案 manifest + 現有純電阻 netlist → `missing` BLOCKING FAIL
- [ ] 正案：補齊恆流器件（或已批准 NPN sink）的 netlist → gate PASS
- [ ] manifest 缺席 → 顯式 `MANIFEST_MISSING` 錯誤
- [ ] 同輸入跑兩次 → 報告 byte-identical（確定性）
- [ ] MCP 工具已註冊；converged tool-count 測試同步且綠
