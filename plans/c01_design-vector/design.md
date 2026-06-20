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
- **DD-5** (2026-06-17, EXTEND): 範圍從單一 `c01_emit_design_vector` 擴成 **三 bucket emitter**（依 BR）。三者各自獨立工具、共用 answer_state + `Interface_Constraints.json` 輸入、共用 fail-fast 與 draft-marking 紀律：
  - `emit_c01_id_visual_package` → `C01-ID/Ai file/`（`<product>_ID_skeleton.svg` 內部沿用 DD-1 S2 分層 SVG 引擎 + `figma_import_spec.json` + `README.md`）。
  - `emit_c01_cmf_package` → `C01-ID/CMF/`（`<product>_CMF_Direction.pdf` + `cmf_tokens.json` + `README.md`）。
  - `emit_c01_uiux_package` → `C01-ID/Display UI_UX/`（`<product>_UIUX_Flow.pdf` + `uiux_wireframes.svg` + `README.md`）。
  注意 bucket 路徑用 BR 指定的 `Display UI_UX/`（底線），與既有 companion 的 `Display UIUX/`（無底線、`C01_OUTPUTS["display_uiux"]`）**並存不衝突**：companion 是 source-of-truth markdown，ID-native bucket 是 optional demo 交付物。
- **DD-6** (2026-06-17, EXTEND): **不偽造原生檔**。`.ai` 僅在有真實 Illustrator-compatible export path 時產出，否則只給 SVG + `figma_import_spec.json`（Figma 不可用時的中間產物）。PDF 經 docxmcp / approved bodesign document pipeline 組裝（`bodesign_emit_doc` → docx+pdf，或 `bodesign_mcp_call` 驅動 docxmcp），不手工拼 PDF bytes。每個視覺產出帶可見 draft 浮水印文字（`draft / not final industrial design` · `not CMF approval` · `not UI sign-off`）。
- **DD-7** (2026-06-17, EXTEND): `assess_c01_package_readiness` 擴成**雙軌**回報但**向後相容**。既有 `readiness_pct` / `usable` / `artifacts`（對五件 core companion，即 `C01_OUTPUTS`）語意完全不變；新增 `companion_readiness`（明確別名既有 core track）與 `id_native_readiness`（三 bucket，optional）兩個獨立 track 欄位。ID-native 產出**不得**讓 package 從 draft 升 approved、**不得**作為 final ID approval 依據（`human_approved` 仍恆為 False，由人工 gate 控制）。
- **DD-8** (2026-06-17, EXTEND): emitter 輸入優先序 = `Interface_Constraints.json`（C01 已產出的下游契約，DD-4 的 `_constraints()` 輸出）為主、answer_state 補充、C02/C03 envelope evidence 可選。三 bucket 缺關鍵欄位時各自 fail-fast（CMF 缺 `cmf_direction`；UIUX 缺 `display_uiux`/status 描述；visual 缺 `form_archetype`/`primary_face`/`exposed_components`），回 `missing`/`external-needed` + 缺欄清單，不以預設值靜默續跑（天條：no silent fallback）。無 display 產品的 UIUX 映射到 LED/status/button 互動，屬顯式設計決策非 fallback。

## Risks / Trade-offs

- **LLM 組裝層方差**：即便圖元確定，LLM 的佈局座標與構圖仍可能崩壞。緩解——佈局約束用「面板網格 + primary_face 對應」收斂；PoC 不及格就強化 prompt 約束或把佈局也部分參數化（退到 S2+S3 混合）。
- **圖元庫覆蓋度**：初期圖元庫只覆蓋常見外露元件（`EXPOSED_COMPONENT_KEYWORDS` 那組）。未覆蓋的元件需標記為 generic placeholder symbol + 告知，不靜默省略。
- **與 C01 deterministic 哲學的張力**：C01 模組明確標 `intentionally script-first`。S2 引入 LLM 是受控例外——LLM 輸出限定在「選圖元 ID + 座標 + 色值」這種可驗證的結構化裁決，非自由吐 SVG 字串。輸出後須通過 schema 驗證（圖層命名齊全、元件 group 存在）才算成功。
- **雙軌分歧**：raster prompt 與 vector 吃同一 answer_state 但走不同生成路徑，可能視覺不一致。緩解——handoff 文件明確兩者定位（參考 vs 落地骨架），不要求像素級一致。

## Critical Files

- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py` — 新增三 bucket emitter（`emit_c01_id_visual_package` / `emit_c01_cmf_package` / `emit_c01_uiux_package`）；SVG 圖元庫定義；CMF token 表 + 材質族對應；UIUX wireframe 圖元；draft-marking helper；沿用 `C01_INTERACTION_FIELDS` / `EXPOSED_COMPONENT_KEYWORDS` / `_constraints()` / answer_state 機制；擴充 `assess_c01_package_readiness` 為雙軌；新增 bucket rel path 常數（`C01-ID/Ai file/`, `C01-ID/CMF/`, `C01-ID/Display UI_UX/`）。
- `services/mcp/server.py` — 新增 3 個 handler（`_h_c01_emit_id_visual_package` / `_h_c01_emit_cmf_package` / `_h_c01_emit_uiux_package`）+ tool schema 註冊（c01 區塊 ~line 793 附近），readiness handler 沿用既有 `_h_c01_readiness`（回傳已含新分軌欄位）。
- PDF 組裝 — 透過既有 `bodesign_emit_doc`（markdown→docx+pdf）或 `bodesign_mcp_call` 驅動 docxmcp；不手工拼 PDF。
- `tests/test_mcp_server.py` / `tests/test_c01_id_package.py` — 新增三 bucket 工具測試（schema、bucket 輸出、缺輸入 fail-fast、draft 標記、readiness 分軌、no-fallback）。
- `specs/architecture.md` — C01 能力邊界更新（raster → raster 參考 + ID-native 三 bucket draft deliverable + readiness 雙軌）at living transition。
