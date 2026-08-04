# BR_20260802 — fidelity gate 對 PWR_FLAG 兩側不對稱：基準側保留、候選側結構上不可能有，於是恆報一個假開路

- **Status**: FIXED — `4a58fdf`（2026-08-04 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`）。§8 記錄實作與驗收；§6「沒量」的前兩點現已量完，第三點仍未查
- **Severity**: P2 — **判準缺陷（false positive），非電路缺陷**。它讓一個永遠不會消失的假訊號混在真訊號裡
- **Family**: `schematic-engine`（**unassigned**）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py:204`（`_drop_power_flags`）× `:249-251`（`compare_partitions` 兩側套用處）
- **Filed**: 2026-08-02 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）
- **Parent**: `BR_20260802_real_product_pages_carry_dozens_of_open_circuit_nodes_cause_untraced` §8.4

---

## §1 一句話

`PWR_FLAG_3V3PB.1` 被 fidelity gate 報為 `only_baseline`（節點缺席），**在 L6 ON 與 OFF 兩版都存在**，先前被記為「獨立於 L6 的第三成因、機制未追」。

**機制是判準本身的兩側不對稱，不是電路壞掉。**

---

## §2 最小重現（3 個元件，含控制組）

```
[TREATMENT with PWR_FLAG] spec_comps=3 netlist_comps=2
                          missing=['PWR_FLAG_X']  only_baseline=['PWR_FLAG_X.1']
[CONTROL  no PWR_FLAG   ] spec_comps=2 netlist_comps=2
                          missing=[]             only_baseline=[]
```

兩個 spec 只差一個 `power:PWR_FLAG` 元件（以及它在 net 裡的那個 node）。**treatment 報假開路，control 乾淨。**

真實產品頁上同一個算術：spec 47 個元件 → netlist **46** 個，差的正是 `PWR_FLAG_3V3PB`。

---

## §3 機制

```
基準側 expected_partition_from_nets(spec.nets)
    → 逐字保留 spec 宣告的每個 node，含 "PWR_FLAG_3V3PB.1"

候選側 sch_union_classes() → kicad-cli sch export netlist
    → KiCad 的 PWR_FLAG 是 ERC 用的繪圖標記，**本來就不出現在 netlist**
      （實測：netlist 裡 'PWR_FLAG' 出現 0 次、'FLG' 0 次，
        控制組 'U9' 出現 30 次、bogus 'ZZQQ' 0 次）

compare_partitions() 對兩側都套 _drop_power_flags()
    → 但它只剝除 n.startswith("#")
    → "PWR_FLAG_3V3PB.1" 是使用者命名的 ref，不以 # 開頭
    → 基準側留著它，候選側從來沒有它
    → only_baseline 恆含這一個節點
```

