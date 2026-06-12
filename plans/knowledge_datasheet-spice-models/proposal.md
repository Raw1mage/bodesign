# Proposal: knowledge_datasheet-spice-models

## Why

- bodesign 四層驗證的第 3 層（SPICE 模擬）目前**沒有自動的 model 來源**：`bodesign_simulate` 走 kicad analyzer + spice skill 對偵測到的類比子電路（分壓/濾波/運放/晶振）做 ngspice 模擬，但元件的 SPICE model 參數要嘛是通用預設、要嘛依賴使用者手動提供——datasheet 裡明明有這些參數，卻沒有管線把它們變成可模擬的 model。
- arXiv 第二輪調研（`docs/research/arxiv/workflow-analysis.md` §5.1 K2）確認可借鏡路線：**D2S-FLOW**（2502.16540，datasheet → 電氣參數抽取 → SPICE model 生成的 LLM workflow，含結構化文件處理提升精度）與 **DocEDA**（2412.05301，版面分析模型 + LLM 從電路文件抽電氣參數）。
- bodesign 已有承接這條管線的底座：vault L4 spec_values（EAV，`FIELD_ALIASES` registry、min/typ/max + condition 共存、`trust='verified'` 需 evidence）、L3 chunks（FTS5 + page anchors）、L2 documents（provenance 強制）。缺的是「**L4 參數 → SPICE model 卡**」的 derived artifact 層與抽取面的 SPICE 參數欄位擴充。
- 與「展示可靠度」主張直接相關：有了 datasheet-grounded 的 SPICE model，第 3 層模擬結果才能宣稱「依據該元件 datasheet 參數」而非「依據通用預設」——每個 model 參數都帶 page-anchor 證據可回溯。

## Original Requirement Wording (Baseline)

- 使用者確認第二輪調研後的建議：「OK yes」（2026-06-12，針對「要不要把 K1–K3 任何一條開成 plan？（K2 datasheet→SPICE 與你現有 vault/SPICE 層的銜接最直接）」）

## Requirement Revision History

- 2026-06-12: initial draft created via plan-init.ts
- 2026-06-12: proposal 內容撰寫（依 arXiv 第二輪調研 K2 結論：D2S-FLOW + DocEDA 借鏡）
- 2026-06-12: 使用者確認 scope 決策——(1) model 卡生成器落點 = `packages/component-kb`（vault L4 derived artifact，eda-bridge 只消費）；(2) v1 包一個 MCP 工具 `bodesign_spice_model_card`；(3) 第一批元件類別 = 被動件（R/C/L 寄生參數）+ 二極體（.model）+ LDO（行為級 subckt）——對應 bodesign_simulate 現有子電路類型與 vault 既有 LDO 欄位

## Effective Requirement Description

1. **SPICE 參數欄位擴充**：在 vault L4 `FIELD_ALIASES` / field_path registry 中新增 SPICE-model 相關參數命名空間（如 `spice_model.*`：BJT 的 Is/Bf/Vaf、MOSFET 的 Vth/Kp/lambda、二極體的 Is/N/Rs、LDO 的 dropout/PSRR/輸出阻抗、被動件的寄生參數 ESR/ESL 等），沿用 EAV min/typ/max + condition 共存模型。
2. **Datasheet → SPICE 參數抽取管線**（D2S-FLOW 借鏡）：以 vault L3 chunks 為輸入（已有 page anchors），結構化抽取目標元件的 SPICE 參數寫入 L4，每筆值帶 evidence（document sha + page anchor）、預設 `trust='unverified'`。抽取失敗顯式回報「參數不可得」，不編造（pcbGPT info-tool 同款紀律）。
3. **L4 → SPICE model 卡生成**（確定性模板，非 LLM）：從 L4 查詢一顆元件的 SPICE 參數集合，依元件類別套用確定性模板產出 `.model` / `.subckt` 卡；缺必要參數即 fail fast 列出缺項清單（錯誤即修復指引），不得用 silent 預設值補洞。產出的 model 卡帶 provenance 註解（來源 document + page + trust 等級）。
4. **simulate 流程接線**：`bodesign_simulate` 的子電路模擬可消費 vault-backed model 卡；無 vault model 時維持現行為（通用模型），但結果須標注 model 來源（`vault-grounded` | `generic-default`），對齊「不宣稱超過能展示的」誠實模型。
5. **驗證迴圈**：model 卡生成後跑 smoke 模擬（DC operating point 級）驗證語法與收斂性；模擬結果可包裝為 `ValidationEvidence` envelope（`tool="spice"`，已在 oracle 枚舉內）回流 spine。

