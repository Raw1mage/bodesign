# Proposal: c01_design-vector

## Why

- C01 目前的「設計形象」產出只有 raster 一條路：`c01_generate_concept_image` 走 Google AI Studio 生 PNG（reference-only、不可編輯、不可商用直引），`c01_emit_concept_prompts` 只產 markdown prompt。**沒有任何向量／可編輯的設計稿輸出。**
- 使用者要的是「透過描述繪製產品設計形象，且要有落地的向量稿」——一個設計師打開後能直接動工（改 CMF、調比例、選取單一元件）的乾淨 SVG 來源。
- repo 內既有的 SVG 能力全部在 PCB 域（`gerber-core.render_geometry_svg`、`eda-bridge` kicad-cli pcb export svg），是電路幾何渲染，無法複用為產品 ID 向量引擎。
- → 這是 C01 階段一個**真實能力缺口**，不是重造輪子。

## Original Requirement Wording (Baseline)

- 「評估新功能的可行性。我希望能透過描述來繪製產品設計形象。要有落地的向量稿。」

## Requirement Revision History

- 2026-06-13: initial draft created via plan-init.ts
- 2026-06-13: 釐清後定調為「雙軌產出」。使用者確認：視覺風格選擇擬真 render，但在理解「擬真 render 與可編輯向量技術互斥」後，接受**擬真參考圖 + 扁平可編輯向量**並行；落地用途為設計師可編輯來源 SVG；整合位置併入現有 C01 工業設計流程。

## Effective Requirement Description

1. 在 C01 階段新增一個工具（暫名 `c01_emit_design_vector`），由 C01 的結構化描述（answer_state）驅動，產出**乾淨分層的可編輯 SVG** 產品設計稿：扁平／技術風格的產品輪廓、主視覺面板佈局、CMF 配色色塊、外露元件標示、（可選）爆炸圖。
2. 與既有的 `c01_generate_concept_image`（擬真 PNG 參考）並行：擬真圖當「設計師看的視覺定錨」，向量稿當「設計師改的落地骨架」，兩者吃同一份 C01 描述。
3. SVG 必須語意化分層（圖層命名、元件可獨立選取），讓設計師在 Figma/Illustrator 能直接接手，而非一坨碎路徑。

## Scope

### IN
- 新增 description→可編輯向量 SVG 的 C01 工具，吃既有 C01 answer_state 欄位（`form_archetype` / `usage_posture` / `primary_face` / `visible_component_treatment` / `exposed_components` / `cmf_direction` / `display_uiux`）。
- 定義 SVG 分層 schema（圖層命名規範、元件群組、CMF 色票對應）。
- 定義產品形態的「元件庫／圖元庫」策略（如何把外露元件如 camera/LED/USB-C/button 對應到可重用 SVG 圖元，收斂 LLM 直出 SVG 的品質方差）。
- 與既有 C01 raster 產出並行對齊（同一 answer_state、輸出互不衝突、handoff 文件交代兩者關係）。
- Phase 1 PoC：用一個真實描述驗證扁平向量品質天花板。

### OUT
- **擬真產品照感的向量化**（把擴散模型 PNG 丟 potrace/vtracer 描圖 → 碎路徑）。技術上無乾淨解，明確排除。
- 取代或修改既有 `c01_generate_concept_image` 的 raster 生圖路徑。
- 3D／CAD／STEP（屬 C02 機構）與製造尺寸標註（除非 plan 後續評估參數化路線 D 才納入）。
- 最終工業設計核可（C01 本就不宣稱 final ID approval）。

## Non-Goals

- 不追求「擬真 render 的單一向量產物」——這是物理互斥，不假裝能做到。
- 不做通用 description-to-vector 平台；範圍鎖定 C01 產品設計形象。
- 不在 PoC 階段就堆複雜有機曲面；先驗證扁平／技術風的品質天花板。

## Constraints

- LLM 直出 SVG 對複雜有機曲面品質不穩 → 必須靠分層 schema + 元件庫圖元約束收斂，不能裸生。
- 必須與既有 C01 deterministic、script-first 的設計哲學一致（C01 模組明確標註「intentionally script-first」）：LLM 只負責結構化幾何裁決，產出可重現、可驗證。
- 不可宣稱可商用直引或 final ID approval；輸出定位為設計師可編輯來源。
- 沿用 C01 既有 answer_state / readiness / handoff 機制，不另立平行狀態。

## What Changes

- 新增 workflow-core 函式 + MCP handler（`c01_emit_design_vector` 或近似命名）。
- 新增 C01-ID 輸出物：分層 SVG（例如 `C01-ID/Ai file/Design_Vector.svg`）+ 對應 layer/CMF 對照說明。
- C01 handoff 文件補上「擬真參考 vs 可編輯向量」雙軌說明。
- 可能擴充 readiness rubric 把向量稿納入 C01 完成度。

## Capabilities

### New Capabilities
- `c01_emit_design_vector`: 由 C01 answer_state 描述產出乾淨分層、設計師可編輯的扁平／技術風產品設計向量 SVG。

### Modified Capabilities
- C01 handoff / readiness: 納入雙軌（raster 參考 + 向量落地）產出的對齊與完成度判定。

## Impact

- 程式：`packages/workflow-core/bodesign_workflow_core/c01_id_package.py`（新增函式）、`services/mcp/server.py`（新增 handler + tool 註冊）、對應 tests。
- 文件：C01 handoff、`specs/architecture.md`（C01 能力邊界更新）。
- 設計流程：C01 ID 交付物從「純 raster 參考」升級為「raster 參考 + 可編輯向量骨架」。
