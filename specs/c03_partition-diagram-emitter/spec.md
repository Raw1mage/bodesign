# Spec: c03_partition-diagram-emitter

## Purpose

讓 bodesign 把 C03 板級分割（core/carrier）+ board-to-board pin classes 從結構化資料（ICD / `c03_export_mechanical_constraints` 輸出 / 顯式 JSON）投影成可交付的「概念分割 / breakout 圖」：分層可編輯 SVG + PNG，選配 editable PPTX，自動帶 honest-boundary 標註。圖是 ICD 的可重生衍生，非手做。

## Requirements

### Requirement: 由 MODEL 產出分層分割 SVG

#### Scenario: MODEL 完整時生成 breakout 圖
- **GIVEN** 一個 partition MODEL：`{boards:[{name, role, tier, modules:[...]}], interconnect:[{class, signals, dir}]}`，欄位齊全
- **WHEN** 呼叫 `c03_emit_partition_diagram`
- **THEN** 產出一個分層 SVG，含 `boards`（板輪廓 + 角色/層級標題）/ `modules`（每板模組方塊）/ `interconnect`（pin-class 連線 + 方向箭頭）/ `legend`（pin-class 圖例）/ `annotations`（honest-boundary footer）圖層
- **AND** 每塊板包成獨立命名 `<g id="board-<name>">`，每個模組包成 `<g id="module-<board>-<n>">`，每條互連包成 `<g id="net-<class>">`
- **AND** 回傳 result 列出產出檔路徑 + 圖層清單 + boards/modules/interconnect 計數 + 套用的 honest-boundary 標註文字

#### Scenario: 多板（>2）
- **GIVEN** MODEL 含 3 塊以上 boards
- **WHEN** 呼叫 emitter
- **THEN** 版面自適應排列所有板（不寫死 2 板），互連線正確連到對應板
- **AND** result 反映實際板數

### Requirement: MODEL 不足時 fail-fast，不捏造分割

#### Scenario: 關鍵欄位缺失
- **GIVEN** MODEL 的某塊 board 缺 `role`，或某條 interconnect 缺 `class` / `dir`
- **WHEN** 呼叫 emitter
- **THEN** 不產出圖，回傳 `missing` 狀態並列出缺失欄位（board 名 / interconnect 索引）
- **AND** 不以預設角色 / 預設方向 / 第一個可用值靜默續跑

#### Scenario: 模組型別未被圖元庫覆蓋
- **GIVEN** MODEL 某模組型別圖元庫未收錄樣式
- **WHEN** 呼叫 emitter
- **THEN** 該模組以 generic placeholder 方塊呈現並命名標註
- **AND** result 明確列出哪些模組用了 placeholder（不靜默省略）

### Requirement: honest-boundary 標註內建

#### Scenario: 任一成功產出
- **GIVEN** 任一可成功 emit 的 MODEL
- **WHEN** 產出 SVG / PNG / PPTX
- **THEN** 圖上自動帶 honest-boundary footer：`design partition, not fab pinout`、`no RefDes.Pin→net`、`no DRC-SI claim`
- **AND** 標註由程式自動帶上，不依賴使用者手寫；result 回報實際標註文字
- **AND** 永不把 design partition 標成 fab pinout（no fabrication 天條）

### Requirement: PNG 與 PPTX toolchain-gated（不偽造交付物）

#### Scenario: PNG raster
- **GIVEN** 環境有 cairosvg（或等價 raster toolchain）
- **WHEN** emit
- **THEN** 產出 PNG 並列入 `files`
- **AND** 缺 toolchain 時 `png_rendered=false`，PNG **不列入** `files`（不放 phantom 檔），SVG 仍正常產出

#### Scenario: editable PPTX（可選）
- **GIVEN** 呼叫者要求 PPTX 且 docxmcp 可達（`bodesign_mcp_call`）
- **WHEN** emit with PPTX 選項
- **THEN** bodesign 內部走 `mcp_call → docxmcp` 產原生可編輯 shape，使用者不接觸 add_shape ops
- **AND** docxmcp 不可達時回報 PPTX unavailable + 原因，SVG/PNG 仍交付（不偽造 .pptx）

### Requirement: 確定性可重生

#### Scenario: 相同 MODEL 重複 emit
- **GIVEN** 同一份 MODEL
- **WHEN** 兩次呼叫 emitter
- **THEN** 產出 SVG byte-stable（或結構等價），無隨機座標
- **AND** ICD 更新後重生圖反映新分割（圖是 ICD 衍生）

### Requirement: 資料/繪圖分離

#### Scenario: emitter 內部結構
- **GIVEN** emitter 實作
- **WHEN** 檢視其結構
- **THEN** 純資料（MODEL dict）→ 繪圖函式 → SVG/ops 三段分離，MODEL 即工具參數
- **AND** 加 board 數或換主題只需改 MODEL / 主題參數，不需改繪圖核心

## Acceptance Checks

- [ ] MODEL 完整 → 五圖層分割 SVG，board/module/net group 命名齊全。
- [ ] >2 板版面自適應，互連連線正確。
- [ ] 缺 role/class/dir → fail-fast 列缺項，不捏造。
- [ ] 未覆蓋模組型別 → placeholder + result 告知，不靜默省略。
- [ ] honest-boundary footer 自動帶（三條），result 回報文字。
- [ ] 缺 cairosvg → png_rendered=false 且 PNG 不列 files；SVG 正常。
- [ ] PPTX 選項：docxmcp 可達產原生 shape；不可達回 unavailable，不偽造。
- [ ] 相同 MODEL → byte-stable SVG（確定性）。
- [ ] 資料/繪圖分離（MODEL→繪圖函式→SVG/ops）。
