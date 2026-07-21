# Errors: mcp_r16-domain-kb

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `KB_UNAVAILABLE` | `BODESIGN_KB_DB` 未設、檔案不存在、或 sqlite 開啟失敗 | MCP isError=true，content text 首行 `KB_UNAVAILABLE: <reason>`，第二行 `remedy: KB lives host-side at <repo>/.specbase/ragbase.sqlite; distill via specbase producer.ts (ragbase_distill); mount is live, no restart needed.` | 依 remedy 在 host 端補 KB / 修掛載；工具可即時重試（連線 per-request） |
| `KB_BAD_QUERY` | q 為空字串或全空白 | MCP isError=true，`KB_BAD_QUERY: empty query` | caller 補 q 重呼叫 |
| `KB_OBJECT_NOT_FOUND` | kb_get 的 id 不存在 | MCP isError=true，`KB_OBJECT_NOT_FOUND: <id>`，附 `consider: bodesign_kb_query` | 先 kb_query 找正確 id |
| `KB_READONLY_VIOLATION` | （防禦性）任何寫入嘗試觸及 query_only 連線 | sqlite 拋錯原樣上拋，不吞 | 不應發生；發生即 bug，report issue |
