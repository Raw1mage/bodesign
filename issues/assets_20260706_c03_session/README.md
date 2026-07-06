# aiguard C03 v03 session 驗證資產(2026-07-06)

來源:thesmart_products aiguard C03 v03 交付 session 的 scratch(~/.cache/claude-work/c03-v03/,volatile)。
這些是 4 份 BR_20260706_* 引用的「已實戰驗證」種子腳本,收編進引擎時以此為基礎,勿重新發明。

- fidelity_cc.py — 連通分量等價類保真閘(BR1 種子)。繞過 net 命名,union-find 重建 candidate 全板網 vs spec 期望劃分。實戰抓出全部 3 次共線熔合短路(GND 141 / BAT_SENSE 177 / +3V3_PB 189)。教訓:baseline 不可用 compose 匯出的 .net(可能已污染),SSOT 是 spec 電氣定義 dump。
- qa_svg_text.py — 渲染層文字疊字 QA(BR2 種子)。掃渲染 SVG 全部 <text> bbox,交疊>15% 即 violation。是唯一與 fresh-eyes 視覺判定對齊的機器閘;模型層錨點 QA 有結構盲區。
- dump_expected.py / dump_expected_product.py — 期望劃分 dump(exec spec 腳本 + compose stub,取 merged nets 為 SSOT)。
- gen_ccm_pages.py — CCM 5 頁分頁生成器(成功範本:按功能拆 page_nets、每頁稀疏、跨頁同名 global label 連通;保真閘 PASS diff 0/0)。
- gen_product_v3.py / v4.py — product 板失敗記錄(v3=netlist style 仍短路;v4=all_label 全覆蓋仍短路)→ 鐵證:根因在 placement 密度,不在 label/wire 選擇。BR2 密度預算 lint 的實證依據。

已知實測數據(BR2 密度標定用):04_wireless 頁 violation=3(合格參考)、03_memory=18(超標參考)、product 全板單頁=231(不可行)。
