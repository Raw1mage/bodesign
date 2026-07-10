# BR: draftsman placement 不做圖紙面積規劃——全部元件擠中央窄帶（~20% 利用率），外圍大片空白；label 仍貼線疊字

日期：2026-07-06
來源：thesmart_products aiguard C03 審閱 gate（user 三次人工審圖，四邊 pin 版 01_power 頁）
層級：工具（eda-bridge draftsman placement / composer 佈局規劃）
嚴重度：高（C03 審閱 gate 三度不合格）
狀態：OPEN

## 現象（硬證據）

四邊 pin 幾何落地後的 01_power 頁渲染（user 附圖審閱）：

1. **圖紙利用率 ~20%**：U1（四邊 pin 版）+ 三顆 regulator + 週邊件全部排成**中央一條垂直窄帶**，圖紙左右各 ~40% 完全空白。A3 圖框形同虛設。
2. **元件間距不足**：窄帶內 U1 四邊的電源符號/net label 與 pin、wire 貼疊；三顆 regulator 縱向緊排，各自外接件互相貼近。
3. User 審閱原話：「你只用了圖紙的 20%，其他全空白。非常沒有效率，而且字都擠在線上」→ 判不合格。

## RCA

placement 只做元件相對排序（top-down 功能流），**沒有「圖紙可用面積 → 展開係數」的全域規劃步驟**：
- 元件座標由局部啟發（相鄰/掛件貼附）累加得出，總 bbox 遠小於圖框可用區，且無 post-placement 的 scale-to-sheet / 重心平衡。
- 間距常數是絕對值（mm），未依「本頁元件數 × 外接件密度 ÷ 可用面積」動態放大——空間明明有，卻不用。
- label 疊字是同一根因的下游症狀：元件不散開，per-pin label 帶再怎麼錯位都在窄帶內互擠（先前 BR_20260706_symbol_geometry_two_side_only 與 left_pin_stub 的密度殘餘，正解在 placement 層——與 product 板單頁 all_label 實驗結論一致：placement 密度才是文字疊字的第一因）。

## 建議修復

1. **sheet-fill 規劃步驟**（post-placement、pre-emit）：計算圖框可用區（扣 title block 與邊界 margin）與元件群 bbox，得出 x/y 展開係數，把元件座標按係數重佈（保持相對拓撲），目標利用率 60-80%。
2. **動態間距**：元件間 pitch 依「pin 數 + 掛件數」加權——U1 這種百 pin 大件四周預留 label+電源符號的環形淨空帶（clearance ring），淨空半徑 = max(label 長度) + 電源符號高 + margin。
3. **多欄佈局**：單頁元件多時分 2-3 欄（功能流蛇形走向），而非一條縱帶。
4. **QA 閘**：render_qa 加圖紙利用率檢查（元件群 bbox / 可用區 < 40% → warn；label-wire 交疊沿用既有 bbox 檢查 fail-loud）。

## 影響範圍

所有 draftsman 產生頁（CCM 5 頁 + product 板未來分頁）。與既有兩 BR（left_pin_stub、two_side_only）構成同一 placement/emit 幾何鏈：四邊 pin 解決了「pin 塞側邊」，本 BR 解決「元件塞中央」——兩者都過才可能過視覺 QA。

## 驗證手段

- 重產 01_power → 量測：元件群 bbox 佔可用區 ≥60%；無 label/符號與 wire/pin/本體 bbox 相交；三 regulator 與 U1 間距目視鬆朗。
- fresh-eyes 視覺 QA（subagent）5 頁全 PASS。
- fidelity gate PASS diff 0/0（座標重佈不得動電氣）。
- 迴歸全綠。

## 復發記錄 2026-07-07

第四次人工審圖（05_stamp_lcd 頁）確認同批缺陷仍在且更嚴重：
- 左側 symbol 數十個六角 label 互相重疊、蓋住 pin 號與本體邊緣，完全不可讀
- 垂直 wire 直接穿過 label 文字
- 右側 symbol pin name/number 互疊
- 全頁仍擠左上窄帶、右下大片空白；底部懸空 `SHARED_I2C_SDA` label 未接線
使用者裁決：放棄舊幾何引擎，重構 v2（plans/eda_draftsman-v2），分期：Phase 1 單一 pinout 圖 → Phase 2 排頁。本 BR 由 v2 天然吸收，不再逐項補丁。
