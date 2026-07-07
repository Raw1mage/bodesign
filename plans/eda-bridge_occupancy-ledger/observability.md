# Observability: eda-bridge_occupancy-ledger

## Events

- `[budget] page=<slug> paper=<A0..> pitch=<mm> fill=<ratio> candidates_tried=<n>` — A2 求解定案時一行；含被否決候選數
- `[budget] INFEASIBLE page=<slug> edges=<...>` — BUDGET_INFEASIBLE 時輸出缺項摘要（完整報告在例外 payload）
- `[ledger] reserve owner=<ref/net> kind=<body|label|...> ok=<bool>` — DEBUG 級逐筆 reserve 軌跡（預設關閉，環境變數開啟）
- `[ledger] conflict owner=<x> vs=<y,...> displaced=<n>/<cap>` — 顯式位移策略每次觸發時一行（含上限用量）
- `[gate] page=<slug> pitch=<v> frame=<v> fill=<v> overlaps=0 offpage=0 PASS` — A5 斷言通過的五組數字一行（沿用現行機械閘輸出格式）
- `[gate] ASSERTION_FAILED page=<slug> violations=<n> snapshot=<path>` — 斷言失敗時快照落地路徑

## Metrics

- `fill_ratio` per page — 內容佔紙面比（目標 0.60–0.75；斷言下限 0.40）
- `reserve_conflict_count` per page — compose 全程衝突次數（健康頁應接近 0；持續高值=placement 品質退化訊號）
- `displacement_budget_used` per page — 顯式位移策略用量/上限（逼近上限=內容逼近物理極限的早期預警）
- `candidates_tried` per page — pitch-scan 掃描效率（暴增=預檢淘汰失效）
- `compose_wall_time` per page — 效能守門（DD 風險：dry-run reserve O(候選×實體)；基準秒級）

## Debug artifacts

- LedgerSnapshot dump（JSON）：`LEDGER_ASSERTION_FAILED` 時自動落地，含全帳本矩形＋違規清單——RCA 唯一入口，取代本役的逐層埋點考古
