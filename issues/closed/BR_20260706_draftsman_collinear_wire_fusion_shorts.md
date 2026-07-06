# BR: draftsman drawn-wire 共線熔合造成電氣短路 + 引擎無 post-emit 電氣自檢閘

日期:2026-07-06
來源:thesmart_products aiguard C03 v03 schematic 交付 session(15+ 接力棒)

## 現象(含硬證據)

draftsman path 產出的 `.kicad_sch` 在 connector 密集版面上反覆出現「不同 net 被 KiCad 判為同一 net」的真電氣短路,且引擎自身無任何機制攔截,全靠交付 session 內臨時發明的保真閘才發現:

1. CCM stamp 頁:GND 吞 141 節點(期望 50),14 個不同 net(+1V8/+3V3/GND/BAT_SENSE/BOOT0/DBG_UART_RX/TX/NRST/NRST_CAM/PWR_EN/SHARED_I2C_SCL/SDA/SWCLK/SWDIO)短成一團 230 節點。機制:power port stub / stagger jog wire 在同一 x column(x=319.73)共線重疊,KiCad 熔合共線 wire。
2. product 板(全板單頁):`BAT_SENSE` 吞 177 pin;修復後重產又出 `+3V3_PB` 吞 189 pin(draftsman)/196 pin(style=netlist)。機制:`_bus_route` 在密集 x column 用 orthogonal wire 串接 pin,共線熔合。
3. 呼叫層無解已實測窮舉:`connection_style="label"` + `power_ports=False` 仍短(2-node net 在 emit 573-574 行仍走 drawn wire);加 `all_label`(全 net 走 global label)後 wire 仍 372、75 net 塌成 26 連通分量——placement 密度下 label anchor(=pin 絕對座標)共點仍被熔合。
4. `compose_schematic` 的 `validate=True` 路徑(ERC + netlist 匯出)**全程回報成功**,對上述短路零攔截——ERC 不查「網表劃分 vs spec 期望劃分」。

## RCA

- 直接原因:draftsman 的 wire 幾何生成(`_bus_route`、power port stub、stagger jog)只保證「端點正確」,不保證「不同 net 的 wire 不共線/不共點」。KiCad 的 wire 連通語意是幾何的:共線重疊 = 電氣連接。
- 系統原因:引擎信任「我畫了什麼」而從不驗證「KiCad 讀到什麼」。spec 的 net 劃分(SSOT)與 emit 後 kicad-cli 匯出的 netlist 劃分之間,沒有任何等價性檢查。ERC/netlist count 檢查對「net 熔合」型缺陷天然盲(net 數變少、無 dangling,ERC 反而更乾淨)。

## 建議修復

1. **內建 post-emit 保真閘(必做,gate verb)**:把 session 內已驗證的連通分量等價類比對(`fidelity_cc.py` 手法:spec 期望劃分 → union-find;candidate netlist → 連通分量;節點集等價比對,繞過 net 命名)收編為引擎 verb(如 `verify_schematic_fidelity`),`compose_schematic(validate=True)` 預設執行,diff != 0/0 即 fail-loud 拋錯。此閘在 session 內抓出全部三次短路,已證明有效。
2. **wire 幾何防熔合(治本)**:emit 產生任何 wire segment 前,對全局 wire 集合做共線/共點檢查;不同 net 的 segment 共線重疊或端點落他 net wire 上 → 調整 jog 偏移(按 net hash 錯開)或 fail。
3. **connector 密集版面預設 label**:`all_label` 旗標已落地(composer T3b,spec["all_label"]=True);建議升級為自動判定——頁面 connector pin 密度超過閾值時自動切 all_label,並保證 label anchor 不與他 net 幾何共點。
4. **2-node net 的 drawn-wire 逃逸關閉**:emit 573-574 行對 2-node net 的 drawn-wire 分支應尊重 all_label/force_label,現況已修,補迴歸測試釘住。

## 影響範圍

- `packages/eda-bridge/bodesign_eda_bridge/composer.py`(T3/T3b label 推導、validate 流程)
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`(`_bus_route`、power stub、wire emission)
- 所有用 draftsman path 產 schematic 的下游(C03 交付、kidoc HDD 附圖)
- 已有交付物:aiguard CCM 5 頁(已修復、保真閘 PASS diff 0/0);product 板(未收斂,分頁方案中斷)

## 驗證手段

- 迴歸:connector 密集 fixture(≥2 個 Conn_01x36 + 30 元件單頁)compose 後跑保真閘,diff 必須 0/0。
- 現有 17/27 項 unittest 維持全綠。
- 歷史案例回放:aiguard CCM stamp 頁 + product 板 spec 作為 regression fixture(勿含專案私有資料,抽象化後入 tests/)。

## Resolution (2026-07-06)

經 spec `specs/eda_schematic-draftsman-quality` extend（DD-8/DD-11）實作完成：

1. **post-emit 保真閘（建議 1，已收編）**：`fidelity.py verify_partition_fidelity`——spec 期望劃分（union-find）vs kicad-cli 匯出 netlist 連通分量，節點集等價比對（無視 net 命名）；`compose_schematic(fidelity=True)` 接線，diff!=0/0 raise `FidelityError`。MCP schema 已加 `fidelity` 參數。tests/test_fidelity_gate.py 釘住。
2. **wire 幾何防熔合（建議 2，治本，已實作）**：`kicad_emit.py` 全局 fusion_registry——每條 drawn-wire segment 落盤前檢查跨 net 共線重疊/端點落線；衝突 → net-hash 確定性 jog（1-3 grid step）重試 ≤3 次；仍衝突 → 降級 label 並記入 `route_stats.label_fallback_reasons`（可見）。無衝突輸入 byte-equivalent（R6 回歸釘住）。
3. **connector 密集自動判定（建議 3，以密度預算承接）**：`compose_schematic(density_budget=...)` 前置 lint，超標 raise `DENSITY_BUDGET_EXCEEDED` 強制分頁（aiguard 04_wireless PASS / 03_memory FAIL 實測標定），從源頭避免密度超標頁面。
4. **2-node drawn-wire 逃逸（建議 4）**：交付 session 已修；本次防熔合 guard 對 2-pin/3+pin 路徑統一覆蓋 + 迴歸測試（test_kicad_emit 共線 fixture）。

驗證：62 tests OK（含新增防熔合 3 案例 + density 7 案例；TV1-TV10 byte-stable 全綠）。
