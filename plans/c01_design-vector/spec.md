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

## Acceptance Checks

- [ ] PoC：一個真實描述生出一張及格「完整產品形象圖」（外殼輪廓 + 面板佈局 + CMF 色塊 + 外露元件標示），設計師能直接開 Figma 接手修改
- [ ] 圖層命名規範固定且齊全，元件可獨立選取
- [ ] 缺關鍵 answer_state 時 fail-fast，不捏造
- [ ] 未覆蓋元件以 placeholder + 告知，不靜默省略
- [ ] 與既有 raster 軌輸出互不衝突
- [ ] 輸出通過 SVG schema 驗證
