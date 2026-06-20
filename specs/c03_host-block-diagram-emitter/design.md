# Design: c03_host-block-diagram-emitter

## Context

新增 emitter 與既有 `c03_partition_diagram.py` 是 sibling 關係：同一 family（concept-diagram emitter）、
同一組契約（layered SVG / fail-fast / placeholder / honest-boundary / determinism / gated raster）。
最大化複用既有 pattern，最小化發明新結構。

## Goals / Non-Goals

- **Goal**: host-centric 放射狀功能方塊圖的 deterministic emitter，可被 router 指名、tool 暴露。
- **Goal**: derived-product reference-diff 結構化承載（emitter 欄位 + 文件模板）。
- **Non-Goal**: 不重構 partition emitter；不自動從 netlist 推導架構；不產 fab/DRC claim。

## Decisions

- **DD-1**: 新 emitter 獨立成 `c03_host_block_diagram.py`，**不**併入 partition emitter。
  理由：兩者佈局演算法不同（partition = 水平 board 並列；host-block = center + 四向放射），
  合併會讓單檔承擔兩種 layout 分支，違反單一職責；sibling 檔案更易維護與測試。
- **DD-2**: 完全鏡射 partition emitter 的 dataclass 結構：`HostBlockModel` / `EmitHostBlockResult`
  + `_validate_model` / `_layout` / `_draw_*` / `_render_svg` / `emit_c03_host_block_diagram`
  + `_emit_pptx` / `_pptx_shapes`。降低 reviewer 認知成本、行為一致。
- **DD-3**: 放射狀佈局 deterministic 規則 — peripherals 依 `side`(top/bottom/left/right) 分組，
  組內依**宣告順序**排列；無 RNG。center box 固定置中，四側對稱分佈。
- **DD-4**: layers = `("center","peripherals","buses","legend","annotations")`（對應 partition 的
  boards/modules/interconnect/legend/annotations，語意平移）。
- **DD-5**: honest-boundary footer 改為 host-block 語境且常開、不可參數化：
  `("functional block diagram, not a netlist", "no RefDes.Pin→net", "no DRC-SI claim")`。
- **DD-6**: glyph library 沿用 partition 的 `_MODULE_GLYPHS`（soc/memory/power/connector/phy/
  sensor/fpga/mcu/rf），未知 type → dashed placeholder + 列入 placeholders[]/warnings[]。
- **DD-7**: PNG 經 cairosvg gated；PPTX 經 docxmcp bridge（`mcp_call` 注入）gated；皆無 phantom。
- **DD-8**: `reference_baseline` 為 optional 頂層欄位 `{name, diffs:[str], sourcing_gates:[str]}`，
  有則在 annotations layer 額外渲染「⊕ derived from <name>」+ diffs + gates；無則完全不渲染
  （不憑空造 baseline，符合 honesty model）。
- **DD-9**: 輸出路徑 `C03-EE/block/Host_Block_Diagram.{svg,png,pptx}`（與 partition 的
  `C03-EE/partition/` 平行命名）。

## Risks / Trade-offs

- **R1**: 放射狀 layout 的對稱演算法比 partition 的水平並列複雜，邊界 case（某側 0 個 peripheral、
  某側極多）需在 test-vectors 覆蓋，避免 overflow/重疊。緩解：test-vector 含 lopsided 分佈。
- **R2**: bus 連線正交路徑在四向放射時可能交叉。MVP 接受直線連 center↔peripheral（不做 obstacle
  avoidance）；honest-boundary 已聲明非 fab 圖，交叉可接受。
- **R3**: 文件改動（SKILL.md router + 2 GUIDE）若與既有措辭衝突需小心 in-place edit，不破壞結構。

## Critical Files

- `packages/workflow-core/bodesign_workflow_core/c03_partition_diagram.py` — **範本**（鏡射對象）
- `packages/workflow-core/bodesign_workflow_core/c03_host_block_diagram.py` — **新檔**（emitter）
- `packages/workflow-core/bodesign_workflow_core/__init__.py` — export 新 entry point
- `services/mcp/server.py` — `_h_c03_emit_host_block_diagram` handler + tool 註冊（範本見 line 365, 935）
- `tests/test_c03_partition_diagram.py` — **範本**（鏡射對象）
- `tests/test_c03_host_block_diagram.py` — **新檔**（test）
- `skills/bodesign/SKILL.md` — concept-diagram router 表（§"Concept-diagram router"，約 line 130-140）
- `skills/bodesign/stages/c01-id/GUIDE.md` — 責任邊界文字
- `skills/bodesign/stages/c03-ee/GUIDE.md` — block-diagram 段落指向新 emitter（約 line 74）

## Code Anchors

- partition handler 範本: `services/mcp/server.py:365` (`_h_c03_emit_partition_diagram`)
- partition tool 註冊: `services/mcp/server.py:935`
- partition emitter 全檔: `packages/workflow-core/bodesign_workflow_core/c03_partition_diagram.py:1-586`
- router 表: `skills/bodesign/SKILL.md:130-140`
- c03 block-diagram 指引: `skills/bodesign/stages/c03-ee/GUIDE.md:74`
