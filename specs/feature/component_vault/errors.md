# Errors: feature_component_vault

> 錯誤碼命名：`VAULT-E<layer><nn>`。層碼：0=storage、1=identity、2=documents、3=chunks、4=specs、5=eda、6=app-knowledge、7=trust/audit、8=usage/sourcing、9=API。
> 全域原則（handoff.md 紅線）：fail-fast、顯式報錯、不靜默 fallback、不重建空庫。

## Error Catalogue

## Storage（0x）

| Code | Message（user-visible） | Recovery | Responsible layer |
|---|---|---|---|
| VAULT-E001 | Vault database is corrupted or unreadable: `<path>` | 不自動重建。停止服務，回報 DB 路徑與 sqlite 錯誤；操作者自 volume 備份還原 | storage.py |
| VAULT-E002 | Vault directory is not writable: `<path>` | 檢查 docker volume 掛載與權限；env `BODESIGN_VAULT_DIR` | storage.py |
| VAULT-E003 | Schema version mismatch: db=`<n>` expected=`<m>` | 執行 migration 腳本；不得直接覆寫 schema | storage.py |
| VAULT-E004 | Blob/DB consistency gap: `<n>` records without blobs, `<m>` blobs without records | startup 掃描報告；列出缺口清單，人工或 import 工具修復；服務照常但缺口元件查詢回 absent + gap 註記 | storage.py |

## Identity（1x）

| Code | Message | Recovery | Layer |
|---|---|---|---|
| VAULT-E101 | Empty or invalid MPN | 呼叫端修正輸入；不接受空字串/純符號 | repository.py |
| VAULT-E102 | Alias conflict: `<alias>` already maps to `<other_canonical_key>` | 回報衝突雙方；需顯式 `force_remap` 或人工裁決，不自動改綁 | repository.py |

## Documents（2x）

| Code | Message | Recovery | Layer |
|---|---|---|---|
| VAULT-E201 | Document provenance is required (user-provided / distributor-api / docxmcp-chunk / client-cache-import) | 呼叫端補 provenance 後重試 | repository.py |
| VAULT-E202 | External datasheet fetch is policy-gated and not approved | 維持既有 `/knowledge/external-fetch` approval-required 行為；提供 user-provided 路徑 | services/api |
| VAULT-E203 | Blob write failed before DB commit: `<os_error>` | 交易未提交，無半套狀態；修復磁碟/權限後重試 | storage.py |
| VAULT-E204 | Unsupported document type: `<ext>` | 支援清單回報（pdf/txt/md/csv…）；呼叫端轉檔或標 doc_type=other | repository.py |

## Chunks（3x）

| Code | Message | Recovery | Layer |
|---|---|---|---|
| VAULT-E301 | Chunk references unknown document id `<id>` | 先 ingest document；FK 違反即 ABORT | repository.py |
| VAULT-E302 | Chunk missing required field: `<field>`（chunk_kind/extractor/content） | 呼叫端補齊；不寫入部分 chunk | repository.py |
| VAULT-E303 | FTS index out of sync with chunks table | 重建 FTS（`INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')`）；記 audit | storage.py |

## Specs / EAV（4x）

| Code | Message | Recovery | Layer |
|---|---|---|---|
| VAULT-E401 | Unknown field_path: `<path>` (not in registry) | 回報 registry 鄰近候選；需要新 path 時走 registry 擴充（amend），不接受任意字串 | repository.py |
| VAULT-E402 | verified spec requires evidence_chunk_id or source_note | DB trigger ABORT 的 API 層轉譯；補 evidence 或改 unverified | storage.py trigger |
| VAULT-E403 | Spec value has no value (num/text/min/typ/max all null) | 呼叫端補值；CHECK constraint 違反 | storage.py |
| VAULT-E404 | Pin uniqueness violation: (component, package, pin_number) exists | 用 update 路徑而非重複 insert；回報既有列 | repository.py |

## EDA assets（5x）

| Code | Message | Recovery | Layer |
|---|---|---|---|
| VAULT-E501 | EDA asset mapping not found for `<mpn>`/`<kind>` | 顯式 absent；消費端（kicad_emit/footprint_map）不得猜測，提示登錄映射 | repository.py |
| VAULT-E502 | Invalid verification status transition: `<from>` → `<to>` | 僅允許 unverified→pin-checked→drc-passed 前進或顯式 reset；回報合法轉移 | repository.py |

## App knowledge（6x）

| Code | Message | Recovery | Layer |
|---|---|---|---|
| VAULT-E601 | companion-part knowledge requires companion_component_id | 先 upsert 必配料元件，再寫關係 | repository.py |
| VAULT-E602 | app_knowledge payload is not valid JSON for type `<knowledge_type>` | 呼叫端修正 payload 結構 | repository.py |

## Trust / audit（7x）

| Code | Message | Recovery | Layer |
|---|---|---|---|
| VAULT-E701 | audit_log is append-only (UPDATE/DELETE rejected) | 設計如此；任何修正以新 insert 記錄 | storage.py trigger |
| VAULT-E702 | Write attempted without audit context (actor missing) | repository 交易 helper 必帶 actor；修呼叫端 | repository.py |

## Usage / sourcing（8x）

| Code | Message | Recovery | Layer |
|---|---|---|---|
| VAULT-E801 | Usage record missing project_id | 呼叫端補 project_id | repository.py |
| VAULT-E802 | Sourcing snapshot rejected: live-query semantics not supported | 設計如此；只接受帶 snapshot_at 的快照資料 | services/api |

## API（9x）

| Code | Message | Recovery | Layer |
|---|---|---|---|
| VAULT-E901 | Component not found: `<query>`（explicit absent） | 非錯誤態的 404 對應；回 absent 語意，建議 ingest | services/api · services/mcp |
| VAULT-E902 | Import manifest unreadable or schema-unknown: `<path>` | 檢查 client cache `manifest.json` 版本；支援 manifest/index 兩代名稱（沿用 vault.py 慣例） | services/api |
| VAULT-E903 | Import conflict report: `<n>` conflicts kept side-by-side | 非阻斷；回衝突清單供人工裁決，不靜默覆蓋 | repository.py |
