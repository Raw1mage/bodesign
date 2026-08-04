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

---

## §9 上游追溯：設計原意有記錄，而它推翻了 §6 的二選一

**2026-08-04，使用者裁示「回上游查設計原意」。查到了，而答案是第三種。**

### §9.1 上游是誰

`spec.json` **未進版控**（`git ls-files` 不認；控制組：已追蹤檔會回檔名），無 history。改以內容特徵追溯：

```
grep -rIl 'PP_VBUS|PP_BAT|USB_ESD_VBUS'  排除 experiments/ 後唯一產生器命中：
  issues/assets_20260706_c03_session/gen_product.py
CONTROL bogus token 'ZZNOPE_VBUS' -> 0 個檔案（探針有判別力）

該檔宣告的 netdef 總數 = 13        spec.json 的 net 總數 = 84
comm 差集：只在腳本裡的 = 1（PP_ON_GND，腳本自己在 :139 刪掉）
```

**它不是產生器，是增補腳本**——`:31` 從既有 `.net` 反建，再補三顆定案料。`VBUS_5V` / `VBAT` 不在它手上，來自被反建的那份 netlist。

> **邊界**：`sch_product/aiguard_product.net` 現在是**空的**（817 bytes，`(nets)` 無內容，時間戳比 spec.json 晚 1 分鐘 —— 已被後續重跑覆蓋）。`VBUS_5V`/`VBAT` 的原始出處**無法從它復原**。以下結論全部來自腳本內的文字記錄與 spec.json 現況，不依賴那個檔。

### §9.2 設計原意，逐字

`gen_product.py:78-81`：

> 反建發現: 既有 .net 把 J1 全 pin + U9.SYS/BAT + JSA/JSB 全 pin 熔進單一 "BAT_SENSE" 巨網
> (前棒 all_label 前殘留結構)。**為 min-change 且不破壞既有 ERC-0, 新料以「獨立新 net」銜接,
> 不改寫既有 BAT_SENSE 節點。** 新料因此建立獨立 power-path 支線 (PPATH_*),
> **與既有巨網並存** —— 電氣上這代表 U10/U11/U12 為新增保護段, 既有 U9 主幹不動。

**所以那 6 個多-net 宣告不是失誤，也不是別名——是一個被明文記錄的 min-change 決策的必然產物。** 作者刻意不改寫既有巨網，於是新支線與舊網共用同一批 pin。

§6 問「是別名還是 spec 漏了元件」。**兩個都不是。元件在，宣告也是刻意的。**

### §9.3 但那段註解宣稱的電氣意義，與資料實際表達的不同

保護鏈的設計路徑（`:103-118` 註解）：

```
J1.A4B9/B4A9 -> U10.3(VIN1)  ...  U10.2/7(VOUT) -> U11.1(VIN)  ...  U11.6(VOUT) -> U9.1
```

而 `VBUS_5V` 的成員（**同時含鏈的兩端**）：

```
VBUS_5V = [C1.1, J1.A4B9, J1.B4A9, JSA.1, JSA.2, U9.1]
                 ^^^^^^^^ 鏈的輸入端              ^^^^ 鏈的輸出端

CONTROL 只含輸入端不含輸出端的 net：PP_VBUS · USB_ESD_VBUS（探針能區分）
CONTROL PP_VBUS 是否含 U10 輸出（U10.2/U10.7）？False —— 新支線本身沒有旁通
```

**一條線直接把 U10 與 U11 兩顆保護元件並聯短路掉。**

註解說「電氣上這代表 U10/U11/U12 為新增保護段」。資料說的是「新增一段保護，與一條把它短路的線並聯」。**並聯在短路上的保護元件不提供保護。**

這不是作者說謊——是「並存」這個 min-change 決策在 VBUS 側的電氣後果，而那段註解**陳述了決策卻沒有陳述後果**。

### §9.4 電池側是不同的答案：那才是真別名

```
VBAT   = [BT1.1, C5.1, L1.2, U9.13, U9.14]
PP_BAT = [U10.6, BT1.1, U9.13, U9.14, C_PP2.1]
shared = BT1.1 · U9.13 · U9.14

CONTROL PP_BAT 是否含 U10 輸出（U10.2/U10.7）？ False -> 這側沒有旁通
```

`U10.6` 是 VIN2，**取樣點不是輸出點**。兩條 net 都是「電池正極 ↔ 充電 IC BAT 腳」這同一個電氣節點的兩個名字。**這側是別名，§6.1 的 union-find 修法對它成立。**

### §9.5 所以 6 個 pin 分成兩組，修法不同

| 組 | pin | 判定 | 修法 |
|---|---|---|---|
| **VBUS 側** | `J1.A4B9` `J1.B4A9` `U9.1` | **真電氣缺陷** —— legacy 網把保護鏈短路 | 資料側：從 `VBUS_5V` 移除 `U9.1`（讓充電輸入只能經 U11 到達）。**需人裁決**，因為那正是作者刻意不動的巨網 |
| **BAT 側** | `BT1.1` `U9.13` `U9.14` | **真別名** | §6.1 union-find，或合併兩個名字 |

**§6 的二選一在這份 spec 上同時為真，只是各對一半。** 把 6 個當同一件事處理，無論選哪個選項都會錯 3 個。

### §9.6 這對 gate 的意義

§6.3 的 fail-loud（已於 `31d537b` 落地）**仍然正確且已足夠**——它顯式標示「基準不是分割」，不預設哪一種成因。

但 §6.1 的 union-find **不可無條件套用**：對 BAT 側正確，對 VBUS 側會把一個真短路吸收成「預期如此」，讓 gate 永久看不見它。**這正是 gate 存在的理由被反轉。**

> 若日後實作 union-find，必須要求呼叫端顯式列舉被合併的 net 名（allow-list），不得自動合併所有共點 net。

### §9.7 沒量的

- `VBUS_5V` / `VBAT` 的**原始**出處（來源 `.net` 已被覆蓋清空）
- 這條短路是否已反映在實體板上（本 BR 全程在資料層，未查 layout / 實測）
- 其他 spec（led / CCM）是否有同形狀的 legacy 旁通
