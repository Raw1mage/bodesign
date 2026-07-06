---
slug: failure-mode/qa/model-layer-vs-render-layer-mismatch
title: 模型層 QA 過、渲染層 FAIL 的量測層錯位
layer: ragbase
type: failure-mode
confidence: verified
---
# 模型層 QA 過、渲染層 FAIL 的量測層錯位

**症狀**:程式化 QA 宣稱 0 缺陷,fresh-eyes 視覺 QA 判 FAIL。連續兩輪發生。

**根因**:QA 在 schematic 模型層量 label 錨點座標,交付判準在渲染層(SVG/PDF 像素)。兩層之間隔著 KiCad 文字寬度/justify/rotation 語意——模型層估算天然盲區;且第一輪只量 net label 一類,漏掉 pin-name/pin-number/refdes-value/power-port Value 四類渲染文字。

**通則**:「可量測的 QA 若不在交付層,過了也不算過。」生成→渲染類交付必須以渲染結果為 QA 對象(掃 SVG 全部 <text> bbox,交疊>15% 即 violation)——qa_svg_text.py 是唯一與人眼判定對齊的機器閘。

**收斂數據**:引入渲染層 QA 前兩輪假收斂;引入後 37/32/38/26/161/231 → 修至 13/6/18/3/2/53,量測才真實。

見 BR_20260706_schematic_text_render_qa_gap.md + assets qa_svg_text.py。

## Source evidence

- `distilled_from` → [[extract/issues/assets/20260706/c03/session/readme/md|text: issues/assets_20260706_c03_session/README.md]] @ issues/assets_20260706_c03_session/README.md — source_weight 7

## Related

- → `references` [[issue/schematic-text-render-qa-gap|BR: schematic 文字疊字無渲染層 QA 閘;emit 層防疊已達結構極限,正解在 placement 密度]]

