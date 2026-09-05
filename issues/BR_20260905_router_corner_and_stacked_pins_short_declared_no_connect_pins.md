# BR_20260905 — 繞線轉角壓在他網 pin 上、與堆疊 pin 的庫語意衝突，使宣告的 NO_CONNECT 腳被真的短路

- **Status**: PARTIALLY FIXED（U2.17 已修並驗證；D1.5 判定為 spec/庫語意衝突，非 emitter 缺陷，**未改**）
- **Severity**: HIGH（產出的原理圖含真短路；且原定修法會使 fidelity gate 永久失去判別力）
- **Family**: schematic-engine
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`（**不是** `fidelity.py` — 見 §5）
- **Related**: `BR_20260905_compose_schematic_lacks_multi_unit_symbol_support.md` §4.4（本單路標來源，其成因推論已被本單證偽）

> **給未來 handler 的第一句話**：這張 BR 原本的檔名是「no_connect_nodes_not_excluded_from_fidelity_spec_baseline」。
> **那個成因是錯的，而且照著修會把 gate 弄瞎。** 先讀 §5 再動手。

---

## 1. 結論

真板 btdongle 的殘留 `ONLY_CANDIDATE ['D1.5','U2.17']` **不是** fidelity 記帳誤判，
是產出的原理圖裡**兩個真的短路**，各自成因獨立：

| 節點 | 成因 | 處置 |
| --- | --- | --- |
| `U2.17` | **繞線轉角落在他網 pin 上**（router 選轉角只看幾何；KiCad 在 wire 頂點處與 pin 相接）| **已修**（§4.1）|
| `D1.5` | **庫把 pin2/pin5 宣告為同一節點**（共陽極 `A`，同名同座標），spec 卻要 pad2 接 GND、pad5 不接 | **未修**：spec/庫語意衝突，非 emitter 缺陷（§4.2）|

---

## 2. 派工前提被證偽（NC 從未進 baseline）

原假設：「NC 節點被算進 fidelity 的 spec partition 母體 → 誤判斷路 FAIL」。實測**兩個環節都不成立**：

```
NC pins declared            : 32
NC pins present in baseline : 0   []
CONTROL: D1.2 (真 GND pin) in baseline -> True
baseline node count         : 135
```

控制組回 True ⇒ 探針讀得到 baseline，那個 0 是真的。
機制：baseline 只由 `fidelity.py:341 expected_partition_from_nets(design.NETS)` 建構；
`NO_CONNECT` 走 `spec["nc"]` → composer `nc_list` → emitter 畫 `(no_connect ...)` 圖示，**從未進 nets**。
⇒「把 NC 排除出 baseline」是 **no-op**。

### 2.1 既有豁免本來就對

`D1.6` 同為 NC 宣告，在 candidate 側是乾淨 singleton（`unconnected-(D1-K4-Pad6)`），
落進既有的 `fidelity.py:411 singleton_only_candidate` 豁免，**完全沒造成 FAIL**。

⇒ 真正未接的 NC pin 既有機制已正確放行。**唯一會衝到 `only_candidate` 的 NC pin，
是那些被接上了東西的**——也就是恰恰該報的那些。

---

## 3. 量測：那兩個 FAIL 是什麼

改前 gate 輸出（真板，逐字）：

```
baseline nets=27 nodes=135 | candidate nets=57 nodes=167 | shared=135
FIDELITY FAIL moved=0 only_baseline=0 only_candidate=2
  ONLY_CANDIDATE (extra in candidate): ['D1.5', 'U2.17']