## Scope

### IN
- vault L4 SPICE 參數 field_path 命名空間 + `FIELD_ALIASES` 擴充（`packages/component-kb`）
- datasheet 抽取管線的 SPICE 參數目標 schema（抽取執行由 AI/skill 驅動，管線只定義契約 + 寫入 + evidence 驗證）
- 確定性 model 卡生成器（L4 → `.model`/`.subckt`，模板化、fail-fast、provenance 註解）
- `bodesign_simulate` 接線：vault model 消費 + model 來源標注
- smoke 驗證（ngspice 語法/收斂檢查）+ `ValidationEvidence(tool="spice")` 包裝
- fixture 測試：抽取契約、model 卡生成、缺參數 fail-fast、來源標注

### OUT
- 進階 model 擬合（curve fitting I-V 特性曲線、行為級 model 自動擬合——D2S-FLOW 的 optimization 段屬未來 extend）
- 版面分析模型訓練（DocEDA 的 layout model；bodesign 沿用 doc-core 現有抽取面）
- RF/高頻 model（S-parameter、IBIS）
- 廠商 model 檔案的自動下載/匯入（另案；本 plan 只處理 datasheet 參數路線）
- SPICE skill 本身的改動（skill 屬 host 側；本 plan 只動 MCP server 側）

## Non-Goals

- 不追求取代廠商官方 SPICE model——datasheet 參數生成的 model 是「無官方 model 時的 grounded 替代」，精度定位為第一階近似，model 卡上明示此限制
- 不做 LLM 直接吐 SPICE netlist——LLM 只參與參數抽取（且每值帶證據），model 卡生成是確定性模板

## Constraints

- **Fail-fast 天條**：缺必要參數不得用預設值補洞；抽取不到就回報不可得
- 每筆 L4 參數值必須帶 evidence（document sha256 + page anchor），無證據不得寫入
- model 卡生成確定性：同 L4 狀態必產生 byte-identical model 卡
- `trust='verified'` 升級沿用 vault 既有 evidence-gated 機制，本 plan 不放鬆
- 與現有 vault schema 相容：只新增 field_path roots，不改 EAV 結構

## What Changes

- vault L4 field registry 新增 `spice_model.*` 命名空間
- 新增 model 卡生成模組（落點 design 階段定：component-kb 或 eda-bridge）
- `bodesign_simulate` 增加 vault model 消費路徑 + 來源標注
- 可能新增 1–2 個 MCP 工具（如 `bodesign_spice_model_card`）

## Capabilities

### New Capabilities
- **datasheet-grounded SPICE model**：從 vault L4 參數確定性生成帶 provenance 的 `.model`/`.subckt` 卡；缺參數 fail-fast 列缺項
- **spice 參數抽取契約**：L3 chunks → L4 spice_model.* 的結構化抽取目標 schema + evidence 驗證

### Modified Capabilities
- **bodesign_simulate**：結果標注 model 來源（vault-grounded | generic-default）；可消費 vault model 卡
- **vault L4**：field_path registry 擴充 SPICE 參數命名空間

## Impact

- `packages/component-kb`（FIELD_ALIASES / field_path roots、可能的 model 卡生成模組）
- `packages/eda-bridge`（simulate 接線）
- `services/mcp/server.py`（工具面）
- `specs/architecture.md`（vault L4 描述 + 驗證第 3 層資料流）
- `tests`（fixture 驗證）
