# Proposal: feature_component_vault

## Why

- bodesign 以 HTTP/MCP server 形式長駐運作，但目前元件知識（component-kb）是 **無持久化的 placeholder**：`ingest_datasheet_knowledge()` 每次重算、結果不落地；`vault.py` 只是唯讀 gate，讀的是 client 端 `datasheets/` skill 的 per-project cache。
- 任何工作（reverse 重建、forward 設計、RCA、BOM 作業）中收集到的元件資訊在 session 結束後就蒸發，下個專案遇到同一顆料要全部重來。
- Server 端需要一個跨專案、可累積、可驗證的 **Component Vault DB**：把「工作中收集到的元件資訊」結構化沉澱，越用越肥（養 datasheet）。

## Original Requirement Wording (Baseline)

- "bodesign 是以 http server 的型式存在。我現在覺得 server 端必須有 DB 來養 datasheet。也就是任何工作中收集到的元件資訊。你可以盤點一下總共應該要收集的資訊類型並且規劃一個結構化的 repo 嗎？"

## Requirement Revision History

- 2026-06-10: initial draft created via plan-init.ts
- 2026-06-11: 盤點 8 層資訊類型；決策 SQLite+FTS5、schema 一次規劃全部 8 層、實作分期。

## Effective Requirement Description

1. Server 端建立持久化 Component Vault（SQLite + FTS5），作為跨專案元件知識的單一儲存點。
2. 盤點並 schema 化「工作中會收集到的元件資訊」全部類型（下方 8 層），一次規劃完整 schema，實作分期。
3. 所有寫入都必須帶 evidence/provenance；無來源的數值標 `unverified`，不得偽裝成已驗證（沿用既有 RCA gate 哲學）。

## 資訊類型盤點（8 層）

### L1 — Identity（身分與檢索鍵）
| 資訊 | 說明 |
|---|---|
| MPN（canonical） | 正規化主鍵；`component_knowledge_key()` 既有正規化邏輯升級為 DB key |
| Aliases / orderable PN | 同一晶粒的料號變體（封裝/溫度/捲帶後綴） |
| Manufacturer | 製造商正規名 + 別名 |
| Category taxonomy | MCU / LDO / flash / connector / passive…階層分類 |
| Distributor PN | LCSC Cxxxxx、DigiKey、Mouser、element14 對應料號 |
| Lifecycle status | active / NRND / EOL / obsolete + 查證日期 |

### L2 — Documents（原始文件庫）
| 資訊 | 說明 |
|---|---|
| Datasheet PDF | 檔案 blob/路徑 + sha256 去重 + 版本（rev/日期） |
| App notes / reference designs / errata | 同上，type 標記 |
| Source provenance | 來源（user-provided / distributor API / docxmcp chunk）、取得時間、policy gate 記錄 |
| Document↔MPN 多對多 | 一份 datasheet 涵蓋整個料號家族 |

### L3 — Source Chunks（抽取中間層）
| 資訊 | 說明 |
|---|---|
| docxmcp-style chunk | per-page/per-table/per-section 文字與表格資產 |
| EvidenceRef anchor | chunk → 原 PDF 頁碼/座標的 provenance 錨點 |
| 抽取器版本 | extractor + 版本號，供 re-extract 失效判斷 |
| FTS5 全文索引 | chunk 內容全文檢索（找 "dropout voltage" 在哪頁） |

### L4 — Normalized Specs（結構化規格）
| 資訊 | 說明 |
|---|---|
| Pinout | pin number/name/role/electrical_type（既有 `ComponentPin` 升級） |
| Package | 封裝名、尺寸、pitch、exposed pad、land pattern 參數 |
| Electrical | abs max、recommended operating（vin/vout/iout/dropout/vref…既有 `FIELD_ALIASES` schema 落 DB） |
| Power topology | 電源 pin 群、rail 需求、上電順序、PG/EN 行為 |
| Interfaces | pin group → 介面（SPI/I2C/USB/SWD…）+ 速度等級 |
| Thermal | θJA/θJC、功耗限制 |
| 每個欄位帶 | value + unit + condition + EvidenceRef（指向 L3 chunk）+ confidence |

### L5 — EDA Assets（設計資產）
| 資訊 | 說明 |
|---|---|
| Symbol 對應 | KiCad lib symbol 名 + pin 映射驗證狀態（`kicad_emit.py` 消費端） |
| Footprint 對應 | KiCad footprint 名 + IPC 命名 + 驗證狀態（`footprint_map.py` 消費端） |
| 3D model | STEP/WRL 參照 |
| 驗證紀錄 | 哪個專案/哪次 DRC 驗證過此 mapping |

