# BR_20260804c — 一條 wire 被寫三次，而測試把它報成「cross-net fusion 存活」

- **Severity**: MEDIUM（不造成短路，但**讓 anti-fusion 回歸網在基線就是紅的**，且紅燈指向錯誤的成因）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`（wire emission）／
  `tests/test_kicad_emit.py:142-174`（`test_anti_fusion_guard_prevents_collinear_cross_net_wires`）
- **Status**: OPEN
- **Filed**: 2026-08-04 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（dispatcher，量測 kiutils 是否擋住 P0 時撞到）
- **Owner**: `schematic-engine`（`ses_03408d1fa`）
- **Family**: `schematic-engine`
- **Related**:
  - `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion.md`
    （同族：兩者都以 collinear overlap 為表徵；**本 BR 是那個判準的假陽性來源**，
    723e 的修法驗收會直接踩到它）
  - `BR_20260804_bus_route_docstring_promises_a_channel_router_the_code_does_not_implement.md`
    （同一輪、同一 owner；同族失敗形狀：**宣稱與實際不符，而讀者無從分辨**）

---

## 症狀

`tests/test_kicad_emit.py::test_anti_fusion_guard_prevents_collinear_cross_net_wires`
在 **HEAD 基線** 即為 FAILED（工作區對 `packages/eda-bridge/` 與該測試檔皆乾淨，故此即 HEAD 行為）：

```
AssertionError: True is not false : collinear cross-segment fusion survived:
  ((100.33, 114.3), (100.33, 115.57)) X ((100.33, 115.57), (100.33, 114.3))
```

## 真正發生的事：同一條線被寫了三次

emitted `.kicad_sch` 中 `(wire` 出現 8 次，逐字：

```
(wire (pts (xy 100.33 114.3) (xy 100.33 115.57))
(wire (pts (xy 100.33 115.57) (xy 100.33 114.3))     <- 反向
(wire (pts (xy 100.33 114.3) (xy 100.33 115.57))     <- 再一次
```

依端點集合正規化後計數：

| multiplicity | segment |
|---|---|
| **×3** | `[(100.33, 114.3), (100.33, 115.57)]` |
| ×1 | 其餘 5 條（控制組：`unique=5`，證明重複計數有判別力，非全部都重複） |

那三條的端點集合**完全相同**（`set(a) == set(b)` = True），其中一條只是方向相反。
座標落在 R2(100,110) 與 R3(100,120) 之間，即測試中的 `NET_B`；`NET_A` 是繞行 `x=96.52`
的另外 5 條。**所以這不是兩條不同的線共線，是一條線被 emit 了三次。**

## 為什麼測試報錯了成因

`_wire_segments`（`:132-140`）只用 regex 抽 `(wire (pts ...))` 的座標，
**完全沒有 net 歸屬**（探針確認：測試原始碼不含 `net_of` / `owner` / `net_name` / `by_net` 任一）。
於是 `:166-170` 的雙層迴圈把**任意兩條共線重疊的 segment** 都判為
「collinear cross-segment fusion survived」。

而 KiCad 的語意裡，**同一條 net 的重複 wire 不是 fusion**——它就是同一條線畫了三次，
電氣上無害。測試的判準無法區分：

| 真實情況 | 測試看到 | 測試的結論 |
|---|---|---|
| 兩條**不同 net** 的線共線重疊（真缺陷） | 共線重疊 | fusion survived |
| 同一條 net 的線被 emit 多次（本 BR） | 共線重疊 | fusion survived ← **錯歸因** |

**這是「缺席態與失敗態共用輸出」的一個變形：兩個不同的成因共用同一個失敗訊息。**
讀者（包含即將接手 723e 的 handler）看到紅燈會去修 anti-fusion guard，
而 guard 沒有壞——`fusion_jogged_nets=[]` 且 `fusion_label_fallbacks=[]`，
guard 根本沒被觸發，因為**沒有跨 net 的共線可攔**。

## 打擊半徑

- **不是短路**。三條同 net 的重複線在 KiCad 裡合併回一條，`fidelity` 的 net partition 不受影響
  （這也是為什麼它能在基線紅著而沒有人發現電氣問題）。
- **但它讓 anti-fusion 回歸網不可用**。`test_kicad_emit.py` 目前 `2 failed, 8 passed`，
  而其中一個 failed 正是 723e 的主題。**handler 要拿它當 P0 的回歸網，網本身是紅的。**
- 第二個 failed（`test_load_symbol_returns_definition_and_pin_endpoints`）是獨立成因：
  `pins["1"]` 現在回 `(0.0, 3.81, 270.0)` 三元組，測試仍斷言二元組——pin 端點加了角度欄位
  而測試沒跟上。**與本 BR 無關，一併記錄以免被誤併。**

## 修法（兩件事，不要混為一談）

1. **引擎側**：查明為何同一 net 的同一段 segment 被 append 三次（其中一次反向）。
   反向那條暗示至少有兩條不同的產生路徑寫入同一個清單。
   **emit 前對 segment 依端點集合去重**是治標；治本要找出重複的來源。
2. **測試側**：`_wire_segments` 要帶 net 歸屬，或至少**先去重再比對**，
   讓「同 net 重複」與「跨 net 共線」不再共用同一個紅燈。
   **注意**：純去重會讓這個測試由紅轉綠，但那是**遮蔽**引擎側缺陷而非修復它——
   兩件事必須都做，且引擎側先做。

## 我沒量什麼（誠實邊界）

- **沒有讀 net 歸屬自檔案**：`.kicad_sch` 的 `(wire ...)` 區塊**不帶 net 名**
  （net 由連通性隱含），所以「那三條屬於 NET_B」是**從座標與元件位置推得**，不是讀出來的。
  若要坐實，需從 netlist export 反查。
- **沒有查重複的來源**（哪幾行 append 了它）——那是 owner 的工作面。
- **沒有量這在真實產品頁上發生幾次**。本 BR 全部證據來自那個 4-resistor 合成測試。
- **沒有動任何檔案**：`git status --porcelain packages/eda-bridge/ tests/` 對這兩條路徑為空。
