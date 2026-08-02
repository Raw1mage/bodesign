# BR_20260802 — 真實產品頁上有數十個開路節點，成因未追

- **Status**: OPEN
- **Filed**: 2026-08-02 by `ses_0c87bab06fferQ0umBs2Nybb5U`（值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH` 於 round=4 指示 file）
- **Severity**: HIGH — 電氣正確性缺陷，發生在**真實產品頁**上
- **Family**: `schematic-engine`（unassigned）
- **Parent**: `BR_20260802_fidelity_gate_is_red_after_restore_and_never_ran_at_head`
- **Related**: `BR_20260802_fidelity_gate_cannot_report_open_circuit_and_hardcodes_a_diagnosis`（儀器修復，已 commit `cedc262`）

---

## §1 一句話

`compose_schematic` 對 **aiguard C03** 產出的 schematic 有 **38 個節點失去與 spec 宣告之同 net 夥伴的全部連接**，對 **e2e-led-driver** 有 **8 個**。**成因未追。**

這與 parent BR 的**合成 fixture**（`test_fidelity_gate`，3 個節點）是不同的東西：這是實際要送去做板的頁面。

---

## §2 這不是新缺陷，是新**可見**的缺陷

在 `cedc262`（fidelity 儀器修復）之前，這些節點**結構上不可能被 gate 報出來**：

- `sch_union_classes` 只 union `nodes[1:]`，單節點 net（`unconnected-(R1-Pad1)`）從未進入 parent dict
- 於是斷路的腳不是「多出來的」，而是**不存在於候選宇宙**
- `only_candidate` 對開路缺陷**恆為 0**

所以本 BR 的數字**不是回歸**，是儀器從失明變成會報數之後第一次看見的既有狀態。

---

## §3 量測（版本無關 A/B，兩側語意相同）

### §3.1 判準

**不讀任何 `FidelityReport` 欄位。** 直接從 partition 計算：

> 一個節點在 spec 裡**有**夥伴，但它在候選 partition 的 class 裡**一個夥伴都沒有** ⇒ 失去連接。

理由見 §5——`getattr(rep, 'disconnected', [])` 會讓「HEAD 沒有這個欄位」與「有但是空的」共用同一個輸出，兩邊量的就不是同一件事。

探針原始碼：`$XDG_RUNTIME_DIR/fidrca/realprobe2.py`（`lost_connectivity()`）。

### §3.2 結果

| 頁面 | HEAD（`fe85249f` 前） | 修復後（`fbcc7f3`） | 修好 | 弄壞 |
|---|---|---|---|---|
| aiguard C03 | **48** | **38** | 10 | **0** |
| e2e-led-driver | **9** | **8** | 1 | **0** |

計數用 `grep -c .`（不受檔尾換行影響），控制組：空檔回 0。

### §3.3 修好的 11 個（本 BR 不再追）

```
aiguard: JSB.32  JSB.33  J_LED.1  J_LED.3  RL1.1  RL1.2
         RL2.1   RL3.2   R_TS1.1  R_TS2.1
led:     R8.1
```

### §3.4 仍紅的 38 個（aiguard C03）

```
C_BTST.1   C_BTST.2   C_PMID.1   C_PP1.1    J1.A4B9
JSA.8      JSB.27     JSB.28     JSB.5      JSB.7
J_CAM.15   J_CAM.16   J_CAM.17   J_CAM.6    J_CAM.8
L1.1       L2.1       L2.2       PWR_FLAG_3V3PB.1
R_ILIM.1   U10.3      U10.7      U11.6      U12.5
U9.1       U9.10      U9.11      U9.19      U9.20
U9.21      U9.22      U9.23     U9.7
U_3V3B.3   U_3V3B.5   U_IMU.13   U_IMU.14   U_IMU.5
```

### §3.5 仍紅的 8 個（e2e-led-driver）

```
D5.1  Q1.3  Q2.3  Q3.3  Q4.2  R3.1  R4.1  R5.1
```

---

## §4 成因未追 ⚠

**本 BR 只確立「它存在、有多少、是哪些」，不確立「為什麼」。**

已知的相鄰假設（**皆未驗證，列出僅為避免下一個人重走**）：

- parent BR 的層次 3 契約衝突（label anchor 為避開圖形而被移離 pin endpoint，DD-22/23 禁止 stub wire 接回）在真實頁上的表現
- `BR_20260802_dd20_opposing_flag_split_moves_anchors_with_no_gate`（DD-20 對向旗標分離路徑，**連 `l6_avoidance` 閘都沒有**）
- 第三個尚未被指認的獨立成因

**這三者之間，本輪沒有任何量測可以區分。** 觀察到的分布（U9 佔 9 個、J_CAM 佔 5 個、JSB 佔 4 個，集中在多腳元件）與上述任一假設都相容，也與其他成因相容。

> **不要把它寫成「疑似層次 3」。** 那是假設不是結論，而一旦被寫成結論，下一個人就不會去驗它。

---

## §5 方法論 — A/B 判準必須在兩側語意相同

第一版 A/B 探針用：

```python
lost = sorted(set(rep.only_baseline) | set(getattr(rep, 'disconnected', [])))
```

**這是壞的。** `disconnected` 是修復版才有的欄位：

| build | `getattr(rep,'disconnected',[])` | 讀者看到 |
|---|---|---|
| HEAD（無此欄位） | `[]` ← default | 沒有斷路節點 |
| 修復版（有此欄位、恰好是空的） | `[]` | 沒有斷路節點 |

**「欄位不存在」與「欄位存在但是空的」共用同一個輸出。** 於是 A/B 兩側量的不是同一件事，而差異會被讀成「修復造成的改善」。

**修法**：判準不讀任何版本相關的欄位，直接從 partition 本身計算（§3.1）。這在兩個 build 上都是同一段程式碼、同一個語意。

這是 `ragbase/control/no-silent-degradation/` 的同族變體：**缺席態與失敗態不得共用同一個輸出**，這次發生在 `getattr` 的 default 上。

---

## §6 量了什麼 / 沒量什麼

**量了**：
- 兩個真實頁在 HEAD 與修復後的失連節點**完整清單**（不是數量）
- 差集雙向（修好 11、弄壞 0）
- 計數器對空檔的行為（控制組）

**沒量**：
- **任何一個節點的成因**——一個都沒有
- 這 46 個節點是否共用同一個成因，或分屬多個
- 它們在 layout / netlist 下游是否已被其他 gate 攔下（`check_c03` 的 R1–R8 是否重疊覆蓋）
- 除 aiguard / led 外的其他真實頁（**只量了兩頁**）
- baseline（spec 側期望分割）本身是否正確——值星官 round=3 明示不追，若日後可疑另立 BR

---

## §7 派工提示

- 這是**電氣正確性**缺陷，需要 wire geometry / DD-22/23 的**原作決策脈絡**，不是「手上剛好有 context」的人
- §3.4 / §3.5 的清單可直接當回歸判準：修法應使清單縮短且**不新增任何一個**
- 修復儀器（`cedc262`）已讓 `FidelityReport.diagnosis()` 能區分開路/短路/重分割——修法驗收應使用它，不要再用 `nets` 數量差
