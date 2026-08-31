# BR_20260804 — `_bus_route` 的 docstring 承諾一個 code 沒有實作的 channel router

- **Status**: FIXED（Option C，2026-08-31，handler `ses_fa7a4e045ffeM5zWajS6JvljoT`）
- **Severity**: MEDIUM（本體無使用者可感知傷害；傷害在**它讓兩張 BR 的 RCA 指向錯的函式**）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:3016-3060`（`_bus_route` docstring）
- **Family**: schematic-engine
- **Owner**: ses_03408d1faffeKuPkQZ9Zj6gWO2
- **Filed**: 2026-08-04
- **Scheduled**: 未排（先於 P0 fixture 之前建檔，不插隊施工）

---

## 1. 現象

`_bus_route`（3+ pin net 的路由器）的 docstring 逐字描述一個 **channel 演算法**：

```
- rule: channel_y = max(pin_y) + 5.08 mm (grid: 4×1.27), guaranteed below all pins
        so drops never cross a symbol. Each distinct pin.x gets one drop; shared-x
        pins share a drop. Junctions only at interior taps.
```

**executable code 是 daisy-chain，不是 channel。** 實作把相鄰 pin 兩兩丟給 `_orthogonal_route`
（2842），junction 打在 `pts[1:-1]`（2848）。

## 2. 量測（可重跑）

```bash
cd /home/pkcs12/projects/bodesign
F=packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py

grep -n 'channel_y' "$F"
#   2806, 2813, 2814, 2815, 2819  <- 全部落在 docstring 區間 (2799-2824)
grep -c '_orthogonal_route' "$F"
#   5                              <- CONTROL：pattern 抓得到本檔識別字，不是 grep 壞了

awk 'NR>=2825 && NR<=2851' "$F" | grep -nE 'max\(|min\(|channel|drop'
#   (空)                           <- executable body 零 channel/drop/max-min 詞彙
```

**它不是被摧毀的，是從未寫過。** 本 repo 有過 `reset --hard` 摧毀 `kicad_emit.py` 的事故
（`BR_20260802_reset_hard_destroyed_kicad_emit_*`），該 BR 的教訓正是把「被摧毀」誤讀成
「從未寫過」，所以這格必須查證而非假設：

```bash
git log --oneline --all -S 'channel_y =' -- "$F"   # 1 hit: 1731897
git show 1731897 -- "$F" | grep '^+' | grep 'channel_y'
#   5 行，全部是 docstring 散文（'+    pin's drop-wire...' 等），無一行是賦值
echo "CONTROL:"; git log --oneline --all -S 'segments: list' -- "$F" | wc -l   # 2

# 事故的三個回收 ref 也查了：
git show refs/recovered/readiness_wip:$F | grep -c channel_y        # 5  == 現況，仍只有 docstring
git show refs/recovered/ses0c87_wip_provenance:$F | grep -c channel_y # 5
```

引入 docstring 的那個 commit **同時**引入了 daisy-chain 實作。兩者從第一天就不一致。

## 3. 為什麼這是缺陷而不是「註解過時」

docstring 給的不是描述，是**安全保證**：

> a channel y that is **strictly below every pin** … so drops **never cross a symbol**
> … it **never overlaps a symbol body or the part's other pin**

daisy-chain 給不出這個保證。它依賴 `_orthogonal_route` 的障礙迴避，而該函式在
「完全被包圍」時**明文退回 legacy elbow**（2773-2774：`fully boxed in: legacy
endpoint-correct route (machine check will flag it)`）。

這是 code-thinker §8.1.3(d) 的形狀：**宣稱存在但實際不存在的護欄，比缺少護欄更貴**——
它讓讀者停止尋找防護。而讀者確實停了，見 §4。

## 4. 實際代價：兩張 BR 的 RCA 指向錯的函式

`BR_20260723e`（HIGH，open）的 RCA 寫：

> draftsman 的 wire 幾何生成器 (`_orthogonal_route` / `_bus_route` / power stub)
> **只保證端點正確**，不保證不同 net 的 segment 不共線/不共點

但該 BR 自己的 repro spec，**最大 net = 2 nodes**：

| net | nodes | 走哪條路 |
|---|---|---|
| VO | 2 | `_orthogonal_route` |
| VOUT | 2 | `_orthogonal_route` |
| GND | 2 | `_orthogonal_route` |
| VIN | 1 | label |

`_bus_route` 的分流條件是 `len(endpoints) >= 3`（1416）。**它的 repro 一次都沒有執行
`_bus_route`。** RCA 把它列為並列根因，是因為 docstring 讀起來像在描述一個會產生共線
幾何的 channel（「one horizontal channel wire spanning [min_x, max_x]」——那確實會共線）。

**代價具體化**：照 723e 現有 fix proposal 派工，handler 會去改一個與該 symptom 無關的函式。

## 5. 順帶查出：723e 的 fix proposal #1 已經不成立

723e 要求：

> `_segment_fuses` 補「端點首尾相接（間隔=0）即熔合」的判定——目前 `_collinear_overlap`
> 要求 `overlap > _FUSION_EPS`（正重疊）

**該判定已存在**（2560-2571）：

```python
def _segment_fuses(seg, other_net_segs):
    for o in other_net_segs:
        if _collinear_overlap(seg, o):            # 正重疊
            return True
        if _point_on_segment(seg[0], o) or _point_on_segment(seg[1], o):   # 端點相接
            return True
        if _point_on_segment(o[0], seg) or _point_on_segment(o[1], seg):   # 反向
            return True
