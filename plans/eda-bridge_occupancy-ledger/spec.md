# Spec: eda-bridge_occupancy-ledger

## Purpose

保證 eda-bridge 原理圖管線（compose→emit）中，任何佔紙面面積的實體都經由單一 occupancy ledger 的 reserve→draw 交易落筆；空間衝突在 reserve 期即顯式報出，圖框與 scale/pitch 在落筆前由 budget-first 求解一步定案。因此「撞字、溢框、label 互疊、offpage」在架構上不可能到達輸出——事後驗收閘恆為斷言，不是品質守門。

## Requirements

### Requirement: Reserve-before-draw

系統 SHALL 要求所有佔紙面實體（符號 body、pin 外伸、stub、label、電源/GND 符號、pwr_flag）在寫入 .kicad_sch 之前先向 OccupancyLedger 完成 reserve；reserve 失敗 SHALL 拋出 `LedgerConflict` 並附衝突矩形清單，不得靜默改位置續跑。

#### Scenario: label reserve 衝突

- **WHEN** 某 global label 的 bbox 與已 reserve 的鄰欄 label 相交
- **THEN** ledger 回報衝突矩形清單；呼叫端走顯式位移策略（帶上限、記錄軌跡），耗盡即拋 `BUDGET_INFEASIBLE`，不進入無限重試

### Requirement: Budget-first frame solving

系統 SHALL 在落筆前完成內容清點（pin-inclusive bbox＋label 伸展量）並一步選定圖框與 scale/pitch，目標內容佔紙面 60–75%；pitch-scan 候選 SHALL 以 dry-run reserve 預檢淘汰，物理不可行的候選不得進入 emit。

#### Scenario: 無可行 frame×pitch 組合

- **WHEN** 掃描完所有候選仍無法在最大圖框內以最小 pitch 滿足內容配額
- **THEN** compose 拋 `BUDGET_INFEASIBLE`，附缺項清單（超載邊/欄、所需 vs 可用空間），不升框迴圈、不靜默降 scale

### Requirement: Single geometry truth

系統 SHALL 由 `kicad_symbol` 單點提供 pin-inclusive 符號 extent；composer 不得持有第二份估算幾何（`_estimate_bbox` 退役）。

#### Scenario: placement 與 emit 幾何對帳

- **WHEN** placement 期 reserve 的符號矩形與 emit 期實際寫出的幾何比對
- **THEN** 兩者一致（同一來源），不存在「估算 bbox 說塞得下、emit 真實幾何塞不下」的時序死結

### Requirement: Assert-only acceptance gates

系統 SHALL 把五組機械驗收（每頁 pitch／圖框／利用率≥40%／label 互疊=0／offpage=0）實作為事後斷言；斷言失敗 SHALL 拋 `LEDGER_ASSERTION_FAILED` 附違規實體與帳本快照，且 SHALL NOT 觸發任何調參或重試。

#### Scenario: 斷言失敗

- **WHEN** emit 完成後任一斷言不成立
- **THEN** 視為 ledger 實作 bug：輸出違規實體＋帳本快照供 RCA，compose 以錯誤終止

## Acceptance Checks

- [ ] 迴歸測試全綠（≥39/39，含新 ledger 單元測試）
- [ ] CCM 5 頁重產：五組驗收數字全過且不劣化於 golden baseline
- [ ] `_estimate_bbox`、`_resolve_overlaps`、x-corridor、avail_y corridor、gutter floor 半身項已刪除（grep 無殘留）
- [ ] 人為構造超載頁面時 compose 拋 `BUDGET_INFEASIBLE` 附缺項清單（非無限迴圈、非靜默升框）
- [ ] 斷言閘路徑有測試覆蓋（注入帳本 bug 時拋 `LEDGER_ASSERTION_FAILED`）
