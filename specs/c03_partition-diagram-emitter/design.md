# Design: c03_partition-diagram-emitter

## Context

bodesign 已有「結構化設計意圖 → 分層可編輯 SVG」的 emitter 先例：`emit_c01_id_visual_package`（`packages/workflow-core/bodesign_workflow_core/c01_id_package.py`，MCP `_h_c01_emit_id_visual_package` server.py:251/840）。本 plan 是它在 **C03/C04 電氣域** 的對應物——把板級分割（core/carrier）+ board-to-board pin classes 投影成概念 breakout 圖。

**查證的現況**（grep + server.py 確認）：
- 無任何 `partition_diagram` / `emit_partition` emitter（程式碼層真空）。
- `c03_export_mechanical_constraints`（server.py:908）已把 C03 跨層機構資料結構化——可當未來 MODEL 來源之一。
- `bodesign_mcp_call`（server→docxmcp 委派）+ `bodesign_stage_dir`（inline file tree → token）皆在工具表，PPTX orchestration 零件齊全。
- 參考藍本：手做 `gen_breakout.py`（SVG/PNG）/ `gen_breakout_pptx.py`（資料→docxmcp ops），已驗證「資料/繪圖分離」形狀可行。

## Goals / Non-Goals

### Goals
- 新增 emitter，對齊 c01 範式（分層、命名 group、placeholder 不靜默、result 列產出/圖層/邊界標註）。
- 資料/繪圖嚴格分離（MODEL → 繪圖函式 → SVG/ops）。
- honest-boundary footer 程式自動帶。
- PNG / PPTX toolchain-gated，缺則誠實標 unavailable。

### Non-Goals
- 不做真實 PCB placement（emit_layout 既有）。
- 不取代 drawmiat C4。
- 不做互動編輯器。

## Decisions

- **DD-1** **歸屬 workflow-core，不放 eda-bridge**。emitter 是「設計意圖投影成圖」（與 c01_id_package 同類），純 deterministic SVG 組裝，不觸 KiCad/pcbnew toolchain。放 `packages/workflow-core/bodesign_workflow_core/c03_partition_diagram.py`，與 c01_id_package.py 平行。理由：core 側 pure-python，避免硬依賴 worker-only 套件。

- **DD-2** **MODEL 即工具參數（資料/繪圖分離）**。三段結構：
  - `PartitionModel`（純資料 dict）：`{boards:[{name, role, tier, modules:[{name, type}]}], interconnect:[{class, signals, dir}]}`。
  - `_draw_*`（繪圖函式）：MODEL → SVG 圖元（純函式，無 IO）。
  - `emit_c03_partition_diagram(folder, model, ...)`：組裝 + 寫檔 + result，回 `.to_dict()`。
  - 換主題 / 加 board 數只動 MODEL 或主題參數，繪圖核心不改。

- **DD-3** **輸入路徑分階**（MVP-first）：
  - 階段 1（本 plan 實作）：吃**顯式 JSON MODEL**（工具參數）。最小可用、最易測。
  - 階段 2（後續，留接口）：讀 `C03_核心板模組ICD.md` 結構化區塊 / 吃 `c03_export_mechanical_constraints` 輸出 → 轉 MODEL。design 預留 `model` 直給 vs `icd_path` 解析兩入口，但本 plan 只實作 `model`。
  - 理由：避免一次吞 ICD 解析的不確定性，先把繪圖核心 + emitter 入口做穩。

- **DD-4** **五圖層 SVG 結構**（對齊 c01 分層）：`boards`（板輪廓 + role/tier 標題）/ `modules`（每板模組方塊，命名 `module-<board>-<n>`）/ `interconnect`（pin-class 連線 + 方向箭頭，命名 `net-<class>`）/ `legend`（pin-class 圖例）/ `annotations`（honest-boundary footer）。每板 `<g id="board-<name>">`。

