# Design: eda-bridge_occupancy-ledger

## Context

eda-bridge 現行原理圖管線是兩段脫節的流水線：`composer.py`（placement，用 `_estimate_bbox` 估算幾何決定位置後凍結）→ `kicad_emit.py`（label/stub/文字，emit 才知道真實幾何但已無位置自由度）。兩段之間沒有共用空間帳本，衝突只能靠事後補丁（`_resolve_overlaps`、x-corridor 守衛、gutter floor、avail_y corridor、`_staggered_label_blocks` 位移規則）逐案撲滅。CCM 交付戰役（BR_20260706 族）實際剝了五層根因洋蔥，證明補丁路線每遇新符號拓撲就會再逼出一層。

使用者裁決升級為正式架構：**budget-first / frame-first**——畫前清點內容、一步選框、配額反解 scale、落筆走 reserve→draw、驗收閘降為斷言。本 design 以 idef0.A0（A1 清點 → A2 選框 → A3 reserve-place → A4 reserve-draw → A5 斷言）為骨架。

## Goals / Non-Goals

**Goals**

- 單一 `OccupancyLedger`（2D 佔用帳本）作為 A3/A4 共用 mechanism；任何佔紙面實體 reserve 成功才落筆
- A2 budget-first 求解：內容佔紙面 60–75% 一步選框；pitch 候選以 dry-run reserve 在掃描期淘汰
- 符號幾何契約統一為 pin-inclusive（含 label 伸展量），消滅估算 bbox 與真實幾何的雙重真相
- 五組機械閘（pitch／圖框／利用率≥40%／label 互疊=0／offpage=0）降為事後斷言
- 可被 ledger 統一表達的補丁層淨刪除（不留兩套真相）
- CCM 5 頁交付基準與迴歸測試（39/39）不回歸

**Non-Goals**

- chip-to-chip wire routing（label-only 架構維持，使用者裁決）
- 通用 EDA 自動佈圖品質、美學最佳化
- C04/PCB placement、WebDAV cache 遷移（BR_20260707 另行）

## Decisions

- DD-1: **Ledger 為新獨立模組 `occupancy.py`，不寄生在 composer 或 emit 內。** composer/emit 都 import 它；帳本實例由 compose 入口建立並貫穿全程（AR10/AR11「同一實例」）。拒絕方案：在 emit 內建 placed-rect list（現狀 `_staggered_label_blocks` 做法，只覆蓋 label 分支，placement 看不見）。
- DD-2: **Reserve 語義是 fail-loud 交易，不是 best-effort 提示。** `reserve(rect, owner, kind)` 衝突時回傳衝突矩形清單並拋 `LedgerConflict`；呼叫端不得捕捉後靜默改位置重試——改位置必須是顯式策略（帶上限、記錄嘗試軌跡），耗盡即升級為 `BUDGET_INFEASIBLE`。拒絕方案：無限重試迴圈（使用者明文禁止）。
- DD-3: **A2 的可行性預檢用 dry-run reserve（同一 ledger 代碼路徑），不用第二套估算公式。** pitch-scan 每個候選建臨時帳本跑骨架級 reserve（符號 body＋label 走廊配額）；預檢與正式落筆共用同一幾何真相，杜絕「掃描說可行、emit 才炸」的時序死結（本役第五層根因）。
- DD-4: **符號 bbox 契約改為 pin-inclusive extent，由 `kicad_symbol` 單點提供。** `_estimate_bbox` 退役；composer 不得再持有第二份幾何估算。label 伸展量（`label_reach`）在 A1 清點期一併計入內容清單。
- DD-5: **驗收閘 assert-only：斷言失敗＝`LEDGER_ASSERTION_FAILED`，附違規實體＋帳本快照，不調參不重試。** 閘從「品質守門」降為「帳本實作正確性偵測器」——帳本正確則斷言恆真。
- DD-6: **補丁層收編清單**：`_resolve_overlaps`（事後推擠）、x-corridor 守衛、gutter floor 半身項、avail_y corridor、`_staggered_label_blocks` 的局部避讓——全部由 reserve→draw 統一表達後刪除。保留：四邊 pinout 鏡像、stub 直出、label 錨點外端、電源/GND 旋轉、每頁獨立 pitch（使用者裁決的產品行為，非補丁）。
- DD-7: **U1 拆 unit 的 gen 腳本層 opt-in（`_U1_SPLIT_BY_SLUG`）維持現狀不動**；ledger 落地後單邊 label 欄超載會在 A2 期以 BUDGET_INFEASIBLE 顯式報出，屆時再評估是否把拆 unit 升級為 A2 的建議輸出。
- DD-8: **分階段落地，每階段迴歸綠才進下一階段**（見 tasks.md M1–M4）：先建 ledger 模組＋單元測試 → emit 分支接上（label/stub/電源符號）→ placement 分支接上＋`_estimate_bbox` 退役 → A2 budget 求解重寫＋補丁刪除。拒絕方案：一次性大爆炸重寫（打擊半徑不可控，且工作區已有大量未 commit 改動）。
- DD-9: **重構起點基準必須先固化**：動工前把現有未 commit 的補丁層改動 commit（或至少 tar snapshot），並以 CCM 5 頁重產結果（五組數字）建立 golden baseline。任何階段的驗證都是「迴歸測試綠＋5 頁重產數字不劣化」。

