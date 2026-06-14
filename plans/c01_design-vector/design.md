# Design: c01_design-vector

## Context

C01（工業設計）階段目前的「設計形象」產出只有 raster 一條路：

- `c01_generate_concept_image` → Google AI Studio 生 PNG（reference-only、不可編輯、不可商用直引）
- `c01_emit_concept_prompts` → 只產 markdown prompt（`Concept_Image_Prompts.md`）

**沒有任何向量／可編輯的設計稿輸出。** repo 內既有 SVG 能力全在 PCB 域（`gerber-core.render_geometry_svg`、`eda-bridge` kicad-cli pcb export svg），是電路幾何渲染，無法複用為產品 ID 向量引擎。

使用者要的是「由描述繪製產品設計形象 + 落地向量稿」。經釐清，擬真 render 與可編輯向量在技術上互斥，定調為**雙軌產出**：擬真 PNG 當視覺定錨（既有），新增可編輯分層 SVG 當落地骨架。本工作只負責新增向量軌，吃同一份 C01 answer_state。

## Goals / Non-Goals

### Goals
- 新增 `c01_emit_design_vector`（暫名）：由 C01 answer_state 產出乾淨分層、設計師可編輯的扁平／技術風產品設計 SVG（外殼輪廓 + 面板佈局 + CMF 色塊 + 外露元件標示，可選爆炸圖）。
- 建立確定性 SVG 圖元庫（外殼原型 + 外露元件 symbol），LLM 只負責選圖元 + 佈局 + CMF 套色（S2 策略）。
- 與既有 raster 軌並行對齊：同一 answer_state、輸出互不衝突、handoff 交代雙軌關係。
- Phase 1 PoC：用一個真實描述生出一張及格的「完整產品形象圖」。

### Non-Goals
- 不做擬真產品照感的向量化（描圖碎路徑路線）。
- 不取代／修改既有 `c01_generate_concept_image` raster 路徑。
- 不做 3D/CAD/STEP（屬 C02）與製造尺寸標註（除非後續評估參數化路線才納入）。
- 不宣稱 final ID approval 或可商用直引。

## Decisions

<!-- DD entries appended by spec_record_decision -->
- **DD-1**: SVG 生成策略採 **S2（元件庫 + LLM 組裝）**。預建確定性 SVG 圖元庫（外殼原型 + 外露元件 camera/LED/USB-C/button/display/antenna/vent 對應可重用、命名穩定的 symbol），LLM 只負責「選圖元 + 佈局座標 + CMF 套色 + 構圖」。理由：S3 純參數化表現力受限退化成示意框；S1 純 LLM 直出違反 C01 deterministic 哲學且圖層命名不穩；S2 是甜蜜點——確定性圖元保證可驗證 + 圖層語意穩定（每元件獨立命名 `<g>` group，Figma/AI 可直接選取改動），方差可控，圖元庫能隨時間擴充，呼應既有 `EXPOSED_COMPONENT_KEYWORDS` 元件分類邏輯。
- **DD-2**: PoC（Phase 1）驗收標準 = 用一個真實描述生出一張「完整產品形象圖」：含外殼輪廓 + 主視覺面板佈局 + CMF 配色色塊 + 外露元件標示的分層 SVG，設計師能直接開 Figma 接手修改即為及格。不及格（圖層碎裂/元件無法選取/構圖崩壞）則回頭調 S2 圖元庫與佈局 prompt 策略，不進 implementing 後續 phase。
- **DD-3**: SVG 必須語意化分層——固定圖層命名規範（`outline` / `panel` / `cmf-fill` / `components/<type>` / `annotations`），每個外露元件包成獨立命名 `<g id="component-camera-1">` group。這是「設計師可編輯」承諾的具體實現，也是 PoC 及格判定的客觀依據。
- **DD-4**: 輸入單一來源 = 既有 C01 answer_state 欄位（`form_archetype` / `usage_posture` / `primary_face` / `visible_component_treatment` / `exposed_components` / `cmf_direction` / `display_uiux`），不另立平行狀態。沿用 C01 readiness/handoff 機制；answer_state 不足時標 `missing`/`external-needed`，不捏造幾何。

## Risks / Trade-offs

- **LLM 組裝層方差**：即便圖元確定，LLM 的佈局座標與構圖仍可能崩壞。緩解——佈局約束用「面板網格 + primary_face 對應」收斂；PoC 不及格就強化 prompt 約束或把佈局也部分參數化（退到 S2+S3 混合）。
- **圖元庫覆蓋度**：初期圖元庫只覆蓋常見外露元件（`EXPOSED_COMPONENT_KEYWORDS` 那組）。未覆蓋的元件需標記為 generic placeholder symbol + 告知，不靜默省略。
- **與 C01 deterministic 哲學的張力**：C01 模組明確標 `intentionally script-first`。S2 引入 LLM 是受控例外——LLM 輸出限定在「選圖元 ID + 座標 + 色值」這種可驗證的結構化裁決，非自由吐 SVG 字串。輸出後須通過 schema 驗證（圖層命名齊全、元件 group 存在）才算成功。
- **雙軌分歧**：raster prompt 與 vector 吃同一 answer_state 但走不同生成路徑，可能視覺不一致。緩解——handoff 文件明確兩者定位（參考 vs 落地骨架），不要求像素級一致。

## Critical Files

- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py` — 新增 `emit_c01_design_vector` 函式；圖元庫定義；沿用 `C01_INTERACTION_FIELDS` / `EXPOSED_COMPONENT_KEYWORDS` / answer_state 機制；新增輸出物 rel path（如 `C01-ID/Ai file/Design_Vector.svg`）。
- `services/mcp/server.py` — 新增 `_h_c01_emit_design_vector` handler + tool schema 註冊（line ~176 區塊鄰近）。
- `tests/test_mcp_server.py` — 新增 design-vector 工具測試（schema、分層輸出、缺輸入 fail-fast）。
- `specs/architecture.md` — C01 能力邊界更新（raster → raster + 可編輯向量雙軌）at living transition。
