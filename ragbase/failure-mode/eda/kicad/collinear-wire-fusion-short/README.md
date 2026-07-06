---
slug: failure-mode/eda/kicad/collinear-wire-fusion-short
title: KiCad drawn-wire 共線熔合短路(draftsman path)
layer: ragbase
type: failure-mode
confidence: verified
---
# KiCad drawn-wire 共線熔合短路(draftsman path)

**症狀**:compose 產出的 .kicad_sch 中不同 net 被 KiCad 判為同一 net(net 熔合),netlist 匯出後某 net 吞併異常多節點。實例:GND 吞 141(期望 50)、BAT_SENSE 吞 177、+3V3_PB 吞 189。

**機制**:KiCad 的 wire 連通語意是幾何的——共線重疊/共點 = 電氣連接。draftsman 的 `_bus_route`、power port stub、stagger jog 只保證端點正確,不保證不同 net 的 wire 不共線。connector 密集 x column 上 orthogonal wire 必然共線熔合。

**為何 ERC/validate 抓不到**:net 熔合讓 net 數變少、無 dangling,ERC 反而更乾淨。唯一有效檢測是連通分量等價類比對(spec 期望劃分 vs netlist 實際劃分,繞過 net 命名)。

**呼叫層無解(已窮舉實證)**:connection_style=label、power_ports=False、all_label 全覆蓋皆 FAIL——placement 密度下 label anchor(=pin 絕對座標)共點仍熔合。正解:分頁稀疏化(gen_ccm_pages 範本已驗證 PASS)或引擎 wire 幾何防熔合。

見 BR_20260706_draftsman_collinear_wire_fusion_shorts.md + issues/assets_20260706_c03_session/fidelity_cc.py。

## Source evidence

- `distilled_from` → [[extract/issues/assets/20260706/c03/session/readme/md|text: issues/assets_20260706_c03_session/README.md]] @ issues/assets_20260706_c03_session/README.md — source_weight 7

## Related

- → `references` [[issue/draftsman-collinear-wire-fusion-shorts|BR: draftsman drawn-wire 共線熔合造成電氣短路 + 引擎無 post-emit 電氣自檢閘]]
- → `references` [[workflow/eda/schematic-fidelity-gate|連通分量等價類保真閘(schematic 電氣正確性驗收)]]

