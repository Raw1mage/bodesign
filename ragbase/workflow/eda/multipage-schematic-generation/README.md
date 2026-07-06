---
slug: workflow/eda/multipage-schematic-generation
title: connector 密集板多頁 schematic 生成範式(gen_ccm_pages 已驗證)
layer: ragbase
type: workflow
confidence: verified
---
# connector 密集板多頁 schematic 生成範式(gen_ccm_pages 已驗證)

**適用**:元件多/connector 密集的板,單頁 compose 必然疊字+短路(見 placement-density failure-mode)。

**範式**(gen_ccm_pages.py,CCM 5 頁保真閘 PASS):
1. 按功能拆 page_nets(power/mcu_core/memory/wireless/stamp_icd),每頁只放該頁 net 涉及的元件。
2. 跨頁 net 靠同名 global label 連通(KiCad 語意)。
3. 大 BGA(STM32N657 222-ball)做 per-page pin 子集渲染——每頁只畫該頁用到的 ball(152→64),黑塊唯一解。
4. connector 密集頁(castellated edge)用 per-pin net label 風格 + all_label(composer T3b spec 旗標),零 drawn wire;MCU/power 頁保留 power symbol 慣例(GND 朝下/VCC 朝上)。
5. 每頁 compose 後跑保真閘(多頁 union)+ 渲染層 text QA。

**密度預算**:每頁密度 ≤ 04_wireless 頁水準(violation=3);03_memory 頁(18)已超標需再拆。

## Source evidence

- `distilled_from` → [[extract/issues/assets/20260706/c03/session/readme/md|text: issues/assets_20260706_c03_session/README.md]] @ issues/assets_20260706_c03_session/README.md — source_weight 6

## Related

- → `references` [[failure-mode/eda/text-overlap-placement-density-bound|schematic 文字疊字的結構極限在 placement 密度,emit 位移無解]]

## ICOM

- **Inputs**: _(none — backfill)_
- **Controls**: _(none)_
- **Outputs**: _(none — backfill)_
- **Mechanisms**: _(none)_

