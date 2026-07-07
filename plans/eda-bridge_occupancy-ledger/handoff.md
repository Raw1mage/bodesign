# Handoff: eda-bridge_occupancy-ledger

## Execution Contract

- 執行代理（coding subagent 或主線 inline）必須交付 tasks.md M0–M5 的逐項成果；「done」定義為：迴歸測試全綠 ＋ CCM 5 頁重產五組驗收數字（每頁 pitch／圖框／利用率≥40%／label 互疊=0／offpage=0）全過且不劣化於 M0-2 golden baseline。
- 每完成一個 task slice，立即勾 tasks.md 對應 checkbox（`spec_tick_task` 或直接編輯），不得批次補勾。
- 每階段（M1→M2→M3→M4）結束必須回報 `Result / Changes / Validation / Issues`，並附 `__engine_rev__` 交棒戳記（bodesign skill delivery contract）。
- 引擎改動走 dev-loop：`BODESIGN_DEV=1 ./mcpctl.sh restart`；容器內唯一合法拷貝 `/app/packages`；改前 tar snapshot。

## Required Reads

- `plans/eda-bridge_occupancy-ledger/design.md`（DD-1..DD-9 全部）
- `plans/eda-bridge_occupancy-ledger/spec.md`（4 條 Requirement + Acceptance Checks）
- `packages/eda-bridge/bodesign_eda_bridge/composer.py`（`_estimate_bbox` / `_resolve_overlaps` / `_fit_sheet`）
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`（`_staggered_label_blocks` / `_label_bbox`）
- `tests/test_composer_draftsman.py`（迴歸基準）
- `issues/BR_20260706_symbol_geometry_*.md`（已證偽死路清單：反向帶分桶、corridor clamp、位移層補丁、降 scale 硬壓——禁止再試）

## Stop Gates In Force

- **M0-1 使用者 commit 裁決**：工作區現有未 commit 補丁改動如何固化，須使用者批准後才動工 M1。
- **M2/M3 補丁刪除**：逐個刪、逐個驗；任一 golden baseline 數字劣化即停，回報不硬修。
- **BUDGET_INFEASIBLE 語義**：任何「加 fallback 讓它過」的衝動一律禁止（no-silent-fallback 天條）；不可行就 fail-loud 回報使用者。
- 全程不 commit、不碰 GDrive 交付點，除非使用者明確指示。

## Execution-Ready Checklist

- [ ] M0-1 使用者 commit 裁決已取得
- [ ] M0-2 golden baseline 已建立（五組數字＋sch md5 記錄在案）
- [ ] 執行者已讀 design.md DD-1..DD-9 與已證偽死路清單
- [ ] dev-loop 環境可用（`BODESIGN_DEV=1 ./mcpctl.sh status` 正常）
