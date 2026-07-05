# Observability: capability_refs-derived-design

## Events

- `refs_gate_start verb=<v> layer=<C0x>` — refs-gate 進場（stderr，比照 gate.py landing_verb 慣例）
- `refs_gate_reject verb=<v> code=<REFS_SSOT_MISSING|...> missing=<n>` — fail-fast 拒絕時發出，帶缺項數
- `refs_gate_pass verb=<v> traced=<n>` — 放行時發出，帶已追溯項數
- `upstream_constraint_load type=<face-layout|envelope|mechanical> owner=<C01|C02>` — 上游約束載入
- `dod_traceback item=<id> traceable=<bool>` — DoD 每項回溯結果
- `board_surgery_wrapper op=<castellated|stamp> drc_roundtrip=<pass|fail>` — board-surgery 產物 DRC 驗證

## Metrics

- `refs_gate_reject_rate` — fail-fast 拒絕佔比（範式翻轉初期應高，反映憑空發明被擋）
- `traceback_coverage_pct` — 交付物可追溯 SSOT 佔比（目標 100%，<100% 即有憑空發明）
- `anchor_completeness_pct` — SSOT 帶 owner 錨點佔比（No fabrication gate 指標）
- `board_surgery_segfault_count` — 徒手 pcbnew scripting segfault 次數（目標 0，wrapper 生效後）
- `aiguard_regression_invented_items` — aiguard 全鏈回歸中憑空發明項數（驗收判準，目標 0）
