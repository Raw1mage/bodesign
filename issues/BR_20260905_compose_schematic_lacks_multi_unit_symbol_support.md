# BR_20260905 — compose_schematic 缺乏 multi-unit symbol 支援，壓平符號致引腳座標重合與短路

- **Status**: OPEN
- **Severity**: HIGH（立身能力缺陷 · 無法支援標準庫 multi-unit 元件）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`、`kicad_symbol.py`、`composer.py`
- **Filed**: 2026-09-05 by bodesign 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`（依 thesmart_products C03 handler `ses_f95148a02ffenF83aJE6hX1paA` 取證立案）
- **Family**: schematic-engine
- **Related**:
  - `issues/closed/BR_20260706_left_pin_stub_orientation_blind_draws_inside_symbol_body.md`（§48 附註曾將 multi-unit 標記為 future work）
  - `issues/BR_20260905_schematic_emitter_produces_pin_label_stubs_only_zero_pin_to_pin_wires_and_zero_junctions.md`（§11 實測揭露）

---

## 1. 缺陷症狀

當設計 spec 包含標準 KiCad multi-unit 符號（如 `Power_Protection:PESD5V0L4UF` 4 通道 ESD 陣列、雙/四通道運算放大器、多邏輯閘 IC 等）時，調用 `bodesign_compose_schematic` 會觸發 `FidelityError` 被 gate 擋下；若強制關閉 gate，產出的原理圖會發生跨網路短路熔合，且大部分 unit 的引腳未被電氣連接。

在 04.btdongle 實測（D1 為 PESD5V0L4UF，extends PESD3V3L4UF，共 4 個 unit）：
```
baseline nets=27 nodes=135 | candidate nets=54 nodes=164 | shared=133
FIDELITY FAIL moved=10 only_baseline=2 only_candidate=2
  MOVED          ['D1.1','F1.1','J1.A4','J1.A5','J1.A9','J1.B4','J1.B5','J1.B9','R1.1','R2.1']
  ONLY_BASELINE  ['D1.3','D1.4']
  ONLY_CANDIDATE ['D1.5','U2.17']
```

---

## 2. 根因分析

1. **代碼自陳與硬編碼**：
   - `kicad_emit.py:18-19` 自陳：「`Only single-unit symbols and rotation-0 placement are supported in this slice; multi-unit symbols and rotated placement are explicit future work.`」
   - `EmitComponent` 定義了 `unit: int = 1`，但在 `kicad_emit.py` 全檔中，`component.unit` 從未被讀取（0 hit）。
   - `(unit 1)` 在 `kicad_emit.py` 6 處寫死（行 1944, 1951, 2305, 2311, 2373, 2379）。
2. **符號載入展平（Flattening）**：
   - `load_symbol` 載入 multi-unit 符號時，未保留 unit 歸屬，直接將所有 unit 的 pin 展平成單一 `{pin_number: pin}` dict。
   - KiCad 的 multi-unit 符號中，不同 unit 在其局部座標系常使用相同座標（例如 unit 1 pin 1 與 unit 2 pin 3 皆在 `(-2.54, 0)`）。展平後導致不同引腳在同一位置重疊：
     * `D1` pin `['1', '3', '4', '6']` 全部重疊在 `(-2.54, 0)`。
     * 由於引腳分屬 `VBUS_CON`、`CC1`、`CC2`、`<NC>`，幾何重合引發 net 分割崩塌（Moved=10），fidelity gate 正確報錯攔截。

---

## 3. 修復方針（Fix Plan）

1. **符號庫解析支援 unit 維度**：
   - `kicad_symbol.py` / `load_symbol` 需解析並記錄每個 pin 的 unit 所屬（例如 `(unit U)`）。
2. **Spec 與放置層支援 multi-unit 實例化**：
   - `spec["components"]` 支援宣告或自動拆分 multi-unit 實例（例如 `D1.A`, `D1.B` 或 `ref="D1", unit=1` ...）。
   - 放置器將同一 ref 的不同 unit 視為獨立圖形區塊分別排版與走線。
3. **發射器讀取 `component.unit`**：
   - 將寫死的 `(unit 1)` 改為動態發射對應的 `(unit {component.unit})`。
