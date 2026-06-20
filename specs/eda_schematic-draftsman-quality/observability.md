# Observability: eda_schematic-draftsman-quality

> compose_schematic 是同步 pure-python 工具，無長駐 runtime。觀測點以 result 欄位 + warnings + ink 度量為主。

## Events

無背景 worker、無 Bus event；「事件」以 result 回報 + warnings 形式呈現（呼叫端可記入 specbase event log）。

- `compose.draftsman.ok` — draftsman 模式成功產圖，帶 clusters/route_stats/sheet_fit/ink_metrics。
- `compose.netlist.ok` — 預設 netlist 模式成功（既有行為，byte-equivalent）。
- `compose.cluster.degenerate` — net-degree clustering 退化（E-DRAFT-003）。
- `compose.placement.overlap` — force-directed 後仍重疊、套 gutter 兜底（E-DRAFT-004）。
- `compose.sheet.overflow` — 內容超最大頁（E-DRAFT-005）。
- `compose.ink.unavailable` — ink toolchain 缺（E-DRAFT-006）。

## Metrics

| 指標 | 計算 | 用途 |
|---|---|---|
| ink_pct | ink_metrics.ink_pct | 著墨率；draftsman 應 ≥ 2× netlist 基準、絕對 ≥ 10%（核心驗收） |
| content_fill_pct | ink_metrics.content_fill_pct | 內容佔版面比；消除「浮在空白」 |
| wired_nets / labelled_nets | route_stats | 實體導線 vs label 退回比例；越多 wired 越像電路圖 |
| clusters_count | len(clusters) | 分群數；驗證 placement 有分群 |
| overlap_pairs | force-directed 後殘留重疊對數 | placement 品質（應為 0） |
| selected_paper | sheet_fit.selected_paper | sheet-fit 選頁是否合理 |

ink_pct 是本 plan 的硬驗收訊號（vs BR 量測的 3-6% 基準）。

## Logs（structured，於 result.warnings）

- 累積 E-DRAFT-001..006 的 warnings，定位 symbol 載入失敗 / unresolved pin / 分群退化 / 重疊 / 溢出 / toolchain 缺。

## Invariants 觀測

- **預設不破壞**：style 省略時 result.style 必為 "netlist"，且與升級前 byte-equivalent（TV9 守門）。
- **確定性**：兩次 run placement 必相同（TV10 守門）。
- **fail-fast**：symbol/net 問題必入 warnings/unresolved，不靜默吞。

## Alerts（人工 gate，非自動）

- ink_pct 未達門檻 → 視為 placement/wire 未改善，回 design 檢討，非自動重跑。
- 無持久狀態、無背景 worker、無 race window → 不需 Bus event / metrics endpoint / 長駐健康檢查。
