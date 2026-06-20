# Observability: c01_design-vector (BR-extended)

C01 是 deterministic script-first 工具，無長駐 runtime；觀測點落在工具回傳結構與 readiness 報告，而非 metrics/alerts 系統。

## Events

工具回傳即事件。

| Event | 觸發 | 載體欄位 |
|---|---|---|
| `bucket.emitted` | 任一 bucket emitter 成功 | `BucketResult.status=success` + `bucket` + `files` + `draft_markings` |
| `bucket.fail_fast` | emitter 缺關鍵欄位 | `status=missing/external-needed` + `missing_fields` |
| `bucket.validation_failed` | Ai file SVG schema 不過 | `status=validation-failed` + `validation_errors` |
| `bucket.placeholder_used` | Ai file 用 generic placeholder | `placeholders[]`（非空即告知，不靜默） |
| `bucket.ai_skipped` | 無 Illustrator path | `ai_emitted=false`（顯式，不偽造） |
| `bucket.pdf_pending` | PDF pipeline 不可用 | `C01D-E001` blocker + markdown 已產 |
| `readiness.dual_track` | `c01_readiness` 呼叫 | `companion_readiness` + `id_native_readiness` |

## Metrics

可由回傳推導，非即時系統。

- `companion_readiness.readiness_pct`：core 五件就緒度（向後相容既有 `readiness_pct`）。
- `id_native_readiness.present / total`：三 bucket 已產數 / 3。
- `draft_markings count`：每個視覺/文件的 draft 標記數（恆 ≥ 1，否則缺陷）。
- `placeholders count`：Ai file 用 placeholder 的元件數（圖元庫覆蓋度反指標）。

## Logs（structured，emitter 寫入 README/result）

- 每 bucket 的 `README.md` 記錄：產出檔清單、輸入來源（Interface_Constraints + answer_state 欄位）、draft 標記、缺欄/placeholder 告知。
- result dict 為主要結構化日誌載體；無另立 log sink。

## Invariants 觀測

- `human_approved` 恆為 False（ID-native 產出永不升 approved）— readiness 報告可驗。
- `draft_markings` 非空 — 每次 emit 可驗。
- fail-fast 不產檔 — `missing_fields` 非空時 `files` 應為空。

## Alerts（人工 gate，非自動）

- PDF pipeline 不可用 → 回 blocker，使用者決策（停 gate），不自動 fallback。
- 圖元庫覆蓋度低（placeholders 過多）→ 提示擴充圖元庫，非自動補。
