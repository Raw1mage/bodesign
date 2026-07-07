# Errors: eda-bridge_occupancy-ledger

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `LedgerConflict` | reserve 的矩形與帳本既有矩形相交 | Python 例外，payload 含衝突矩形清單（owner/kind/座標） | 呼叫端顯式位移策略（帶上限、記錄軌跡）；耗盡上限 → 升級 `BUDGET_INFEASIBLE`。禁止捕捉後靜默改位續跑 |
| `BUDGET_INFEASIBLE` | A2 掃畢所有 frame×pitch 候選無可行組合；或 A3/A4 顯式位移上限耗盡 | compose 以錯誤終止；報告含 overloaded_edges（所需 vs 可用 mm）與 candidates_tried（各候選否決原因） | 人工裁決：拆 unit（DD-7）、分頁、或修改內容。不升框迴圈、不降 scale 硬壓 |
| `LEDGER_ASSERTION_FAILED` | A5 事後斷言任一不成立（互疊>0、offpage>0、利用率<40%、超框） | compose 以錯誤終止；附違規實體清單＋帳本快照（LedgerSnapshot） | 視為 ledger 實作 bug：走 RCA 修 ledger/預檢，不調參、不重試 |
| `SYMBOL_GEOMETRY_MISSING` | A1 清點期符號缺 pin 幾何或 extent 無法計算 | compose 以錯誤終止；列缺項符號清單 | 修符號庫來源；不得以估算值靜默補位（no-silent-fallback） |

## Invariants

- 所有錯誤都在 compose 邊界拋出，帶結構化 payload；上層（MCP tool handler）原樣透傳，不吞不轉譯。
- 錯誤路徑零 fallback：任何「讓它先過」的默認值都是缺陷（repo 天條 §2.1）。
