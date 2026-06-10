# Spec: feature_component_vault

## Purpose

Server 端持久化 Component Vault（SQLite + FTS5）：把 bodesign 各工作流（ingest / reverse / forward / RCA / BOM）中收集到的元件資訊結構化沉澱，跨專案累積、可全文檢索、每筆規格值可回溯證據。

## Requirements

### Requirement: R1 — Vault 持久化與身分解析（L1）

#### Scenario: 以 MPN upsert 元件身分
- **GIVEN** 一個 MPN 字串（任意大小寫/分隔符變體）
- **WHEN** 呼叫 vault upsert
- **THEN** 以 canonical key（沿用 `component_knowledge_key()` 正規化）作為唯一鍵寫入 `components` 表，重複 upsert 不產生重複列

#### Scenario: alias 解析到同一元件
- **GIVEN** 元件已登錄且帶有 alias（料號家族變體 / distributor PN）
- **WHEN** 以 alias 查詢
- **THEN** 回傳 canonical 元件記錄，並標示命中的 alias 類型（family-variant / distributor / manufacturer-alias）

#### Scenario: 未知元件查詢
- **GIVEN** vault 中不存在的 MPN
- **WHEN** 查詢
- **THEN** 回傳明確 `absent`（不得回傳空殼記錄或猜測值）

### Requirement: R2 — 文件庫去重與版本（L2）

#### Scenario: 重複文件入庫
- **GIVEN** 已入庫的 datasheet PDF（sha256 已存在）
- **WHEN** 再次 ingest 同一檔案
- **THEN** 不重複儲存 blob，回傳既有 document id，並把新的 document↔MPN 關聯補上（若不同 MPN）

#### Scenario: 文件版本鏈
- **GIVEN** 同一 MPN 的兩份不同 rev 的 datasheet
- **WHEN** 兩份都入庫
- **THEN** 兩份各自保留，以 rev/日期排序成版本鏈，查詢預設回傳最新 rev 並可列出歷史

#### Scenario: 來源 policy 記錄
- **GIVEN** 任一文件入庫
- **WHEN** 寫入 `documents`
- **THEN** 必填 provenance（user-provided / distributor-api / docxmcp-chunk）與取得時間；外部自動下載仍被 policy gate 擋下（不在本案解鎖）

### Requirement: R3 — Source Chunks 與全文檢索（L3）

#### Scenario: chunk 入庫
- **GIVEN** 一份已入庫文件經 docxmcp-style 分解
- **WHEN** chunk 寫入
- **THEN** 每個 chunk 帶 document id、頁碼/座標錨點、抽取器版本，內容進 FTS5 索引

#### Scenario: 全文檢索
- **GIVEN** vault 中有多個元件的 chunks
- **WHEN** 以關鍵字（如 "dropout voltage"）搜尋
- **THEN** 回傳依 BM25 排序的 chunk 命中，含 MPN、document、頁碼錨點

#### Scenario: 抽取器升級失效
- **GIVEN** chunk 帶舊版抽取器版本
- **WHEN** 以新版抽取器重新分解同一文件
- **THEN** 舊 chunks 標記 stale（不刪除），新 chunks 成為現行版本

### Requirement: R4 — 結構化規格 EAV 儲存（L4）

#### Scenario: 規格值寫入
- **GIVEN** 一筆規格值（field_path、value、unit、condition）
- **WHEN** 寫入 `spec_values`
- **THEN** 必須帶 EvidenceRef（指向 L3 chunk 或顯式 source note）與 confidence；無 evidence 的寫入自動標 `unverified`，不得標 `verified`

#### Scenario: field_path 約定
- **GIVEN** 既有 `FIELD_ALIASES` dotted path 約定（如 `recommended_operating_conditions.vin_min_v`）
- **WHEN** 任何讀寫
- **THEN** field_path 沿用同一 dotted 命名空間；alias 解析在 API 層完成，DB 只存 canonical path

#### Scenario: 同 field 多值（條件不同）
- **GIVEN** 同一元件同一 field 在不同 condition 下有不同值（如不同溫度的 dropout）
- **WHEN** 寫入第二筆
- **THEN** 兩筆並存（以 condition 區分），查詢可指定 condition 或回傳全部

#### Scenario: pinout 寫入
- **GIVEN** 一組 pin 定義（number/name/role/electrical_type）
- **WHEN** 寫入 `pins`
- **THEN** 以 (component, pin_number, package) 唯一；同元件不同封裝的 pinout 並存

### Requirement: R5 — EDA 資產映射（L5）

#### Scenario: symbol/footprint 映射登錄
- **GIVEN** 一個 MPN 與 KiCad symbol/footprint 名稱
- **WHEN** 寫入 `eda_assets`
- **THEN** 記錄映射 + 驗證狀態（unverified / pin-checked / drc-passed）+ 驗證出處（哪個專案哪次驗證）

