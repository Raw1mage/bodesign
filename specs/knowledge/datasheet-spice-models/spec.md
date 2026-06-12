# Spec: knowledge_datasheet-spice-models

## Purpose

把 datasheet 抽取出的電氣參數（vault L4，帶 page-anchor evidence）變成可被第 3 層 SPICE 驗證消費的確定性 model 卡（`.model` / `.subckt`），並讓模擬結果誠實標注 model 來源。LLM 只參與抽取（每值帶證據）；model 卡生成是純確定性模板，缺參數 fail-fast。

## Requirements

### Requirement: R1 — vault L4 `spice_model.*` 命名空間

L4 field_path registry 必須支援 SPICE model 參數，沿用既有 EAV（min/typ/max + condition 共存）與 trust 機制，不改表結構。

#### Scenario: 註冊的 spice_model field 可寫入
- **GIVEN** L4 registry 已含 `spice_model.*` roots（diode/passive/ldo 第一批）
- **WHEN** 呼叫 `upsert_spec_value(component_id, "spice_model.diode.is_a", value_num=2.52e-9, evidence_ref=...)`
- **THEN** 寫入成功，`resolve_field_path` 回傳 canonical path，row 帶 evidence_ref

#### Scenario: 未註冊 field fail-fast
- **GIVEN** registry 不含 `spice_model.mosfet.vth_v`（v1 範圍外）
- **WHEN** 以該 field 寫入
- **THEN** 拋出含 "Unknown field_path" 與 nearby candidates 的錯誤（沿用既有行為），不靜默建立

#### Scenario: verified 升級仍需 evidence
- **GIVEN** 一筆 `spice_model.*` 值欲標 `trust='verified'`
- **WHEN** 無 evidence_ref
- **THEN** DB trigger 拒絕（既有 `trg_spec_verified_needs_evidence`，本 plan 不放鬆）

### Requirement: R2 — 抽取契約（L3 → L4，evidence 強制）

定義 datasheet → `spice_model.*` 的抽取目標 schema 與寫入驗證。抽取執行由 AI/skill 驅動；管線只負責契約、寫入與 evidence 驗證。

#### Scenario: 合法抽取批次寫入
- **GIVEN** 一份抽取結果批次，每筆含 field_path / value / unit / condition? / evidence（document sha256 + page）
- **WHEN** 呼叫抽取入庫 API（`ingest_spice_extraction`）
- **THEN** 全部寫入 L4，`trust='unverified'`，回傳 per-field 寫入摘要

#### Scenario: 缺 evidence 的值被整筆拒絕
- **GIVEN** 批次中某筆缺 page anchor 或 document sha
- **WHEN** 入庫
- **THEN** 該筆拒絕並回報錯誤碼 `SPX_EVIDENCE_MISSING`（列明 field 與缺項）；其餘合法筆不受影響（per-row 判定，回傳明細）

#### Scenario: 參數不可得顯式回報
- **GIVEN** datasheet 中找不到某目標參數
- **WHEN** 抽取結果以 `not_found` 標記該 field
- **THEN** 系統記錄「不可得」狀態於回傳摘要（不寫入偽值、不寫入 0/預設），下游 model 卡生成據此列缺項

### Requirement: R3 — 確定性 model 卡生成

從 L4 查詢一顆元件（MPN）的 `spice_model.*` 參數集合，依元件類別套確定性模板產出 model 卡。同 L4 狀態必產 byte-identical 輸出。

#### Scenario: 二極體 .model 卡生成
- **GIVEN** L4 有某 MPN 完整的 `spice_model.diode.*` 必要參數（Is、N；Rs/Cj0/BV 選配）
- **WHEN** 呼叫 `generate_model_card(mpn, category="diode")`
- **THEN** 產出 `.model D_<MPN> D(IS=... N=... ...)` 卡，含 provenance 註解（document sha、page、trust、生成時間戳除外的確定性內容）

#### Scenario: LDO 行為級 subckt 生成
- **GIVEN** L4 有 `spice_model.ldo.*` 必要參數（vout、dropout、iout_max）
- **WHEN** `generate_model_card(mpn, category="ldo")`
- **THEN** 產出 `.subckt LDO_<MPN> in out gnd` 行為級卡（含 dropout 行為與電流限制），帶 provenance 註解與「第一階近似」限制聲明