- **DD-5** **honest-boundary 預設內建**。emitter 永遠在 `annotations` 層寫三條：`design partition, not fab pinout`、`no RefDes.Pin→net`、`no DRC-SI claim`。不可由參數關閉（誠實模型）；result 回報實際文字。對齊 repo「視覺交付物必帶可見 draft 標記」天條。

- **DD-6** **placeholder 不靜默**。模組 type 未被樣式庫覆蓋 → generic 方塊 + 標註型別 + result `placeholders[]` 列出。對齊 c01「uncovered components become labelled placeholders, never silently dropped」。

- **DD-7** **PNG / PPTX toolchain-gating**：
  - PNG：cairosvg 在 → 產出 + 列 `files`；不在 → `png_rendered=false`、**不列** files（no phantom），SVG 仍交付。對齊 c01 DD-9。
  - PPTX（可選，`emit_pptx=True`）：bodesign 內部 `bodesign_mcp_call(server="docxmcp", ...)` 產原生 shape；docxmcp 不可達 → `pptx_status="unavailable"` + reason，不偽造 .pptx。MODEL→docxmcp ops 轉換藍本取自 `gen_breakout_pptx.py`。

- **DD-8** **fail-fast 缺項**：MODEL 缺 `board.role` / `interconnect.class` / `interconnect.dir` → 回 `status="missing"` + 缺項清單（board 名 / interconnect 索引），不產圖、不以預設值續跑（no silent fallback 天條）。

- **DD-9** **確定性**：版面座標由 MODEL 順序 + 確定性 layout（板依宣告序、模組依宣告序）決定，無 RNG。相同 MODEL → byte-stable SVG。

- **DD-10** **skill 概念圖路由段**（R3）：在 `skills/bodesign/` 補一段四類圖路由表：板級分割 fan-out → `c03_emit_partition_diagram`；機構外觀 → `c01_emit_id_visual_package`；實體落點 → `emit_layout`；軟體容器 → drawmiat C4。屬文件改動，與 emitter 同 plan 但獨立 task。

## Risks / Trade-offs

- **R1** ICD 自動解析（DD-3 階段 2）格式不穩 → 緩解：本 plan 只做顯式 MODEL，ICD 解析另開 task/plan，不阻塞 MVP。
- **R2** PPTX 經 mcp_call 跨 server 失敗難測 → 緩解：PPTX 設為可選，核心交付是 SVG/PNG；PPTX 走 graceful unavailable。
- **R3** >2 板版面演算法複雜 → 緩解：MVP 用確定性網格/列排版（板水平排列、互連走板間通道），力導向等進階排版非本期目標。
- **R4** 與既有 c03_export_mechanical_constraints 資料模型不一致 → 緩解：本期 MODEL 自定義 schema，階段 2 再寫 adapter，不改既有工具輸出。

## Critical Files

- `packages/workflow-core/bodesign_workflow_core/c03_partition_diagram.py`（新，emitter + MODEL + 繪圖函式）。
- `packages/workflow-core/bodesign_workflow_core/__init__.py`（export `emit_c03_partition_diagram`）。
- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py`（範式參照，唯讀）。
- `services/mcp/server.py`（新 handler `_h_c03_emit_partition_diagram` + schema 條目）。
- `skills/bodesign/`（概念圖路由段，R3）。
- `tests/test_c03_partition_diagram.py`（新，MODEL→SVG 確定性 + honest-boundary + fail-fast + placeholder）。

## Code Anchors

- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py`（emit_c01_id_visual_package 範式：分層 SVG + preview/png gating + placeholder）
- `services/mcp/server.py:251` `_h_c01_emit_id_visual_package`（handler 範式）
- `services/mcp/server.py:840` c01 emitter schema 條目（schema 範式）
- `services/mcp/server.py:908` `c03_export_mechanical_constraints`（MODEL 來源候選，階段 2）
- 參考藍本：手做 `gen_breakout.py` / `gen_breakout_pptx.py`（資料/繪圖分離演算法）
