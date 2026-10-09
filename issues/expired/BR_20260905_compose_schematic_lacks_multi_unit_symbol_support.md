# BR_20260905 — compose_schematic 缺乏 multi-unit symbol 支援，壓平符號致引腳座標重合與短路

- **Status**: **PARTIAL**（2026-09-06 改判 · 原記 FIXED。§4 的 moved 10→0 成立且未被推翻，但修復只落在 emitter 讀取端；composer 寫入端從未填 `unit`，見 §5）
- **Severity**: HIGH（立身能力缺陷 · 無法支援標準庫 multi-unit 元件）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`、`kicad_symbol.py`、`composer.py`
- **Filed**: 2026-09-05 by bodesign 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`（依 thesmart_products C03 handler `ses_f95148a02ffenF83aJE6hX1paA` 取證立案）
- **Family**: schematic-engine
- **Related**:
  - `issues/closed/BR_20260706_left_pin_stub_orientation_blind_draws_inside_symbol_body.md`（§48 附註曾將 multi-unit 標記為 future work）
  - `issues/BR_20260905_schematic_emitter_produces_pin_label_stubs_only_zero_pin_to_pin_wires_and_zero_junctions.md`（§11 實測揭露）
  - `issues/BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm_on_non_label_friendly_topology.md`（OPEN，schematic-engine 家族第四獨立成因；本 BR 是座標壓平，該 BR 是連線策略降級，兩條獨立修復線）

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

---

## 4. 真板實驗結論（2026-09-05，handler `ses_f8e45aabdffeS6jd3hxBkjf5fV` 實測）

語料：`thesmart_products/04.btdongle/C03-EE/02_build/sch_gen/design.py`（D1 = `Power_Protection:PESD5V0L4UF`，
4-unit ESD 陣列，extends PESD3V3L4UF）。唯讀複製進 scratch 轉 spec 測，guest repo 未寫入。

### 4.1 落地修改

`packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`（+199/−2，單檔）：

- 新增 `_unit_children` / `_pin_unit_map` / `_unit_stride` / `_unit_offsets` / `_translate_block_y` / `_stack_units`。
- `load_symbol` 在 `_flatten_extends` 之後、`_scale_symbol_geometry` 之前插入 `_stack_units`，
  把 N 個 unit 投影成單一 body 的垂直堆疊（unit u 下移 u×stride，**stride 由各 unit 實際繪製範圍量出**，非假設常數）。
- `_symbol_instance_block` 的寫死 `(unit 1)` 改讀 `component.unit`。
- `_pwr_flag_instance` / `_power_symbol_instance` 的 4 處 `(unit 1)` **刻意保留**（PWR_FLAG / power port 本質單 unit）。

### 4.2 四格驗證與控制組

- **G1（`component.unit` 真的被讀了嗎）**：改前 grep 0 hit；改後 2 hit（`:2184` `:2193` `:2200`）。
  正控制 `component.lib_id`=25；**負控制** `component.zzznotafield`=0（證明 grep 不會亂回非零）。
- **G2（D1 四 unit 座標還重合嗎）**：改前 distinct 2/6，pin 1/3/4/6 全在 `(-2.54, 0)`；
  改後 distinct 5/6，pin3 `(-2.54,-7.62)` / pin4 `(-2.54,-15.24)` / pin6 `(-2.54,-22.86)`。
  控制組 A：`Device:R` `Device:C` 座標與改前**逐字相同**（single-unit 未被弄壞）。
  控制組 C：**突變控制** — in-process 把 `_stack_units` 換 no-op → distinct 掉回 2/6；還原 → 5/6。
- **G3（既有測試回歸）**：`test_kicad_emit` Ran 46 OK、`test_composer` Ran 5 OK、
  `test_generic_symbol` Ran 3 OK、四顆 `test_fidelity_*` Ran 5/19/12/7 全 OK。
  判別欄位取 `Ran N` 而非 rc；跑前清 `__pycache__`。
- **G4（kicad-cli 接受這份檔嗎）**：`validate=True` 未 raise、`symbol_load_failures=[]`、
  gate `intra_overlap=0 label_overlap=0 rects=263 PASS`。額外做的：本修改重寫了 symbol s-expr 區塊，
  需證明不只自家 parser 讀得懂。

G2 的**突變控制組是決定性的**：它排除了「數字是環境或其他改動造成」這個解釋——
關掉 `_stack_units` 立刻退回 2/6，證明位移確實由本修改承重。

### 4.3 電氣軸結果（本 BR 核心判準）

```
改前  baseline nets=27 nodes=135 | candidate nets=54 nodes=164 | shared=133
      FIDELITY FAIL moved=10 only_baseline=2 only_candidate=2
        MOVED          ['D1.1','F1.1','J1.A4','J1.A5','J1.A9','J1.B4','J1.B5','J1.B9','R1.1','R2.1']
        ONLY_BASELINE  ['D1.3','D1.4']
        ONLY_CANDIDATE ['D1.5','U2.17']

改後  baseline nets=27 nodes=135 | candidate nets=57 nodes=167 | shared=135
      FIDELITY FAIL moved=0 only_baseline=0 only_candidate=2
        ONLY_CANDIDATE ['D1.5','U2.17']
```

逐項對照（非裸數字）：**MOVED 10 項全清、ONLY_BASELINE `['D1.3','D1.4']` 全清**，shared 133→135。

### 4.4 ⭐ 關鍵發現：修復序列的路標（留給後續 handler）

