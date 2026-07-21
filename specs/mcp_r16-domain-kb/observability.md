# Observability: mcp_r16-domain-kb

## Events

- server log line per kb_query：`kb_query q=<trunc> matchMode=<m> hits=<n> ms=<t>`（audit 對齊既有工具日誌格式）
- server log line per KB_UNAVAILABLE：`kb_unavailable path=<p> reason=<r>`（fail-fast 證據）
- kb_get miss：`kb_get_miss id=<id>`

## Metrics

- kb_query 命中率（hits>0 比例）——後續評估 KB 覆蓋缺口的訊號（0-hit 高頻主題 = 蒸餾 backlog）
- matchMode 分佈（like-scan 比例過高 = 查詢習慣或 tokenizer 教育問題）
- kb_query 延遲 ms（純 sqlite FTS，預期 <50ms；異常升高查掛載健康）
