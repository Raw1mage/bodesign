# Proposal: c03_partition-diagram-emitter

## Why

- bodesign 把「核心板/載板分割 + board-to-board pin classes」當成**第一級 C03 交付物**（`C03_核心板模組ICD.md`、`bodesign_c03_export_mechanical_constraints`），卻**沒有任何工具**能把這份結構化資料畫成概念分割圖。
- 使用者要這張圖時只能離開 bodesign、手寫腳本、手刻 docxmcp ops——即便 bodesign 自己已具備所有必要零件（diagram emitter 先例 `c01_emit_id_visual_package`、docxmcp orchestration `bodesign_mcp_call` + `bodesign_stage_dir`）。
- 手做版本致命缺點是**重做性差**：ICD 一改，圖要全手工重畫。違背 bodesign「spec 是產品、圖是衍生」精神。
- 來源：`issues/issue_20260619_partition_diagram_emitter.md`（feature request，medium）。Origin task：aiguard C00 PRD 需要 CCM（核心板）/ECB（擴充載板）模組安排的 breakout 圖示。

## Original Requirement Wording (Baseline)

- "新增 `bodesign_c03_emit_partition_diagram`：輸入 core/carrier 分割 + interconnect pin classes（讀 ICD / 吃 c03_export_mechanical_constraints 輸出 / 吃顯式 JSON）；輸出分層 SVG + PNG（比照 c01_emit_id_visual_package），可選 editable PPTX（bodesign 內部用 mcp_call→docxmcp 產原生可編輯 shape，使用者不接觸 ops）；圖上自動標註 honest-boundary（design partition, not fab pinout / no RefDes.Pin→net / no DRC-SI claim）。資料/繪圖分離，emitter 吃 MODEL。skill 補概念圖路由段。"

## Requirement Revision History

- 2026-06-19: initial draft created via plan-init.ts
- 2026-06-19: 草案填寫；查證 BR gap 屬實（grep 確認無 partition_diagram emitter；c01_emit_id_visual_package(server.py:251/840) / c03_export_mechanical_constraints(server.py:908) 皆存在）。方向：開 plan-builder design-first。

## Effective Requirement Description

1. **新增 emitter `c03_emit_partition_diagram`**（R1 主）：吃 MODEL（boards + interconnect pin classes），產分層 SVG + PNG，比照既有 `c01_emit_id_visual_package` 的分層可編輯模式。
2. **資料/繪圖分離**（R2）：emitter 內部採「純資料 dict（boards + pin classes）→ 繪圖函式 → ops/SVG」結構，MODEL 即工具參數，方便日後加 board 數（>2 板）或換主題。參考實作藍本 `gen_breakout.py` / `gen_breakout_pptx.py` 已驗證形狀可行。
3. **honest-boundary 內建**：圖上自動帶誠實邊界標註（design partition, not fab pinout；no RefDes.Pin→net；no DRC-SI claim），預設帶上而非靠使用者手寫 footer。
4. **可選 editable PPTX**：bodesign 內部 `mcp_call → docxmcp` 產原生可編輯 shape，使用者不碰 ops。
5. **skill 補概念圖路由段**（R3）：明確區分四類圖該走哪個工具（板級分割→本工具、機構外觀→c01、實體落點→emit_layout、軟體容器→drawmiat C4）。

## Scope

### IN
- 新增 emitter 函式（workflow-core，比照 c01_id_package.py 範式）+ MCP 工具 `bodesign_c03_emit_partition_diagram`（handler + schema）。
- MODEL 資料契約（boards + interconnect pin classes）；輸入路徑：顯式 JSON（一階）、可選讀 ICD / 吃 `c03_export_mechanical_constraints` 輸出（後續）。
- 分層 SVG + PNG 產出（toolchain-gated PNG，比照 c01）。
- honest-boundary footer 內建。
- 可選 editable PPTX（內部走 `mcp_call → docxmcp`）。
- bodesign skill 概念圖路由段。

### OUT
- **不**處理 docxmcp repo 的 `issue_20260619_docxmcp_pptx_addshape_friction`（屬他 repo；若 emitter 走 mcp_call 可一併規避其摩擦，但修復不在本 plan）。
- **不**做實體 PCB placement（`emit_layout` / `route_net2pcb` 既有）；本工具是示意概念圖，非真佈局。
- **不**宣稱 fab pinout / RefDes.Pin→net / DRC-SI（honest-boundary 明確排除）。

## Non-Goals

- 不取代 drawmiat C4（軟體容器圖）；本工具專責電氣板級分割 + pin-class fan-out（C4 語意不適用）。
- 不做互動式拖拉編輯器；產出是可重生的 ICD 投影 + 可編輯 SVG/PPTX。

## Constraints

- **No silent fallback / no fabrication**（repo 天條）：MODEL 缺欄位（board/role/pin-class/dir）→ fail-fast + 顯式報錯 + 缺項清單；honest-boundary 標註程式自動帶，永不把 design partition 翻成 fab pinout；`files` 只列磁碟真實存在的檔（PNG toolchain 缺時不列、標 unavailable）。
- **可重生**：相同 MODEL 輸入 → 確定性 SVG/PPTX 產出（無隨機性），符合「圖是 ICD 衍生」。
- core vs worker 邊界：MODEL→SVG 繪圖屬 pure-python（core 側，比照 c01 deterministic 組裝）；PNG raster（cairosvg）與 PPTX（docxmcp orchestration）toolchain-gated。
- emitter 範式對齊既有 `emit_c01_id_visual_package`（分層、命名 group、placeholder 不靜默省略、result 列產出檔/圖層/邊界標註）。

## What Changes

- bodesign 新增「C03/C04 電氣域 diagram emitter」，補上 `c01_emit_id_visual_package`（機構域）的電氣對應物，讓板級分割圖從「手做、重做性差」變成「ICD 的可重生投影」。

## Capabilities

### New Capabilities
- **`c03_emit_partition_diagram`**：MODEL（boards + pin classes）→ 分層 SVG/PNG（+ 可選 editable PPTX），自動帶 honest-boundary。
- **概念圖路由（skill）**：四類圖的工具選擇明確化。

### Modified Capabilities
- （無破壞性修改；純新增。後續可讓 `c03_export_mechanical_constraints` 的輸出直接餵本 emitter，但不改其既有行為。）

## Impact

- 程式：`packages/workflow-core/`（emitter + MODEL，比照 c01_id_package.py 範式）；`services/mcp/server.py`（handler `_h_c03_emit_partition_diagram` + schema）。
- 既有範式複用：`emit_c01_id_visual_package`（分層 SVG/PNG emitter 模式）、`bodesign_mcp_call` + `bodesign_stage_dir`（PPTX orchestration）。
- skill：`skills/bodesign/`（概念圖路由段）。
- 測試：`tests/`（MODEL→SVG 確定性 + honest-boundary + fail-fast 缺項）。
- 參考藍本：手做 `gen_breakout.py` / `gen_breakout_pptx.py`（資料/繪圖已分離，演算法藍本）。
- 下游：C00–C07 的「板級分割確認」早凍結 milestone 直接受益（ICD 更新可重生圖）。
