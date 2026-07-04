# Errors: quality_verify-checker-skillification

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `CHK_IR_FIELD_MISSING` | checker 需要的 design-ir 欄位 / artifact key 不存在 | `ok=false` + `missing_fields[]` 缺項清單，exit≠0 | 補齊 IR 欄位或改用有該欄位的 artifact；**不得**以預設值續跑（no-silent-fallback） |
| `CHK_TIER_FORBIDDEN_PARTIAL` | 嘗試對 confidence=partial/todo 的 control 建 T-A 硬 gate checker | fail-fast，拒絕註冊 | 該 control 只能走 T-C advisory；待知識升 verified 才可重分類（no-fabrication） |
| `CHK_THRESHOLD_UNBOUND` | T-A checker 執行期在 ragbase control 找不到 threshold block | `ok=false` + control_id | 為該 control 補 machine-readable threshold block（DD-3），不硬編門檻 |
| `CHK_SOURCE_ANCHOR_MISSING` | threshold block 缺 source_anchor（電氣門檻無 datasheet 來源） | BLOCKING，拒絕產出 evidence | 補逐字來源錨點（datasheet-grounded 天條）；無來源的規格值不得成 gate |
| `ENV_TOOL_UNKNOWN` | checker 的 tool 名不在 `ORACLE_TOOLS` | `ValidationEvidence.__post_init__` 拋 `ValidationEvidenceError` | 先把 tool 加進 `ORACLE_TOOLS` + 對應 `_ADAPTERS`（兩處同步） |
| `ENV_RAW_RESULT_MISSING` | 空的 raw_result 傳進 `wrap_validation_evidence` | 拋 `ValidationEvidenceError` | checker 必須回非空 raw_result dict |
| `CHK_ADAPTER_MISSING` | tool 在 ORACLE_TOOLS 但 `_ADAPTERS` 無對應 adapter | `wrap_validation_evidence` 拋 ENV_TOOL_UNKNOWN | 補 adapter（如 M1-1 的 `erc` adapter） |
