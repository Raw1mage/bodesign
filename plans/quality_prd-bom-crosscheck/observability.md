# Observability: quality_prd-bom-crosscheck

## Events

- `crosscheck report written` — 每次執行落盤 `prd_bom_crosscheck.report.json` 至 netlist 同層（同輸入覆寫，byte-identical 為確定性訊號）
- `gate FAIL` — 報告 `gate: "FAIL"` 時 MCP 回傳 payload 含逐項 BLOCKING 與 matched_refs（誤配審計軌）
- `manifest stale warn` — answer_state hash 漂移時 stderr 一行 warn + 報告欄位

## Metrics

- `verdict 分佈`（present / substituted / missing 計數）— 報告內建，跨案累積可量化 PRD→C03 履約率
- `blocking 率` — gate FAIL 次數 / 執行次數；L2 協議生效後應趨零（降級在 C03 內就被引導回允許集合）
- `netlist_components` — 解析元件數 sanity 訊號（0 = NETLIST_PARSE_ERROR，不會靜默）