## Risks / Trade-offs

- **打擊半徑大**（composer 1529 行＋emit 2141 行核心路徑重排）— mitigation: DD-8 分四階段、每階段迴歸綠＋5 頁 golden baseline 比對；DD-9 起點固化。
- **dry-run reserve 的骨架級近似與正式落筆的完整 reserve 可能有縫**（預檢過、落筆炸）— mitigation: 縫隙一律視為 A2 預檢 bug 修預檢，不在 A3/A4 加容忍；斷言閘（DD-5）會把縫隙顯式暴露。
- **效能：pitch-scan × dry-run reserve 是 O(候選×實體) 的矩形相交測試** — mitigation: 帳本用簡單 sorted-interval / 網格 bucket 即可（頁面實體數 <10³，Python 純算可負擔；本役實測全頁 compose 只需秒級）。
- **補丁刪除可能拆掉隱性依賴**（某補丁順帶修了未記錄的 case）— mitigation: 補丁逐個刪、刪一個跑一輪迴歸＋golden baseline，不批次刪。
- **工作區未 commit 改動與重構混雜** — mitigation: DD-9；M1 開工前先取得使用者 commit 裁決。

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/occupancy.py`（新）— OccupancyLedger：reserve/query/dry-run/衝突報告/快照
- `packages/eda-bridge/bodesign_eda_bridge/composer.py` — A1 清點、A2 budget 求解、A3 reserve-place；`_estimate_bbox`/`_resolve_overlaps`/gutter floor 退役點
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` — A4 reserve-draw；`_staggered_label_blocks`/x-corridor/avail_y corridor 收編點
- `packages/eda-bridge/bodesign_eda_bridge/kicad_symbol.py` — DD-4 pin-inclusive extent 單點真相
- `tests/test_composer_draftsman.py` — 迴歸基準（39 tests）＋新 ledger 單元測試落點
- `issues/assets_20260706_c03_session/gen_ccm_pages.py` — golden baseline 重產腳本（介面不變）

## Code Anchors

- `composer.py:263 _estimate_bbox` — DD-4 退役對象
- `composer.py:569 _resolve_overlaps` — DD-6 收編對象（事後推擠）
- `composer.py:1067 _fit_sheet` — A2 budget 求解重寫落點
- `kicad_emit.py:1351 _staggered_label_blocks` — A4 reserve-draw 主改造點
- `kicad_emit.py:1123 _label_bbox` — label 幾何真相，改為向 ledger 提供 reserve rect
