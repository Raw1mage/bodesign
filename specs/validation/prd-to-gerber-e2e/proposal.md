# Proposal: validation_prd-to-gerber-e2e

## Why

- 沙盤推演（2026-07-03）判定 compose 路徑「理論上」可 PRD→Gerber 走通，但 G3（擺件智能=天真網格）、G4（vault 冷啟動）只有紙上證據。需一次真實小案實跑，把痛點打成實測證據；並行徵集公開專業知識（專利/論文/OSS），決定「引 OSS 工具 vs 自研確定性工具」方向。

## Original Requirement Wording (Baseline)

- 「實證測一測。建議使用patentmcp去檢索公開專利知識，使用arxiv檢索論文，補足專業知識，建立ragbase，再檢索公開github找符合需求的軟體，或根據你學習的知識設計軟體工具」

## Requirement Revision History

- 2026-07-03: initial draft created via plan-init.ts
- 2026-07-03: filled from user directive（E2E 實證 + 三線知識徵集 + ragbase + 工具方向）

## Effective Requirement Description

1. compose 路徑 E2E 實跑：C00 PRD → C03 原理圖（ERC）→ C04 `.kicad_pcb`（DRC gate）→ Gerber + preview，全程工具真跑、證據落盤 `.work/e2e-led-driver/`。
2. 每站記錄實際痛點（工具缺口、知識缺口、手動介入點），對照 G1-G4 驗證/推翻。
3. 知識徵集三線（patentmcp 專利 / arXiv 論文 / GitHub OSS），findings 帶可追溯錨點（專利號/arXiv id/repo）。
4. 知識沉澱 ragbase（`plan:validation/prd-to-gerber-e2e` scope，收尾 rescope repo）。
5. 缺口報告：工具建設優先序（OSS 引入 vs 自研確定性工具）。

## Scope

### IN
- E2E 實跑（USB 供電 LED driver 小案）、知識徵集三線、ragbase 沉澱、findings.md 缺口報告。

### OUT
- ato 路徑主線（G1 wrapper 未補，另案）、send-to-fab、實體打樣、新工具實作（本案定方向）。

## Non-Goals

- 不做 IC 級 EDA placement；目標場景是 <100 零件小板。
- 不在本案內修 bodesign 工具缺陷（記 findings，另開 plan）。

## Constraints

- bodesign 天條：驗證/比對零 LLM、no silent fallback、datasheet-grounded 規格值。
- 專利檢索萃取通用工程規則，不做 FTO 分析。
- OSS license 邊界：GPL 只能 subprocess 隔離。

## What Changes

- 新增 `.work/e2e-led-driver/` 實證工件 + `findings.md`；ragbase 新增擺件/佈線/EMC 知識物件；無 production code 變更。

## Capabilities

### New Capabilities
- 實證基線：PRD→Gerber 全程可行性與痛點清單（後續工具開發的需求輸入）。

### Modified Capabilities
- （無）

## Impact

- 後續 plans（pre-placement 指導工具、autoroute 強化、vault 批次 ingest）的立案依據；`specs/architecture.md` Immediate Capability Gaps 段落可能更新。
