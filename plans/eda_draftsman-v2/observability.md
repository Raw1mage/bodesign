# Observability: eda_draftsman-v2

## Events

- symbol 覆蓋率報告（A1 每輪）：resolved/gap 比例 + SymbolGap 清單（JSON + markdown）
- 單圖 QA verdict（A3 每積木）：`{block_id, render_qa: pass|fail(overlaps[]), fidelity: pass|fail(diff)}`
- 整頁 QA verdict（A5 每頁）：雙閘 + utilization 數值
- 每輪迭代記 event log（scope: eda_draftsman-v2）：改了什麼、閘結果 delta
- 人工 gate 裁決逐字記 event log（含打回原因），打回項 BR 化為可機檢規格回填 spec.md

## Metrics

- `symbol_coverage`：resolved MPN / 全 BOM MPN
- `overlap_count`：render_qa text-bbox 相交數（目標恆 0）
- `fidelity_diff`：連通分量差異數（目標恆 0）
- `utilization`：ink_metrics 圖紙利用率（門檻 ≥ 0.55）
- `roundtrip_exit`：kicad-cli render exit code（CI 回歸）
- **迭代健康度（防原地踏步——本計畫存在的理由）**：每 QA FAIL 記缺陷簽名（error code + block_id + 位置）；同簽名連續 2 輪未收斂 → 強制停手 RCA，不得第 3 輪疊補丁
