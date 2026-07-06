---
slug: failure-mode/eda/text-overlap-placement-density-bound
title: schematic 文字疊字的結構極限在 placement 密度,emit 位移無解
layer: ragbase
type: failure-mode
confidence: verified
---
# schematic 文字疊字的結構極限在 placement 密度,emit 位移無解

**現象**:emit 層文字防疊(全域 occupancy pass)把 violation 從 161+ 收斂到 total 29 後趨平;繼續硬推 regression 到 173。

**定性**:殘餘全是「同一根 pin 的多類文字天生同位」(pin-name×net-label 同 pin、power-port×pin-name 同端點)——文字可用空間由 placement 密度(per-page pin 子集、cluster 間距、頁面 net 數)決定,超過臨界密度後任何位移策略都無解。

**實測密度標定**(同一引擎,唯一差異是密度):04_wireless 頁 violation=3(合格)、03_memory=18(超標)、product 全板單頁=231(不可行)。

**正解**:compose 前置密度 lint(net 數/元件數/單 symbol pin 數閾值)強制分頁;emit 防疊降級為「密度合格頁的精修」。

**停損教訓**:同類缺陷 2 輪修復不收斂就該升層定性(呼叫層→emit→placement→方法論),不是繼續同層迭代。

## Source evidence

- `distilled_from` → [[extract/issues/assets/20260706/c03/session/readme/md|text: issues/assets_20260706_c03_session/README.md]] @ issues/assets_20260706_c03_session/README.md — source_weight 7

## Related

- → `references` [[issue/schematic-text-render-qa-gap|BR: schematic 文字疊字無渲染層 QA 閘;emit 層防疊已達結構極限,正解在 placement 密度]]
- ← `references` [[workflow/eda/multipage-schematic-generation|connector 密集板多頁 schematic 生成範式(gen_ccm_pages 已驗證)]]

