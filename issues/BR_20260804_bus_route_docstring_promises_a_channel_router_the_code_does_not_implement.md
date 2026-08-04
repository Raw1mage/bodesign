# BR_20260804 — `_bus_route` 的 docstring 承諾一個 code 沒有實作的 channel router

- **Severity**: MEDIUM（本體無使用者可感知傷害；傷害在**它讓兩張 BR 的 RCA 指向錯的函式**）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:2797-2850`（`_bus_route`）
- **Family**: schematic-engine
- **Owner**: ses_03408d1faffeKuPkQZ9Zj6gWO2
- **Status**: open
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

## Related

- `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion.md`
  （**同一個 fix surface，且本 BR 直接修正它的兩處 RCA**：路徑歸屬錯誤 §4、fix#1 已實作 §5）
- `issues/closed/BR_20260706_draftsman_collinear_wire_fusion_shorts.md`
  （同 failure class：共線熔合。當時的 fix 建立了 `fusion_registry`，而本 BR §6 指出該
  registry 的註冊/檢查不對稱）
- `BR_20260802_reset_hard_destroyed_kicad_emit_and_the_BR_blamed_the_import_that_was_correct.md`
  （**方法論引用**：該 BR 因把「被摧毀」誤讀為「從未寫過」而寫出反向根因；本 BR §2 的
  recovery-ref 查證正是為了不重蹈，且結論相反——這次確實是從未寫過）
