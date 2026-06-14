# Design: c02_voice-to-design

## Context

使用者願景：「口述需求 → 直接得到 3D 結構設計稿」。探勘證據（實跑 50×30 板 + 完整約束對照組）證明 C02 中段已通：`c02_readiness`（38%→補齊→100%）→ `c02_generate_openscad`（source_generated）→ `c02_export_stl`（worker 有 OpenSCAD CLI，stl_exported，viewable+printable_draft_ready）。

缺口集中在兩端 + 一個對話層，而且三者都有**現成基礎設施可仿/可接**：

- **前端 NL 抽取**：`plan_design_intent`（requirement_planning.py）已是 deterministic keyword-binding + 三態(answered/stated/missing) + 自動產 ClarifyingQuestion 的成熟架構，但綁的是 C03 電路欄位（compute/comms/memory/power）。C02 抽取仿同款架構、換成機構欄位。
- **約束 schema**：`c03_export_mechanical_constraints` 已輸出 C02 要的整組欄位（component_heights / connector_openings / heat_sources / antenna_keepouts / battery_envelope）。C02 抽取的目標 schema 直接對齊它。
- **對話式反問**：`c01_next_question` + `c01_update_answers` 是驗證過的「讀 answer_state → 回下一題 → 收答覆 → 重算 readiness」迴圈。C02 反問層仿此模式。
- **末端渲染**：`render_board_model`（model_render.py）的 pyrender+trimesh 渲染後段（top/iso、pose、EGL offscreen）已完整，只是入口寫死吃 glb；trimesh 原生讀 STL，接管子即可。

## Goals / Non-Goals

### Goals
- C02 口述意圖抽取：自然語言 → C02 約束草稿（對齊 c03_export_mechanical_constraints schema）+ 缺失澄清問題。
- C02 對話式反問補全：缺關鍵約束時反問，使用者答覆併入、重算 readiness（保留 fail-fast）。
- enclosure 渲染：STL → top/iso 設計稿圖（重構 render_board_model 抽共用後段，新增 render_enclosure_model）。
- 串成「口述→反問→確認→生外殼→STL→渲染圖」閉環，尊重 100% readiness 的 approval gate。

### Non-Goals
- 原生 SKP（維持 c02_export_skp 現狀 unavailable + import guide，不造假）。
- 改動 C02 不猜尺寸哲學。
- 語音轉文字（ASR）；「口述」指自然語言文字輸入。
- 重寫渲染管線、ME 核可、製造交付。

## Decisions

<!-- DD entries appended by spec_record_decision -->
- **DD-1**: NL 抽取**仿 `plan_design_intent` 架構**（deterministic keyword-binding + 三態 + ClarifyingQuestion），不從零、不純 LLM。換綁 C02 機構欄位，目標 schema 對齊 `c03_export_mechanical_constraints` 已輸出的整組約束（heights/openings/heat/antenna/battery）。理由：複用驗證過的抽取骨架，降低方差，與既有 answer_state 機制一致；LLM 僅在 keyword 無法覆蓋的自由語句上做輔助標註（可選增強，非必須）。
- **DD-2**: 不完整時用**反問補全 + 保留 fail-fast**（使用者選定）。仿 `c01_next_question`/`c01_update_answers` 對話迴圈：缺關鍵約束 → 反問 → 收答覆 → 重算 readiness。系統永遠不猜尺寸；顯式尺寸（壁厚/間隙/蓋間隙）必來自答覆。100% readiness 時尊重既有 approval gate（「Generate parametric source only after the user approves」），不自動跨過。
- **DD-3**: enclosure 渲染**重構複用，不重寫**。把 `render_board_model` 的渲染後段（pyrender 場景/視角/光照/EGL offscreen）抽成共用函式，新增 `render_enclosure_model(stl_path)` 用 `trimesh.load(STL)` 餵入。理由：渲染機制已存在且驗證可跑（me worker 有 GL libs），STL→glb 多一層轉換無必要，trimesh 原生讀 STL。degrade 行為（no-deps/no-gl）沿用既有 ModelRenderResult。
- **DD-4**: 編排層串閉環但**每段尊重既有 gate**。口述→抽取→反問（缺則停問使用者）→使用者確認約束（approval gate）→生 source→STL→渲染。不在 readiness 不足或未確認時自動往下生 CAD。

## Risks / Trade-offs

- **keyword 抽取覆蓋度**：deterministic keyword 對「50×30 的盒子」「側面開 USB-C」這類自然語句可能漏抽尺寸數字。緩解——抽取層對數字/單位做 regex 輔助；真正抽不到的轉成反問，不靜默省略（與 DD-2 一致）。
- **反問輪數**：口述越模糊反問越多，體驗下降。緩解——只對「阻擋生 source 的關鍵約束」（board_outline/壁厚/間隙）強制反問，次要約束（heat/RF/battery）可標 missing 但不擋 source 草稿（對齊實跑：38% 仍 can_generate_cad_source）。
- **渲染重構打擊半徑**：抽共用後段可能影響既有 board 渲染。緩解——重構保持 render_board_model 對外行為不變（同樣回 ModelRenderResult），只內部抽函式；加 enclosure 渲染回歸測試 + 確認 board 渲染不回歸。
- **worker 環境依賴**：渲染需 EGL/GL，STL 需 OpenSCAD CLI。兩者實跑已證存在，但 enclosure 渲染是新路徑，需實測一次確認 trimesh STL load 在 worker 可跑。

## Critical Files

- `packages/workflow-core/bodesign_workflow_core/c02_me_package.py` — 新增 C02 口述抽取 + 反問補全；對齊 c03_export_mechanical_constraints schema；沿用 assess_c02_constraint_readiness / answer_state。
- `packages/workflow-core/bodesign_workflow_core/requirement_planning.py` — 參考 plan_design_intent 抽取骨架（keyword-binding/三態/ClarifyingQuestion），評估抽共用 helper。
- `packages/eda-bridge/bodesign_eda_bridge/model_render.py` — 重構 render_board_model 抽共用渲染後段；新增 render_enclosure_model（trimesh.load STL → pyrender）。
- `services/mcp/server.py` — 新增 handlers + tools：c02_plan_intent、c02_next_question/c02_update_answers（或擴充既有）、c02_render_enclosure。
- `tests/test_mcp_server.py`、`tests/test_eda_bridge.py` — 抽取/反問/渲染回歸測試（含 board 渲染不回歸）。
- `specs/architecture.md` — C02 從約束輸入升級為對話式設計 + enclosure 渲染路徑（at living transition）。
