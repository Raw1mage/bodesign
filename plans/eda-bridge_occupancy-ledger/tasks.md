# Tasks: eda-bridge_occupancy-ledger

> 分階段落地（DD-8）：每階段迴歸綠＋CCM 5 頁 golden baseline 不劣化，才進下一階段。

## M0 — 起點固化（DD-9）

- [ ] M0-1 取得使用者 commit 裁決：現有未 commit 補丁層改動 commit 或 tar snapshot
- [ ] M0-2 建立 golden baseline：CCM 5 頁重產，記錄五組驗收數字（pitch／圖框／利用率／互疊／offpage）與各頁 sch md5

## M1 — Ledger 模組（新增，零打擊半徑）

- [ ] M1-1 `occupancy.py`：`OccupancyLedger`（rect reserve/query/conflict 報告/快照 dump），`LedgerConflict` 例外
- [ ] M1-2 dry-run 模式（臨時帳本、不落筆），供 A2 pitch-scan 預檢（DD-3）
- [ ] M1-3 單元測試：reserve 成功/衝突/衝突清單/dry-run/快照
- [ ] M1-4 迴歸驗證：既有測試全綠（ledger 尚未接線，應零影響）

## M2 — Emit 分支接線（A4 reserve-draw）

- [ ] M2-1 compose 入口建立帳本實例，先由 placement 結果批次 reserve 符號 body＋pin 外伸（唯讀鏡像既有行為）
- [ ] M2-2 `_staggered_label_blocks` label/stub 幾何改為 reserve→draw；衝突走顯式位移策略（帶上限），耗盡拋 `BUDGET_INFEASIBLE`
- [ ] M2-3 電源/GND 符號、pwr_flag 佔用進帳本
- [ ] M2-4 x-corridor 守衛、avail_y corridor 局部規則收編刪除（DD-6，逐個刪、逐個驗）
- [ ] M2-5 驗證：迴歸綠＋5 頁 golden baseline 數字不劣化

## M3 — Placement 分支接線（A1 清點 + A3 reserve-place）

- [ ] M3-1 `kicad_symbol` 提供 pin-inclusive extent 單點真相（DD-4）；A1 清點含 label_reach
- [ ] M3-2 composer placement 改 reserve→落位；`_estimate_bbox` 退役
- [ ] M3-3 `_resolve_overlaps` 事後推擠、gutter floor 半身項收編刪除（逐個刪、逐個驗）
- [ ] M3-4 驗證：迴歸綠＋5 頁 golden baseline 數字不劣化

## M4 — Budget-first 求解（A2）＋斷言閘（A5）

- [ ] M4-1 `_fit_sheet` 重寫：內容清點→一步選框（60–75%）→配額反解 scale/pitch
- [ ] M4-2 pitch-scan 候選以 dry-run reserve 預檢淘汰；無可行組合拋 `BUDGET_INFEASIBLE`（附缺項清單）
- [ ] M4-3 五組驗收閘降為 assert-only（`LEDGER_ASSERTION_FAILED` 附違規實體＋帳本快照）
- [ ] M4-4 殘餘補丁與重試迴圈清點刪除；淨行數統計
- [ ] M4-5 終驗：迴歸全綠＋5 頁重產五組數字全過＋與 golden baseline 對照報告

## M5 — 收尾

- [ ] M5-1 `specs/architecture.md` eda-bridge 段落全貌同步
- [ ] M5-2 收尾 event log（Key Decisions / Verification / Friction）＋ragbase distill
- [ ] M5-3 BR_20260706 族關閉評估（引用本 spec 作為結構性修復）
