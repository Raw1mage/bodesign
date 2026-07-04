# Errors: quality_prd-bom-crosscheck

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `MANIFEST_MISSING` | `main_components_structured.json` 不存在於 C00 資料夾 | ValueError / MCP error payload，訊息指示先抽取 + 人工審計 | LLM 抽取 manifest → 使用者審計 → 重跑 |
| `MANIFEST_INVALID` | manifest JSON 不合 schema（缺 roles、qty_min 非正整數、pattern 非法正則） | ValueError 列出全部違規欄位（一輪報全，不逐項擠牙膏） | 修 manifest → 重跑 |
| `NETLIST_MISSING` | netlist 路徑不存在或不可讀 | ValueError | 先跑 C03 export_netlist |
| `NETLIST_PARSE_ERROR` | .net S-expr 解析失敗或零元件 | ValueError 帶檔案路徑與解析位置 | 檢查 netlist 完整性（可能被截斷） |
| `GATE_FAIL` (非 error) | 報告含 ≥1 BLOCKING 項 | 正常回傳 `gate: "FAIL"` + blocking 清單（工具不 raise；執法在 readiness/工作流層） | 使用者修設計或記 approval → 重跑 |
| `MANIFEST_STALE` (warn) | answer_state sha256 與 manifest 快照不符 | 報告 `manifest_stale: true` + stderr warn | 重抽取 manifest 對齊 PRD 修訂 |
