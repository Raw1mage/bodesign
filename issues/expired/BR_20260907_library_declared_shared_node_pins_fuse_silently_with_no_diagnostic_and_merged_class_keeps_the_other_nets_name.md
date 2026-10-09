# BR_20260907 — 庫宣告的共節點 pin 與 spec 衝突時，引擎靜默熔合且無任何診斷；合併後沿用他網名稱使名稱型檢查讀成乾淨

- **Status**: OPEN（未修 · 本單只立案取證，未動 code）
- **Severity**: MEDIUM（真板現況**無害**且 fidelity gate 攔得住；缺的是診斷，不是攔截）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`（`load_symbol` / `_stack_units`）、
  `packages/eda-bridge/bodesign_eda_bridge/fidelity.py`（合併類別的命名）
- **Filed**: 2026-09-07 by handler `ses_f87134d36ffe7Bgm4z5GclPidc`，
  依 btdongle 真板 baseline 量測 session `ses_f871fc491ffeUC3rImkn99fop4` §Issues-2 取證立案
- **Family**: schematic-engine
- **HEAD at filing**: `ded8b95`
- **Related**:
  - `issues/BR_20260905_router_corner_and_stacked_pins_short_declared_no_connect_pins.md` §4.2 —
    **同一失效機制的已裁決前例**。該單對 `D1.5`（`PESD5V0L4UF` pin2/pin5 同名同座標）判定為
    「spec 與庫的語意衝突，**非 emitter 缺陷**，未修」。**本單的 `U2` 是同一形狀**（見 §2 控制組 B），
    因此本單**不主張** emitter 有幾何缺陷；本單主張的是該單留下的缺口：**衝突發生時沒有任何診斷**。
    該單 §4.2 也已量出「壓平時 pin 座標去重 + 重合即 fail-fast」是死路（13.46% 標準庫符號會被拒），
    本單 §5 承接該結論，不重複那條路。
  - `issues/BR_20260905_compose_schematic_lacks_multi_unit_symbol_support.md` —
    **明確劃清：本單不被該單涵蓋。** 該單處理 multi-unit 壓平造成的**跨 unit** 座標重合
    （`_stack_units` 位移可解）。`U2` 是**真正的單 unit** 符號（`extends RaspberryPi_Pico_Debug`，
    只有 `_0_1` / `_1_1`，量測見 §2），**沒有 unit index 可供分離**，`_stack_units` 對它是 no-op。
    這是不同成因，故獨立立案。

---

## ⚠ 給讀者的第一句話：派工前提已被本單量測修正

立案派工單的假設是「這 8 支 pin **現況無害只因它們剛好全接 GND**」——
言下之意是座標重合屬意外，換一張 spec 就會爆。

**本單量測推翻了這個假設。** 8 支 pin **全部名為 `GND`**（`distinct_names=1`）。
依 `BR_20260905_router_corner...` §4.2 的既有判準，**同名共座標是 KiCad 庫表達
「一個電氣節點、多個封裝腳」的標準慣用法**，不是缺陷。

**這改變了 framing，也改變了修法**：它們不是「碰巧同 net」，而是**庫宣告它們就是同一個節點**。
下面 §2 是這個修正的證據與控制組。

---

## 1. 現況（真板，`ok`）

```
symbol: MCU_Module:RaspberryPi_Pico_W_Debug   (U2)
coord (0.0, -35.56) → pins ['3','8','13','18','23','28','38','D2']   count=8
```

真板 spec 上這 8 支全在 `GND` 上，`fidelity_ok=True moved=0`，
GND 49 pin round-trip 完整存活。**本板無缺陷行為。**

---

## 2. 本單一手量測：它們是同名的（修正派工前提）

探針直接從 `load_symbol` 回傳的 s-expr 取 `(name ...)`，非推論：

```
U2 = MCU_Module:RaspberryPi_Pico_W_Debug   total_pins=43
coincident_groups=1
  coord=(0.0, -35.56) count=8
    pins  = ['3','8','13','18','23','28','38','D2']
    names = ['GND','GND','GND','GND','GND','GND','GND','GND']
    distinct_names=1        ← 1 = KiCad 合法慣用法；>1 才是缺陷
