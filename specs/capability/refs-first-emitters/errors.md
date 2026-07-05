# Errors: capability_refs-first-emitters

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| REFS_SSOT_MISSING | emit 呼叫時 stage `01_refs/` 不存在或無 source | RefsGateError（既有 refs_gate 家族），不產出任何檔案 | 先把 owner 權威來源分解進 `01_refs/`（refs_ingest） |
| (gap) kind_derived | 約束項 provenance.kind == derived | 非錯誤：readiness `provenance_gaps[]` + `dod_ok:false` | 使用者親答該欄位或補 refs source 後重 emit |
| (gap) refs_source_unresolvable | kind=refs 但 source 路徑不在 `01_refs/` 下 | readiness gap + `dod_ok:false` | 修正 source 相對路徑或補檔 |
| (gap) provenance_missing | v1 舊檔（無 provenance 欄位） | readiness gap + `dod_ok:false`，訊息附「重 emit 即升 v2」指引 | 以現行 emitter 重跑 |
