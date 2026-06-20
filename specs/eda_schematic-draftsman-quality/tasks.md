# Tasks: eda_schematic-draftsman-quality

> 來源：`issues/issue_20260618_compose_schematic_draftsman_quality.md`（BR）。對齊 design.md DD-1..DD-7。
> 決策（2026-06-19）：opt-in `style="draftsman"`，預設 `style="netlist"`（舊行為零破壞）。
> 任務狀態：`[ ]` pending / `[~]` in-progress / `[x]` done / `[!]` blocked / `[?]` decision。

## 1. style 參數與向後相容骨架

- [x] 1.1 `composer.py` 的 `compose_schematic` 加 `style` 參數（"netlist" | "draftsman"），預設 "netlist"（DD-3）
- [x] 1.2 style="netlist" 路徑 = 既有行為（naive `_auto_place` grid + connection_style=label），與升級前 byte-equivalent
- [x] 1.3 呼叫者明確給 `connection_style` 時尊重之（style 不覆蓋顯式 connection_style）
- [x] 1.4 擴充 ComposeResult 回傳：style/clusters/route_stats/sheet_fit/ink_metrics（對齊 data-schema.json）

## 2. Placement：分群 + 群內 force-directed

- [x] 2.1 實作 symbol bbox 估算 `_estimate_bbox`（load_symbol pin-extent proxy + margin，DD-4；載入失敗 fail-visible 不塞預設）
- [x] 2.2 階段 A 分群 `_cluster`：有 group 宣告用宣告；否則 net-degree clustering（確定性連通分量/greedy，DD-2）；star hub degree-capping（R4）
- [x] 2.3 階段 B 群內確定性 force-directed `_refine`：固定初始化/迭代/步長、無 RNG，被動件靠主 IC（DD-2）
- [x] 2.4 收斂後 AABB 重疊檢查 + 確定性 gutter 重排兜底（非隨機，R1）
- [x] 2.5 終局座標 `_snap_grid`；spec 帶 explicit x/y 時沿用、不套分群（保留 AI-owns-placement 契約）

## 3. Drawn-wire 與 sheet-fit（draftsman 模式）

- [x] 3.1 draftsman 模式呼叫既有 `emit_kicad_schematic(connection_style="wire")`（複用 _orthogonal_route/_bus_route，DD-1，不改幾何）
- [x] 3.2 net kind 推導：power/bus/單pin/unresolved → label fallback，記 route_stats.label_fallback_reasons（不靜默）
- [x] 3.3 sheet-fit `_fit_sheet`：算內容 AABB → 選最小可容納標準頁（A4/A3/A2…）置中（DD-5）；超最大頁 → warning 不裁切
- [x] 3.4 netlist 模式維持 A4（DD-5/R2）

## 4. Ink/bbox 量化驗收模組

- [x] 4.1 新模組 `ink_metrics.py`（pure-python core）：PDF/PNG → ink%（非背景像素比）+ 內容 bbox 佔版面比（DD-6）
- [x] 4.2 toolchain-gating：缺 pdftoppm/poppler/PIL → measurement_unavailable + 缺項清單，不偽造（天條）
- [x] 4.3 接進 compose 結果（draftsman 模式回 ink_metrics；netlist 模式可略）

## 5. MCP schema 同步

- [x] 5.1 `services/mcp/server.py` 的 `bodesign_compose_schematic` schema 加 `style` 參數（預設 netlist），handler 透傳

## 6. 測試

- [x] 6.1 `tests/`：帶 group → 同群相鄰、群間分離、群內無 bbox 重疊（TV1）
- [x] 6.2 無 group → net-degree 分群生效、非 index%columns（TV2）
- [x] 6.3 2-node net 有實體 wire + local label、無 global-label（TV3）
- [x] 6.4 power/bus/單pin/unresolved 退回 label 且 route_stats 可見（TV4）
- [x] 6.5 sheet-fit 選頁正確、內容不溢出（TV5）
- [x] 6.6 ink% 相對 netlist 基準明顯提升（TV6）；缺 toolchain → unavailable（TV7）
- [x] 6.7 draftsman 產出 kicad-cli validate 通過、與 label 模式電氣等價（TV8）
- [x] 6.8 style=netlist / connection_style=label 舊行為保留（TV9 向後相容）
- [x] 6.9 相同輸入 → 穩定產出（TV10 確定性，force-directed 無 RNG）

## 7. 驗證與收尾

- [x] 7.1 跑全測試（PYTHONPATH 含所有 package 子目錄；python3）
- [x] 7.2 plan-sync + 更新 tasks checkbox
- [x] 7.3 architecture.md 同步（composer placement/style 邊界）— orchestrator 已更新 eda-bridge 行（draftsman 模式 + wire 引擎啟用 + ink_metrics + 預設 netlist 不破壞）
- [x] 7.4 收尾 event_record（實作完成紀錄：Scope/Key Decisions/Verification/Remaining）
