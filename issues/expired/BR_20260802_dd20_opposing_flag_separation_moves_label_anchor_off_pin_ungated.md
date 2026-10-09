# BR_20260802 — DD-20 對向旗標分離會把 label anchor 移離 pin endpoint，且這條路徑連閘都沒有

- **Status**: OPEN
- **Owner**: unassigned（`schematic-engine` family 無 owner）
- **Family**: `schematic-engine`
- **Severity**: **latent**（2026-08-04 下修，原 `real`）— 機制為真且該路徑無閘，但實測兩個產品頁位移皆 0，見 §補量。原評「一定會被執行」指的是**函式被呼叫**，不是**幾何條件成立**。
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:2199-2245`（`_dd19_dense_column_offsets` 的 DD-20 段）× `:2359-2366`（emit loop 套用處）
- **Filed at**: 2026-08-02
- **時區**: Asia/Taipei (UTC+08:00)
- **Filed by**: `ses_0c87bab06fferQ0umBs2Nybb5U`（依值星官 `ses_04db7a1c5` 的 §4 指示補量；**指示明言「若會，那是新的 BR，不要順手修」，故本輪未修**）
- **Parent**: `issues/BR_20260802_fidelity_gate_is_red_after_restore_and_never_ran_at_head.md`

## 為什麼另立一張

Parent BR 的根因是 `_avoid_label_overlap`（DD-14 graphics clearance）把 anchor 推離腳位。
那條路徑**至少名目上有一個閘**（`l6_avoidance` 參數，雖然已證實是死的、1515 行硬編 `True`）。

**DD-20 這條路徑連閘都沒有**，而且是刻意的——原始碼自己寫明：

```python
# kicad_emit.py:2320-2322
# It must NOT be gated behind l6_avoidance (product all-label pages leave that
# off, which is exactly where the connector co-point blob appears).
_dd19_offset = _dd19_dense_column_offsets(columns)
```

於是：**產品 all-label 頁（`l6_avoidance=False`）走不到 parent BR 的那條路徑，
卻一定會走到這一條。** 已量測的風險面比 parent BR 更大，而先前無人量過。

## 實測（兩段，各帶控制組）

### 段 1 — 真函式**能**產出非零位移

呼叫的是 `_dd19_dense_column_offsets` 本體，不是複製品：

```
輸入：同一 x 欄上一組對向垂直旗標
  ("VBUS_SENSE", 100.0, 50.0, (0.0, +1.0))   向 +y 生長，位置在上
  ("GND_RET",    100.0, 60.0, (0.0, -1.0))   向 -y 生長，位置在下
  w(VBUS_SENSE) = 12.90mm   w(GND_RET) = 9.75mm   anchor 間距 = 10mm < wp+wn

輸出：{('VBUS_SENSE',100.0,50.0): 6.96,  ('GND_RET',100.0,60.0): 6.96}

控制組 A（同一對，拉遠到 gap > wp+wn）      → {}   空
控制組 B（同向兩支，無對向關係）            → {}   空
```

兩個控制組證明這個偵測器**有鑑別力**，不是對任何輸入都吐東西。

### 段 2 — 位移的後果就是斷路

為了讓「只有 DD-20 這條路徑能移動 anchor」，先把 `_avoid_label_overlap` 中性化
（直接回傳原座標），再注入段 1 已證明真函式吐得出來的 6.96mm：

```
A 控制組  l6 中性化、dd19/dd20 未動      → fidelity ok=True   only_baseline=[]
                                          （證明測試骨架本身不會弄斷連接）
B 實驗    同上 + 對垂直 anchor 施加 6.96 → fidelity ok=False
            only_baseline = J1.1..J1.8 + R1.1..R8.1  （16 個節點，整頁斷光）
            wires = 9（與 A 相同）        labels = 16
            被任何 wire endpoint 觸及的 label = 0
