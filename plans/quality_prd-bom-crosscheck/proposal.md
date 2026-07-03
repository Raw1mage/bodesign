# Proposal: quality_prd-bom-crosscheck

## Why

- E2E 實證（`specs/validation/prd-to-gerber-e2e/`）使用者驗收發現 C04 交付物不合格：C00 PRD `main_components` 明載「NPN/resistor linear current sink 或 AL5809-ish 2-pin CC regulator」，但 C04 板上 16 零件**零電晶體、零 regulator IC**——電流控制淪為 4×140R 純電阻鎮流（假設值、無 datasheet 錨定），P1（60mA±10%）結構性達不到。
- RCA 三層失效鏈（`issues/BR_20260703_prd_bom_crosscheck_gap_cc_regulator_missing.md`，High）：
  1. vault absent 降級落點由 LLM session 內自行裁定，超出 PRD 允許集合無人攔截；
  2. 不存在 C00 `main_components` ↔ C03 netlist 的確定性履約 crosscheck；
  3. DRC/ERC 只驗板自身一致性、不驗履約 PRD——四層驗證在 C00→C03 縫上是空的。
- 哲學對齊：「展示可靠度」要求履約也是確定性證據，不能靠 LLM 自律。

## Original Requirement Wording (Baseline)

- 「C04的交物付不合格。C00不是有定義各種晶片模組嗎？為什麼沒有在C04的電路板上擺放出來？」「開案處理。一級一級治」

## Requirement Revision History

- 2026-07-03: initial draft created via plan-init.ts
- 2026-07-03: filled from BR RCA；使用者指示「一級一級治」→ 三層各立一治理級（gate → 降級協議 → 本案重做）

## Effective Requirement Description

依失效鏈由下而上「一級一級治」，三級各自可獨立驗收：

1. **L1 — 確定性履約 gate（`bodesign_prd_bom_crosscheck`）**：core 側 pure function。輸入 C00 `answer_state.json` 的 `main_components`（自然語句）+ C03 netlist（`.net` S-expr）；`main_components` 先經一次結構化步驟拆成逐項元件角色清單（LLM 只做上游抽取、結果落盤可審計，比對本身純確定性）；輸出逐項 `present / substituted / missing` 判定 + BLOCKING 清單。`missing`/集合外 `substituted` 未經使用者批准 → gate FAIL。
2. **L2 — 降級協議（vault-absent substitution protocol）**：C03 vault absent 時，替代方案必須先過 L1 允許集合比對；集合外替代一律 BLOCKING 等使用者決策，LLM 不得自行落點。協議寫進 C03 GUIDE + readiness 檢查。
3. **L3 — 本案重做（E2E LED driver C03→C04 重跑）**：按使用者裁決拓撲（AL5809 datasheet ingest 首選 / NPN sink 備選）重設計 C03，L1 gate 全 `present` 後重跑 C04；新板成為 `quality/deterministic-preplacement` 的基線板。

## Scope

### IN
- L1：`prd_bom_crosscheck` pure function（workflow-core）+ MCP 工具註冊 + `main_components` 結構化中間檔 schema + tests。
- L2：C03 GUIDE 降級協議段 + C03 readiness 接 L1 結果。
- L3：E2E LED driver 案 C03 重設計 + C04 重跑（含 DRC/ERC/Gerber 證據重出）。

### OUT
- pre-placement 演算法（`quality/deterministic-preplacement` 另案）；SPICE P1 驗證自動化（C06 既有路徑）；vault 批次 ingest（G4 另案）；參考設計 `reference_crosscheck` 改動。

## Non-Goals

- 不做 NLP 全自動解析 `main_components`——結構化抽取結果必須落盤供人工審計，抽取錯誤是可見的、可修的。
- 不追溯歷史案件；gate 只對新走 C03→C04 的案件生效。

## Constraints

- 比對核心純確定性（同輸入同輸出），LLM 不參與比對與判定，只參與上游一次性結構化。
- no silent fallback：`main_components` 缺席/結構化檔缺席 → gate 顯式報錯，不得跳過。
- L3 需 datasheet 錨定（AL5809 或 NPN+Rsense 計算書），無來源規格值 BLOCKING。

## What Changes

- `packages/workflow-core/bodesign_workflow_core/`：新增 `prd_bom_crosscheck.py`（pure function + 結構化清單 schema）。
- `services/mcp/server.py`：新增 `bodesign_prd_bom_crosscheck` handler + schema。
- `skills/bodesign/stages/c03-ee/GUIDE.md`：降級協議 + gate 接線段。
- `experiments/e2e-led-driver/`：C03/C04 重做產物。

## Capabilities

### New Capabilities
- prd_bom_crosscheck: C00 main_components ↔ C03 netlist 逐項履約判定（present/substituted/missing + BLOCKING）。
- substitution protocol: vault-absent 降級的確定性允許集合比對，集合外一律等使用者決策。

### Modified Capabilities
- C03 readiness: 接入 crosscheck 結果，BLOCKING 未清不得進 C04。

## Impact

- 所有 compose 路徑案件的 C00→C03→C04 handoff（新增一道 gate）。
- `services/mcp/server.py` 工具數 +1（tool count 測試需同步）。
- `specs/architecture.md` C03 段需補 gate 說明。
