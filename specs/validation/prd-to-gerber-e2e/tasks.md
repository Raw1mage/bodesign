# Tasks: validation_prd-to-gerber-e2e

## 1. 知識徵集（三路並行 subagent）

- [x] 1.1 專利線：patentmcp 檢索擺件/decap/EMC 規則（18 條，R1-R18，16 專利錨點）
- [x] 1.2 arXiv 線：擺件/佈線/PDN 演算法評估（12 篇＋前 3 名自研 MVP 設計）
- [x] 1.3 GitHub 線：OSS 候選判定（13 項；KiCad-Autoplace 首選、PDN checker 自研）
- [x] 1.4 ragbase 沉澱：3 source → 3 asset → 3 extract → 1 workflow + 3 concept（plan scope）

## 2. E2E 實證：USB LED driver（compose 路徑 PRD→Gerber）

- [x] 2.1 C00：consultant intake → readiness → emit PRD（answer_state.json + Project_Requirements + Handoff）
- [x] 2.2 C03：compose_schematic(draftsman, label) → ERC → netlist（16 零件 10 net；ERC 6 errors 全為 power-only 刻意 NC 殘留）
- [x] 2.3 C04：route_net2pcb（grid 基線）→ freerouting autoroute（100% 佈通，99 seg/4 via）→ GND pour → DRC gate（1 違規：J1×H2 courtyard）
- [x] 2.4 Fab：emit_fab（gerber 25 檔＋drill＋pos＋STEP＋PDF）→ render_gerber_preview（F.Cu PNG 實渲）
- [x] 2.5 缺口報告：G3 擺件品質基線證據＋G4 vault 冷啟動＋工具 friction 清單（research/gap-report-draft.md）

## 3. 收尾

- [x] 3.1 收尾 event_record（done；scope=plan:validation/prd-to-gerber-e2e）
- [x] 3.2 Friction→BR 掃描（3 BR：bodesign×2（REF** 假成功 High、T1-T8 彙整）+ specbase×1（producer 參數命名/CJK FTS）；已 ragbase_project_issues 投影）
