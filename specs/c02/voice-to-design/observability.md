# Observability: c02_voice-to-design

口述→設計稿閉環的可觀測訊號。所有訊號從工具回傳值的結構化欄位導出，不另立日誌系統。

## Events

回傳訊號（所有訊號從工具回傳值的結構化欄位導出）。

| Signal | Source | Shape | Purpose |
|---|---|---|---|
| `intent.extracted` | plan_c02_intent 回傳 | `{field_status: {key: answered\|stated\|missing}, readiness_pct}` | 看口述抽出多少、缺什麼 |
| `intent.next_question` | plan_c02_intent.next_question | `{key, question, blocks_source}` | 追蹤反問輪數與卡在哪個欄位 |
| `intent.status` | IntentPlanResult.status | `needs-clarification\|ready-for-approval\|approved` | 編排狀態機當前態 |
| `pipeline.stage` | voice_to_design 編排 | `source_generated → stl_exported → rendered` | 閉環走到哪一段 |
| `render.status` | ModelRenderResult.status | `rendered\|no-deps\|no-gl\|empty\|error` | 渲染成敗 + degrade 原因 |
| `render.bounds_mm` | ModelRenderResult.bounds_mm | `[x0,y0,z0,x1,y1,z1]` | 驗證幾何尺寸對應約束（如 56×36×18 對應 50×30+壁厚） |

## Metrics

（可從回傳推導）

- **反問輪數**：到 status=ready-for-approval 前的 next_question 次數（越少體驗越好；DD-2 風險緩解的觀測點）。
- **抽取覆蓋率**：stated+answered 欄位數 / 8（readiness_pct 即此）。
- **閉環成功率**：approve=true 後走到 status=rendered 的比例。

## Alerts / 健康訊號

- `render.status != rendered` 且 worker 應有 GL → 環境退化（檢查 me worker EGL/GL）。
- `pipeline.stage` 停在 stl_exported 未到 rendered → 渲染缺口回歸（DD-3 回歸測試守護）。
