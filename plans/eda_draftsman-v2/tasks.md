# Tasks: eda_draftsman-v2

## 0. 基礎（TDD 紅線前置）

- [x] 0.1 kiutils 選型驗證：kiutils 1.4.8 讀 MCU_ST_STM32H7→抽符號寫 .kicad_sym→嵌 .kicad_sch→重解析→kicad-cli 9.0.9 render exit 0（53KB SVG）；KiCad 9 方言無相容問題
- [x] 0.2 fidelity.py / render_qa.py 補獨立單元測試：tests/test_fidelity_gate.py（faithful pass + fusion/split fail）、tests/test_render_qa_gate.py（clean pass + stacked fail）皆綠，只加測試未改行為
- [x] 0.3 KiCad 官方 symbol 庫落地與索引：庫在 /usr/share/kicad/symbols（系統安裝，kicad 9.0.9）；symbol_index.py（resolve lib_id→(path,Symbol) / search 覆蓋掃描 / SymbolNotFound=SYMBOL_GAP）；**STM32N657/STM32N6 官方庫零覆蓋**（MCU_ST 最高到 H7/U5），aiguard C03 主控必落缺口清單

## 1. Phase 1 — 單一 pinout 圖

- [x] 1.1 `symbol_resolver.py`：BOM MPN → 官方 lib_id + pin_map；產 symbol 覆蓋率報告 + SymbolGap 缺口清單（aiguard C03 全 BOM 跑一輪）— 覆蓋率 3.4%(1/29)，誤配已剔除，缺口清單 disposition=pending 待 1.2；tests 5/5 綠，雙閘不退化 8/8
- [x] 1.2a STM32N657 vendor CAD 匯入（DD-7）：LCSC C42457345 STM32N657L0H3Q 經 easyeda2kicad 取真 KiCad symbol，入 vendor_symbols/，ballout 交叉驗證 222/222 共同 ball 名稱 0 mismatch；resolver 接 vendor_cad 來源，15 tests OK
- [x] 1.2 缺口清單交使用者裁決（換料/原廠CAD/手工補繪）——**stop gate 已裁決 2026-07-07**：27 筆 disposition 回填 → vendor_cad×1（U1 已由 1.2a 解）/ defer×21（TBC 佔位料，交 C03 定料並行）/ pending-defer×5（真缺 official symbol：J_CAM/J3/U_S/LENS/U_EE，Phase 2 前解）；使用者裁定放行 Phase 1 引擎，1.5 用已解 symbol（STM32N657+被動+連接器）開發，不等全 BOM 解完
- [x] 1.3 `block_drafter.py`：單圖繪製（kiutils 物件層）——實作完整：angle→edge 判定、label bbox stagger 防疊字、pin-inclusive bbox；已接 __init__.py exports（draw_block/PinoutBlock）+ engine-rev hash 70c3e12c1624；14 純邏輯單測綠
- [x] 1.4 `block_qa.py`：單圖機檢迴路（render_qa 疊字閘 + fidelity 連通閘），2-round anti-treadmill halt——雙閘實測會咬；qa_block/qa_loop/BlockQAVerdict 已 export；21 tests OK（官方 symbol + kicad-cli 9.0.9 整合測含）。⚠ 暴露 1.5 前置缺口：draftsman 對共用 net（GND/VDD）發獨立 LocalLabel 且未畫 joining wire → KiCad 判分離 net
- [x] 1.5 代表元件單圖驗收：**三張全 PASS**（stm32n657 / conn_gnd / cap_decap 均 fidelity+scoped-render_qa 雙闘綠），23 tests OK（STM32 integration 實跑未 skip）。三層 RCA 逐層拆解：(a) 連通性——symbol 未 netlistable（缺 full lib_id/per-pin uuid/instances block）+ wire 接錯點（KiCad 電氣點是 pin ROOT Y-mirror）；(b) DD-8 render_qa scope——閘只計 draftsman 畫的 peripheral label，排除 vendor 符號內部 125 個 pin-name 互撞（DD-1 不可動）+ _label_box 旋轉軸修；(c) DD-9——dense-BGA 電源網改 power-port 符號（power:GND/+3V3/+1V8 同名自動連通、溶解 24×/17× 同名 label 密度）+ signal label seed vendor pin-name/number box 避讓。無 stock symbol 的 rail（VBAT/VDDCORE/VREF）設 loud gap 記 PinoutBlock.power_gaps 未偽造（DD-1/no-fabrication）
- [ ] 1.6 使用者人工抽查單圖——**Phase 1 gate，未過不得進 Phase 2**

## 2. Phase 2 — 排頁

- [ ] 2.1 `sheet_composer.py`：sheet-fill 排頁——validated 積木平移/鏡射擺放 + 頁間 hierarchical label；積木內部不可變
- [ ] 2.2 利用率機檢：ink_metrics ≥ 0.55 門檻接進整頁 QA 迴路
- [ ] 2.3 CCM 5 頁以 v2 全量重產：雙閘 + 利用率全綠
- [ ] 2.4 使用者 C03 審閱 gate——**stop gate**

## 3. 收尾

- [ ] 3.1 砍除 kicad_emit.py / composer.py / kicad_symbol.py；`__init__.py` 三 export 換新，其餘 re-export 不變（test_eda_bridge / test_companion_render 仍綠）
- [ ] 3.2 test_composer.py / test_density_budget.py 重寫對接 v2；test_bom_export.py 改接 v2 compose
- [ ] 3.3 三份幾何 BR 閉環（補 Resolution 段移 issues/closed/）；eda-bridge_occupancy-ledger 計畫作廢
- [ ] 3.4 architecture.md 同步 + event log 收尾 + ragbase 蒸餾
