# BR_20260802 — spec 把 6 個 pin 宣告在多條 net 上，於是 gate 的「基準分割」不是分割，而它把 spec 的自我矛盾報成 emitter 缺陷

- **Status**: OPEN
- **Severity**: **P1** — 它讓 fidelity gate 的 `fused` 判定**整欄不可信**，而該欄是電氣正確性的主要訊號之一
- **Family**: `schematic-engine`（**unassigned**）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py:223`（`expected_partition_from_nets`）× 資料側 `experiments/aiguard_c03_compose/spec.json`
- **Filed**: 2026-08-02 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）
- **Parent**: `BR_20260802_real_product_pages_carry_dozens_of_open_circuit_nodes_cause_untraced` §9

---

## §1 一句話

`spec.json` 有 **6 個 pin 各自被宣告在 2–3 條 net 裡**。`expected_partition_from_nets` 逐字照收，產出一個**類別互相重疊的「分割」**——而分割的定義就是類別不重疊。

fidelity gate 拿它當基準，於是**要求 emitter 把 spec 宣告為相連的東西分開**。emitter 照 spec 做（把三個標籤放在同一個 pin 上），gate 就報 `fused`。

**emitter 沒有做錯。gate 報的是 spec 的自我矛盾。**

---

## §2 資料（含控制組）

```
spec 節點總數                     = 259
宣告在 >1 條 net 的節點           = 6
CONTROL 恰好 1 條 net 的節點      = 253
CONTROL 不存在的節點 'ZZ.9'       = 不在（探針有判別力）
```

那 6 個：

```
J1.A4B9  -> PP_VBUS + USB_ESD_VBUS + VBUS_5V
J1.B4A9  -> PP_VBUS + VBUS_5V
U9.1     -> PP_U9_VBUS + VBUS_5V
BT1.1    -> PP_BAT + VBAT
U9.13    -> PP_BAT + VBAT
U9.14    -> PP_BAT + VBAT
```

`expected_partition_from_nets` 產出的基準裡，**恰好這 6 個節點同時屬於多個 class**。

---

## §3 它解釋全部 fused，兩個版本都是

以那 6 個 pin 所屬 net 的**傳遞閉包**為預測集：

```
closure(3 個共點 pin: J1.A4B9 / J1.B4A9 / U9.1)  = 10 節點
closure(3 個分置 pin: BT1.1 / U9.13 / U9.14)     =  7 節點

HEAD 新增的 10 個 fused  全部落在 closure(共點)?  True   未解釋 = 0
PARENT 的  7 個 fused    全部落在 closure(分置)?  True   未解釋 = 0
CONTROL: 兩個閉包外確實有節點（BT1.2 / C1.2 / C2.1）
```

**17 = 10 + 7，兩側 fused 全部被同一個根因解釋，殘留為零。**

---

## §4 L6 在這裡的真實角色：遮蔽，不是製造

先前記錄（parent BR §9）說「L6=OFF 造成 6 個新短路」。**那個歸屬是錯的。**

同輸入只換程式碼，看那 6 個 pin 的標籤是否共點：

| pin | parent（L6 ON） | head（L6 OFF） |
|---|---|---|
| `J1.A4B9` | SPLIT | **CO-LOCATED** `(928.37,715.01)` |
| `J1.B4A9` | SPLIT | **CO-LOCATED** ×2 |
| `U9.1` | SPLIT | **CO-LOCATED** `(571.50,697.23)` |
| `BT1.1` | SPLIT | SPLIT |
| `U9.13` | SPLIT | SPLIT |
| `U9.14` | SPLIT | SPLIT |

L6 開啟時把**同一個 pin 的多個 net 標籤推到不同座標**，於是 KiCad 看不出它們同點——**但那三個 pin 在 netlist 裡仍然透過「同一支 pin」被合併**（後三列證明：始終 SPLIT 卻始終 fused）。

所以 L6 做的是**把 spec 宣告的連接在圖面上藏起來**，代價是把 anchor 推離 pin（55 個開路）。

> **L6=ON 不是「比較正確」，是把一個資料層的矛盾用繪圖位移蓋住。**

---

## §5 為什麼是 P1

`fused` 欄目前混著兩種東西，而**讀者無法分辨**：

1. spec 自己宣告的連接（本 BR，17/17 個節點）
2. emitter 真的畫錯造成的短路（**目前數量未知，可能為 0**）

**一個恆定的、涵蓋整欄的假陽性，比一個間歇的偽陽性更危險**——它讓整欄失去判別力，而輸出看起來完全正常。今天我自己就三次以這一欄為據做出結論，其中兩次是錯的。

---

## §6 修法選項（未裁示）

**先決問題：那 6 個宣告是 spec 的錯，還是合法表達？**

`J1.A4B9` 是 USB-C 的 VBUS 腳。它同時出現在 `VBUS_5V` / `PP_VBUS` / `USB_ESD_VBUS` 三條 net——這在人的意圖上可能是「這三個名字指同一個電氣節點」（別名），也可能是「這裡本該有保護元件而 spec 漏了」。**兩者的修法相反，而本 BR 沒有量測可以區分。**

1. **若是別名** → `expected_partition_from_nets` 應先做 union-find 把共用節點的 net 併成一個 class，並在報告中列出被併的 net 名。基準才會是真的分割。
2. **若是 spec 缺漏** → 修 `spec.json`，補上該有的元件；gate 不動。
3. **無論何者，`expected_partition_from_nets` 都應該 fail-loud**：偵測到節點出現在多個 class 時顯式報錯或警告，而不是靜默產出一個非分割的東西。**這條與 1/2 的選擇無關，可以先做。**

---

## §7 量了什麼 / 沒量什麼

**量了**：
- 6 個多 net 節點的完整清單，含正/負控制組
- 傳遞閉包解釋兩版全部 fused，殘留 0
- L6 ON/OFF 對這 6 個 pin 的標籤共點狀態（A/B，兩側都印 `CODE_FROM` 證明模組來源不同）
- delta-debug 最小觸發集：`VBUS_5V` + `PP_VBUS` + `J1` 三者缺一即 FUSED=0

**沒量**：
- **那 6 個宣告是意圖還是錯誤**——這是產品/設計決策，不是我能量的
- **扣掉本 BR 之後，還剩幾個真短路**——可能是 0，但未驗證
- 其他 spec（led / CCM 頁）是否也有多 net 節點
- `expected_partition_from_nets` 加上 fail-loud 後會不會讓現有測試大量變紅

---

## §8 派工提示

- **先做 §6.3**（fail-loud），它與 1/2 的裁決無關，且能立刻讓這個矛盾停止靜默。
- 驗收判準：加上 fail-loud 後，`aiguard_c03_compose/spec.json` 必須觸發它，而一個乾淨的合成 spec 必須不觸發（雙向）。
- **不要**逕自把 6 個宣告當成錯誤刪掉——那是設計意圖問題，需要人裁決。
