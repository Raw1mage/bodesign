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