#### Scenario: 被動件寄生參數卡生成
- **GIVEN** L4 有 `spice_model.passive.*`（esr_ohm / esl_h，對應 C/L）
- **WHEN** `generate_model_card(mpn, category="passive")`
- **THEN** 產出含寄生網路的 `.subckt`（C+ESR+ESL 串聯）

#### Scenario: 缺必要參數 fail-fast 列缺項
- **GIVEN** L4 缺二極體必要參數 `spice_model.diode.n`
- **WHEN** 生成
- **THEN** 拋錯 `SPX_PARAMS_MISSING`，payload 列出缺項 field_path 清單與「補抽取」修復指引；不得用預設值補洞、不產出半成品卡

#### Scenario: 確定性驗證
- **GIVEN** 同一 L4 狀態
- **WHEN** 生成兩次
- **THEN** 兩次輸出 byte-identical

### Requirement: R4 — simulate 接線 + model 來源標注

model 卡落入 spice skill 既有 model resolution cascade 的第 1 優先位置（project `spice/models/` + manifest），`bodesign_simulate` 結果標注每個子電路使用的 model 來源。

#### Scenario: vault model 卡被模擬消費
- **GIVEN** 已對專案執行 model 卡物化（寫入 `<project>/spice/models/` + manifest）
- **WHEN** `simulate_schematic` 跑該專案
- **THEN** spice skill cascade 第 1 步命中專案卡；SimResult 對應子電路標注 `model_source="vault-grounded"`

#### Scenario: 無 vault model 維持現行為 + 誠實標注
- **GIVEN** 專案無 model 卡（或該元件無 L4 參數）
- **WHEN** 模擬
- **THEN** 行為與現狀相同（generic/ideal model），對應結果標注 `model_source="generic-default"`，不誤稱 grounded

### Requirement: R5 — smoke 驗證 + ValidationEvidence 回流

model 卡生成後跑 ngspice 語法/收斂 smoke 檢查；結果可包裝為 `ValidationEvidence(tool="spice")` 回流 spine。

#### Scenario: smoke 通過
- **GIVEN** 一張生成的 model 卡與 ngspice 可用
- **WHEN** 跑 DC operating point 級 smoke 測試
- **THEN** 回傳 pass，卡標記 `smoke="pass"`

#### Scenario: smoke 失敗 fail-fast
- **GIVEN** 卡語法錯或不收斂
- **WHEN** smoke
- **THEN** 回報 `SPX_SMOKE_FAILED` 含 ngspice stderr 摘要；卡不得進入 manifest（不可被 cascade 消費）

#### Scenario: ngspice 不可用顯式 skip
- **GIVEN** 環境無 ngspice
- **WHEN** smoke
- **THEN** 回報 `smoke="skipped-no-simulator"`（顯式，不偽裝 pass）；卡可生成但 manifest 註記 smoke 狀態

#### Scenario: 包裝為 ValidationEvidence
- **GIVEN** 一次 smoke 結果
- **WHEN** 以 `wrap_validation_evidence(tool="spice", ...)` 包裝
- **THEN** 產生合法 envelope 可回流 spine `evidence_returns/`

## Acceptance Checks

1. `spice_model.*` roots 進 registry；未註冊 field 寫入 fail-fast（既有錯誤路徑回歸）
2. 抽取入庫：合法批次全寫入 unverified + evidence；缺 evidence per-row 拒絕（`SPX_EVIDENCE_MISSING`）；`not_found` 不產生偽值
3. 三類別（diode/ldo/passive）model 卡 fixture 生成 + byte-identical 確定性測試
4. 缺參數 `SPX_PARAMS_MISSING` 列缺項清單測試
5. simulate 結果帶 `model_source` 標注（兩種值各一 fixture）
6. smoke pass / fail / skipped-no-simulator 三態測試；fail 的卡不進 manifest
7. MCP 工具 `bodesign_spice_model_card` 走 run_tool 包裝層，錯誤碼透傳
8. 全 suite 回歸綠（484+ 既有測試不破）
