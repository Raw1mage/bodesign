---
slug: workflow/eda/schematic-fidelity-gate
title: 連通分量等價類保真閘(schematic 電氣正確性驗收)
layer: ragbase
type: workflow
confidence: verified
---
# 連通分量等價類保真閘(schematic 電氣正確性驗收)

**用途**:驗證 compose 產出的 schematic 電氣劃分與 spec 定義等價——唯一能抓 net 熔合短路的檢查。

**步驟**:
1. 期望劃分 SSOT:exec spec 生成腳本 + compose stub,dump merged nets(dump_expected.py 手法)。**勿用 compose 匯出的 .net 當 baseline**(可能已污染——實戰中 baseline .net 184 nets/HSE_IN 吞 241 就是污染品)。
2. candidate:kicad-cli 匯 netlist → union-find 重建連通分量(多頁 union:跨頁同名 global label 連通)。
3. 節點集等價類比對(繞過 net 命名,只比節點集合),diff 必須 0/0。

**實戰戰績**:抓出全部 3 次共線熔合短路;CCM 5 頁最終 PASS diff 0/0。

種子:issues/assets_20260706_c03_session/fidelity_cc.py + dump_expected*.py。BR1 要求收編為 compose validate 內建閘。

## Source evidence

- `distilled_from` → [[extract/issues/assets/20260706/c03/session/readme/md|text: issues/assets_20260706_c03_session/README.md]] @ issues/assets_20260706_c03_session/README.md — source_weight 7

## Related

- → `references` [[issue/draftsman-collinear-wire-fusion-shorts|BR: draftsman drawn-wire 共線熔合造成電氣短路 + 引擎無 post-emit 電氣自檢閘]]
- ← `references` [[failure-mode/eda/kicad/collinear-wire-fusion-short|KiCad drawn-wire 共線熔合短路(draftsman path)]]

## ICOM

- **Inputs**: _(none — backfill)_
- **Controls**: _(none)_
- **Outputs**: _(none — backfill)_
- **Mechanisms**: _(none)_

