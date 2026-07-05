# Observability: quality_deterministic-preplacement

## Events

- result dict `effective` 段：echo seed / SA 權重 / die_shadow_margin_mm / board_mm（每次呼叫可稽核）
- result dict `placement_violations`：每筆帶 rule id + source 錨點 + measured/limit

## Metrics

- `hpwl_mm` — 最終 half-perimeter wirelength（與 grid 基線對比軸）
- `violations_count` — R1/R8 違反數
- `overlap_pairs` — 擺後殘留 AABB 重疊對數（應為 0）
- SA 收斂：iterations / final energy（result 內回報）

## Debug checkpoints

- 分群結果（clusters）完整回傳，可直接檢視 decap 歸屬是否正確
- 貪婪初擺與 SA 後擺件可分別取得（純核心分段函式，unit test 直接呼叫）
