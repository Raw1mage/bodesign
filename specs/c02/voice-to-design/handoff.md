# Handoff: c02_voice-to-design

## Execution Contract

實作剩餘三環（前端抽取 DD-1 / 反問補全 DD-2 / 編排 DD-4）；末端渲染 DD-3 已完成。

## Required Reads

- `design.md` — DD-1~4 決策（尤其 DD-2 fail-fast 不猜尺寸、approval gate）
- `data-schema.json` — SpokenIntentInput / C02ConstraintDraft / ClarifyingQuestion / IntentPlanResult 契約
- `packages/workflow-core/bodesign_workflow_core/requirement_planning.py` — 要仿的 plan_design_intent 抽取骨架
- `packages/workflow-core/bodesign_workflow_core/c02_me_package.py` — assess_c02_constraint_readiness 的 8 欄位 + generate_openscad 簽名

## Stop Gates In Force

- **不猜尺寸**：wall/clearance/lid 及任何顯式尺寸必來自抽取或答覆，抽不到轉澄清問題（DD-2）
- **approval gate**：約束齊備時只回 ready-for-approval + 約束集，須 approve=true 才生 source（DD-4）
- **次要約束不擋**：heat/antenna/battery/environment 缺失標 missing 但不擋 source 草稿（對齊 38% 實跑）

## Execution-Ready Checklist

- [x] 渲染缺口已補（DD-3，前一 session）
- [x] 要仿的基礎設施已讀透（plan_design_intent / c02 readiness / c01 反問迴圈）
- [x] 跨 package 編排定案放 MCP server handler
