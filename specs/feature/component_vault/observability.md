# Observability: feature_component_vault

> 原則：vault 是 server 端長駐資產，觀測重點是「知識庫健康度」與「寫入路徑可追溯」。
> Audit trail 本身已由 `audit_log` 表承載（L7）；本文件定義其上的 events / metrics / logs / alerts。

## Events

> 結構化事件，走既有 bus/log pipeline。

| Event | Payload | 觸發點 |
|---|---|---|
| `vault.component.upserted` | `{canonical_key, mpn, is_new}` | repository upsert |
| `vault.document.ingested` | `{sha256, doc_type, provenance, dedup_hit, mpn_links}` | document ingest |
| `vault.chunks.indexed` | `{document_id, chunk_count, extractor, stale_marked}` | chunk pipeline |
| `vault.spec.written` | `{canonical_key, field_path, confidence, has_evidence}` | spec write |
| `vault.spec.rejected` | `{canonical_key, field_path, error_code}` | trigger ABORT / registry reject |
| `vault.import.completed` | `{source, imported, conflicts, unverified_count}` | client cache import |
| `vault.usage.recorded` | `{canonical_key, project_id, workflow, occurrences}` | workflow 回寫 |
| `vault.consistency.scanned` | `{records_without_blobs, blobs_without_records}` | startup 掃描 |
| `vault.db.error` | `{error_code, sqlite_error}` | VAULT-E001/E002/E003 |

## Metrics

> 健康度量測；首版可由 SQL view 派生，不強制 metrics backend。

| Metric | 型別 | 說明 |
|---|---|---|
| `vault_components_total` | gauge | 元件總數 |
| `vault_documents_total` | gauge | 文件總數（含 rev 分布） |
| `vault_chunks_active` / `vault_chunks_stale` | gauge | 抽取層健康度 |
| `vault_specs_verified_ratio` | gauge | verified / total spec_values —— 知識庫可信度核心指標 |
| `vault_gaps_open` | gauge | 未解 knowledge gaps 數 |
| `vault_queue_depth` | gauge | knowledge queue 長度（補齊待辦壓力） |
| `vault_ingest_duration_ms` | histogram | ingest 管線耗時（per phase） |
| `vault_spec_rejections_total` | counter | trigger/registry 拒絕次數（寫入品質訊號） |
| `vault_import_conflicts_total` | counter | 匯入衝突累計 |

## Logs（結構化，沿用 services/api logging 慣例）

- 所有 repository 寫入：`actor` + `action` + `table` + `row_id`（與 audit_log 同源，log 為流、audit 為帳）
- ingest 管線：每 phase 開始/結束一行，帶 document sha256 前 8 碼
- 錯誤一律帶 `VAULT-Exxx` 碼；sqlite 原始錯誤進 detail 欄不進 message
- 禁止 log 完整 datasheet 內容（chunk content 只 log 長度與頁碼）

## Alerts（首版為報告型，非即時 paging）

| 條件 | 等級 | 動作 |
|---|---|---|
| `vault.db.error` (E001/E003) | critical | 服務 fail-fast 停止；操作者介入 |
| consistency scan 缺口 > 0 | warning | startup 報告列入 web UI 健康面板 |
| `vault_specs_verified_ratio` 下降趨勢 | info | knowledge queue 優先級提示 |
| import conflicts 未裁決累積 | info | web UI Candidates/知識面板顯示待裁決清單 |

## Debug checkpoints（code-thinker 契約對齊）

1. **CP-ingest**: blob 寫入成功 → DB commit 前後各一 checkpoint（驗證 DD-6 順序）
2. **CP-trigger**: verified 無 evidence 寫入 → 必須觀測到 ABORT + VAULT-E402（不是靜默降級）
3. **CP-import**: 衝突 case → 必須觀測到兩列並存 + conflict_reported（不是覆蓋）
4. **CP-restart**: container 重啟 → components/blobs 計數前後一致
