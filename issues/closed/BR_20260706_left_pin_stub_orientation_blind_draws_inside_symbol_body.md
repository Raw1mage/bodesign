# BR: kicad_emit 左側 pin 的 stub/電源符號/label 方向盲——一律向右展開，把外接件畫進符號本體內

日期：2026-07-06
來源：thesmart_products aiguard C03 v03 審閱 gate（user 人工審圖，01_power 頁）
層級：工具（eda-bridge kicad_emit / composer emit 幾何）
嚴重度：高（C03 審閱 gate 直接判不合格；影響所有含左側 pin 外接件的頁面）
狀態：OPEN

## 現象（硬證據）

`sch_ccm_pages/01_power/` 渲染 PNG（`~/.cache/claude-work/c03-v03/qa_png/01_power-1.png`）：

- U1（STM32N657，矩形符號、左右兩側出 pin）**左排** pin（A19/D4/F1/F12/F7/F8/G1/G2/G6/H1/H2/H6/J1…K16）的電源符號（GND/VDDA/+3V3/+1V8）、stub wire、net label 全部向**右**（符號內部方向）延伸，疊進黃色符號本體、與 pin name 文字互疊成一團，不可讀。
- **右排** pin（K2…W19）same 結構向右外側展開，大致正確——證明 emit 邏輯存在單一固定方向假設（stub 一律 +x），未依 pin 所在邊翻轉。
- User 審閱原話：「左側 pin 腳外接的電阻怎麼畫在 pin 的右邊？這樣全部都畫在格子裏了」→ C03 審閱 gate 判**不合格**。

## RCA

kicad_emit 的 power port / stub / label anchor 幾何以 pin 端點為原點、固定向 +x 方向出線（適用右側 pin），未讀 pin 的 orientation（KiCad pin 有 0/90/180/270 方向屬性）做鏡射。左側 pin（orientation=0，指向 -x 外側）的外接件因此被畫進符號 bbox 內。與 BR_20260706 stub 共線熔合缺陷同屬 power symbol emission 幾何層，但正交：一個是「不同 net stub 共線」，這個是「stub 方向不看 pin 邊」。

## 建議修復

1. `_power_symbol_instance` / stub wire / label anchor 的偏移向量依 pin orientation 決定：左側 pin 向 -x 展開、右側 +x、上下側 ±y（若未來有上下 pin）。
2. 展開後的符號/label bbox 必須落在父符號 bbox **之外**——加 post-emit assert（可併入既有 render_qa / fidelity 閘）：任何 power symbol / label bbox 與元件符號 bbox 相交 → fail-loud。
3. fixture 測試：左右兩側各取一 pin，assert 電源符號座標在符號 bbox 外之正確側。

## 影響範圍

所有由 composer/draftsman 產生、含左側 pin 外接電源件的頁面（CCM 5 頁全部、product 板分頁未來實作）。C03 v03 已因此判不合格；CCM 頁重產（本已因 stamp 短路待重產）必須一併帶此修復。

## 驗證手段

- 修復後重產 01_power 頁 → 渲染 PNG 人工/subagent 視覺 QA：左排外接件全部在符號左外側、無疊字。
- post-emit bbox assert 全 5 頁綠。
- 迴歸 17+ 項全綠。

## Resolution（2026-07-06，engine rev 4c5572223786）

狀態：修復落地，待 orchestrator 全量視覺複驗後關閉。

實作（`kicad_emit.py`）：
1. **方向修復**：新增 `_pin_side(ref, pin)` helper，由 pin symbol-local x 符號判邊（`ex<0`=左/`ex>0`=右，沿用 `_pin_name_box_abs` 既有正確判定）；net loop 建 `endpoint_sides`，三處 `power_endpoints.append` 帶入 side（4-tuple→5-tuple）；power-port 展開 `direction` 由 pin side 決定，取代舊 column-中點啟發（`_x_mid`）——左 pin 一律向 -x（body 外）、右 pin +x。
2. **guard C（post-emit bbox assert）**：emit 尾端掃 power_endpoints，任一 port 落在任何元件符號本體 bbox 內（含 inset 容差）→ `raise ValueError("POWER_PORT_INSIDE_SYMBOL_BODY")` fail-loud。
3. **fixture**（`tests/test_composer_draftsman.py::LeftPinStubOrientationTests`）：LM358 左 pin→GND、右 pin→VCC single-pin net，assert GND port 在左 pin 外側、VCC port 在右 pin 外側。

驗證：draftsman 迴歸 18/18 綠（含新 fixture）；CCM 5 頁以新引擎重產，內建 fidelity gate PASS diff 0/0、signal_balls_lost=0、orphan_nodes=0；01_power + 05_stamp_icd 渲染 PNG 已交 orchestrator 視覺複驗（`~/.cache/claude-work/c03-multiunit/`）。

多 unit 附註：user 裁決「多 unit 拆符號」的語意（每頁只畫該頁相關 pin、降 pin 密度）在 gen_ccm_pages.py 的 DD-6 per-page U1 pin-subset variant（`STM32N657_FULL__<slug>`）已實作達成；KiCad 原生 multi-unit（U1A/U1B 同 ref 另建 lib 格式）未做——因 pin-subset variant 已解 user 主訴（pin 密度）且電氣 fidelity PASS，另建原生 multi-unit lib 屬非必要大重構。EmitComponent 已預埋 `unit` 欄位供未來原生 multi-unit 擴充。