```

**位移後沒有任何導體把 anchor 接回腳位**——與 parent BR 完全相同的機制，
因為受同一條 DD-22/23 契約約束（禁止 stub / jog / wire）。

## 誠實邊界（未量測的部分）

- **本 fixture 的真實輸入不會觸發 DD-20**：`DENSE_SPEC` 的垂直標籤 edge 全是 `(0,-1)`，
  無對向配對，真函式回 0 筆（段 2 的 `real_dd19_entries=0` 即為此）。
  **段 2 的 6.96 是注入的，不是本 fixture 自然產生的。**
- 因此本 BR 證明的是：**「若 DD-20 觸發 → 斷路」**（段 1 證明前件可達，段 2 證明後件成立），
  **而不是**「某個具體產品頁現在正在斷路」。
- ~~**真實產品頁（aiguard C03 等）是否已經在觸發 DD-20，未量測。**~~
  **已補量，見 §「補量：真實產品頁的觸發狀態」。結論：兩頁皆 0 筆位移。**
- DD-19 水平段（`_DD19_DENSE_MIN` 那條）在 DD-24 之後已無位移（原始碼註解稱 staircase
  已廢止），本輪未獨立驗證該註解是否與程式一致。

## 補量：真實產品頁的觸發狀態（2026-08-04, `ses_04db7a1c5`）

上面「最該優先補的一格」已補。方法是**包住真函式**（`_dd19_dense_column_offsets`）
在完整 `compose_schematic` 流程裡記錄它實際回傳幾筆，不重寫、不複製它的邏輯。

### 結果

| 產品頁 | wrapper 到達 | 標籤 | 欄 | 對向配對 | **位移筆數** |
|---|---|---|---|---|---|
| `experiments/aiguard_c03_compose/spec.json`（47 comp / 84 net, all_label） | 1 | 182 | 60 | 1 | **0** |
| `experiments/e2e-led-driver/…-npn.spec.json`（22 comp / 15 net） | 1 | 22 | 20 | 0 | **0** |

**兩頁都不觸發 DD-20。**

### 這個 0 為什麼可以採信

`entries=0` 與「函式壞了 / 探針沒上路」共用同一個輸出，故兩個控制組：

1. **wrapper 到達控制組** — `calls` 從 0 變 1。第一次量測 `calls=0`，原因是 compose 在
   `SymbolLoadError` 就中止（未傳 `symbol_dirs`），**根本沒走到 DD-20**。若當時採信，
   會得到「產品頁不觸發」這個**正確結論配上錯誤的證據**。
2. **同一個真函式的正控制組** — 對合成對向配對輸入
   `{100.0: [("VBUS_SENSE",100,50,(0,+1)), ("GND_RET",100,60,(0,-1))]}`
   回 **2 筆 × 6.96mm**（與 §段 1 逐字相符）。證明它有鑑別力，不是對任何輸入都回空。

### 為什麼不觸發（機制，非猜測）

aiguard 頁的 edge 分佈：`(-1,0)`=120 · `(0,-1)`=38 · `(0,+1)`=14 · `(1,0)`=10。
**12 個欄同時含兩個垂直方向**——欄層級的配對條件是滿足的。擋住它的是 `:2262-2275`
更細的幾何條件（`grow_pos` 須嚴格在 `grow_neg` 下方，且 `gap < wp + wn`）：

```
唯一通過「下方」篩選的對向配對：overlap = (wp + wn) - gap = -151.12 mm
觸發門檻：overlap > _CLEARANCE_MM (1.27)
```

**相隔 151mm，離觸發門檻極遠。** LED 頁則連一組對向配對都沒有（`grow_pos` 下方無 `grow_neg`）。

### 對本 BR 結論的影響

- §「為什麼另立一張」宣稱「產品 all-label 頁**一定會**走到這一條」——**這句話過強**。
  程式路徑確實無閘、確實一定會被呼叫（`calls=1` 證實），但**幾何條件在實測的兩頁上都不成立**，
  故實際位移為 0。「路徑無閘」≠「該頁正在斷路」。
- Severity 由 `real` 下修為 **latent**：機制為真且無閘（§段 1、段 2 仍成立），
  但**目前沒有已知產品頁在觸發它**。
- 仍**不建議單獨修**（§修法形狀不變）：它與 parent BR 層次 3 是同一個契約衝突。

### 本次未量的（誠實邊界）

- 只量了 **2 個** 產品頁。其他 spec（`payload*.json` 等）未量。
- **未量「未來的頁會不會觸發」**——本節是現況快照，不是不變式。元件位置或標籤命名一變，
  `gap` 與 `wp+wn` 都會變。要當不變式必須寫成測試，本輪未寫。
- DD-19 水平段的 DD-24 廢止註解，本輪**仍未**獨立驗證（沿用原 BR 的未量標記）。

## 修法形狀（不修，僅記錄）

與 parent BR 的層次 3 是**同一個契約衝突**：

> 「為了排版而移動 label anchor」與「anchor 必須落在 pin endpoint 上才有電氣連接」
> 直接衝突，而 DD-22/23 禁止用 stub wire 調和。

差別只在觸發者不同（DD-14 graphics clearance vs DD-20 對向旗標分離）。
**因此不應該各修各的**——若 parent BR 的層次 3 採「位移後斷言 anchor 仍在 pin endpoint
否則 fail-loud」，這條路徑會被同一個斷言涵蓋。

**建議與 parent BR 的層次 3 合併裁決，不要單獨修這一條。**

## Cross-ref

- parent BR §6 層次 3（契約層）
- `plans/eda-bridge_layered-pipeline/` — DD-19 / DD-20 / DD-22 / DD-23 / DD-24 決策紀錄