```

| 控制組 | 目的 | 結果 |
| --- | --- | --- |
| **A**：`Device:R`（確定單純的單 unit 符號） | 探針不會亂報重合 | `total_pins=2` **`coincident_groups=0`** ✅ |
| **B**：`Power_Protection:PESD5V0L4UF`（已裁決前例） | 探針能重現已知案例 | `coord=(2.54,0.0) pins=['2','5'] names=['A','A'] distinct=1` ✅ |

**控制組 B 是決定性的**：它讓探針對一個**已被 `BR_20260905_router_corner...` §4.2 判定為
「非 emitter 缺陷」的案例**回報出**與 `U2` 完全相同的形狀**（重合、同名、distinct=1）。
⇒ `U2` 落在同一個已裁決類別，不是新的幾何缺陷。
控制組 A 排除「這支探針對任何符號都回報重合」。

**單 unit 佐證（轉述自量測 session §②，本單未複現）**：
`_pin_unit_map(block)` → 43 entries、`distinct_units=[1]`；`_unit_offsets` → `{1: 0.0}`
⇒ stacking 對此符號 INACTIVE。

---

## 3. 缺陷是什麼（既然不是幾何）

**缺陷是：當 spec 要求把庫宣告為同一節點的 pin 分到不同 net 時，引擎靜默熔合，
且沒有任何一格輸出說出「你的 spec 與庫的宣告矛盾」。**

量測 session 的判別對照（**轉述**，本單 handler 未複現）：

| arm | mutation | fidelity | KiCad 判定 |
| --- | --- | --- | --- |
| **A**（正控制） | `U2.D2`（共座標）GND→SWCLK | `failed, fused=51` | **GND size 0**，SWCLK **51** — 整片接地被吸收 |
| **B**（負控制） | `U2.31`（獨立座標）VBAT_SENSE→SWCLK | `ok, fused=0` | GND=49、SWCLK=3 乾淨 |

同一種 mutation、相反結果 ⇒ **機制是座標重合，不是「改了 spec」**。

**本單 handler 的補充判讀（推論，非量測）**：arm A 的那個 mutation
**本身就是一份不可能被滿足的 spec**——它要求一個節點同時是兩條 net，與
`BR_20260905_router_corner...` §4.2 的 `D1.5`（spec 要 pad2 接 GND、pad5 不接）逐字同構。
所以 arm A 證明的不是「引擎會壞」，而是**引擎在收到自相矛盾的 spec 時，
以熔合的形式沉默地選了一邊**。

---

## 4. ⭐ 最該被記住的一層：合併類別沿用**他網**名稱，使名稱型檢查回報 false pass

arm A 熔合後，合併類別**保留了另一條 net 的名字**（`SWCLK`，size 51），
而 `GND` 這個名字對應到 **size 0**。

於是這樣寫的謂詞會**讀成乾淨**：

```python
# ✗ 零判別力：J3.1 確實還在某個叫 GND 的東西裡（或 GND 已不存在而查詢回空被讀成無異常）
assert ("J3","1") in nets_by_name["GND"]
```

**量測 session 的第一版謂詞就是這樣寫的，會回報 false pass**（轉述自 §②）。

**有判別力的是 size（0 / 51），不是名字。** 這條要寫進任何觸碰 net 歸屬的檢查：

```python
# ✓ 有判別力：問「這條 net 的規模對不對」，而不是「這個名字還在不在」
assert len(nets_by_name["GND"]) == 49
```

> 這正是 code-thinker §8 說的「判別力不是一行代碼的性質，是這一行 ＋ 它要回答的問題這一對的性質」。
> `("J3","1") in nets["GND"]` 拿來問「J3.1 接地嗎」在正常情況下完全正確；
> 拿來問「有沒有發生熔合」零判別力——**因為熔合恰好保留了那個名字**。

---

## 5. 好消息：閘是有效的（缺陷不在攔截，在診斷）

開 `fidelity=True` 時 composer **抓得到** arm A：

```
FidelityError … 51 node(s) gained peers
```

**所以本單不是「有東西會漏出去」。** 缺陷精確地是：

1. **缺陷條件（8 支共節點 pin）存在於出貨產物中**，只被「8 支剛好同 net」掩蓋著；
2. **衝突發生時，錯誤訊息說的是後果不是原因**——`51 node(s) gained peers` 不會告訴
   作者「因為 `U2.D2` 與 `U2.3/8/13/...` 在庫裡是同一個節點」。作者要自己去翻庫才知道。

`BR_20260905_router_corner...` §4.2 的 `D1.5` 花了一整輪 handler 時間才查出這件事。
**同一件事會再花一次。**

---

## 6. Proposed（**方向，不是實作** — 本單未動任何 code）

**不要做的**（已被前例證偽，寫下來避免重蹈）：
- ✗ **壓平時 pin 座標去重 + 重合即 fail-fast**。`BR_20260905_router_corner...` §4.2 實測：
  223 個標準庫、23747 個 sub-unit 區塊中 **13.46% 有共座標 pin**，其中同名 24137 對、
  異名僅 1 對。對同名共座標 fail-fast ＝ 讓 emitter 拒絕八分之一的標準庫。
- ✗ 讓 emitter 代為裁決該聽 spec 還是聽庫。那是 owner 的設計決定。

**建議方向 —— 補診斷，不改行為**：

1. **`load_symbol` 記錄共節點群組**：把 `{coord: [pin_numbers]}` 中 `len >= 2` 且**同名**的群組
   保留成符號的一項屬性（例：`shared_node_groups`），而非在壓平時丟棄。
2. **spec 綁定時做一次交叉檢查**：若同一群組內的 pin 被 spec 指派到 **>1 條 net**，
   在**熔合發生之前**發出明確診斷：

   ```
   spec/library conflict: U2 pins ['3','8','13','18','23','28','38','D2'] are ONE node in
   MCU_Module:RaspberryPi_Pico_W_Debug (all named 'GND' at (0.0,-35.56)), but the spec
   assigns them to 2 nets: GND, SWCLK. A schematic cannot express this.
   Fix in the spec, or use a symbol that draws these pads separately.
   ```
3. **這個診斷同時涵蓋 `D1.5`**，是 `BR_20260905_router_corner...` §4.2 留下的缺口的正解——
   該單當時把它歸為「輸入自相矛盾」而未修，正確；但**「輸入自相矛盾」本身應該被說出來**。
4. **`FidelityError` 訊息增補歸因**：`51 node(s) gained peers` 後面接一句
   「largest gain traces to a library-declared shared node: ...」。

### 6.1 修法必須自帶的控制組

- **正控制**：arm A（`U2.D2` → SWCLK）必須產生新診斷。
- **負控制 1**：arm B（`U2.31` → SWCLK，獨立座標）**不得**產生該診斷。
- **負控制 2**：真板未修改的 spec **不得**產生該診斷（8 支同 net，無衝突）。
- **負控制 3（防過度攔截）**：一個含同名共座標但 spec 一致的標準庫符號
  （例 `74xx:74ALVC164245_1_1` pin10+pin15 both `GND`，前例 §4.2 記載）**不得**被拒。

---

## 7. 邊界宣告（引用本批讀數者必須一併帶走）

本單引用的讀數來自 btdongle fixture。**這塊板沒有被製造、組裝或量測過**——
`design.py:44-46` 自陳：「no board here has been fabricated, assembled, or measured.
Charge current, buck output and antenna performance are design targets computed from
datasheet formulae, never bench results.」

這批讀數是有效的**幾何／連通性**回歸母體，**不是**已驗證的電氣行為基準。
**任何電氣宣稱不得引用它。**

---

## 8. 量了什麼 / 沒量什麼

**一手量測（本單 handler，配控制組）**：
- `U2` 共座標群組的 pin 編號、座標、**pin 名稱**與 `distinct_names`（§2）
- 控制組 A：`Device:R` → 0 群組
- 控制組 B：`PESD5V0L4UF` pin2/5 → 同名，重現已裁決前例的形狀
- `U2` total_pins = 43

**轉述（來源 `ses_f871fc491ffeUC3rImkn99fop4` §②，本單 handler **未**複現）**：
- arm A / arm B 對照表的全部數值（`fused=51`、GND size 0、SWCLK 51、arm B 乾淨）
- `_pin_unit_map` / `_unit_children` / `_unit_offsets` 的單 unit 判定
- `FidelityError … 51 node(s) gained peers`
- 「第一版謂詞會回報 false pass」這件事

**本單 handler 的推論（標明為推論，非量測）**：
- §3 末段：arm A 的 mutation 本身是不可滿足的 spec，與 `D1.5` 同構
- §6 的修法方向與診斷訊息措辭

**沒量**：
- **未複現 arm A / arm B**。整張對照表是轉述。修法落地前應先把 arm A 變成會紅的測試。
- **未普查本 repo 其他 fixture 是否有異名共座標**（`distinct_names > 1` 那一類，
  前例全庫普查中只有 1 例）。只查了 `U2` 與兩個控制組。
- **未量診斷本身的效能成本**（每次綁定要做群組交叉比對）。
- **視覺軸完全未量**。
- 幾何／座標綠燈**不授權**「電路對了」的宣稱。
