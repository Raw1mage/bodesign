# Vendor Symbol Provenance — eda_draftsman-v2 DD-7

## STM32N657L0H3Q (ST_vendor.kicad_sym)

- **來源**：LCSC / EasyEDA 公開元件庫（manufacturer-backed）
- **LCSC part number**：C42457345
- **MPN (vendor)**：STM32N657L0H3Q — BGA-223 (10×10, 0.5mm pitch)
- **目標 MPN (aiguard C03 BOM)**：STM32N657L0Q3 — 同 die 同 VFBGA223 封裝，僅封裝後綴標示差異（H3Q/Q3 皆 223-ball 10×10）
- **取得方式**：`easyeda2kicad --full --lcsc_id=C42457345`（CLI v1.0.1，容器 bodesign-pkcs12-bodesign-ee-1 內執行）
- **下載日期**：2026-07-07
- **格式**：原生 KiCad `.kicad_sym`（無手工格式轉換），kiutils 1.4.8 解析通過
- **附帶產物**：footprint `BGA-223_L10.0-W10.0-P0.50-STM32N657L0H3Q.kicad_mod`、3D STEP + WRL（ST_vendor.3dshapes/）
- **lib_source**：`vendor_cad`（DD-1 no-fallback：非官方 KiCad 庫，非自產幾何）

### 為何不用 ST 官方 CAD / SnapEDA
- ST 官方產品頁 CAD Resources：webfetch timeout（st.com 反爬）
- SnapEDA / SamacSys / Component Search Engine：需登入或填表單牆（403 / form-gate），無法自動化直接下載
- LCSC/EasyEDA 公開庫是唯一可程式化、無登入牆、且 manufacturer-backed 的來源，且 bodesign 既有 `component_fetch` 管線本就走此路

## Ballout 交叉驗證（權威級一致）

對照權威來源 `thesmart_products/.../n6_board/manufacturable/stm32n657_ballout.json`
（VFBGA223 ballout，STM32N657L0 datasheet DS14791 Rev 3 Figure 11 轉錄，222/223 balls）：

- vendor symbol pins：**223**
- 權威 ballout balls：**222**（datasheet 本身 1 ball 待 reconcile）
- 共同 222 ball 訊號名稱：**100% 一致（0 mismatch）**
- 差異：vendor symbol 多 1 pin `V6`（權威 ballout 缺的那一顆），vendor 反而更完整
- 交叉驗證報告：`~/.cache/claude-work/draftsman-v2/ballout_crosscheck.json`

**結論**：vendor CAD 與 authoritative ballout 為同一顆 die 的權威資料，pin 定義可信度達 gate 級，可作為 Phase 1 單圖繪製的 symbol 幾何來源。fab 前仍建議以 ST STM32CubeMX 最終覆核（README 既有建議）。

## Bodesign_Presentation.kicad_sym — PESD5V0L4UF_Boxed (R6 presentation asset)

- **Status**: project-authored from datasheet facts; license pending owner decision; not cleared for redistribution or global promotion; internal review use only. No SPDX identifier is asserted.
- **Scope**: pin function / topology / presentation only. NON-FABRICABLE: the library Footprint property is intentionally EMPTY; no PCB / package / BOM / fab release. Footprint defect filed at `/home/pkcs12/products/thesmart_products/issues/BR_20261006_d1_pesd5v0l4uf_footprint_sot363_contradicts_datasheet_sot886.md`.
- **Facts taken from**: Nexperia PESDxL4UF/UG/UW data sheet, Document ID PESDXL4UF_G_W_4, Rev. 04 (28 Feb 2008); file sha256 `62d2166079ebe42ac5d37b1fe704abde1a59b5a1c74d48daf50dc9682bcf036a`; URL `https://assets.nexperia.com/documents/data-sheet/PESDXL4UF_G_W.pdf`. Table 3 (p.2 of 17), PESD3V3L4UF/PESD5V0L4UF rows: 1 cathode (diode 1), 2 common anode, 3 cathode (diode 2), 4 cathode (diode 3), 5 common anode, 6 cathode (diode 4).
- **Geometry**: freshly drawn generic shapes (rectangle, diode triangle/bar, bus, junction dots). No KiCad library polyline and no Nexperia illustration was copied. Pin placement is a presentation choice (K1..K4 left, common-anode pins 2 and 5 stacked on one right tip); only pin function/connectivity is binding.
- **Use**: selected per run, per ref (D1 only) through a copied candidate spec and `symbol_dirs`; NOT registered in `symbol_resolver._VENDOR_MAP`.
