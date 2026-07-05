# Design: capability_refs-first-emitters

## Context

BR_20260704（emitter modular-platform BR）以 aiguard 消費端證據確立：C01/C02 emitter 產出的約束 JSON（`Interface_Constraints.json` / `Mechanical_Constraints.json`）可在無任何 refs 回溯下生成並通過 readiness——`c01_readiness` 只驗檔案存在 + `exposed_components` 是 list（`c01_id_package.py:449/954`），`c02_readiness` 只驗 key 存在（`c02_me_package.py:630-644`）。勘查結論：repo 內**沒有**硬編碼的 "modular platform" 字面模板；汙染向量是三個結構缺口：(1) emit 入口無 refs gate（`refs_gate.require_refs()` 基建已存在但 C01/C02 emitter 未接）；(2) 約束項目無 provenance 欄位，agent 注入的臆造 answers 與 refs-derived 內容不可區分；(3) `_component_list` 的 keyword-corpus 推導（`c01_id_package.py:781`）會在無人確認下合成元件清單（silent-default 向量）。修這三個缺口即為本案。

## IDEF0 skeleton mapping

架構掛在 idef0.json 五活動骨架上：A1（refs gate：emit 入口呼叫 `require_refs`，缺 SSOT fail fast）→ A2（provenance 標記模型建構：C01 components / C02 constraints 每項掛 `provenance {kind, source, detail}`）→ A3（約束 JSON v2 產出：per-item provenance 落盤）→ A4（readiness provenance gate：不可回溯項 → `dod_ok:false` + gap 清單）→ A5（驗收：BR §5 三條 + 全 suite 回歸）。grafcet step 0-5 對應同鏈 runtime 行為。

## Goals / Non-Goals

**Goals**

- C01/C02 emit verbs 入口接 `refs_gate.require_refs()`：無 `01_refs/` SSOT → `RefsGateError`（REFS_SSOT_MISSING），不產出任何檔案。
- 約束項目 per-item provenance：`{kind: refs|answer|derived, source, detail}`；readiness 對 `kind ∈ {refs, answer}` 才放行 dod。
- keyword-corpus 推導降級為 `kind: derived`（可見、可審，但擋 dod）——不刪推導（它是有用的 draft 起點），但它永遠不能無聲通過 gate。
- emitter 自身不合成 variant slug/命名（檔名只用清洗後 product_name）。

**Non-Goals**

- 不做 SSOT 內容正確性裁決（owner adjudication 職責）。
- 不改 C01/C02 markdown 文件產出結構；只動約束 JSON 與 readiness。
- C00/C03+ 各層同型改造另案（本案建立可複製模式）。
- `place_components` 生成 verb 另案。

## Decisions

- DD-1: **Gate 接在 emitter 函式入口，不是 server handler** — `emit_c01_rockbox_package` / `emit_c02_enclosure_package` 第一動作呼叫 `require_refs(out_dir, "C01"/"C02")`；`RefsGateError` 原樣上拋。這樣 host-landed gate.py verb 與任何直接呼叫者都被同一 gate 保護（chokepoint 唯一）。
- DD-2: **Provenance taxonomy（BINDING）** — 每個 `exposed_components[]` / c02 約束項掛 `provenance` dict：`kind="refs"`（source = `01_refs/` 下相對路徑，detail = 錨點）、`kind="answer"`（source = `answer_state.json`，detail = field key；使用者親答視同 owner 輸入）、`kind="derived"`（source = 推導來源標籤如 `c00_corpus` / `caller_unattributed`，detail = 命中 keyword 或原因）。缺 provenance 的傳入項 → emit 時標 `kind="derived", source="caller_unattributed"`（可見不可過 dod），不拋錯（emit 是 draft 生產；gate 在 readiness）。
- DD-3: **dod 掛點沿用既有 `dod_ok` 鏈** — C01 在 `assess_c01_package_readiness` 加 provenance 檢查：任一項 `kind ∉ {refs, answer}` 或 `kind=refs` 但 source 無法解析到 `01_refs/` → `dod_ok:false` + `provenance_gaps[]`（列項名 + 原因 + 修復指引）。C02 在 `assess_c02_constraint_readiness` 增列 blocker item（同語義）。`readiness_pct` 不變義——`dod_ok` 才是 gate（沿用 c00 慣例）。
- DD-4: **Schema 顯式升版** — `Interface_Constraints.json` schema 升 `bodesign.c01.interface_constraints.v2`（v1 欄位全保留 + per-item provenance + 頂層 `refs_manifest` 摘要）；c02 `constraint_status` 增 `provenance_gaps`。讀取端（`_valid_constraints`、c04 消費者）容 v1（讀舊檔不炸）但 readiness 對 v1 檔報 provenance gap（舊產物不自動漂白）。
- DD-5: **corpus 推導保留但永不無聲** — `_component_list` 的 keyword 推導產物一律 `kind="derived"`；`decision_status` 維持 `drafted`。刪推導會毀掉合法 draft 工作流；讓 gate 擋它即可（fail-visible 而非 fail-silent）。
- DD-6: **Variant 命名清除** — emitter 產物檔名/`product_name` 不得由 emitter 拼接 archetype/variant 字串；slug 生成只用 product_name 清洗結果。呼叫端傳入的 product_name 原樣保留（內容權威在 owner，emitter 不改寫使用者輸入——只保證自己不添料）。
- DD-7: **測試策略** — 既有 c01/c02 測試補 `01_refs/` fixture（一個 markdown source 即過 gate）；新增 BR §5 三條：(a) 乾淨 SSOT 重跑無臆造項且全帶 provenance；(b) 無回溯元件集 → `dod_ok:false`；(c) 舊行為回歸（有 refs fixture 下產物欄位向後相容）。

## Risks / Trade-offs

- 破壞性：所有無 `01_refs/` 的既有呼叫將 fail fast——這是天條要求的顯式行為，測試全數補 fixture；aiguard 已有乾淨 SSOT 可直接用。
- provenance 解析成本：readiness 需檔案系統查證 `kind=refs` 的 source 存在性——限相對路徑解析，無內容驗證，成本可忽略。
- v1 舊檔在新 readiness 下永遠 dod_ok:false —— 預期行為（舊產物需重 emit 或人工補 provenance），在 gap 訊息中明示修復路徑。

## Critical Files

- `packages/workflow-core/bodesign_workflow_core/provenance.py` — 新增：provenance taxonomy + 驗證 helper（c01/c02 共用）。
- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py` — emit gate、`_component_list` provenance、`_constraints` v2、readiness provenance gap。
- `packages/workflow-core/bodesign_workflow_core/c02_me_package.py` — emit gate、`_normalized_constraints` provenance、readiness blocker。
- `packages/workflow-core/bodesign_workflow_core/refs_gate.py` — 既有 chokepoint（不改，接上）。
- `tests/test_refs_first_emitters.py` / `tests/test_c01_id_package.py` / `tests/test_c02_me_package.py`。

## Code Anchors

- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py:256` — `emit_c01_rockbox_package`（gate 接入點）
- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py:777` — `_component_list`（corpus 推導）
- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py:891` — `_constraints`（schema v2）
- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py:429` — `assess_c01_package_readiness`
- `packages/workflow-core/bodesign_workflow_core/c02_me_package.py:216` — `emit_c02_enclosure_package`
- `packages/workflow-core/bodesign_workflow_core/c02_me_package.py:607` — `assess_c02_constraint_readiness`
- `packages/workflow-core/bodesign_workflow_core/refs_gate.py:257` — `require_refs`