立案時的假設是「moved 由多缺陷疊加，修完 multi_unit 仍會有 BR_20260723e collinear fusion 的殘留」。
**實測推翻此假設**，兩點皆已量測：

1. **真板 moved 直接歸零（10 → 0），不是遞減。**
   那 10 項 MOVED **全部由 multi-unit 壓平單獨造成**。BR_20260723e（collinear fusion）
   **在這塊板上不貢獻任何 moved**——它以既有 anti-fusion guard 的降級形式被吸收：
   `anti-fusion guard down-graded 3 net(s) to label: ['CHG_LED_A','LED_WIFI','VBAT_SENSE']`。
   ⇒ 723e 的優先序在此板可下修；它不是真板 fidelity gate 的 blocker。

2. **殘留的 gate FAIL 成因已換人，是第三條獨立缺陷。**
   `ONLY_CANDIDATE ['D1.5','U2.17']` 改前改後**逐字相同**，未被本修改觸碰。
   查 `design.py:271`（`("D1","5"), ("D1","6")` spare ESD 通道）與 `:278`（`("U2","17")`），
   兩者都在 `NO_CONNECT` 清單中 ⇒ **NC 節點未被排除在 fidelity 的 spec 母體之外**，
   與 multi_unit 無關、與 723e 亦無關。真板 gate 要 PASS，下一張要開的是這條，不是 723e。

### 4.5 修法邊界（誠實標記）

`_stack_units` 是**投影法，不是 KiCad 原生 multi-unit 實例化**。
原生做法是發射 N 個 `(symbol ... (unit u))` 實例、各自獨立擺放；那需要放置層把 `(ref, unit)`
當作 entity key，屬**放置器改寫**，超出本 BR 邊界，故未做。
兩者**電氣等價**，差別僅在製圖慣例（一顆高 body vs N 顆可各自擺放的 body）。
此差異已寫進 `_stack_units` docstring，不靠這張 BR 記住。

### 4.6 未量邊界

- **視覺軸完全未量**：未轉圖、未做 fresh-eyes subagent 覆核。D1 現為 4 unit 垂直堆疊的高 body，觀感未知。
- **ERC 告警內容未逐條讀**：只證明 kicad-cli 未拒絕檔案，未審視個別 violation。
- **三 sheet 拆分未做**：仍 `content exceeds largest standard sheet`（A0）——改前即存在，非本次回歸。
- **僅驗此一顆 multi-unit 符號**：雙運放 / 多邏輯閘等其他 multi-unit 家族未測。
- **未跑全套 142 模組**，只跑上述 7 顆。
- 幾何/座標綠燈**不授權**「電路對了」的宣稱；電氣軸證據僅 moved 10→0 一項。

---

## 5. §5 殘留：修落在讀取端，寫入端從未填（2026-09-06 改判 FIXED → PARTIAL）

**§4 的結論沒有被推翻。** `5599793f`（`Fix BR_20260905 compose_multi_unit: load_symbol reads
component.unit, stack multi-unit symbols`）確實讓 emitter **讀** `unit`，真板 moved 10→0 也
確實發生。改判的理由不是那格量錯，是那格**只覆蓋了半條路**。

### 量測（2026-09-06 一手複驗）

| 探針 | 結果 | 讀法 |
| --- | --- | --- |
| `grep -c 'unit=' composer.py` | **0** | 三個建構點沒有任何一個傳 `unit` |
| `grep -n 'EmitComponent(' composer.py` | **3**（`:2251` / `:2262` / `:2377`） | 建構點確實有三個，不是檔案讀不到 |
| CONTROL：`grep -c 'unit' kicad_emit.py` | **90** | emitter 端大量處理 `unit` —— 所以 composer 的 0 是「這一側沒有」，不是「這個詞不存在於本專案」 |

控制組是決定性的：同一個詞在隔壁檔案有 90 次命中，於是 composer 的 0 不可能是探針壞掉或
拼寫錯誤，只可能是真的沒填。

### 為什麼這是「修落在平行段」的又一例

`EmitComponent.unit` 現在是一個 **emitter 會認真讀、而唯一的生產者從不寫**的欄位。它的預設
值於是成為實際行為的全部，而 `5599793f` 的修復只在「呼叫端自己填了 `unit`」時才會被走到——
P1 交付路徑（`composer.py` → `kicad_emit.py`）不填。

這與 `tooling-failmodes.failure-mode.fix-lands-on-parallel-pipeline-off-delivery-path`
同形：修復真實存在、測試真的綠、而交付路徑不經過它。也與本 repo
`BR_20260906_gate_unit_fixtures_blind_to_emission_site_mutation.md` 同形——**生產端與消費端
各自正確，接縫沒人驗**。

### 未量

- **`unit` 的預設值在 P1 路徑上會產生什麼幾何**：未跑。所以本節不宣稱「今天的圖是錯的」，
  只宣稱「emitter 的 multi-unit 分支在 P1 上不可能被觸發」。
- **三個建構點該不該都填**：`:2262` 與另外兩處的上下文未逐一讀，可能只有部分需要。
- **根因**：未追。與 `BR_20260906_occupancy_ledger_wire_reserves_never_survive_to_final_ledger.md`
  同樣停在量測。

> 立案脈絡：`/home/pkcs12/products/thesmart_products/issues/BR_20260906_c03_schematic_chain_delivered_label_stub_pinout_instead_of_circuit.md`
> §3.2 與 fanout 建議 **B-8**（`:376`）。該報告本身也標明「舊描述（never read）已被 `5599793` 取代」——
> 本節補的是它的另一半：讀取端修好了，寫入端還沒。
