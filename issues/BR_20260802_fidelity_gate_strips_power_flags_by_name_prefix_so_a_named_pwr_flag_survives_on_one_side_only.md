# BR_20260802 — fidelity gate 對 PWR_FLAG 兩側不對稱：基準側保留、候選側結構上不可能有，於是恆報一個假開路

- **Status**: OPEN
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
