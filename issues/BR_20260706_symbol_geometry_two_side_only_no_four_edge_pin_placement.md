# BR: draftsman symbol 幾何只支援左右兩側 pin——缺四邊排位（VDD 上緣/GND 下緣），違業界原理圖慣例且為側邊電源符號擁擠的結構根因

日期：2026-07-06
來源：thesmart_products aiguard C03 審閱 gate（user 二次人工審圖）
層級：工具（eda-bridge draftsman/composer symbol 幾何）
嚴重度：高（C03 審閱 gate 二度不合格；且為 BR_20260706_left_pin_stub_orientation_blind 密度殘餘問題的結構根因）
狀態：RESOLVED（待 user 審閱 gate 複驗後關閉）

## 現象（硬證據）

- CCM 5 頁全部：U1（STM32N657）等大 IC symbol 一律只有左右兩側出 pin，上下緣空白。
- User 審閱原話：「你有去看過別人畫的原理圖嗎？一個 block 應該四個邊都有 pin 腳吧？為什麼你畫的只有左右有腳」→ 審閱 gate 判不合格。
- 業界對照：KiCad 官方 STM32 symbol 慣例——VDD/電源 pin 排上緣、VSS/GND 排下緣、訊號 IO 排左右側。
- 連鎖病：02_mcu_core / 03_memory 頁左右窄帶擠入大量電源 pin 的電源符號+label，互疊不可讀（兩輪 fresh-eyes QA FAIL）。根因即「電源 pin 被迫塞側邊」——四邊排法下電源上下移出，側邊只剩訊號，密度自然鬆開。

## RCA

draftsman 的 symbol box 生成（pin 分邊邏輯）只實作 left/right 兩側分配（歷史上按 pin 數對半分或按功能左入右出），無 top/bottom 邊支援。emit 層的 pin orientation 處理也僅覆蓋 0/180（BR_20260706_left_pin_stub 修復時只做了左右鏡射，±y 未做——該 BR 的建議修復第 1 點已預言「上下側 ±y（若未來有上下 pin）」）。

## 建議修復

1. symbol 幾何支援四邊 pin 排位：分類器把 pin 分四組——電源（VDD*/VDDA/VLX*/+*V*）→ 上緣；GND/VSS → 下緣；訊號依流向左入右出。
2. emit 層 stub/電源符號/label anchor 的偏移向量補 ±y 方向（上緣 pin 向上外側、下緣向下外側）。
3. 上下緣 pin 的電源符號天然朝向正確（GND 朝下、VCC 朝上符合 KiCad 慣例），順勢消除側邊密度病。
4. bbox assert（完整 bbox 相交檢查）覆蓋四個方向。

## User 裁決（2026-07-06，覆蓋建議修復第 1 點的分組策略）

User 明確裁決：pin 排位**照實體晶片 pinout 鏡像**，不採功能分組（VDD上/GND下）。原話意旨：「不是應該完全還原實體晶片的 pinout 腳位嗎？不然看圖的人不都要精神錯亂了。」即：

- symbol 四邊排位以**實體封裝腳位座標**決定每支 pin 落在哪一邊、與該邊上的順序。
- BGA：ball 座標 (row letter, col number) 正規化後投影至最近邊（perimeter projection），邊上順序忠於實體座標。
- QFP/QFN 數字腳：標準逆時針 perimeter walk（pin 1 左緣頂端起）。
- 建議修復第 2~4 點（emit ±y、電源符號朝向、四向 bbox assert）不變。

## 影響範圍

所有 draftsman 產生的 schematic 頁（CCM 5 頁 + product 板未來分頁）。C03 v03/v04 交付被此阻塞。

## 驗證手段

- fixture：四邊 pin symbol 產出，assert 各 pin 落邊符合實體座標投影、各邊外接件 bbox 在本體外正確側且互不相交。
- CCM 5 頁重產 → fidelity gate PASS diff 0/0（電氣不回退）+ 渲染視覺 QA 全 PASS。
- 迴歸全綠。

## Resolution（2026-07-06，依 User 裁決的實體鏡像規格實作）

實作（host 工作區，未 commit）：

1. **kicad_symbol.py 四邊幾何**：新增 `_assign_pin_sides` + `_SymbolGeometry`——BGA（`^[A-Z]{1,2}\d+$`）ball 座標 perimeter projection 到最近邊、邊上順序忠於實體；數字腳 ≤24 pin 採 DIP/SOIC 兩側鏡像（右邊由下到上）、>24 pin 採 QFP 逆時針 perimeter walk；混合/無法解析腳號 fail-fast（無 silent fallback）。矩形寬高依四邊 pin 數計算；新增可選 `pin_pitch` 參數（預設 1.27 不變，CCM per-page 50–74-ball subset 用 3.81 防 pin name 互疊）。舊 `_pin_sort_key` 功能分組不再用於分邊。
2. **kicad_emit.py 四向展開**：`_pin_side` 擴為 left/right/top/bottom 四值；power port / stub / label 依邊外展（左 -x、右 +x、上外、下外）；guard C（POWER_PORT_INSIDE_SYMBOL_BODY）四向覆蓋，重產全程未觸發。
3. **gen_ccm_pages.py::build_u1_variant**：原手刻 s-expr 左右雙欄 re-flow 完全繞過引擎（CCM 頁沒用上新幾何的根因），改為重建 `KiCadSymbolPin` 交給引擎 `_symbol_geometry`（pin_pitch=3.81）；電氣（ball number）一字不動。

驗證：引擎迴歸 23/23 綠（含四邊 fixture；實作階段全套 87/0）；CCM 5 頁重產 SSOT 保真閘 PASS diff 0/0（ssot_nets=110、u1_balls_drawn=152、signal_balls_lost=0、orphan_nodes=0，三次重跑一致）；渲染視覺 QA 5 頁全過（05_stamp_icd 黑霧團從根修復；02/03 側邊不再擁擠）；交付已單向拷回 GDrive `03.aiguard/C03-EE/02_build/full_board/sch_ccm_pages/`。

### 追補（2026-07-06 晚，user 二次審圖回饋）

1. **忠實度稽核（user 質疑「真的有遵照實體 pinout？各邊 pin 數不等」）**：逐 pin 稽核 5 頁 U1 variant——由 symbol `at` 座標+rotation 反推實際落邊，獨立從 VFBGA223 ballout 格座標（row→y、col→x、A1 左上）重算預期最近邊，逐 ball 比對 **PASS=315 / FAIL=0**（`~/.cache/claude-work/c03-pitch3x/audit_pinout_fidelity.md`）。投影無 bug（kicad_symbol.py 未改動）；各邊 pin 數不等是 per-page ball 子集實體分佈不均的自然結果，稽核表逐 ball 可查。
2. **pitch 3x（user 指示「pin 間距直接拉大 3 倍」）**：CCM variant `pin_pitch` 3.81 → 11.43（gen_ccm_pages.py:123，host/容器同 inode 一改雙生效）。5 頁重產 overflow=False（01/03 升 A2，02/04/05 維持 A3）、SSOT 保真閘 PASS diff 0/0、渲染複查間距鬆開、交付（工程檔 + `C03_原理圖_*.pdf`）已覆蓋更新。

附註：外部閘 `issues/assets_20260706_c03_session/fidelity_cc.py` 對本多頁 global-label 架構回 FAIL（moved=234，only_baseline=0/only_candidate=0）——經 net-name/節點層直比 `nodes MISSING from candidate=[]` 判定為其 union-find 不處理同名 label 跨頁連接的結構性假陽性，非電氣破壞；驗收以 SSOT 閘為準。
