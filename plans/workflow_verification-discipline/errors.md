# Errors: workflow_verification-discipline

> 錯誤目錄：每個錯誤碼帶觸發條件、訊息、恢復策略、責任層。全部 fail-fast，無 silent fallback（天條）。

## Error Catalogue

| Code | 觸發條件 | 訊息（使用者可見） | 恢復策略 | 責任層 |
|---|---|---|---|---|
| `REQ_ORACLE_INVALID` | `oracle_tool` 不在封閉枚舉內（DD-2） | `oracle_tool '<value>' is not a recognized oracle; allowed: drc_gate, erc, crosscheck, si_check, gerber_compare, spice, user_judgment, none` | 修正合約欄位後重跑合約收斂 | `requirement_planning.py` |
| `REQ_UNVERIFIABLE` | `oracle_tool == "none"` 的需求進入驗證流程而非 open_questions | `requirement '<key>' is unverifiable and must be escalated to open_questions, not verified` | 升級使用者決策：補 oracle 或接受 `user_judgment` | `requirement_planning.py` |
| `REQ_BINDING_MISMATCH` | `C00_REQUIREMENT_FIELD_BINDINGS` 校驗失敗（既有 fail-fast 模式沿用） | `requirement binding validation failed: <detail>`（既有訊息不變） | 修正 C00 PRD template 欄位對應 | `requirement_planning.py` |
| `REQ_VERDICT_NO_EVIDENCE` | pass verdict 無對應 oracle 執行記錄（DD-9） | `requirement '<key>' cannot be marked pass without an oracle execution record; status remains unverified` | 補跑 oracle 工具並提交 evidence return | `orchestration.py`（C00 ingest） |
| `REVIEW_MISSING` | workflow 推進到 deterministic-validation 但無 design-review 記錄（G2） | `design-review record not found; deterministic-validation is blocked until review completes` | 執行 design-review 節點，落盤 DesignReviewRecord | `contracts.py`（stage gate） |
| `REVIEW_VERDICT_INVALID` | review 文檔缺裁決欄位或情境清單為空 | `design-review record is incomplete: <missing fields>; gate requires verdict and non-empty scenarios` | 補完 review 文檔（最低情境集見 skills/bodesign） | `contracts.py`（stage gate） |
| `REVIEW_REJECTED` | review 裁決為 `REJECT`，validation 仍被請求 | `design-review verdict is REJECT; resolve concerns and re-review before validation` | 依 concerns 修改 layout intent 後重審 | `contracts.py`（stage gate） |
| `XCHK_DIMENSION_UNAVAILABLE` | 請求比對的維度缺 evidence（DD-5；這是顯式回報不是錯誤中斷） | `dimension '<dim>' skipped: <reason>`（出現在 `dimensions_unavailable[]`，非 exception） | 補對應 evidence（如 pad 資料）後重跑 | `reference_crosscheck.py` |
| `XCHK_EMPTY_REFERENCE` | 參考板 evidence 為空集合 | `reference evidence is empty; crosscheck cannot produce a meaningful diff` | 確認參考板資料匯入完成 | `reference_crosscheck.py` |
| `EV_SCHEMA_INVALID` | evidence return payload 不符 `bodesign.c00.evidence_return.v1`（DD-7） | `evidence return payload malformed: <validation detail>`（`OrchestrationError`） | 修正 payload 後重送；不落盤、不寫 log | `orchestration.py` |
| `EV_PACKET_NOT_FOUND` | `packet_id` 引用不存在的 work packet | `evidence return references unknown packet '<packet_id>'` | 確認 packet id；可能 spine 目錄不一致 | `orchestration.py` |
| `EV_ID_CONFLICT` | count-based evidence ID 與既有檔案衝突 | `evidence id '<id>' already exists; concurrent write suspected` | 重新取號重試一次；再失敗即人工介入 | `orchestration.py` |
| `ENV_TOOL_UNKNOWN` | `wrap_validation_evidence` 收到未支援的工具名（DD-6） | `no envelope adapter registered for tool '<tool>'` | 為新工具註冊 adapter 或修正工具名 | `validation_evidence.py` |
| `ENV_RAW_RESULT_MISSING` | adapter 收到空 raw_result | `cannot wrap empty tool result for '<tool>'` | 確認工具實際執行並產出結果 | `validation_evidence.py` |
| `SPINE_NOT_INITIALIZED` | `derive_workflow_plan()` 在無 `_orchestration/` 的資料夾執行（DD-8） | `orchestration spine not initialized for this project; run workflow init first (no fallback to static plan)` | 初始化 spine；**禁止** fallback 回參數快照 | `contracts.py` |
| `SPINE_STATE_CORRUPT` | spine 檔案存在但 JSON 解析失敗 / 必要欄位缺失 | `orchestration spine state corrupt at <path>: <detail>` | 人工檢查 `_orchestration/`；從 `log.jsonl` 重建或還原 | `orchestration.py` |
| `CMP_IR_INVALID` | comparator 輸入 IR 缺必要欄位（元件無 pin 定義、net 引用不存在的 pin 等）（DD-13） | `comparator input IR invalid: <detail>; no partial comparison performed` | 修正 IR 後重跑；不做部分比對 | `design_ir/compare/` |
| `CMP_CONFIG_INVALID` | scoring config 權重和不為 1.0 或含負值 | `comparator scoring config invalid: weights must be non-negative and sum to 1.0` | 修正 config | `design_ir/compare/` |

## 錯誤處理原則

1. **Fail fast**：所有 `EV_*` / `SPINE_*` / `REQ_*` 錯誤立即拋出（`OrchestrationError` 或 `ValueError` 沿用既有 hierarchy），不重試、不降級。
2. **`XCHK_DIMENSION_UNAVAILABLE` 是回報不是中斷**：唯一的非 exception 條目，因為缺維度 evidence 是合法狀態，必須顯式出現在 `CrossCheckDiff.dimensions_unavailable[]`。
3. **不污染 spine**：schema 校驗失敗的 payload 不落盤、不寫 `log.jsonl`（避免 append-only log 含垃圾事件）。
4. **錯誤碼進 envelope**：工具層錯誤包進 `ValidationEvidence.findings[]`（`severity=critical`）回流，讓 C00 看得到失敗原因。
