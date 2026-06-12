# Observability: workflow_verification-discipline

> 事件、指標、日誌、告警定義。全部建立在 spine 既有 `log.jsonl` append-only 模式與 specbase event log 之上，不新建觀測管道。

## Events

> 落點：`_orchestration/log.jsonl`（append-only）

| Event | 觸發點 | Payload 關鍵欄位 | 消費者 |
|---|---|---|---|
| `requirement.contractualized` | 合約收斂完成（1.3） | `{requirement_key, metric, threshold, oracle_tool}` | C00 plan 檢視、pass/fail 表 |
| `requirement.unverifiable` | `oracle_tool=none` 升級 open_questions（1.2） | `{requirement_key, reason}` | 使用者決策佇列 |
| `requirement.status_changed` | C00 ingest 更新 verification_status（3.3） | `{requirement_key, from, to, evidence_id}` | pass/fail 表、workflow plan 推導 |
| `review.completed` | DesignReviewRecord 落盤（2.2） | `{subject, verdict, counts}` | stage gate、審計 |
| `review.gate_blocked` | 無 review 記錄或 REJECT 時請求 validation（2.2） | `{reason: REVIEW_MISSING\|REVIEW_REJECTED}` | workflow plan、使用者 |
| `crosscheck.diff_computed` | `crosscheck_diff()` 完成（2.4） | `{label, coverage_pct, first_divergence, dimensions_unavailable[]}` | root-cause 流程、evidence 包裝 |
| `comparator.scored` | comparator 完成一次 IR-vs-IR 比對（5.4/5.5；經 envelope 進 spine，非 comparator 直寫） | `{S_comp, S_attr, S_conn, S_total, matched, missing, extra, first_divergence}` | 交叉檢核報告、evidence 包裝 |
| `rootcause.reported` | 四段式報告寫入 events（2.6） | `{divergence_key, fix}` | 審計、後續 debug 參考 |
| `evidence.returned` | evidence return 落盤（3.2） | `{evidence_id, packet_id, source_layer, severity, requirement_verdicts_count}` | C00 ingest、workflow plan 推導 |
| `evidence.rejected` | malformed payload fail-fast（3.2；**不寫 log.jsonl**，改走 specbase event） | `{error_code: EV_SCHEMA_INVALID, detail}` | 開發者 debug |
| `blocker.simple_fixes_attached` | blocker 附 simple_fix_candidates（1.5） | `{blocker_id, candidates_count}` | debug ladder 紀律檢查 |
| `blocker.structural_unlocked` | 全部 candidates ruled_out（1.6 gate） | `{blocker_id, evidence_refs[]}` | 結構性提案授權 |
| `workflow.plan_derived` | `derive_workflow_plan()` 執行（4.1） | `{stages_blocked[], stages_ready[], evidence_count}` | `/workflow/reference-board` 回應 |
| `workflow.spine_not_initialized` | 無 `_orchestration/` 查詢（4.2；specbase event） | `{folder}` | 使用者引導初始化 |

## Metrics

> 衍生計算，不另建 store

| Metric | 定義 | 來源 | 用途 |
|---|---|---|---|
| `contract_coverage_pct` | 帶完整 metric/threshold/oracle 的需求 ÷ 全部需求 | requirement set 掃描 | G1 落地成效；目標 ≥ 80% |
| `verification_pass_rate` | `pass` ÷ (`pass`+`fail`) per 輪 | pass/fail 表 | 每輪驗證健康度 |
| `unverified_residual` | 驗證輪結束仍 `unverified` 的合約數 | pass/fail 表 | 漏測偵測；非零需解釋 |
| `review_reject_rate` | `REJECT` ÷ 全部 review | `review.completed` events | G2 gate 是否形式化（長期 0% 可疑） |
| `simple_fix_hit_rate` | 由 simple fix 解決的 blocker ÷ 附 candidates 的 blocker | blocker resolution 記錄 | G6 紀律有效性（DC 數據點：多數失敗是簡單原因） |
| `dimension_coverage` | crosscheck 可用維度數 ÷ 4 | `crosscheck.diff_computed` | diff 維度擴展進度 |
| `evidence_return_latency` | packet dispatch → 首筆 evidence return 的事件間隔 | log.jsonl 時間戳 | spine 回流是否實際被使用 |

## Logs

- **Spine 事件**：沿用 `_orchestration/log.jsonl`（append-only，count-based ID 對齊）。新增三類事件前綴：`requirement.*`、`evidence.*`、`workflow.*`。
- **工具層**：envelope 包裝失敗（`ENV_*`）記在 MCP 工具回應 + specbase event log，不進 spine log（spine log 只記成功的狀態轉移）。
- **Review 文檔**：DesignReviewRecord 本體落盤 client 專案資料夾（evidence 即 log）；gate 判定結果進 spine log。

## Alerts（人工巡檢條件，無自動告警基礎設施）

| 條件 | 等級 | 含義 |
|---|---|---|
| `unverified_residual > 0` 且驗證輪宣告完成 | 高 | 有合約被漏測，pass/fail 表不完整 |
| `review_reject_rate == 0` 持續多專案 | 中 | review gate 可能形式化（橡皮圖章） |
| `evidence_returns/` 長期為空但 validation 有跑 | 高 | A3 回流斷鏈，工具結果沒進 spine |
| 同一 blocker 結構性提案出現但 candidates 未全 ruled_out | 高 | G6 紀律被繞過 |

## 驗證觀測點（implementing 階段 debug checkpoints）

1. **合約收斂邊界**：`plan_design_intent` 輸入/輸出 — 抽取的 requirement 是否帶齊新欄位
2. **Gate 邊界**：stage 推進請求 → gate 判定 — REVIEW_MISSING / REVIEW_REJECTED 路徑可觸發
3. **包裝邊界**：工具原生輸出 → envelope — raw_result 逐欄位比對不變
4. **Spine 邊界**：evidence return 提交 → 落盤 + log — malformed 不污染、well-formed 雙寫一致
5. **推導邊界**：spine 狀態 → workflow plan — 同一 spine 狀態重複推導結果 deterministic
6. **比對邊界**（G7）：兩份 IR → comparator 輸出 — 自比對滿分、重複執行 byte-equal、`CMP_IR_INVALID` 不產生部分結果