```

`_point_on_segment` 的 docstring 明寫 `(endpoints included)`（2543）。

所以 723e **必須在派工前重驗**：它是 2026-07-23 的快照，讀起來像現況。這正是
coordinator-discipline §C.0.1 的「派工前重驗 BR 是否仍成立」。

## 6. 一則觀察（尚未證明有害，不併入本 BR 的修法）

power-port stub 在 1591 **註冊進 `fusion_registry` 但從未被 `_segment_fuses` 檢查**：

```
註冊點： 1408 (2-pin)  1449 (bus)  1591 (power stub)
檢查點： 1261, 1267 (2-pin guard)  1421 (bus)      <- 無 1591 對應
```

power port 迴圈在 net 迴圈**之後**執行（net loop 止於 ~1476，power loop 始於 1526），
所以 stub 是最後加入的，且加入時不檢查與既有 segment 是否熔合。

**我沒有證明這會造成短路**，因此不寫成缺陷。同 net 的多個 port 本來就該連通；不同 power
net 的相鄰 stub 是否會共線，需要實例才知道。記在這裡是因為它與 §4 是同一個問題的兩面：
`fusion_registry` 的註冊與檢查不對稱，而不對稱不會自己發出訊號。

### 6.1 狀態：`observed-not-proven`（2026-08-04，handler `ses_03408d1fa` 量測）

**這不是「還沒有人看過」，是「已經有人看過、判定證據不足」** —— 兩者在下一個讀者眼裡必須分得開。
缺的是什麼：**不同 power net 的相鄰 stub 是否會共線，需要實例**。

P0 fixture 建好後順手量了（成本近乎零，fixture 已在那裡），**拿到負面證據**：

| 場景（完全不放 2-node wire） | 結果 |
|---|---|
| 單一 R，GND + +3V3 兩支腳各一條 power net | **OK** |
| 相鄰兩 R，各一條不同 power net | **OK** |
| CONTROL D：同一 power net 兩支腳 | OK（同 net 本該連通） |
| CONTROL E：已知最小重現 | **FidelityError** ← 探針仍有判別力 |

所以在兩顆電阻的幾何下，不同 power net 的相鄰 stub **不熔合**。這不是全稱證明：未涵蓋密集頁、
未涵蓋其他符號幾何。但它把這個觀察從「未知」移到「已量、未重現」。

### 6.2 我的第一版控制組是壞的 —— 這段比結論本身有價值

第一次量測時，treatment 是「最小重現再加一個 GND stub」→ FidelityError，看起來像坐實了 §6。
**但 CONTROL C 拿掉的正是騎在 SIG 線上那支腳**，所以我量的是已知的 wire-crosses-pin 機制，
**不是 §6 的宣稱**。兩者都回 FidelityError，從結果看不出差別。

重設計成「完全不放 2-node wire」後才拿到有效結果。

> **控制組必須與被測宣稱是同一個問題。**

一個「量了另一件事的控制組」與「沒有控制組」在輸出上完全一樣，而前者更危險 —— 它讓人
停止尋找驗證。同族：`BR_20260804b` 的控制組量的是「jq 讀不讀得到檔」不是「分不分得出缺席與 null」。

## 7. 建議修法（三選一，需 dispatcher 裁示，**不要自作主張選 B**）

| 選項 | 內容 | 風險 |
|---|---|---|
| **A** 改 docstring 對齊 code | 把 channel 敘述換成 daisy-chain 的真實契約 + 明寫「不保證不跨 symbol，依賴 `_orthogonal_route` 障礙迴避，且該迴避有 fallback」 | 最低。不動任何 executable byte |
| **B** 實作 channel router | 照 docstring 補 channel_y 演算法 | **高**。會改變所有 3+ pin net 的既有幾何，衝擊 aiguard CCM 各頁 wire 數基線（01_power=78 / 02_mcu=57），且 `_bus_route` **零測試覆蓋**（見下），改了沒有網接得住 |
| **C** A + 補測試 | A，另加 `_bus_route` 的行為測試鎖住現況 | 中。是我建議的 |

**`_bus_route` 目前零測試覆蓋**：

```bash
grep -rn '_bus_route' tests/     # 無輸出
echo "CONTROL: _orthogonal_route 出現在 3 個測試檔"
```

所以選 B 等於在沒有安全網的情況下改動產品路徑上的路由器。

## 8. 驗收判準（若採 C）

1. docstring 的每一條 `- rule:` 都能用一個可執行斷言對應，或明寫為 NOT-guaranteed
2. 新測試在把 daisy-chain 換成任意其他實作時會紅（mutation proof 三態：before/during/after）
3. 既有 `tests/test_kicad_emit.py` 不變綠→紅

## 9. 修復紀錄（2026-08-31，Option C）

**選 C：改 docstring 對齊 code + 補測試。零 executable byte 變更。**

### 9.1 docstring（`kicad_emit.py:3018-3060`）

刪除的虛假承諾（逐條）：

| 原文 | 為什麼刪 |
|---|---|
| `route every pin out to a shared horizontal CHANNEL` | code 不建 channel，走 daisy-chain |
| `channel_y = max(pin_y) + 5.08 mm` | 該賦值在檔案裡不存在（§2 已量測） |
| `guaranteed below all pins so drops never cross a symbol` | **安全保證**，daisy-chain 給不出 |
| `never overlaps a symbol body or the part's other pin` | 同上 |
| `Each distinct pin.x gets one drop; shared-x pins share a drop` | 無 drop 概念 |