### L6 — Application Knowledge（應用與佈局知識）
| 資訊 | 說明 |
|---|---|
| Layout guidelines | decoupling 規則、placement 距離、星接/平面要求（既有 `layout_guidelines` 結構化） |
| Reference circuits | datasheet 典型應用電路 → 子系統 IR 片段（forward-design 餵料） |
| Companion parts | 必配料（crystal 負載電容、LDO 輸出電容 ESR 範圍…） |
| Design rules | 高速線 impedance、長度匹配等該料專屬約束 |

### L7 — Trust & Gaps（信任與缺口）
| 資訊 | 說明 |
|---|---|
| Per-field confidence | verified / unverified / absent（沿用 `spec_check()` 四態） |
| Knowledge gaps | 顯式缺口清單（既有 `knowledge_gaps` 落 DB） |
| Extraction score | 抽取完整度 |
| Audit log | 誰/何時/憑什麼 evidence 寫入或修改某欄位 |

### L8 — Usage & Sourcing（使用足跡與供應）
| 資訊 | 說明 |
|---|---|
| Project usage | 哪些專案用過、refdes、occurrence count（既有 queue 邏輯落 DB） |
| Priority signal | 高頻使用料優先補齊知識 |
| Sourcing snapshot | 價格/庫存/MOQ 時間戳快照（非即時，僅留證據） |
| Substitution | 替代料關係 + 相容性差異備註 |

## Scope

### IN
- SQLite + FTS5 schema 設計：上述 8 層全部 schema 化（`data-schema.json`）
- Vault 儲存位置與 docker volume 佈局（server-owned，獨立於 client 專案資料夾）
- 寫入 API 面（MCP tools + HTTP）：ingest / upsert / query / audit 的合約定義
- 與既有模組的接縫：`component-kb` contracts 升級、`vault.py` 改為可同時讀 server vault、`datasheets` skill cache 的匯入路徑
- Evidence/provenance 強制：每筆規格值帶 EvidenceRef 與 confidence
- 實作分期計畫（phase 切分進 tasks.md）

### OUT
- 外部自動下載 datasheet（`/knowledge/external-fetch` policy gate 維持 approval-required，不在本案解鎖）
- client 專案資料夾的 storage-share 設計（另案，見 architecture.md）
- 向量檢索/embedding（先 FTS5，embedding 後續再評估）
- 即時供應商 API 整合（只存快照，不做 live query）

## Non-Goals

- 不取代 client 端 `datasheets/` skill 的 per-project cache —— vault 是 server 端跨專案累積層，兩者並存且可互相匯入
- 不做成 authoritative EDA library manager（KiCad 官方庫仍是 symbol/footprint 來源；vault 只存映射與驗證狀態）

## Constraints

- DB 引擎：SQLite + FTS5（單檔、零依賴、隨 docker volume 可攜；未來需要再 migrate 到 Postgres）
- 既有政策：外部下載預設關閉；無來源數值必須顯式標 unverified；fail-fast 不做 silent fallback
- `packages/component-kb` 是 schema 的自然落點；server 寫入面在 `services/api`/`services/mcp`

## What Changes

- 新增 server 端持久化 vault：`packages/component-kb` 增加 storage 層（SQLite schema、migration、repository API）
- `ComponentKnowledge`/`ComponentPin`/`DatasheetIngestionResult` contracts 升級為 DB-backed
- MCP tools / HTTP API 新增 vault ingest/query 端點
- `vault.py`（RCA gate）增加 server vault 作為查證來源

## Capabilities

### New Capabilities
- **Component Vault DB**: 跨專案元件知識持久化，8 層資訊結構化儲存
- **Evidence-grounded spec query**: 任何規格值可回溯到 datasheet chunk 證據
- **Knowledge accumulation**: 工作流（ingest/reverse/forward/RCA）自動回寫元件知識

### Modified Capabilities
- **component-kb ingest**: 從 placeholder 每次重算 → 落 DB、去重、版本化
- **RCA spec gate (`vault.py`)**: 從只讀 client cache → 同時查 server vault
- **knowledge queue**: 從 in-memory 計算 → DB-backed、跨專案優先級

## Impact

- `packages/component-kb`（主要實作面）
- `services/api`、`services/mcp`（API/tool 端點）
- `packages/shared`（EvidenceRef 可能需擴充 confidence 欄位）
- docker volume 佈局（vault.db 持久化掛載）
- `specs/architecture.md`（Knowledge base 段落需同步）