`_drop_power_flags` 的 docstring 寫的是「strip synthetic power-flag/port pseudo-nodes (#PWR*, #FLG*)」——**它預期的是 KiCad 自動產生的合成名稱**。但 spec 可以宣告一個**具名**的 PWR_FLAG 元件，那個名字不帶 `#`，於是同一個概念的兩種寫法只有一種被剝除。

---

## §4 為什麼這格值得單獨立案

它是**判準壞掉而不自報**的又一個實例，但變體是新的：

> **兩側套用了同一個清洗函式，看起來就是對稱的。**

`compare_partitions` 對 baseline 與 candidate 都呼叫 `_drop_power_flags`——程式碼讀起來完全對稱。不對稱藏在**輸入的命名慣例差異**裡：一側的 PWR_FLAG 叫 `PWR_FLAG_3V3PB.1`，另一側根本不存在。

**「同一個函式套用在兩側」不等於「兩側被同等處理」。**

而它的後果是最難察覺的那種：**一個恆定的假陽性**。它不會忽然出現，所以不像回歸；它一直都在，所以讀者會把它當成「已知的殘留問題」。本 BR 的 parent §8.4 正是這樣把它記成「第三個獨立成因，機制未追」。

---

## §5 修法選項（未裁示）

1. **依 lib_id 剝除**：候選/基準兩側都把 `power:PWR_FLAG`（以及 `power:PWR_*` port 類）對應的節點剝掉，不依賴名字開頭的 `#`。**打擊半徑最小、語意最準。**
2. **依 spec 元件型別剝除**：`expected_partition_from_nets` 收一個「哪些 ref 是繪圖標記」的集合，由 caller 從 `spec.components[].symbol` 算出。
3. **不修 gate，改 spec 慣例**：規定 PWR_FLAG 不得列為 net node。**不建議**——它會把一個判準缺陷轉嫁成使用者必須記住的規則。

選 1 或 2 取決於 `fidelity.py` 是否該知道 lib_id（目前它只看節點名字串）。

---

## §6 量了什麼 / 沒量什麼

**量了**：
- 最小重現（treatment/control 只差一個元件）
- 真實產品頁的元件數差（47 spec vs 46 netlist，差集恰為 `PWR_FLAG_3V3PB`）
- netlist 中 PWR_FLAG/FLG 出現次數 = 0，含正控制組（`U9`=30）與負控制組（bogus=0）
- 該節點在 L6 ON/OFF 兩版都是 `only_baseline`（parent 與 head 皆是）

**沒量**：
- **修法 1 或 2 實作後是否真的讓 `only_baseline` 歸零**——未實作、未驗證
- 其他 `power:*` 符號（GND port、supply port）是否有同一個不對稱。實測 emit 出的頁面有 `power_gnd_GND` / `power_supply_VBAT` / `power_supply_VSYS` 三種 lib_id，**它們是否也被 spec 宣告為 net node、是否也逃過 `#` 剝除，完全未查**
- 是否有其他 gate（`check_c03` 的 R1-R8）重複覆蓋或重複回報同一個節點

---

## §7 派工提示

- 驗收判準：`only_baseline` 應從 1 降到 **0**，且 `disconnected` / `fused` / `regrouped` **三者都不得改變**（修 gate 不該動到其他判定）。
- §2 的最小重現腳本可直接當回歸測試骨架：treatment 應乾淨，control 保持乾淨。
- **先查 §6 第二點**（其他 power 符號是否同病）再動刀，否則修完只解決一個 lib_id。

---

## §8 修復（`4a58fdf`）

### §8.1 採用的修法：不是 §5 的 1 或 2，是它們的交集

§5 把選擇框成「依 lib_id 剝除」vs「依 spec 元件型別剝除」，並說取決於 `fidelity.py` 該不該知道 lib_id。**兩個都不對，因為它們都要求列舉。**

實際採用：`power_symbol_refs(sch_files)` 從**繪圖**讀出 KiCad 自己用來判別的那個 token。

```
lib_symbols 裡的定義帶 (power) token  ->  該 lib_id 是 power 符號
實例的 lib_id 在該集合內              ->  它的 Reference 進豁免集
兩側都用同一個集合清洗
```

這樣不需要列舉任何 lib_id 名稱，未來新增的 power 符號自動涵蓋。

**錨定在繪圖而非 spec，是刻意的**：從 spec 讀會把「元件根本沒被放置」一起吸收掉，而那是這個 gate 必須繼續回報的真缺陷。§5 選項 2 正是這個形狀。

### §8.2 機制的決定性證據（§3 原本只證明了「它沒進 netlist」）

原 §3 證明了 PWR_FLAG 不出現在 netlist，但**沒有證明排除是由什麼驅動的**。兩個變異在真實頁上分辨了它：

| 變異 | netlist comp 數 | 節點出現？ |
|---|---|---|
| 原檔 | 46 | ✗ |
| 只改 **ref 名稱** → `#FLG9` | 46 | ✗ |
| 只改 **lib_id** → `Device:R` | **47** | **✓** |

**排除由 SYMBOL 驅動，不是名稱。** 這推翻了一個很自然的修法方向（正規化命名慣例）——那不會有任何效果。

判別 token 也是量出來的：`power:PWR_FLAG` 的定義含 `(power)`，控制組 `Device:R` 的定義沒有。

### §8.3 驗收：達到 §7 的判準

真實頁上、同一份已解析輸入、只有豁免集不同的 A/B：

```
              fix OFF                      fix ON
only_baseline ['PWR_FLAG_3V3PB.1']   ->    []          ← §7 要求 1→0 ✅
disconnected  63                     ->    63          ← §7 要求不變 ✅
fused          7                     ->     7          ← §7 要求不變 ✅
regrouped      3                     ->     3          ← §7 要求不變 ✅
shared       258                     ->   258
baseline_nets 84                     ->    84
```

### §8.4 §6「沒量」的前兩點，現在量了

**第一點（修法是否真讓 `only_baseline` 歸零）**：§8.3 已答，是。

**第二點（其他 power 符號是否同病）**——§7 明令先查再動刀：

```
該頁 lib_symbols 定義共 58 個
  判為 POWER (5): PWR_FLAG · power:PWR_FLAG · power_gnd_GND
                  · power_supply_VBAT · power_supply_VSYS
  判為 NORMAL (53): Device:C · Device:R · Connector_Generic:* ...
```

§6 點名的三個（`power_gnd_GND` / `power_supply_VBAT` / `power_supply_VSYS`）**全部被通用判準涵蓋**，不需個別處理。

而真正的風險面比擔心的窄：全 corpus（3 個帶 nets+components 的 spec）中，**具名 power 符號只有 1 個**，且只有它同時被宣告為 spec net node。

```
probe_spec.json        comps=2  具名 power flag = 0
spec.json              comps=47 具名 power flag = ['PWR_FLAG_3V3PB']  ← 唯一
e2e-led-driver.spec    comps=22 具名 power flag = 0
CONTROL: regex 對 power blob 回 True、對 Device:R blob 回 False
```

**第三點（其他 gate 是否重複回報同一節點）仍未查。**

### §8.5 這個修復自己踩到的那一格（比修復本身值得記）

Mutation proof 第一輪 **3/4**，存活的是 `M4_not_wired_at_entry`——把 `verify_partition_fidelity` 傳遞豁免集那個引數刪掉，**10 個測試沒有一個變紅**。

原因：那 10 個測試全部直接呼叫 `compare_partitions`，**沒有一個走生產入口**。而兩個真實呼叫端（`composer.py:2603`、`block_qa.py:100`）都從 `verify_partition_fidelity` 進來。

```
豁免存在   ✅
豁免正確   ✅
豁免可見   ✅
豁免在產品裡  ✗   ← 沒有任何測試在看這一格
```

這是 `code-thinker §8.3(d)`「護欄可以只存在於一條路徑上」的實例，**發生在一個為了修同族缺陷而寫的驗收上**。補了入口測試（含反向控制組：stub 回缺 `U2.1` 的候選，gate 必須仍然失敗，證明被 stub 的正是受測路徑）後 4/4。

### §8.6 落地

```
commit  4a58fdf  恰 2 檔
  packages/eda-bridge/bodesign_eda_bridge/fidelity.py
  tests/test_fidelity_excludes_named_power_symbols.py   (12 測試)
mutation proof 4/4 killed, restore 位元組相同
回歸: test_fidelity_gate · test_fidelity_instrument_reports_measured_mechanism
      · test_fidelity_reports_when_its_baseline_is_not_a_partition  全綠
消費端 import: block_qa · composer  OK
```

豁免在 `summary()` 中**即使 PASS 也印出**（`EXCLUDED as power symbols`）：它從兩側移除節點，而看不見的豁免與從未做過的檢查無法區分。自動標註的 `#FLG*`（該頁 87 個）刻意不列，否則會把唯一重要的那個埋掉。
