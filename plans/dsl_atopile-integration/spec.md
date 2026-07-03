# Spec: dsl_atopile-integration

## Purpose

保證 bodesign 產出的電路在進入 KiCad 之前，已通過宣告式編譯期驗證（單位型別、公差區間、assert 約束求解、選料可行性）。本 spec 定義 `ato_build` MCP 工具的行為契約、第五層信任證據（`constraint_solve`）的記錄規則，以及選料來源的 fail-fast 策略。

## Requirements

### Requirement: ato_build 編譯與驗證

系統 SHALL 提供 `ato_build` MCP 工具：接受 `.ato` 專案路徑，於 ee worker 執行 pinned atopile 編譯器，回傳編譯期驗證結果與 `.kicad_pcb` 產物路徑。

#### Scenario: 編譯成功

- **WHEN** `.ato` 專案語法正確、所有約束可滿足、所有選料可解
- **THEN** 回傳 `.kicad_pcb` 路徑 + constraint-solving 證據報告（可直接餵 C04 finishing 工具與 layout_drc_gate）

#### Scenario: 約束不可滿足

- **WHEN** `assert` 約束恆假或約束系統無解
- **THEN** 回傳結構化缺項清單（`kind=unsat_constraint` + source anchor），不產出 `.kicad_pcb`，不靜默放寬約束

#### Scenario: atopile toolchain 不可用

- **WHEN** ee worker 不可達或容器內缺 atopile
- **THEN** 顯式回報 `worker_unavailable` / `toolchain_missing`，不退回其他生成路徑

### Requirement: 第五層信任證據

系統 SHALL 將 `ato build` 的約束求解結果記錄為 `constraint_solve` oracle 的 `validation_evidence.v1` 信封，並納入 readiness 聚合。

#### Scenario: 證據記錄

- **WHEN** `ato_build` 完成（成功或失敗）
- **THEN** 產出 constraint_solve 證據信封（含 solver verdict、約束清單、選料 rated⊆spec 證明），readiness 報告顯示第五層狀態

### Requirement: 選料來源 fail-fast

系統 SHALL 依 `component_source` 參數（預設 `vault`）解析零件，任何模式不得靜默跨源。

#### Scenario: vault 模式 pick 無解

- **WHEN** `component_source=vault` 且 Component Vault 無符合參數區間的零件
- **THEN** 回傳 `pick_failure` 缺項清單（含所需參數區間），不自動改查 cloud registry

## Acceptance Checks

- [ ] `ato_build` 對合法 `.ato` 測試專案產出可通過 `layout_drc_gate` 的 `.kicad_pcb`
- [ ] 恆假 assert 的測試專案回傳 `unsat_constraint` 結構化錯誤且無 `.kicad_pcb` 產物
- [ ] monolith（無 ee worker）環境呼叫 `ato_build` 回傳顯式 toolchain 錯誤
- [ ] `constraint_solve` 已加入 ORACLE_TOOLS 白名單、_ADAPTERS 註冊表、c06 _CHECKS 聚合（三處齊備）
- [ ] vault 模式 pick 失敗回傳缺項清單且無 registry 網路呼叫（可觀測驗證）
