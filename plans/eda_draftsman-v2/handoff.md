# Handoff: eda_draftsman-v2

## Execution Contract

- 實作棒交付 tasks.md 對應 slice 的可驗證產出；done = 該 slice 驗收指令全綠 + tasks.md checkbox 已 tick + 短回報（Result/Changes/Validation/Issues）
- 兩條天條：no-fallback（缺 symbol 標缺口不捏造）；禁疊補丁（同缺陷簽名 2 輪未收斂停手 RCA，見 observability.md）
- 改動集中 `packages/eda-bridge/bodesign_eda_bridge/`；保留區禁碰（design.md Critical Files：fidelity.py / render_qa.py / ink_metrics.py 只補測試不改行為）

## Required Reads

- `plans/eda_draftsman-v2/design.md`（DD-1～DD-6 + Architecture A1–A5 對應）
- `plans/eda_draftsman-v2/spec.md`（Requirements + Acceptance Checks）
- `plans/eda_draftsman-v2/errors.md`（error code 語意，fail-fast 契約）
- `issues/BR_20260706_symbol_geometry_two_side_only_no_four_edge_pin_placement.md`（病史）

## Stop Gates In Force

- task 1.2：symbol 缺口清單交使用者裁決
- task 1.6：Phase 1 使用者人工抽查——未過不得動 Phase 2 任何檔案（分期硬閘 DD-3）
- task 2.4：C03 使用者審閱 gate

## Execution-Ready Checklist

- [x] kiutils roundtrip 驗證通過（task 0.1）— kiutils 1.4.8 + kicad-cli 9.0.9，render exit 0
- [x] 雙閘單測綠（task 0.2）— test_fidelity_gate / test_render_qa_gate
- [x] 官方 symbol 庫路徑/版本 pin 住並寫回本檔（task 0.3）— **庫路徑 `/usr/share/kicad/symbols`（KiCad 9.0.9 系統安裝）**，可用 `KICAD_SYMBOL_DIR` 覆寫指向 vendored/pinned 庫；查詢介面 `bodesign_eda_bridge.symbol_index`。注意：STM32N657/STM32N6 官方庫零覆蓋，Phase 1 task 1.1 須先產缺口清單交使用者裁決
- [ ] 檔案交換走 bodesign MCP webdav cache lifecycle（勿 docker exec 直搬——BR_20260707 教訓）；容器 bodesign-pkcs12-bodesign-ee-1 為 kicad-cli 所在

## 交接現況（2026-07-07，由 thesmart_products session 移交）

使用者裁決：引擎開發歸 bodesign 自己的 session 執行，thesmart_products session 不再代駕推進。

- **已完成且已驗證**：tasks §0 全部、1.1、1.2a（vendor CAD 匯入 + ballout 0 mismatch）；15 tests 綠
- **⚠ 未驗證殘留（cancel 前落地，勿直接信任）**：`block_drafter.py`（201 行）與 `block_qa.py`（141 行）是 task 1.3/1.4 實作棒被 cancel 前寫入的**半成品草稿**——未跑過雙閘、未有測試、checkbox 未 tick。接手者自行決定留用重審或砍掉重寫
- **舊引擎檔的 working-tree 修改**（composer.py / kicad_emit.py / kicad_symbol.py，git 未 commit）：前一輪症狀補丁殘留，v2 定案後這些檔屬砍除區，接手者處置時一併決定
- **下一步**：task 1.3（單圖繪製）；外部依賴：thesmart_products 的 BOM 定案提案（`01.openmv/C03-EE/BOM_定案提案_v01.md`）仍在等使用者審，不阻塞 task 1.3（STM32N657 vendor symbol 已就位）
