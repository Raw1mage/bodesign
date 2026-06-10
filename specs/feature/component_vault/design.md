# Design: feature_component_vault

## Context

bodesign 以 host-agnostic MCP/HTTP server 長駐運作。元件知識目前散落三處且都不持久：
`packages/component-kb/contracts.py` 的 placeholder ingest（每次重算）、`vault.py` 的 RCA gate（唯讀 client cache）、`workflow-core` 的 in-memory knowledge queue。本案在 server 端建立持久化 Component Vault（SQLite + FTS5），把工作流中收集到的元件資訊沉澱為跨專案資產。

## Goals / Non-Goals

### Goals

- 單一 server 端持久層承載 8 層元件資訊（L1 identity → L8 usage/sourcing）
- 每筆規格值可回溯 evidence（chunk 錨點或顯式 source note）並帶 confidence
- 既有消費端（`vault.py` spec_check、`kicad_emit.py`、`footprint_map.py`、knowledge queue）改吃 DB
- client 端 `datasheets/` skill cache 可單向匯入 vault

### Non-Goals

- 不取代 client per-project cache（兩層並存）
- 不解鎖外部自動下載 datasheet（policy gate 維持）
- 不做 embedding/向量檢索（FTS5 先行）
- 不做 live distributor query（只存快照）

## Decisions

- **DD-1** DB 引擎 = SQLite + FTS5，單檔 `vault.db` + blob 目錄，掛 docker volume（2026-06-11，user-approved）。Postgres 留待未來 migration；理由：零依賴、可攜、併發寫入需求低。
- **DD-2** L4 規格採 **EAV 長表**（`spec_values`：component × field_path × condition），field_path 沿用既有 `FIELD_ALIASES` dotted 命名空間（2026-06-11，user-approved）。理由：任意類別元件免 migration；型別安全由 API 層 + field_path registry 把關。
- **DD-3** Schema 一次規劃全 8 層，實作分期（2026-06-11，user-approved）。phase 切分見 tasks.md。
- **DD-4** Evidence 強制由 DB trigger 落實：`confidence='verified'` 必須帶 `evidence_chunk_id` 或 `source_note`，否則 ABORT。沿用既有 RCA gate 哲學（unverified ≠ verified），fail-fast 無 silent fallback。
- **DD-5** `audit_log` append-only 由 trigger 強制（BEFORE UPDATE/DELETE → RAISE ABORT），不靠應用層自律。
- **DD-6** 文件 blob 不進 DB：`blobs/<sha256[0:2]>/<sha256>.<ext>` 目錄存放，DB 只存 sha256 與相對路徑。去重以 sha256 為鍵。
- **DD-7** chunk 失效採 stale 標記不刪除：抽取器升級後舊 chunks 標 `stale=1`，保留 provenance 鏈。
- **DD-8** vault 是 server-owned 資產，與 client storage-share 邊界分離：client cache 匯入走顯式 import API，evidence 標 `client-cache-import` 來源；衝突保留兩者並標示，不靜默覆蓋。
- **DD-9** knowledge queue 與 completeness 以 SQL VIEW 實作（`knowledge_queue`、`component_completeness`），取代 in-memory 計算，邏輯沿用既有 `build_component_knowledge_queue` priority 規則。

## Risks / Trade-offs

| 風險 | 影響 | 緩解 |
|---|---|---|
| EAV 查詢人因錯誤（field_path 打錯字查無資料） | 靜默 absent 誤判 | field_path registry 白名單；API 層對未知 path 回 explicit error 而非空結果 |
| SQLite 併發寫入瓶頸 | 多 worker 同時 ingest 卡 lock | WAL mode；寫入集中走單一 repository API；目前併發需求低 |
| blob 目錄與 DB 失同步（檔在記錄無、記錄在檔無） | 證據鏈斷裂 | ingest 交易順序：先寫 blob 再 commit DB；startup 一致性掃描報 gap |
| client cache 匯入品質不齊（舊 schema、無 source） | 垃圾進垃圾出 | 匯入一律標 unverified 除非 extraction 帶真實 source；gap 顯式記錄 |
| schema 一次規劃過度設計，後期欄位不合用 | migration 成本 | `user_version` pragma + migration 腳本框架自 phase 1 就建立 |
| DB 損毀 | 知識全失 | fail-fast 不重建空庫；docker volume 備份策略寫進 observability.md |

## Critical Files

| 檔案 | 角色 |
|---|---|
| `packages/component-kb/bodesign_component_kb/storage.py` | 新增：SQLite schema DDL、migration、connection 管理 |
| `packages/component-kb/bodesign_component_kb/repository.py` | 新增：vault repository API（upsert/query/import/audit） |
| `packages/component-kb/bodesign_component_kb/contracts.py` | 升級：dataclass 對齊 DB schema，新增 confidence/evidence 欄位 |
| `packages/component-kb/bodesign_component_kb/vault.py` | 升級：spec_check 增加 server vault 查證來源 |
| `services/api/` | 新增 vault HTTP 端點（ingest/query/import/queue） |
| `services/mcp/` | 新增 vault MCP tools |
| `packages/shared/` | EvidenceRef 擴充（confidence、chunk 錨點） |
| `docker-compose.yml` | vault volume 掛載 |
| `plans/feature_component_vault/data-schema.json` | schema 單一真相來源 |

## Traceability

- IDEF0 A1–A5（idef0.json）對應 ingest 管線五段：身分解析→文件入庫→chunk 抽取→規格正規化→知識服務
- GRAFCET（grafcet.json）對應單件文件 ingest 生命週期狀態機
- C4（c4.json）對應 component-kb storage/repository 與 services API 的容器邊界
- spec.md R1–R10 ↔ data-schema.json tables ↔ tasks.md phases