#### Scenario: 消費端查詢
- **GIVEN** `kicad_emit.py` / `footprint_map.py` 需要 symbol/footprint
- **WHEN** 查詢 vault
- **THEN** 回傳映射與驗證狀態；無映射回 `absent`，不得猜測

### Requirement: R6 — 應用知識（L6）

#### Scenario: layout guideline 寫入
- **GIVEN** 從 datasheet/app note 抽出的佈局規則
- **WHEN** 寫入 `app_knowledge`
- **THEN** 帶 type（layout-rule / reference-circuit / companion-part / design-rule）、結構化 payload（JSON）、EvidenceRef、confidence

#### Scenario: companion parts 查詢
- **GIVEN** 元件已有 companion-part 知識（如 crystal 的負載電容）
- **WHEN** forward-design 流程查詢
- **THEN** 回傳必配料關係與條件，含證據錨點

### Requirement: R7 — Trust、Gaps 與 Audit（L7）

#### Scenario: spec_check 四態
- **GIVEN** 任一 (MPN, field) 查詢
- **WHEN** 呼叫 spec_check
- **THEN** 回傳 `verified` / `unverified` / `no-field` / `absent` 四態之一（沿用既有 `vault.py` 語意），server vault 與 client cache 都列為查證來源並標示出處

#### Scenario: audit log
- **GIVEN** 任何 vault 寫入或修改
- **WHEN** 交易提交
- **THEN** `audit_log` 追加一筆：誰（agent/user/pipeline）、何時、哪個欄位、舊值→新值、憑什麼 evidence；audit log append-only

#### Scenario: knowledge gaps 顯式化
- **GIVEN** 元件知識不完整（缺 pinout / package / 電氣參數）
- **WHEN** 查詢元件完整度
- **THEN** 回傳顯式 gap 清單與 extraction score，不得以空值偽裝完整

### Requirement: R8 — 使用足跡與供應快照（L8）

#### Scenario: 專案使用記錄
- **GIVEN** 某專案工作流使用了某元件（refdes 出現）
- **WHEN** 工作流回寫
- **THEN** `usage` 表記錄 project id、refdes、occurrence count、時間；跨專案 occurrence 聚合可查

#### Scenario: 知識補齊優先級
- **GIVEN** 多個元件有 knowledge gaps
- **WHEN** 查詢 knowledge queue
- **THEN** 依（使用頻率 × gap 嚴重度 × 既有 priority 規則）排序回傳（既有 `build_component_knowledge_queue` 邏輯落 DB）

#### Scenario: sourcing 快照
- **GIVEN** distributor 查價結果
- **WHEN** 寫入 `sourcing_snapshots`
- **THEN** 以時間戳快照保存（價格/庫存/MOQ/distributor PN），明示非即時；不做 live query

### Requirement: R9 — API 面（MCP tools + HTTP）

#### Scenario: ingest 端點
- **GIVEN** MCP client 或 HTTP caller 提交元件文件/規格
- **WHEN** 呼叫 vault ingest API
- **THEN** 走 L1→L4 管線（身分解析→文件去重→chunk→規格抽取），回傳寫入摘要與 gap 清單

#### Scenario: query 端點
- **GIVEN** 任一查詢（by MPN / by field / 全文 / queue）
- **WHEN** 呼叫 vault query API
- **THEN** 回傳結果一律附 confidence 與 evidence 出處；查無資料回顯式 absent

#### Scenario: client cache 匯入
- **GIVEN** client 專案有 `datasheets/extracted/` cache（datasheets skill 產物）
- **WHEN** 呼叫 import API
- **THEN** 將 cache extraction 轉換為 vault 記錄（evidence 標 client-cache 來源），衝突時保留兩者並標示，不靜默覆蓋

### Requirement: R10 — 儲存與部署

#### Scenario: docker volume 持久化
- **GIVEN** container 重啟
- **WHEN** vault 重新開啟
- **THEN** `vault.db` 與文件 blob 存於掛載 volume，資料完整保留；DB 損毀時 fail-fast 報錯，不得靜默重建空庫

## Acceptance Checks

- [ ] 全部 R1–R10 scenario 有對應 fixture-driven 測試
- [ ] EAV 寫入無 evidence 時自動 `unverified` 的行為有測試覆蓋
- [ ] FTS5 全文檢索回傳 BM25 排序且含頁碼錨點
- [ ] audit_log append-only 由 schema 強制（無 UPDATE/DELETE 路徑）
- [ ] 既有 `vault.py` spec_check 對 server vault 的查證有整合測試
- [ ] docker volume 重啟資料保留驗證
