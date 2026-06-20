# Proposal: eda_schematic-draftsman-quality

## Why

- `bodesign_compose_schematic` 產出的 `.kicad_sch` 電氣正確（ERC-clean、pin→net 正確、`kicad-cli validate` 通過），但**視覺上完全不是一張電路圖**。實測著墨率 3-6%（真實 KiCad 手繪通常 15-40%），9 個 symbol 散佈整張 A4 卻無一條導線相連。
- 下游 C03 若要當「完整電路圖」交付，不成立——目前只能退回 KiCad GUI 人工繪製，這正是本 BR 要消除的缺口。
- 來源：`issues/issue_20260618_compose_schematic_draftsman_quality.md`（major，C03 核心交付實質缺失）。

## Original Requirement Wording (Baseline)

- "compose_schematic（或新增一個 compose_schematic_drawn / --style=draftsman 模式）應能產出人看得懂的電路圖"，至少滿足：有意義的 placement（net 鄰接 / 子系統分群）、實體導線（點對點畫 wire+junction，bus/跨 sheet 才退回 label）、sheet 自適應 fit 內容、用 ink/bbox 量化驗收並可回歸測試。

## Requirement Revision History

- 2026-06-19: initial draft created via plan-init.ts
- 2026-06-19: 草案填寫，方向經使用者確認——placement 採「先子系統分群、群內 force-directed 微調」；走 plan-builder design-first。

## Effective Requirement Description

1. **Meaningful placement**：以子系統分群（spec 宣告 group / net-degree clustering）把相關元件聚在一起、被動件靠近其主 IC，取代現行 `_auto_place(index % columns)` 網格。群內以確定性 force-directed（spring）微調避免重疊。
2. **實體導線（opt-in draftsman）**：新增 `style="draftsman"` 旗標才走 drawn-wire（`connection_style="wire"` 已存在於 `kicad_emit.py`），點對點 net 畫 wire+junction；bus / power / 單 pin / 跨 sheet 才退回 label。**預設 `style="netlist"` 維持既有 label+grid 行為（零破壞，使用者 2026-06-19 決策）**。
3. **Sheet 自適應**：sheet 尺寸 fit 內容（或內容填滿 sheet），消除「浮在空白」。
4. **量化驗收**：ink/bbox 度量（pdftoppm + PIL）納入回歸測試，著墨率與內容佔版面比明顯改善且可回歸。

## Scope

### IN
- `composer.py`：placement 演算法（subsystem clustering + 群內確定性 force-directed）、預設 connection_style 切換、sheet-fit。
- spec 輸入擴充：允許 component 宣告 `group` / `subsystem`（向後相容，無宣告時走 net-degree 推導）。
- 驗收：ink/bbox 度量工具 + 回歸測試 vector（pdftoppm + PIL）。
- 相關 MCP 工具 schema（`bodesign_compose_schematic`）若需新增參數則同步。

### OUT
- 不重寫 KiCad GUI 級的互動繪圖引擎。
- 不碰 layout / fab 路徑（C04 `route_net2pcb` / `emit_fab` 等）。
- 不改 `kicad_emit.py` 既有 wire/junction 幾何引擎的正確性（已驗證可用），僅在其上組裝 placement + 預設切換。

## Non-Goals

- 不追求與商用 EDA 自動佈線/佈局同級的美學；目標是「工程師看得懂、著墨率合理、可回歸量化」。
- 不引入隨機性破壞回歸可重現性——force-directed 必須是確定性（固定 seed / 確定性初始化）。

## Constraints

- **No silent fallback**（repo 天條）：placement 無法分群、symbol 缺失、net 無法解析時 fail-fast + 顯式報錯 + 缺項清單，不以預設座標靜默續跑。
- **確定性可回歸**：相同輸入必須產出 byte-stable（或 ink 度量穩定）結果，force-directed 用固定初始化。
- core vs worker 邊界：placement 與 ink 度量屬 pure-python（core 側）；pdftoppm 渲染若依賴 KiCad/poppler toolchain，量測工具須對缺 toolchain 顯式報 unavailable，不偽造度量。
- 向後相容：既有呼叫者（無 group、connection_style=label）行為不破壞。

## What Changes

- `compose_schematic` 新增 opt-in `style="draftsman"`，提供「subsystem-clustered force-directed placement + drawn-wire + sheet-fit」並可量化驗收；**預設 `style="netlist"` 維持既有「naive grid + label」行為不變**。
- 既有 `kicad_emit.py` 的 wire/junction 引擎在 draftsman 模式下被啟用（目前 composer 預設 label，等於沒用到）。

## Capabilities

### New Capabilities
- **Subsystem-clustered placement**：依宣告 group 或 net-degree clustering 分群擺放。
- **群內 force-directed 微調**：確定性 spring 模型消除重疊、聚攏相關件。
- **Sheet-fit**：依內容 bbox 自適應 sheet 尺寸 / 邊距。
- **Ink/bbox 量化驗收**：pdftoppm + PIL 度量著墨率與內容佔版面比，納入回歸測試。

### Modified Capabilities
- `bodesign_compose_schematic`：預設 connection_style 由 `label` 改為 drawn-wire（或新增 `style=draftsman` 旗標，design 階段決定）；接受 component `group` 宣告。

## Impact

- 程式：`packages/eda-bridge/bodesign_eda_bridge/composer.py`（placement + 預設切換 + sheet-fit）；可能新增度量模組（ink/bbox）。
- 既用引擎：`packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`（`emit_kicad_schematic` 的 wire/`_orthogonal_route`/`_bus_route`/grid-snap，本 plan 直接複用）。
- MCP：`services/mcp/server.py` 的 `compose_schematic` handler + schema（若新增參數）。
- 測試：`tests/`（新增 ink/bbox 回歸 + placement 單元測試）。
- 下游：C03 整合（aiguard 等）可直接拿可讀 schematic 交付。