```

`kicad-cli` 匯出的 netlist（net 名稱層級，非推論）：

```
NET 'GND'                      size=49  hits=['D1.5']
NET '/RUN'                     size=5   members:['C7.1','R8.2','SW2.1','U2.17','U2.30']
NET 'unconnected-(D1-K4-Pad6)' size=1   hits=['D1.6']
```

**D1.5 焊在 GND、U2.17 焊在 /RUN。gate 報 FAIL 是對的。**

---

## 4. 兩個真成因

### 4.1 U2.17：繞線轉角壓在他網 pin 上（已修）

```
WIRE (1023.62,335.28) -> (1092.2,335.28)     # /RUN 從 C7.1 側水平過來
WIRE (1092.2, 335.28) -> (1092.2,213.36)     # 轉角後垂直上行到 U2.30
U2.17 root = (1092.2, 335.28)                # 轉角點，逐字等於 U2.17 接點
```

`_orthogonal_route` 選 H-first / V-first 轉角時只看**障礙盒**，而 pin 尖端**伸出 body 之外**，
落在 router 迴避的盒子外面 ⇒ 轉角壓在 pin 上時，既有每一道 gate 都判它 clear。

**修法**：新增 `_route_clears_points`，把「本網以外的所有 pin 接點」作為**頂點**禁區，
併進 `_guard_route` 的 `extra_ok` 述詞（2-pin 與 multi-node 兩條路徑都接）。

**VERTEX ONLY，這個邊界是量出來的不是假設的**：KiCad 在 wire **頂點**與 pin 相接；
wire 只是**中途橫越**（mid-span）一個 pin 點**不會**連上它。

| 量測 | R2.2 幾何 | netlist 判定 |
| --- | --- | --- |
| HEAD 幾何（2 電阻對照） | mid-span 橫越 | `unconnected-(R2-Pad2)` **未連** |
| 同一張圖的 R2.1 | 頂點 | 在 NET_X 上 **已連**（控制組） |
| 真板 | 20 個 NC pin 落在 mid-span | 只有 2 個（頂點那 2 個）變成額外節點 |

⇒ 用「閉區間相碰」當述詞是**錯的不是保守**：它會否決無害的橫越，
逼 router 去 jog 一段本來電氣正確的幾何。**代價已實測**：第一版我寫成閉區間，
當場弄紅 `test_kicad_emit` 兩顆（見 §6.1）。

**這也順帶回答了前一版 §7「20 個 mid-span 卻只多 2 個節點」的未量問題**：那 2 個正是頂點案例。

### 4.2 D1.5：spec 與庫的語意衝突（未修，非 emitter 缺陷）

上游庫 `Power_Protection:PESD5V0L4UF`（extends `PESD3V3L4UF`）本身就把兩個 pad 宣告為同一節點：

```
lib pin2: name='A' at=(2.54, 0.0)
lib pin5: name='A' at=(2.54, 0.0)      <- 同名 同座標 = 共陽極，一個電氣節點
CONTROL pin1: name='K1' at=(-2.54,0.0)  <- 對照：不同名不同座標
```

而 spec 要求：`D1.2 -> GND`、`D1.5 -> NO_CONNECT`。
**這兩件事在原理圖層面不可能同時成立**：一個堆疊點就是一個節點。
emitter 忠實反映了庫的宣告，`D1.5` 因此隨 `D1.2` 上 GND。

⇒ **不是 emitter 缺陷，是輸入自相矛盾。** 正解在 spec 或庫，不在 emitter：
(a) design.py 把 `("D1","5")` 從 NO_CONNECT 移除（承認它與 pad2 同節點，接 GND 是對的）；
或 (b) 換一顆把四通道分開畫的符號。**兩者都是 owner 的設計決定，不該由 emitter 代為裁決。**

#### 為什麼「壓平時 pin 座標去重 + 重合即 fail-fast」不能做

派工單原本授權這條。實測後**不做**，因為它會拒絕大量標準庫符號：

```
stock libs scanned          : 223
sub-unit symbol blocks      : 23747
blocks WITH coincident pins : 3197  (13.46%)
  coincident, SAME pin name : 24137   <- 庫的合法慣用法（一個節點多個 pad）
  coincident, DIFF pin name : 1
例：74xx:74ALVC164245_1_1 pin10+pin15 both name='GND'
```

**同名共座標是 KiCad 庫表達「一個電氣節點、多個封裝腳」的標準慣用法**，13.46% 的
sub-unit 區塊都有。對它 fail-fast 等於讓 emitter 拒絕八分之一的標準庫。
`_stack_units` 也**沒有製造**這個重合——重合在上游庫裡就有（量測：`_stack_units`
輸出的唯一重合對就是 pin2/pin5，且是同名的那一對；跨 unit 的 pin 因 7.62mm 位移而互不重疊）。

---

## 5. ⛔ 為什麼**不能**在 fidelity.py 加 NC 豁免（給未來 handler 的死路標記）

原定修法＝「建 baseline 時排除 spec 宣告為 NO_CONNECT 的節點」。由於 NC 本來就不在
baseline（§2），實作上只能變成**兩側都剔除 NC 節點**。實測其後果：

```
CURRENT code  : ok=False  only_candidate=['D1.5','U2.17']
PRESCRIBED fix: ok=True   only_candidate=[]
```

**gate 轉綠，而 D1.5 仍實際掛在 GND 上、U2.17 仍實際掛在 /RUN 上。**

它不需要退化成「排除所有孤立節點」就已經發生——**缺陷本身就長在 NC 節點上**，
所以「只排除 NC」剛好精準地蒙住那兩隻眼睛。

### 5.1 三控制組（證明上面那個綠是假綠燈，不是探針失靈）

| 控制組 | 目的 | 結果 |
| --- | --- | --- |
| A：對非 NC pin 造真短路（R8.2 併入 GND class）| 加豁免後仍須紅 | `ok=False moved=49 fused=48` **紅** |
| B：對非 NC pin 造真斷路（移除 C7.1）| 加豁免後仍須紅 | `ok=False only_baseline=['C7.1']` **紅** |
| C：忠實 candidate（accepting control）| 探針必須能回綠 | `ok=True` **綠** |

C 是決定性的：它排除「這支探針恆紅」的解釋 ⇒ A/B 的紅是真判別力，
而 §5 那個 `ok=True` 是**真的假綠燈**。

> `fidelity.py:61` 註解自陳既有豁免刻意保持可見：「an exemption the reader cannot see is
> indistinguishable from a check that was never made」。加一個看不見的 NC 豁免正好違反該設計哲學。

---

## 6. 驗收

### 6.1 修法自身的迴歸（誠實記錄：第一版寫錯過）

第一版述詞用**閉區間相碰**（連 mid-span 都禁），弄紅兩顆既有測試：

```
FAIL: test_anti_fusion_guard_untouched_when_no_collision
      AssertionError: Lists differ: [] != ['NET_X']      <- 乾淨路線被無謂 jog
