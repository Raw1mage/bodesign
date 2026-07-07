# Proposal: eda-bridge_occupancy-ledger

## Why

- CCM 原理圖交付戰役（BR_20260706 族）暴露 eda-bridge 的結構性架構債：composer（placement）與 kicad_emit（label/stub/文字幾何）是**脫節的兩段流水線**——placement 用估算 bbox 決定位置後凍結，emit 才知道真實幾何但已無位置自由度，且兩段之間沒有共用的空間帳本。
- 這條債是撞字、溢框、爆框、label 互疊、offpage 整族病的總根源。本次交付靠 8+ 層補丁（frame-first 時序反轉、x-corridor 守衛、gutter floor、avail_y corridor、U1 拆 unit…）收斂，但補丁彼此是局部規則，不是統一模型——每個新符號拓撲都可能再逼出一層新根因（本役實際剝了五層洋蔥）。
- 使用者終局裁決已定架構方向：**budget-first / frame-first**——畫圖之前就決定畫布大小與構圖比例，畫的當下用空間佔用帳本（reserve→draw），事後驗圖閘只能是斷言，不是重試迴圈。本 plan 把該裁決從補丁層升級為正式架構。

## Original Requirement Wording (Baseline)

- 「先畫圖再核利用率的方式不聰明，應該在畫的時候就決定好畫布大小以及構圖比例」（2026-07-07 使用者裁決）
- 「用plan-builder重新設計程式。」（2026-07-07 本 plan 開工指示）

## Requirement Revision History

- 2026-07-07: initial draft created via plan-init.ts

## Effective Requirement Description

1. 建立單一 **occupancy ledger**（2D 空間佔用帳本）作為 compose→emit 全流程的 SSOT：任何會佔紙面面積的實體（符號 body、pin、stub、label、電源符號、圖框邊界、gutter）在落筆前必須先 reserve，reserve 失敗即 fail-loud（`BUDGET_INFEASIBLE`），不得靜默升框或重試迴圈。
2. **budget-first 正向求解**：畫前清點內容 → 一步選框（內容佔 60–75%）→ 配額反解 scale/pitch → 落筆在帳本內。pitch-scan 候選在掃描期就以帳本可行性淘汰，不允許走到 emit 才炸。
3. composer 與 kicad_emit 共用同一帳本實例：placement 的 bbox 必須是 pin-inclusive 真實幾何（含 label 伸展量），emit 不得再遇到「位置已凍結但塞不下」的死結。
4. 既有機械驗收閘（每頁 pitch／圖框／利用率 ≥40%／label 互疊=0／offpage=0）全部降級為**事後斷言**：帳本正確則必然通過；斷言失敗＝帳本實作 bug，不是調參訊號。
5. 現有 31+ 迴歸測試與 CCM 5 頁交付結果（已通過使用者驗收流程的基準）不得回歸。

## Scope

### IN
- `packages/eda-bridge/bodesign_eda_bridge/composer.py` — placement、frame 選擇、pitch 求解重構為 ledger-driven
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` — label/stub/port 幾何改為 reserve→draw
- `packages/eda-bridge/bodesign_eda_bridge/kicad_symbol.py` — 符號 bbox 契約改為 pin-inclusive 真實外伸
- 新增 ledger 模組（單一 2D 佔用資料結構＋reserve/query API）
- `tests/test_composer_draftsman.py` — 迴歸基準保全＋ledger 單元測試
- 既有補丁層（x-corridor、gutter floor、avail_y corridor、_staggered_label_blocks）的**收編或退役**：能被 ledger 統一表達的補丁必須刪除，不留兩套真相

### OUT
- chip-to-chip wire routing（使用者已裁決取消，label-only 架構維持）
- AI 視覺 QA（使用者裁決：只跑機械閘）
- WebDAV working-cache 遷移（獨立 BR_20260707，另行執行）
- PCB（C04）側的 placement——本 plan 只管原理圖 emit 管線
- U1 拆 unit 的 gen 腳本層 opt-in 機制（已落地，維持現狀）

## Non-Goals

- 不追求通用 EDA 自動佈圖品質；目標是「機械閘全過＋工程可讀」的原理圖
- 不改變 netlist/SSOT 保真閘語義（幾何連通性檢查維持既有行為）

## Constraints

- 天條：no silent fallback——`BUDGET_INFEASIBLE` 必須 fail-loud 附缺項清單，禁止靜默升框迴圈（使用者明文裁決）
- 已證偽死路禁止再試：反向帶分桶、corridor clamp、位移層補丁、降 scale 硬壓
- 使用者既有裁決全部保留：四邊實體 pinout 鏡像、stub 直出、label 錨點最外端、電源/GND 符號旋轉、每頁獨立 pitch、label-only
- 引擎改動走 dev-loop（`BODESIGN_DEV=1 ./mcpctl.sh restart`）；容器內唯一合法拷貝 `/app/packages`；改前 tar snapshot；禁止 git rollback 未 commit 檔
- 工作區現有未 commit 改動（本役全部補丁）是重構起點基準，重構前必須先 commit 或 snapshot（待使用者裁決）

## What Changes

- 新增 `occupancy.py`（暫名）：2D 佔用帳本，rect reserve/query/conflict-report API
- composer 的 frame-fit／page_fill／macro_compact／gutter floor 邏輯重寫為「向帳本申請」模式
- kicad_emit 的 label/stub 幾何從「畫完再驗」改為「先 reserve 後 draw」
- 驗收閘從重試迴圈降為 assert-only
- 補丁層代碼淨刪除（預期 composer/emit 淨行數下降）

## Capabilities

### New Capabilities
- occupancy ledger：compose→emit 全程共用的空間佔用 SSOT，衝突在 reserve 期即報
- budget-first 求解：內容清點→選框→配額反解，pitch 候選掃描期可行性淘汰

### Modified Capabilities
- composer placement：估算 bbox → pin-inclusive 真實幾何＋label 伸展量
- kicad_emit label/stub：局部避讓規則 → 帳本 reserve
- 驗收閘：重試迴圈 → 事後斷言

## Impact

- 受影響代碼：`packages/eda-bridge/bodesign_eda_bridge/{composer,kicad_emit,kicad_symbol}.py`、新 ledger 模組、`tests/test_composer_draftsman.py`
- 受影響交付流程：CCM 5 頁重產腳本（`gen_ccm_pages.py`）不需改（引擎介面不變），但重構後必須重產比對基準
- 文件：`specs/architecture.md` eda-bridge 段落需全貌同步
