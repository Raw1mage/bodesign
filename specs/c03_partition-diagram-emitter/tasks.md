# Tasks: c03_partition-diagram-emitter

> 來源：`issues/issue_20260619_partition_diagram_emitter.md`（FR）。對齊 design.md DD-1..DD-10。
> 任務狀態：`[ ]` pending / `[~]` in-progress / `[x]` done / `[!]` blocked / `[?]` decision。

## 1. MODEL 契約與骨架

- [x] 1.1 在 `packages/workflow-core/bodesign_workflow_core/c03_partition_diagram.py` 定義 `PartitionModel` dataclass（boards / interconnect），對齊 data-schema.json
- [x] 1.2 實作 `_validate_model(model)`：缺 board.role / interconnect.class / interconnect.dir → 回 missing + 缺項清單（DD-8 fail-fast）
- [x] 1.3 定義 `EmitPartitionResult` dataclass + `.to_dict()`（status/svg_path/png_rendered/pptx_status/layers/counts/placeholders/boundary/files/warnings）

## 2. 確定性繪圖核心（資料/繪圖分離）

- [x] 2.1 實作模組樣式庫 + `_resolve_glyphs(model)`：未覆蓋型別 → named placeholder（DD-6，不靜默）
- [x] 2.2 實作 `_layout(model)`：板依宣告序水平排列、模組依宣告序填入板輪廓（DD-9 確定性，無 RNG）
- [x] 2.3 實作 `_draw_boards` / `_draw_modules` / `_draw_interconnect` / `_draw_legend` 純函式 → SVG 圖元（DD-4 五圖層、命名 group board-/module-/net-）
- [x] 2.4 實作 `_draw_honest_boundary`：固定三條 annotations（DD-5，不可關閉）

## 3. Emitter 入口與 toolchain gating

- [x] 3.1 實作 `emit_c03_partition_diagram(folder, model, emit_pptx=False)`：組裝五圖層 SVG + 寫檔 + result
- [x] 3.2 PNG raster（cairosvg）：在則產出 + 列 files；缺則 png_rendered=false 不列 files（DD-7，no phantom）
- [x] 3.3 PPTX 選項：emit_pptx=True 走 `bodesign_mcp_call(server=docxmcp)` 產原生 shape；不可達 → pptx_status=unavailable + reason（DD-7，不偽造）
- [x] 3.4 export `emit_c03_partition_diagram` 於 `bodesign_workflow_core/__init__.py`

## 4. MCP 工具註冊

- [x] 4.1 `services/mcp/server.py` 加 handler `_h_c03_emit_partition_diagram`（比照 `_h_c01_emit_id_visual_package` server.py:251）
- [x] 4.2 加 schema 條目 `bodesign_c03_emit_partition_diagram`（比照 c01 server.py:840；參數 folder/model/emit_pptx）

## 5. 測試

- [x] 5.1 `tests/test_c03_partition_diagram.py`：MODEL 完整 → 五圖層 + group 命名齊全（對齊 test-vectors.json TV1）
- [x] 5.2 缺 role/class/dir → status=missing + 缺項（TV2 fail-fast）
- [x] 5.3 未覆蓋模組型別 → placeholder + result 告知（TV3）
- [x] 5.4 honest-boundary 三條自動帶（TV4）
- [x] 5.5 相同 MODEL → byte-stable SVG（TV5 確定性）
- [x] 5.6 缺 cairosvg → png_rendered=false 且 PNG 不列 files（TV6）
- [x] 5.7 >2 板版面自適應（TV7）

## 6. skill 路由段（R3）

- [x] 6.1 `skills/bodesign/SKILL.md` 補概念圖路由表（四類圖：板級分割→本工具 / 機構外觀→c01 / 實體落點→emit_layout / 軟體容器→drawmiat C4）

## 7. 驗證與收尾

- [x] 7.1 跑全測試（PYTHONPATH 含所有 package 子目錄）— 9 tests OK（orchestrator 獨立複驗）
- [x] 7.2 plan-sync + 更新 tasks checkbox
- [x] 7.3 architecture.md 同步（新增 C03 partition emitter 條目）
- [x] 7.4 收尾 event_record（實作完成紀錄：Scope/Key Decisions/Verification/Remaining）
