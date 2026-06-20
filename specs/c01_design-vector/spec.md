# Spec: c01_design-vector

## Purpose

由 C01 answer_state 描述，產出設計師可編輯的扁平／技術風產品設計向量 SVG，與既有擬真 raster 參考並行，作為 C01 工業設計階段的「落地骨架」交付物。

## Requirements

### Requirement: 由描述產出分層可編輯 SVG

#### Scenario: answer_state 完整時生成完整形象圖
- **GIVEN** 一個 C01 package 的 answer_state.json，`form_archetype` / `primary_face` / `exposed_components` / `cmf_direction` 皆已 answered
- **WHEN** 呼叫 `c01_emit_design_vector`
- **THEN** 產出一個分層 SVG，含 `outline`（外殼輪廓）/ `panel`（面板佈局）/ `cmf-fill`（CMF 配色色塊）/ `components/<type>`（外露元件）/ `annotations` 五類圖層
- **AND** 每個外露元件包成獨立命名 `<g id="component-<type>-<n>">` group
- **AND** 回傳 result 列出產出檔路徑 + 圖層清單 + 使用到的圖元 ID + 套用的 CMF 色值

#### Scenario: 圖元庫未覆蓋的元件
- **GIVEN** answer_state 的 `exposed_components` 含一個圖元庫尚未收錄的元件類型
- **WHEN** 呼叫 `c01_emit_design_vector`
- **THEN** 該元件以 generic placeholder symbol 呈現並命名標註
- **AND** result 明確列出哪些元件用了 placeholder（不靜默省略）

### Requirement: answer_state 不足時 fail-fast，不捏造幾何

#### Scenario: 關鍵描述欄位缺失
- **GIVEN** answer_state 缺少 `form_archetype`（產品形態無從判斷）
- **WHEN** 呼叫 `c01_emit_design_vector`
- **THEN** 不產出 SVG，回傳 `missing` / `external-needed` 狀態並列出缺失欄位
- **AND** 不以預設形態或第一個可用值靜默續跑

### Requirement: 與既有 raster 軌並行不衝突

#### Scenario: 同一 package 同時有 raster 與 vector 產出
- **GIVEN** 一個 C01 package 已產出 `Concept_Reference.png`（raster）
- **WHEN** 呼叫 `c01_emit_design_vector`
- **THEN** 向量 SVG 寫到獨立路徑（如 `C01-ID/Ai file/Design_Vector.svg`），不覆寫 raster 產出
- **AND** handoff 文件交代兩者定位（擬真參考 vs 可編輯落地骨架）

### Requirement: 輸出可被 schema 驗證（deterministic 受控例外）

#### Scenario: LLM 組裝結果通過結構驗證
- **GIVEN** S2 策略下 LLM 回傳「圖元 ID + 座標 + CMF 色值」結構化裁決
- **WHEN** 組裝成 SVG 後
- **THEN** 必須通過 schema 驗證（五類圖層命名齊全、每元件 group 存在、SVG 合法）才回報成功
- **AND** 驗證不過時回報失敗與具體缺項，不輸出半成品

### Requirement: 產出 Ai file ID-native bucket（v2, ADDED 2026-06-17）

來源：BR `issue_20260617_c01_rockbox_style_id_deliverables.md` §1。`c01_emit_design_vector` 升級為完整 ID visual/source bucket emitter（內部沿用同一 S2 分層 SVG 引擎）。

#### Scenario: 從結構化輸入產出 Ai file bucket
- **GIVEN** 一個 C01 package 含 `Interface_Constraints.json` + answer_state（`form_archetype`/`primary_face`/`exposed_components`/`cmf_direction` 已 answered），可選 C02/C03 envelope evidence
- **WHEN** 呼叫 `c01_emit_id_visual_package`
- **THEN** 產出 `C01-ID/Ai file/<product>_ID_skeleton.svg`（分層 SVG）+ `C01-ID/Ai file/figma_import_spec.json` + `C01-ID/Ai file/README.md`
- **AND** SVG 與 figma spec 皆由結構化輸入推導（Interface_Constraints + exposed_components + placement preference + risk notes），不裸生
- **AND** 每個視覺產出帶可見 `draft / not final industrial design` 標記
- **AND** 不產出 `.ai`（除非有真實 Illustrator-compatible export path）；result 列出產出檔 + 使用圖元 + placeholder + 套用 CMF

### Requirement: 產出 CMF draft bucket（v2, ADDED 2026-06-17）

來源：BR §2。

#### Scenario: 從 constraints 產出 CMF 套件
- **GIVEN** 一個 C01 package 含 `Interface_Constraints.json` 與 answer_state 的 `cmf_direction`
- **WHEN** 呼叫 `c01_emit_cmf_package`
- **THEN** 產出 `C01-ID/CMF/<product>_CMF_Direction.pdf` + `C01-ID/CMF/cmf_tokens.json` + `C01-ID/CMF/README.md`
- **AND** 內容含 material family / finish / colour routes / RF-transparent zones / gasket-sealing notes / sample-vendor gates
- **AND** 帶可見 `not CMF approval` 標記，不宣稱 CMF sample 核可
- **AND** `cmf_direction` 缺失時 fail-fast（missing/external-needed），不以預設材質靜默續跑

### Requirement: 產出 Display UI/UX draft bucket（v2, ADDED 2026-06-17）

來源：BR §3。

#### Scenario: 從 uiux 需求產出 Display UI_UX 套件
- **GIVEN** 一個 C01 package 含 answer_state 的 `display_uiux`（或 LED/status 互動描述）與 `exposed_components`
- **WHEN** 呼叫 `c01_emit_uiux_package`
- **THEN** 產出 `C01-ID/Display UI_UX/<product>_UIUX_Flow.pdf` + `C01-ID/Display UI_UX/uiux_wireframes.svg` + `C01-ID/Display UI_UX/README.md`
- **AND** 內容涵蓋 OLED screens/states、LED state vocabulary、module insert/remove feedback、privacy/local-only state、charging/connectivity/error states
- **AND** 帶可見 `not UI sign-off` 標記
- **AND** 無 display 產品映射到 LED/status/button 互動，不靜默省略

### Requirement: readiness 雙軌回報（v2, ADDED 2026-06-17）

來源：BR §4。

#### Scenario: readiness 分軌回報 core companion vs ID-native package
- **GIVEN** 一個 C01 package 已產出五件 core companion，且部分或全部 ID-native bucket（Ai file/CMF/Display UI_UX）已生成或保留 draft
- **WHEN** 呼叫 `c01_readiness`
- **THEN** 回傳兩條獨立 readiness track：`companion_readiness`（五件 source-of-truth）與 `id_native_readiness`（三 bucket optional/demo）
- **AND** 產出的視覺**不得**作為 final ID approval 依據，**不得**把 C01 package 從 draft 提升為 approved
- **AND** 既有 `readiness_pct` / `usable` 對 core companion 的語意不被破壞（向後相容）

## Acceptance Checks

- [ ] PoC：一個真實描述生出一張及格「完整產品形象圖」（外殼輪廓 + 面板佈局 + CMF 色塊 + 外露元件標示），設計師能直接開 Figma 接手修改
- [ ] 圖層命名規範固定且齊全，元件可獨立選取
- [ ] 缺關鍵 answer_state 時 fail-fast，不捏造
- [ ] 未覆蓋元件以 placeholder + 告知，不靜默省略
- [ ] 與既有 raster 軌輸出互不衝突
- [ ] 輸出通過 SVG schema 驗證