新契約明述（每條對應一個測試，見 9.2）：

- 排序去重規則 `(x, y)` ascending，hops = `zip(pts, pts[1:])`；
- 每段 hop 委派 `_orthogonal_route`，waypoint 展開成連續 `(start, end)`；
- junctions = `pts[1:-1]`（interior 3-way meet）；
- **NOT guaranteed**：hop 不保證避開所有 symbol body——`_orthogonal_route`
  fully-boxed-in 時退回 legacy H-first elbow，殘餘穿越由 `check_wire_body_clearance`
  回報；且因為 hop 自己的兩個 host body 也在傳下去的 obstacle set 裡，hop 可能被
  **自己的零件**圍死；
- **NOT guaranteed**：不保證與他 net 不共線/不相接——那是呼叫端的 `_segment_fuses`
  / `fusion_registry` 契約，不是本 router 的；
- **NOT allowed**：對角線段、移動任何輸入 pin。

### 9.2 測試（`tests/test_kicad_emit.py::BusRouteTests`，7 個）

`_bus_route` 從**零覆蓋**變成 7 個測試。無 `skipUnless`（純幾何，不需 symbol lib /
`kicad-cli`——skip 與 pass 在輸出上無法區分）。每個測試對應一條 docstring 子句，
且**每個都自帶控制組**：

