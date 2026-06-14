# Proposal: c02_voice-to-design

## Why

- 使用者要的不是「填 JSON 給工具」，而是「**口述需求 → 直接得到 3D 結構設計稿**」的對話式體驗。
- 探勘證據（實跑 50×30 板 + 完整約束對照組）證明：bodesign C02 的 3D 結構鏈中段已通——`c02_readiness`（38%→補齊→100%）→ `c02_generate_openscad`（source_generated）→ `c02_export_stl`（worker 真有 OpenSCAD CLI，stl_exported，viewable+printable_draft_ready=true）。
- 缺口集中在**兩端**：前端「把口述拆成結構化約束」、末端「把 STL 渲染成可看的設計稿」。中段不缺。
- C02 的 deterministic 哲學（不猜尺寸、缺就 fail-fast）與「口述天生不完整」之間有張力，需靠**反問補全**調和——而這個模式 bodesign 已在 C00/C01 與 `plan_design_intent` 驗證存在。

## Original Requirement Wording (Baseline)

- 「讓我能口述設計需求就得到設計稿。」
- 「我想要3D結構設計，相容skp或stl的產出，可渲染。」

## Requirement Revision History

- 2026-06-14: initial draft created via plan-init.ts
- 2026-06-14: 釐清定調。使用者確認：STL 為主（已有，SKP 維持 import guide 現狀）；MVP 第一刀 = 全鏈閉環（口述→出圖）；不完整時用反問補全（保留 fail-fast，不破壞 C02 不猜尺寸哲學）。

## Effective Requirement Description

1. 使用者用自然語言口述產品結構需求（板尺寸、要裝什麼、開哪些孔、什麼環境），系統把口述抽取成 C02 結構化約束草稿。
2. 系統用 `c02_readiness` 判定完整度，對缺失的關鍵約束**反問補全**（仿 C00/C01 next_question 與 plan_design_intent 的 ClarifyingQuestion 模式），使用者確認後才生 source（不猜尺寸）。
3. 約束齊備 → `c02_generate_openscad` 生實體外殼 → `c02_export_stl` 匯出真 STL。
4. 新增 **enclosure 渲染**：把 STL 渲染成 top/iso 設計稿圖（複用既有 pyrender+trimesh 機制）。
5. 整條串成「口述 → 設計稿（渲染圖 + STL + 可選 STEP）」閉環。

## Scope

### IN
- C02 口述意圖抽取層：自然語言 → C02 約束草稿（仿 `plan_design_intent` 的 keyword-binding + 三態 + open_questions 架構，但綁定 C02 機構欄位）。
- C02 對話式反問補全層：缺失關鍵約束時產生澄清問題，使用者答覆後併入約束、重算 readiness。
- enclosure 渲染：STL → top/iso PNG（重構 `render_board_model` 抽出共用渲染後段，新增 `render_enclosure_model` 吃 STL）。
- 串成口述→設計稿閉環的編排（沿用 C02 readiness/approval gate）。

### OUT
- 原生 SKP 匯出（維持 `c02_export_skp` 現狀：回 unavailable + import guide，不造假）。
- 改動 C02「不猜尺寸、缺即 fail-fast」哲學。
- 語音轉文字（ASR）——「口述」此處指自然語言文字輸入，語音端不在範圍。
- ME 核可、製造交付、廠商 handoff（C02 本就不宣稱）。

## Non-Goals

- 不讓系統在約束不足時自行猜尺寸續跑（反問補全是唯一補洞方式）。
- 不重寫渲染管線（pyrender 場景/視角/EGL 已存在，只接 STL 入口）。
- 不做通用 NL→CAD，範圍鎖定 C02 enclosure。

## Constraints

- C02 deterministic：所有顯式尺寸（壁厚/間隙/蓋間隙）必須來自使用者答覆或明確輸入，系統不猜。
- 100% readiness 時系統有 approval gate（實跑已證：「Generate parametric source only after the user approves this constraint set」），編排須尊重此閘，不自動跨過。
- 渲染需 worker 的 EGL/GL（me worker 已 ship build123d/VTK GL libs）；STL 匯出需 OpenSCAD CLI（已證存在）。
- 抽取層須與既有 answer_state/readiness 機制一致，不另立平行狀態。

## What Changes

- 新增 workflow-core 函式：C02 口述抽取（`plan_c02_intent` 或近似）+ 反問補全。
- 新增 eda-bridge 函式 `render_enclosure_model`（STL→PNG），重構 `render_board_model` 共用渲染後段。
- 新增 MCP tools：`c02_plan_intent`、`c02_next_question`/`c02_update_answers`（若沿用既有則擴充）、`c02_render_enclosure`。
- C02 handoff 文件補上「口述→設計稿」流程說明。

## Capabilities

### New Capabilities
- C02 口述意圖抽取：自然語言 → 結構化 C02 約束草稿 + 缺失澄清問題。
- C02 反問補全：對話式收集缺失約束，重算 readiness。
- enclosure 渲染：STL → top/iso 設計稿圖。

### Modified Capabilities
- `render_board_model`：重構抽出共用渲染後段，供 board 與 enclosure 共用。
- C02 編排：從「填 JSON」升級為「口述→反問→確認→生圖」對話閉環。

## Impact

- 程式：`packages/workflow-core/bodesign_workflow_core/c02_me_package.py`（抽取+反問）、`requirement_planning.py`（可參考/抽共用）、`packages/eda-bridge/bodesign_eda_bridge/model_render.py`（渲染重構+enclosure）、`services/mcp/server.py`（新 handlers+tools）、對應 tests。
- 文件：C02 handoff、`specs/architecture.md`（C02 從約束輸入升級為對話式設計，新增 enclosure 渲染路徑）。
- 體驗：C02 從「工程師填約束」變成「使用者口述、系統反問、確認出圖」。