FAIL: test_minimal_two_resistor_spec_still_shorts
      AssertionError: FidelityError not raised           <- 723e fixture 幾何被擾動，不再複現
```

**歸因方式**：`git stash push -- <單一檔案>` 驗 HEAD ⇒ HEAD `Ran 46 tests ... OK`（零失敗）
⇒ 確認是我造成的，非既有。改為 **vertex-only** 後三模組全綠（§6.2）。

### 6.2 測試（判別欄位 `Ran N`，跑前已清 `__pycache__`）

```
tests/test_kicad_emit.py    : Ran 46 tests   OK
tests/test_fidelity_gate.py : Ran 5 tests    OK
tests/test_composer*.py     : Ran 5 tests    OK
FAIL/ERROR 名稱掃描          : 空（控制組：同一支 grep 對存在的字串回 1）
```

### 6.3 真板（before / after 逐項對照）

| 項目 | 改前 | 改後 |
| --- | --- | --- |
| `moved` | `[]` | `[]` |
| `only_baseline` | `[]` | `[]` |
| `only_candidate` | `['D1.5','U2.17']` | `['D1.5']` |
| candidate nets | 57 | 58 |
| U2.17 在 netlist | `/RUN` 成員 | `unconnected-(U2-GPIO13-Pad17)` ✅ |

**① multi_unit 未被打回**：`moved = 0`（① 把它從 10 → 0，本次維持 0）。

### 6.4 修完後 gate 仍有判別力（迴歸網）

```
A 真短路於非 NC pin : ok=False moved=49 fused=48        紅 ✅
B 真斷路於非 NC pin : ok=False only_baseline=['C7.1']   紅 ✅
C 忠實 candidate 去掉 D1.5 殘留 : ok=True moved=0 only_b=[] only_c=[]   綠 ✅
```

C 這格的寫法有調整並須說明：修完後的真板 candidate 因 D1.5 仍 FAIL，
**它已不能充當 accepting control**（一個永遠回紅的控制組沒有判別力）。
故改用「candidate 去掉 D1.5 殘留」——它回綠，才證明探針**能**回綠，
於是 A/B 的紅是真判斷；同時也證明 **D1.5 是本板唯一剩餘分歧**。

---

## 7. 量了什麼 / 沒量什麼

**量了**：NC 是否進 baseline（配控制組）、兩個殘留節點的 candidate 同班成員、
kicad-cli netlist 的 net 名稱歸屬、涉事 pin 絕對座標與 wire 幾何、
vertex-vs-midspan 連接規則（配控制組）、223 個標準庫的共座標 pin 普查、
原定修法的判別力（配三控制組）、三測試模組、真板 before/after、① 未回歸。

**沒量**：
- **視覺軸完全未量**：未轉圖、未做 fresh-eyes 覆核。新增的頂點禁區可能讓某些網改走較長路徑，觀感未知。
- **未跑全套 142 模組**，只跑指定的 3 個模組。
- **`_route_clears_points` 對大板的效能未量**（每網 O(waypoints × 全域 pin 數)）。
- **只驗這一塊板**：頂點禁區在其他拓撲上是否造成 label 降級增加，未量。
- **D1.5 的兩條正解（改 spec / 換符號）皆未實作驗證**，是紙上推論。
- 幾何/座標綠燈**不授權**「電路對了」的宣稱。

**環境**：作業中途 guest GoogleDrive 掛載 I/O 失效（同掛載控制檔亦失效），
改用前一顆 handler 留在 scratch 的複本（md5 `6aa4d8800c10c9dcc30ebb30a74457bc`、
size 15908，與掛載死前記錄的 guest 端一致）。**guest repo 零寫入。**

---

## 8. Landed diff

```
packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py | 70 insertions(+), 2 deletions(-)
```

`fidelity.py` **零修改**（控制組：`git status --porcelain -- fidelity.py` 回空）。
維持未 commit，等 dispatcher 驗。
