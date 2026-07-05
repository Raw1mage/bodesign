# Errors: quality_deterministic-preplacement

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| PREPLACE_MISSING_GEOMETRY | strategy=deterministic 且任一 ref 的 footprint 無法載入/bbox 不可得 | ValueError 帶缺項 ref 清單 | 補 fpdir / 修 netlist footprint id；不得退回 grid |
| PREPLACE_BOARD_TOO_SMALL | 板框面積 < Σ零件 courtyard（含 gutter）無可行解 | ValueError 帶所需最小面積 | 放大 board_mm 或減件 |
| PREPLACE_INVALID_SEED | seed 非 int | ValueError | 傳 int seed |
| PREPLACE_UNKNOWN_STRATEGY | strategy 不在 {grid, deterministic} | ValueError | 修正參數 |
| (violations) | R1/R8 檢查不過 | 非錯誤：result.violations 列出，board 照常產出 | 呼叫端審查/改板框重跑 |
