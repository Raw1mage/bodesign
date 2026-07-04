# Observability: quality_verify-checker-skillification

## Events

- `checker.run` — 每次 T-A checker 執行時發出：`{control_id, tool, tier, severity, finding_count, threshold_source}`。
- `checker.tier_forbidden` — 嘗試對 partial/todo control 建 T-A gate 被拒時發出（no-fabrication 稽核軌）。
- `checker.field_missing` — IR 缺欄位 fail-fast 時發出：`{control_id, missing_fields[]}`（暴露 parser/IR gap）。
- `evidence.emitted` — control-grounded ValidationEvidence 流回 C00 evidence_returns 時發出：`{control_id, source_anchor, severity}`。
- `registry.status_change` — checker registry 狀態轉移（stub→landed / →advisory）。

## Metrics

- `skillification_coverage` — landed / stub / advisory 三態計數 ÷ 57，技能化進度。
- `tier_distribution` — T-A / T-B / T-C 三層 control 數（實測 3 / 29 / 25），追蹤 parser 解鎖後 T-B→T-A 遷移。
- `checker_grounding_rate` — 帶 source_anchor 的 T-A verdict ÷ 全 T-A verdict（datasheet-grounded 覆蓋率，目標 100%）。
- `parser_unlock_ratio` — 每新增一個 parser 解鎖的 T-B control 數（DD-7 槓桿指標）。
