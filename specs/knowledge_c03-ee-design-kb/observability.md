# Observability: knowledge_c03-ee-design-kb

## Events

- `kb_query` payload 的 `matchMode`（`fts-or`/`fts-and`/`like-scan`/`hybrid`）— 每次查詢回傳，讓「0 hits」自描述是模式問題還是真無知識（A1 後多詞應多為 `fts-or`）。
- `passive_gaps[]` / `PC-001` finding — A3 gate 每次跑對 pinout-only/naked-active 板 emit，帶 ref+pin+class+missing_obligation。
- BR 收尾 `event_record`（specbase）+ BRNS relay `[BRNS-DONE/BLOCKED]` 回 sender。

## Metrics

- **多詞召回率**：BR_A Symptom 表的多詞 query 命中數（修前 0 → 修後 >0）；A1 驗收指標。
- **C03 設計術語 KB 覆蓋**：`regulator 拓撲 / SI 數值 / pull-up sizing` 是否各有可查 control（A2 驗收）。
- **passive gap 攔截率**：pinout-only fixture / aiguard 02_mcu_core 由 FAIL→（補件後）PASS；BR_B 驗收。
- **單詞召回不退化**：`decoupling`/`fuse derating`/`crystal` 命中集修前後一致（A1 防退化）。
