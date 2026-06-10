# Tasks: feature_component_vault

> Phase 切分原則：MVP-first。Phase 1–3 先閉環「收料→抽取→可查證」（L1–L4+L7），
> Phase 4 接上 API 面與既有消費端，Phase 5–6 補 L5/L6/L8 與匯入路徑。
> 每個 task 完成後立即勾選並跑 plan-sync（§16.3 ritual）。

## 1. Storage 基礎（L1+L2+L7 核心）

- [x] 1.1 建立 `packages/component-kb/bodesign_component_kb/storage.py`：SQLite connection 管理（WAL、foreign_keys、user_version）、schema DDL 來自 data-schema.json（components/manufacturers/component_aliases/documents/component_documents/audit_log + triggers）、migration 框架（user_version bump）
- [x] 1.2 建立 blob store helper：`blobs/<sha256[0:2]>/<sha256>.<ext>` 寫入（先 blob 後 DB commit 順序）、sha256 計算與去重查詢、startup 一致性掃描（檔↔記錄缺口報告，fail-fast 不靜默）
- [x] 1.3 建立 `repository.py` 第一批 API：`upsert_component(mpn, …)`（canonical_key 正規化沿用 `component_knowledge_key()`）、`add_alias`、`resolve(alias_or_mpn)`（回 canonical 記錄 + 命中 alias 類型；未知回顯式 absent）、`ingest_document(path, doc_type, provenance, mpns[])`（sha256 dedup、版本鏈、多對多關聯）
- [x] 1.4 audit_log 寫入路徑：所有 repository 寫入走同一交易 helper，append audit row；驗證 append-only triggers（UPDATE/DELETE 應 ABORT）
- [x] 1.5 fixture 測試：R1（identity upsert/alias/absent）、R2（dedup/版本鏈/provenance 必填）、R7 audit append-only；docker volume 重啟資料保留測試（R10）

## 2. Chunks 與全文檢索（L3）

- [x] 2.1 chunks 表 + chunks_fts（FTS5 external-content）DDL 與 sync triggers（insert/update/delete 同步 FTS）
- [x] 2.2 chunk 寫入 API：`ingest_chunks(document_id, chunks[])`（chunk_kind/page/anchor/extractor 必填）；接 doc-core `DocumentSourceChunk` adapter 輸出
- [x] 2.3 stale 標記流程：同 document 以新 extractor 重新分解時，舊 chunks 標 stale=1 不刪除
- [x] 2.4 全文檢索 API：`search_chunks(query)` BM25 排序，回 MPN/document/頁碼錨點（R3）
- [x] 2.5 fixture 測試：R3 三個 scenario（入庫/檢索/抽取器升級失效）

## 3. 規格 EAV 與信任閘（L4+L7）

- [x] 3.1 spec_values/packages/pins 表 DDL + verified-needs-evidence trigger（DD-4）
- [x] 3.2 field_path registry：canonical dotted namespace 白名單（沿用 `FIELD_ALIASES`），API 層 alias 解析；未知 path 回顯式 error 不回空結果
- [x] 3.3 規格寫入 API：`write_spec(component, field_path, value/min/typ/max, unit, condition, evidence)`；無 evidence 自動 unverified；同 field 多 condition 並存（R4）
- [x] 3.4 pinout/package 寫入 API：(component, pin_number, package) 唯一、多封裝並存
- [x] 3.5 knowledge_gaps 表 + `component_completeness` view + `knowledge_queue` view（DD-9，邏輯沿用 `build_component_knowledge_queue` priority 規則）
- [x] 3.6 升級 `vault.py` spec_check：server vault 加入查證來源，回傳標示 origin（server-vault | client-cache），維持四態語意；client cache 路徑不變（R7）
- [x] 3.7 fixture 測試：R4 四個 scenario + R7 三個 scenario（含 trigger ABORT 行為）

## 4. API 面（MCP tools + HTTP）

- [x] 4.1 vault HTTP 端點：POST /vault/ingest、GET /vault/components/{key}、GET /vault/search、GET /vault/queue、GET /vault/spec-check（註：services/api 已於 b4868d3 退役，HTTP 面落在 services/mcp 的 Starlette app，與原意一致）
- [x] 4.2 `services/mcp` vault tools：vault_ingest / vault_query / vault_spec_check / vault_queue（合約對齊 HTTP 端點）
- [x] 4.3 docker volume 佈局：docker-compose 掛載 vault volume、`BODESIGN_VAULT_DIR` env、DB 損毀 fail-fast 行為（R10）
- [x] 4.4 整合測試：R9 ingest/query 端點 happy path + absent/error path

## 5. 匯入與工作流回寫（L8 + client cache）

- [x] 5.1 client cache import API：讀 `datasheets/extracted/manifest.json` extraction、轉 vault 記錄（provenance=client-cache-import、無真實 source 一律 unverified）、衝突保留兩者並標示（R9 import scenario）
- [x] 5.2 usage 回寫 API：`record_usage(component, project_id, refdes[], workflow)`；跨專案 occurrence 聚合查詢（R8）
- [x] 5.3 sourcing_snapshots + substitutions 寫入/查詢 API（時間戳快照，明示非即時）
- [x] 5.4 fixture 測試：R8 三個 scenario + import 衝突測試

## 6. EDA 資產與應用知識（L5+L6）

- [x] 6.1 eda_assets 表 API：symbol/footprint 映射登錄 + 驗證狀態升級（unverified→pin-checked→drc-passed）+ 驗證出處記錄（R5）
- [x] 6.2 `kicad_emit.py` / `footprint_map.py` 消費端接 vault 查詢（無映射回 absent 不猜測）
- [x] 6.3 app_knowledge 表 API：layout-rule / reference-circuit / companion-part / design-rule 四型 payload + evidence（R6）
- [x] 6.4 fixture 測試：R5/R6 全 scenario
- [x] 6.5 收尾：`specs/architecture.md` Knowledge base 段落同步 + CHANGELOG + 收尾 event record
