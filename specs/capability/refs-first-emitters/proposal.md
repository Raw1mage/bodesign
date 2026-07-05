# Proposal: capability_refs-first-emitters

## Why

- BR_20260704（c01_c02_emitter_modular_platform_template_not_refs_derived）以 aiguard 消費端硬證據指出：bodesign 的 C01/C02 emitter 以內建 "modular platform" variant 模板（5 埠 universal socket + MIPI 5→2 mux + host/module 大小樂高）為預設起手，產物自證 `_skeleton_note: "Corrected from generic C01 template"`——架構假設是模板注入的，不是 refs 推導的。
- `c01_readiness` / `c02_readiness` 只檢 deliverable 存在性，不檢 refs 回溯：臆造模板能拿 `dod_ok: true`（aiguard 實測）。
- 下游 GIGO：C01 六面約束 / C02 開孔是 C04 placement 的物理約束來源。deterministic pre-placement 已落地（`specs/quality/deterministic-preplacement/`），但其輸入若來自模板汙染的約束，擺件照著錯的架構跑。HANDOVER_20260705 明確要求「先修 emitter，否則 placement 建在臆造骨架上」。
- 這是 EPIC `capability/refs-derived-design` 切面 1（design-root bypass）+ 切面 5（DoD 涵蓋 refs 回溯）的 emitter 級落點；`refs_gate.py`（`RefsManifest` / `require_refs()`）基建已存在，本案是把 C01/C02 emitter 接上這條既有鏈。

## Original Requirement Wording (Baseline)

- 「畢業，然後另開plan」（使用者批准 deterministic-preplacement graduate 後，指示開下一案；案源 = HANDOVER_20260705 建議排序第 2 項 + BR_20260704 emitter BR）

## Requirement Revision History

- 2026-07-05: initial draft created via plan-init.ts
- 2026-07-05: filled from BR_20260704 emitter evidence + HANDOVER_20260705 backlog

## Effective Requirement Description

1. **去模板化**：C01/C02 emitter 不得以任何 variant 模板（modular platform / generic template）起手；`Interface_Constraints.json` / `Mechanical_Constraints.json` 的 `exposed_components[]` / `connector_openings[]` / `component_heights[]` 必須從該 stage `01_refs/` SSOT 生成，缺 SSOT 時 fail fast 列缺項（走既有 `refs_gate.require_refs()` chokepoint），不得以模板補位。
2. **Provenance 欄位**：emitter 產物每個 component/opening 帶 `provenance` 指回 `01_refs/` SSOT 來源（檔案 + 錨點），無來源者不得出現在產物中。
3. **Readiness provenance gate**：`c01_readiness` / `c02_readiness` 對每項 `exposed_components[]` / `connector_openings[]` 驗證 `provenance` 非空且可解析到 `01_refs/`；缺回溯 → `dod_ok: false`（fail-fast，非存在性檢查）。
4. **Variant 命名清除**：slug / `product_name` 不得夾帶 `modular_platform` 之類架構假設；產品架構由 refs 決定。
5. **驗收**（對齊 BR §5）：(a) 對 aiguard 乾淨 SSOT 重跑 emitter → 產物不含 `expansion_socket_x5` / `U_MUX`，每項帶 provenance；(b) 「元件集存在但無 refs 回溯」的假 package → `dod_ok: false`；(c) 既有合法流程回歸不破。

## Scope

### IN
- `packages/workflow-core/bodesign_workflow_core/`：`c01_id_package.py`、`c01_id_template.py`、`c02_me_package.py`、readiness 相關（`package_readiness.py` / `readiness_common.py` / `guide_dod.py` 接點）。
- 與 `refs_gate.py`（`RefsManifest` / `require_refs`）的接線。
- `services/mcp/server.py` 對應 handler/schema 若簽名有變。
- tests：去模板回歸 + provenance gate 正反例。

### OUT
- `place_components` 獨立 placement 生成 verb（HANDOVER 第 3 項，吃本案輸出，另案）。
- `emit_castellated`（`board_surgery.py build_castellation` + `c04_castellation` verb 已存在，非缺口）。
- C00 PRD / C03 之後各層 emitter 的同型改造（本案限 C01/C02，模式可複製）。
- aiguard 專案側資料修復（消費端已自行清乾淨）。

## Non-Goals

- 不做 LLM 自動裁決 SSOT 內容正確性——provenance gate 只驗「可回溯」，內容權威性由 owner adjudication 決定。
- 不重寫 C01/C02 的文件產出格式（markdown 結構不動，只動約束 JSON 的生成來源與欄位）。

## Constraints

- 天條：no silent fallback——缺 SSOT 必 fail fast 列缺項，不得以模板/預設值補位。
- 向後相容策略須顯式：無 `01_refs/` 的舊專案呼叫 emitter 時，行為是顯式報錯（要求先建 refs），不是靜默沿用舊模板路徑。
- 純 python、確定性（同 SSOT 同輸出）；不引入新依賴。
- readiness 語義沿用既有 `dod_ok` 契約（`readiness_pct` 不是 gate，`dod_ok` 才是）。

## What Changes

- C01/C02 emitter 的約束 JSON 生成段：模板起手 → `01_refs/` SSOT 投影 + per-item provenance。
- `c01_readiness` / `c02_readiness`：加 provenance 回溯檢查，掛 `dod_ok`。
- 移除/隔離內建 modular-platform variant 內容（含 slug/product_name 注入點）。
- `skills/bodesign/stages/c01-id/`、`c02-me/` GUIDE 對應段落同步。

## Capabilities

### New Capabilities
- refs-first constraint emission: C01/C02 約束產物 100% 可回溯 SSOT，per-item provenance。
- readiness provenance gate: DoD 從存在性升級為可回溯性（EPIC 驗收第 5 條）。

### Modified Capabilities
- `c01_emit_id_package` / `c02_emit_me_package`（或現行對應 verb）: 起手來源從內建模板改為 `01_refs/` SSOT，缺 refs fail fast。
- `c01_readiness` / `c02_readiness`: `dod_ok` 增加 provenance 回溯條件。

## Impact

- `packages/workflow-core/`（C01/C02 emitter + readiness）、`services/mcp/server.py`、`skills/bodesign/stages/c01-id|c02-me/GUIDE.md`、tests。
- 消費端：任何走 C01/C02 的新產品不再被模板汙染；aiguard 可作端到端回歸案例（輸入已備妥，見 BR_20260704_aiguard_c04_consumer_input_contract）。
- 證據鏈：BR_20260704 emitter BR + EPIC 切面 1/5 + HANDOVER_20260705 §5-6。
