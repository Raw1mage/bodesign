# BR: schematic 文字疊字無渲染層 QA 閘;emit 層防疊已達結構極限,正解在 placement 密度

日期:2026-07-06
來源:thesmart_products aiguard C03 v03 schematic 交付 session

## 現象(含硬證據)

同一類「渲染文字互疊糊成黑塊」缺陷連續 4 輪修復-驗證循環未收斂,且前兩輪出現「程式化 QA 全過、fresh-eyes 視覺 QA FAIL」的量測層錯位:

1. 第 1 輪:引擎 label 防疊(錨點同點檢查)後聲稱「bbox QA 全過」→ 視覺 QA 判 05/06 頁 FAIL(label 群糊塊)、01/02/03 CONCERNS。
2. 第 2 輪:bbox 防疊重寫後程式化 QA 6 頁 0 重疊 → 視覺複查仍 3 頁 FAIL——因 QA 只量 net label 錨點,漏掉 IC pin-name/pin-number、refdes/value property、power-port Value 等其餘四類渲染文字。
3. 第 3 輪:發明 `qa_svg_text.py`(掃渲染 SVG 全部 `<text>` bbox,交疊>15% 即 violation)才首次量到真相:6 頁 37/32/38/26/161/231 → 修至 13/6/18/3/2/53。
4. 第 4 輪 + 引擎重構棒:單一全域 occupancy pass 最佳收斂 total 29 後趨平;殘餘全是「同一根 pin 的多類文字天生同位」(pin-name×net-label 同 pin、power-port×pin-name 同端點)的結構性擁擠,emit 位移已無解;重構棒繼續硬推反而 regression 到 173。

## RCA

- 量測層錯位:QA 一直在 schematic 模型層(錨點座標)量,交付判準在渲染層(SVG/PDF 像素)。兩層之間隔著 KiCad 的文字寬度、justify、rotation 語意,模型層估算天然有盲區。**「可量測的 QA 若不在交付層,過了也不算過。」**
- 結構性根因:文字疊字的上游是 **placement 密度**——per-page pin 子集、元件 cluster 間距、頁面 net 數決定了文字可用空間。emit 層防疊是在密度既成事實後「擠牙膏」,超過臨界密度後任何位移策略都無解(04_wireless 頁 violation 3 vs product 單頁 231,同一引擎,唯一差異是密度)。

## 建議修復

1. **收編 `qa_svg_text.py` 為引擎 gate verb(必做)**:渲染後掃 SVG 全 `<text>` bbox 的交疊檢查(session 已驗證能精準對應人眼判定),作為 schematic 渲染交付的機器閘;`violation=0` 才允許宣稱呈現層完成。放 `packages/eda-bridge/` 或 skill scripts,含在 c03-ee GUIDE 的交付 checklist。
2. **頁面密度預算(placement 層,治本)**:compose 前置 lint——每頁 net 數 / 元件數 / 單 symbol pin 數超過經驗閾值(以 aiguard 04_wireless 頁 = PASS、03_memory 頁 = FAIL 的實測數據標定)即拒絕單頁、強制分頁。這一條可把「先產出→視覺 QA 打回→再修」的循環,換成「產前預防」。
3. **emit 全域 occupancy(保留但降級為輔助)**:重構棒的單一 TextBox 佔用集方向正確(161→29),值得收編,但定位是「密度合格頁面的精修」,不是密度超標的救火。
4. **refdes/value 動態擺位** 已部分落地(`_place_symbol_props`),補測試釘住。

## 影響範圍

- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`(文字放置全部路徑)
- `packages/eda-bridge/bodesign_eda_bridge/composer.py`(placement/分頁決策)
- skill `bodesign` c03-ee GUIDE(交付 checklist 需加渲染層 QA 閘)
- kidoc 文件引擎的 schematic 附圖品質

## 驗證手段

- `qa_svg_text.py` 對 aiguard CCM 5 頁現況跑出 13/6/18/3/2(known baseline);任何引擎文字改動後此數字只准降不准升。
- 密度 lint 用 aiguard 實測數據標定:04_wireless(PASS, v=3)為合格上限參考,03_memory(FAIL, v=18)為超標下限參考。
- 視覺 QA(subagent fresh-eyes 看 PNG)仍為最終判準,機器閘 0 violation 後至少一輪。

## Resolution (2026-07-06)

經 spec `specs/eda_schematic-draftsman-quality` extend（DD-9/DD-10）實作完成：

1. **qa_svg_text 收編為引擎 gate verb（建議 1）**：`render_qa.py qa_svg_text`（掃 kicad-cli SVG 全部 `<text>` bbox，交疊>15% 即 violation）收編進 `packages/eda-bridge/`，並註冊為 `skills/bodesign/scripts/gate.py` landing verb `qa_svg_text`（免容器）。c03-ee GUIDE done-criteria 已加「render-layer text QA violation=0」+「fresh-eyes 視覺 QA 一輪」兩閘。
2. **頁面密度預算（建議 2，治本）**：`compose_schematic(density_budget=...)`——`DENSITY_BUDGET_DEFAULTS`（max_nets_per_page=20 / max_components_per_page=15 / max_pins_per_symbol=64，aiguard 04_wireless PASS v=3 / 03_memory FAIL v=18 兩點標定）；超標 raise `DENSITY_BUDGET_EXCEEDED`（fail-fast、建議分頁、可顯式 override）。
3. **emit 全域 occupancy（建議 3）**：交付 session 的單一 occupancy pass 已收編於 kicad_emit（pin-name/prop-text 佔用集），定位為密度合格頁的精修（DD-10）。
4. **refdes/value 動態擺位（建議 4）**：`_place_symbol_props` 已落地，迴歸由既有 emit 測試覆蓋。

回歸基線（aiguard CCM 5 頁 13/6/18/3/2）記載於 render_qa.py docstring 與 spec DD-9，「只准降不准升」。
驗證：62 tests OK；gate.py --list 含 qa_svg_text。