| 測試 | 鎖住的子句 | 控制組（證明探針會紅） |
|---|---|---|
| `test_chain_order_is_sorted_and_deduplicated_not_caller_order` | 排序 + 去重 | 換一組真正不同的 endpoint 必須 `assertNotEqual` |
| `test_segments_are_exactly_the_expanded_orthogonal_route_hops` | 幾何 == per-hop `_orthogonal_route` | L 形 net 的 segment 數 > hop 數（證明展開真的發生） |
| `test_chain_is_connected_and_reaches_every_pin` | done-when：連通 + 端點逐字保留 | 對刻意斷開的圖走一次，必須測得不連通 |
| `test_junctions_are_exactly_the_interior_chain_pins` | `junctions == pts[1:-1]` | 4-pin net 必須有 **2** 個 interior（否則「永遠空清單」也會通過） |
| `test_every_segment_is_axis_aligned` | NOT-allowed 對角線 | 對真對角線 `assertFalse` |
| `test_obstacles_are_passed_through_to_every_hop` | 避障是**委派**（行為證明，非閱讀 code） | 遠處無關 obstacle 必須不改變幾何 → 差異來自 obstacle 本身 |
| `test_boxed_in_hop_returns_a_non_clearing_route_not_an_error` | NOT-guaranteed：fallback 會穿越 | 同一探針對遠處 obstacle 必須回報 clear |

**mutation proof（§8 判準 2）**：`test_segments_are_exactly_the_expanded_orthogonal_route_hops`
把預期值**從 `_orthogonal_route` 現場重算**，而非寫死座標。任何非 daisy-chain 實作
（含 §7 選項 B 的 channel router）都會在此紅——它是「這個實作是 daisy-chain」的斷言，
不是「幾何長這樣」的快照。

### 9.3 驗證輸出（rc 逐項獨立捕捉）

```
$ PYTHONPATH="$PP" python3 -m unittest tests.test_kicad_emit.BusRouteTests -v
Ran 7 tests in 0.001s
OK                                            rc=0

$ PYTHONPATH="$PP" python3 -m unittest tests.test_kicad_emit
Ran 36 tests in 3.233s
OK                                            rc=0        (原 29 → 36，+7)

$ PYTHONPATH="$PP" python3 -m unittest tests.test_NON_EXISTENT_MODULE_CONTROL
ModuleNotFoundError: No module named 'tests.test_NON_EXISTENT_MODULE_CONTROL'
FAILED (errors=1)                             rc=1        ← 負控制組：runner 確實會非零
```

負控制組是必要的：`unittest` 對打錯的模組名同樣可能回 `OK`（若被當成 pattern），
**「測試全過」與「測試根本沒跑」在輸出上會共用同一個綠燈**。rc=1 證明本次 rc=0 有意義。

測試前已 `find . -name __pycache__ -prune -exec rm -rf {} +`（AGENTS.md §6.3：
`-B` 擋不掉既有 stale `.pyc`）。

### 9.4 沒有量什麼

- **未量** aiguard CCM 各頁 wire 數基線（01_power=78 / 02_mcu=57）。理由：本次
  **零 executable byte 變更**（`git diff --numstat` 對 `kicad_emit.py` 僅 docstring 行），
  幾何不可能改變。若 dispatcher 要求，可另行執行。
- **未修** §6 的 `fusion_registry` 註冊/檢查不對稱（power stub 1591 無對應檢查點）。
  維持 §6.1 的 `observed-not-proven`，不在本次範圍。
- **未修** §4 / §5 指出的 `BR_20260723e` 兩處 RCA 錯誤。那是另一張 BR 的檔案，
  在本次派工的禁碰清單內。

## Related

- `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion.md`
  （**同一個 fix surface，且本 BR 直接修正它的兩處 RCA**：路徑歸屬錯誤 §4、fix#1 已實作 §5）
- `issues/closed/BR_20260706_draftsman_collinear_wire_fusion_shorts.md`
  （同 failure class：共線熔合。當時的 fix 建立了 `fusion_registry`，而本 BR §6 指出該
  registry 的註冊/檢查不對稱）
- `BR_20260802_reset_hard_destroyed_kicad_emit_and_the_BR_blamed_the_import_that_was_correct.md`
  （**方法論引用**：該 BR 因把「被摧毀」誤讀為「從未寫過」而寫出反向根因；本 BR §2 的
  recovery-ref 查證正是為了不重蹈，且結論相反——這次確實是從未寫過）
