# Handoff: eda_schematic-draftsman-quality

## Execution Contract

升級 `compose_schematic`：新增 opt-in `style="draftsman"`（subsystem-clustered force-directed placement + drawn-wire + sheet-fit + ink 驗收），**預設 `style="netlist"` 維持既有行為零破壞**（使用者 2026-06-19 決策）。複用既有 `kicad_emit.py` wire 引擎，不改其幾何正確性。

## Required Reads

- `plans/eda_schematic-draftsman-quality/design.md`（DD-1..DD-7，特別 DD-3 opt-in 決策、Code Anchors）
- `plans/eda_schematic-draftsman-quality/data-schema.json`（ComposeSpec/Cluster/RouteStats/SheetFit/InkMetrics 契約）
- `packages/eda-bridge/bodesign_eda_bridge/composer.py`（待改：`_auto_place`:33、預設 connection_style:49、AI/tool split:62-68）
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`（複用：`emit_kicad_schematic`:212、`_orthogonal_route`:386、`_bus_route`:406、grid-snap:254-261、`load_symbol`）
- `services/mcp/server.py`（`bodesign_compose_schematic` schema + handler）

## Stop Gates In Force

- **不破壞既有預設**：`style="netlist"`（預設）必須與升級前 byte-equivalent。任何讓既有呼叫者行為改變的改動 → 先停。
- **placement fail-fast**：分群失敗 / symbol 缺失 / net 無法解析 → 顯式報錯 + 缺項清單，不以預設座標靜默續跑（天條）。
- **ink toolchain 缺失**：缺 pdftoppm/poppler/PIL → measurement_unavailable，不偽造度量。
- **確定性鐵律**：force-directed 不得引入 RNG；相同輸入必須穩定輸出。
- **不改 kicad_emit 幾何**：只複用 wire/junction 引擎，不動其正確性。
- **architecture.md 邊界變更**：composer placement/style 邊界，收尾前同步。

## Validation Plan

- 全測試：`PP=$(ls -d packages/*/ | tr '\n' ':') && PYTHONPATH="$PP" python3 -m unittest tests.<module> -v`。
- 關鍵回歸：style=netlist byte-equivalent（TV9）、force-directed 確定性（TV10）、draftsman ink% > netlist 基準（TV6）、kicad-cli validate 通過（TV8）。

## Execution-Ready Checklist

- [x] design / data-schema / sequence / idef0 / grafcet 完成且驗證
- [x] DD-3 決策定案（opt-in draftsman、預設 netlist）
- [x] 複用引擎已定位（kicad_emit wire path 已存在）
- [x] core/worker 邊界明確（placement + ink 屬 core pure-python）
- [ ] 實作依 tasks.md phase 1→7 順序
