# Proposal: quality_deterministic-preplacement

## Why

- E2E 實證（`specs/validation/prd-to-gerber-e2e/`）已量測 G3 基線：grid placement 零電氣感知——C1(100nF) decap 距 LED 負載群 >30mm（違 R1/R8）、M3 安裝孔撞 USB-C courtyard（DRC 1 violation）。小板佈通率 100% 靠板小，品質輸給規則。
- 知識徵集已收斂路線：arXiv 2602.23540 去 RL 化確定性擺件方法 + 專利規則表 R1-R18（ragbase repo scope：`workflow.preplacement-deterministic` + 3 concept）。
- 天條對齊：確定性演算法（固定 seed）可重現、可驗證，LLM 不參與擺件計算——符合「展示可靠度而非宣稱」哲學。

## Original Requirement Wording (Baseline)

- 「再檢索公開github找符合需求的軟體，或根據你學習的知識設計軟體工具」（validation/prd-to-gerber-e2e 徵集結論的工具化落地；使用者以「2」批准開案）

## Requirement Revision History

- 2026-07-03: initial draft created via plan-init.ts
- 2026-07-03: filled from E2E gap report + knowledge-acquisition conclusions（G3 立案證據）

## Effective Requirement Description

1. 在 ee worker 新增確定性 pre-placement 工具（`bodesign_place_pcb` 或升級現有 net2pcb placement 段）：主 IC 錨定 → pin 歸屬先驗分群 → 環帶格點貪婪初擺 → 固定 seed SA 微調。
2. 生成規則注入：專利 R2/R3/R7（decap 背面對置／專屬 ground via／多 via）；擺後檢查 R1（decap 距離）/R8（迴路面積）並輸出規則違反清單。
3. 基線對比驗證：同一 LED driver 案（16 零件 10 net）重跑，量化對比 grid 基線——decap 距離、courtyard 違規數、佈線後 DRC/佈通率。
4. KiCad-Autoplace（MIT）1 天 spike：實測 vs grid 基線，決定引入 or 自研全走（spike 結論記入 design.md DD）。

## Scope

### IN
- ee worker 側 placement 演算法（純確定性、固定 seed）、規則檢查器（R1/R8）、與 route_net2pcb 工具鏈銜接、LED driver 案基線對比。

### OUT
- PDN/decap checker 自研（另案）、length_match_bus 升級（另案）、RL/ML 擺件、多板型泛化調參、autorouter 更換。

## Non-Goals

- 不追求商用 EDA 級擺件品質；目標是「電氣感知 ≥ 明顯優於 grid、規則違反可解釋」。
- 不做互動式手動擺件 UI。

## Constraints

- 純 Python + pcbnew（ee worker 既有 toolchain），不引入重依賴。
- 確定性：同輸入同輸出（固定 seed），否則違反可重現驗證哲學。
- 規則值必須帶來源錨點（專利號/論文 id），無錨點規則不硬編碼（no-silent-fallback）。
- KiCad-Autoplace 若引入需 MIT 授權相容審查。

## What Changes

- `packages/eda-bridge/bodesign_eda_bridge/`：新增 placement 模組（或改造 net2pcb grid 段）。
- `services/mcp/server.py`：若新增獨立工具則補 handler + schema。
- 規則表落盤（R1-R18 中擺件相關子集，帶錨點）。

## Capabilities

### New Capabilities
- deterministic pre-placement: 電氣感知確定性擺件（錨定+分群+貪婪+SA），取代天真 grid。
- placement rule check: 擺後 R1/R8 檢查，輸出可解釋違反清單。

### Modified Capabilities
- `route_net2pcb`: placement 段可選 `strategy: grid|deterministic`（grid 保留為對照基線，非 fallback）。

## Impact

- `packages/eda-bridge/`（ee worker）、`services/mcp/server.py`、`skills/bodesign/stages/c04-*/GUIDE.md`（擺件段落）、tests。
- 證據鏈：ragbase repo scope 的 `workflow.preplacement-deterministic` 為設計骨架 SSOT。
