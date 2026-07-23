# Errors: knowledge_c03-ee-design-kb

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| KB_UNAVAILABLE | ragbase 未掛載/不存在（既有，by-design 天條） | `kb_query` 回 KB_UNAVAILABLE + remedy，非空 hits 假裝無知識 | 依 remedy：KB 在 `<repo>/.specbase/ragbase.sqlite`，host-side producer distill |
| KB_OBJECT_NOT_FOUND | `kb_get` 未知 id（既有） | KB_OBJECT_NOT_FOUND + consider kb_query | 用 kb_query 找正確 id |
| PC-001 (新，BR_B) | active IC（U/Q 帶 power pin）零去耦 / 未履行 pin-class obligation | `analyze_schematic` finding（high，帶 confidence + evidence_source）或 `passive_gaps[]` | 補該 IC 必要被動件；或用 `Netlist_Status.md` 宣告 documented gap + provenance waiver |
| PASSIVE_GAPS_UNWAIVED (新，BR_B) | passive gap 存在且無合法 waiver | gate HARD FAIL；拒 C04 入口（若走 check_c03 R5） | 修設計補被動件，或使用者記錄 waiver（no-silent-fallback） |
| INGEST_NO_SOURCE (A2) | 待蒸主題無來源可錨 | 標 UNVERIFIED 掛帳，不蒸空殼 | 找來源（datasheet/AN/bus-spec）或明記缺口，不臆造 |
