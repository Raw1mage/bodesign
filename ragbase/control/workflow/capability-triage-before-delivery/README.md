---
slug: control/workflow/capability-triage-before-delivery
title: 交付前能力分流 gate(禁止產品 session 內做引擎 R&D)
layer: ragbase
type: control
confidence: verified
locator: issues/BR_20260706_methodology_in_session_engine_rnd_antipattern.md
---
# 交付前能力分流 gate(禁止產品 session 內做引擎 R&D)

**規則**:C0x 交付任務開工時列「交付需要的引擎能力 vs 現有能力」清單;缺口預估 >2 輪引擎修改才能補 → 強制分流:引擎能力缺口在工具 repo 開 plan 走 R&D 生命週期,產品 session 用現有能力出「誠實限制版」交付物先審方向。

**違反實例**:aiguard C03 v03——「畫 placement 圖 + schematic 交付」變成 3.5hr/15+ 棒引擎研發馬拉松,交付物未出。deadline 壓力與引擎品質工程綁同一條線,兩頭輸。

**配套硬規**:(1) 2 輪收斂停損——同類缺陷連續 2 輪修復未收斂,禁止第 3 輪同層迭代,必須升層定性並回報 user;(2) 交付層 QA 先行——先寫渲染層機器 QA + baseline 才准開始修復迭代;(3) 引擎單一持有權——共享可變狀態(引擎目錄)同一時間至多一棒可寫;(4) 引擎改動前強制快照,dispatch 紅線禁 git 回退。

## Source evidence

- `distilled_from` → [[extract/issues/assets/20260706/c03/session/readme/md|text: issues/assets_20260706_c03_session/README.md]] @ issues/assets_20260706_c03_session/README.md — source_weight 6

## Related

- → `references` [[issue/methodology-in-session-engine-rnd-antipattern|BR(方法論): 產品交付 session 內做引擎 R&D 的反模式——收斂預算、能力分流、QA 前置三缺失]]

