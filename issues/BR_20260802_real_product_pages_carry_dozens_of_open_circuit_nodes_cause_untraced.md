# BR_20260802 — 真實產品頁上有數十個開路節點，成因未追

- **Status**: OPEN — **成因已追出 §8**（主成因 = L6 label-anchor 避讓；殘留 6 個新 fused + PWR_FLAG_3V3PB.1 機制未追）
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

---

## §8 成因已追出（2026-08-02，值星官 `ses_04db7a1c5` 覆核 RCA subagent `ses_035d65eea`）

**Status 由「成因未追」轉為 TRACED。** §4 的三個假設中，**假設 1 是主成因**。

### §8.1 決定性 bisect（同輸入、只換程式碼）

`316150f` 唯一的改動是 `kicad_emit.py:1515` 的 L6 閘（`l6_avoidance` 由硬編 `True` 改為真旗標，產品預設 `False`）。用**逐字相同的 `spec.json`（47 components / 84 nets）與 symbols**，只切換 `PYTHONPATH` 指向兩個 commit：

| | `disconnected` | `fused` | `regrouped` | `only_baseline` | 合計 |
|---|---|---|---|---|---|
| parent `436c437`（L6 **ON**） | **55** | 7 | 3 | 1 | **65** |
| head `316150f`（L6 **OFF**） | **0** | **17** | 0 | 1 | **17** |

- 兩側 `CODE_FROM` 已印出證明模組來源不同、輸入相同。
- 判準用 `hasattr` 斷言欄位存在，**不用 `getattr(...,[])`**（§5 的教訓：欄位缺席與欄位為空共用輸出）。
- parent 的 `lost_connectivity` 清單與 §3.4 的 38 個**逐字全等**（`comm` 雙向皆空），證明重現的是同一件事。

**開路歸零。** 假設 1（label anchor 為避開圖形被移離 pin endpoint）解釋了全部 55 個 disconnected。

### §8.2 但這不是零成本——`fused` 從 7 升到 17

`fused`（短路：接到不該接的夥伴）**也是電氣缺陷**，不是外觀問題。逐一分類那 10 個新增：

```
在 parent 的 disconnected 裡（先前被開路遮蔽，非新增）  4/10
  C_PP1.1  U10.3  U11.6  U12.5
兩邊都不在（L6=OFF 真正新造成的）                      6/10
  C1.1  J1.A4B9  J1.B4A9  JSA.1  JSA.2  U9.1
CONTROL comm self = 10/10
```

head 的 fused 集合是 parent 的**嚴格超集**（parent 有而 head 無 = 0）。

**所以 L6=OFF 的真實代價是 6 個新短路，換掉 55 個開路。** 淨值 65→17 仍是大幅改善，但「代價僅是可讀性」的說法**不成立**——當時向使用者陳述裁決前提時，只量了 label 重疊（外觀），未量 fused（電氣）。

### §8.3 被否證的假設

**co-point 錨點不是新短路的機制。** 量測 emit 出的 182 個 global_label：

```
labels_parsed=182   distinct anchor points=178   co-point anchors(>1 label)=3
labels sitting on a shared anchor = 4
CONTROL impossible-coord shared = 0
```

**3 個共點錨、4 個標籤，解釋不了 6 個新短路。** 這 6 個的機制**仍未追**。

### §8.4 殘留的獨立成因

`PWR_FLAG_3V3PB.1` 在 L6 ON/OFF **兩版都是** `only_baseline`，與 L6 無關。已確認它**有被 emit**（`grep -c PWR_FLAG_3V3PB` = 2，控制組 `R_ILIM` = 2、`PWR_FLAG` 全體 = 18），但沒接上 `+3V3_PB` 的任何夥伴（該 net 在 spec 有 19 個成員）。**深層機制未追。**

### §8.5 沒量什麼

- **6 個真正新增的 fused 的機制**——共點錨假設已否證，無替代解釋。
- `PWR_FLAG_3V3PB.1` 為何未連。
- 假設 2（DD-20 無閘路徑）的貢獻**完全未隔離**——L6 效應把它遮蔽了。實測 DD-20 在真實標籤長度（最長 14 字元）上產生 ~6.96mm 位移，遠小於 L6 的 53mm 級，但不等於零貢獻。
- 唯讀產物檔 `aiguard_product.kicad_sch` 未重新產生（它仍是舊程式碼的產出，量它得到的是歷史狀態）。
- 仍只量 aiguard + led 兩頁。
