# BR_20260804d — `load_symbol` 的簽章與 docstring 仍承諾 2-tuple，實際回 3-tuple

- **Status**: FIXED（2026-08-31 by `ses_fa7af3a78ffeUqSLw5dMA12hQj`，handler；驗證紀錄見文末）
- **Closed**: 2026-09-01 by `ses_fa72d47feffeTZNnlOw08pgCgS`（BRNS handler，closeout_three_debts）—
  依據：commit `d0ffb53`；HEAD 上 `kicad_emit.py:376-378` 簽章已是
  `tuple[str, dict[str, tuple[float, float, float]]]` 且 docstring 寫 `(x, y, rotation)`
  （`git grep -A2 'def load_symbol' HEAD` 命中；bogus-def 控制組同檔 rc=1 回空）；
  `tests.test_kicad_emit` 在 HEAD `Ran 36 tests … OK`（先清 `__pycache__`，負控制組 rc=1）。
- **Severity**: LOW（**不是功能缺陷**——所有消費端都已適應；但它讓一個測試永久紅著，而紅燈指向錯誤的方向）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:360-362`（`load_symbol` 簽章 + docstring）／
  `tests/test_kicad_emit.py::test_load_symbol_returns_definition_and_pin_endpoints`
- **Filed**: 2026-08-04 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（dispatcher）
- **Owner**: `schematic-engine`（`ses_03408d1fa`）
- **Family**: `schematic-engine`
- **Related**:
  - `BR_20260804c_one_wire_emitted_three_times_and_the_test_reports_it_as_cross_net_fusion.md`
    （**同一個測試模組的另一個 failed**，且 804c 的「打擊半徑」節就明文記下這兩者是獨立成因、
    要求不得誤併。本 BR 是那筆記錄的兌現）
  - `BR_20260804_bus_route_docstring_promises_a_channel_router_the_code_does_not_implement.md`
    （**同族失敗形狀，且是同一個函式家族**：`_bus_route` 的 docstring 承諾一個 code 沒實作的
    channel router；本 BR 是同一個病的鏡像——**docstring 承諾一個 code 已經超越的介面**。
    兩者都是「宣稱與實際不符，而讀者無從分辨」）

---

## 症狀

```
FAIL: tests/test_kicad_emit.py::KiCadEmitTests::test_load_symbol_returns_definition_and_pin_endpoints
AssertionError: Tuples differ: (0.0, 3.81) != (0.0, 3.81, 270.0)
```

測試斷言 pin 的 local offset 是 2-tuple `(x, y)`，實際回 3-tuple `(x, y, rotation)`。

## 結論：stale 測試，不是回歸

第三個欄位是 **DD-26/27（user review v6/v7）的刻意介面演進**，`3c019df` 引入，理由逐字寫在
`kicad_emit.py:476-482`：

> capture the pin's KiCad rotation (3rd `at` field) alongside (x, y). The rotation is the pin's
> TRUE outward direction … and is the ONLY reliable edge signal: a narrow tall symbol
> (single-row Conn_01x36, 36 pins stacked on ONE left edge) has far-from-origin endpoints where
> |ey|>>|ex|, so the old abs(ex)>=abs(ey) axis test mis-classified them as top/bottom pins

也就是說它是**修一個真缺陷所需的功能欄位**（「亂七八糟 vertical label 疊柱」誤分類），不是手滑多回一個值。

## 所有消費端都已適應（逐項查過）

| 消費端 | 如何處理第三個元素 |
|---|---|
| `kicad_emit.py:991`（routing） | **有 guard**：`rot = int(round(endpoint[2])) % 360 if len(endpoint) > 2 else None`，且有 2-tuple 軸測 fallback。**這是新欄位的主要預期消費者** |
| `_adjacent_pitch`（`:296`，呼叫自 `:337`） | 只索引 `p[0]` / `p[1]`——寬度無關 |
| `composer.py:157,562,2088` | 用 `len(pins)` / 迭代 keys——從不碰 tuple 寬度 |
| `escape_plan.py:57,115` | docstring 明寫 `endpoint = (x, y, rotation)`，並顯式處理 legacy 2-tuple fallback |
| `tests/test_kicad_emit.py` 的 `_segment_owner` | 用 `(lx, ly, *_rest)` 解包 |

**沒有任何消費端會因為第三個元素而壞掉或算錯。**

## 真正的缺陷是「協同的 stale set」

不是只有測試落後。**三個宣告介面的地方全部落後於實作**：

```
kicad_emit.py:361  簽章  -> tuple[str, dict[str, tuple[float, float]]]   <- 說 2-tuple
kicad_emit.py:362  docstring -> "{pin_number: (x, y)}"                    <- 說 2-tuple
tests/…            斷言 -> assertEqual(pins["1"], (0.0, 3.81))           <- 說 2-tuple
kicad_emit.py:476  實際 -> dict[str, tuple[float, float, float]]          <- 是 3-tuple
```

這比「測試沒跟上」嚴重一級：**一個讀簽章的人會得到錯誤的介面認知，而型別標註看起來就是權威來源**。
`:991` 那個 `if len(endpoint) > 2` 的 guard 是唯一洩漏真相的地方——但它讀起來像在防禦 legacy 輸入，
不像在說「其實現在都是 3-tuple」。

## 修法

**改宣告側，不要改 `load_symbol` 的回傳值**（回傳值是對的）：

1. `:361` 簽章改 `dict[str, tuple[float, float, float]]`
2. `:362` docstring 改 `{pin_number: (x, y, rotation)}`，並說明 rotation 的語義
   （0=+x/right, 90=+y, 180=-x/left, 270=-y）與它為何存在（指向 `:476` 的 DD-26/27 註解）
3. 測試斷言改成 3-tuple

**⚠ 不要用 `assertEqual(pins["1"][:2], (0.0, 3.81))` 讓它轉綠。** 那會讓測試對第三個欄位
**永久盲目**——rotation 是 label 邊緣判定的唯一可靠訊號，它算錯時這個測試必須要能紅。

## 我沒量什麼（誠實邊界）

- **沒有跑端到端 render**：驗的是消費端 *code* 處理 3-tuple 的方式，不是產出的原理圖畫面。
- **沒有查 `packages/` 以外的消費端**（例如序列化 / cache 過的產物）。grep 範圍限定在 `packages/`。
- **沒有驗該測試的其他兩個斷言**（`assertIn '(symbol "Device:R"'`、`set(pins) == {"1","2"}`）——
  它們在失敗行之前，因此從未被執行到。幾乎確定沒問題，但**未量**。
- **沒有查 rotation ≠ 0 的元件在真實頁上的分布**。

## 附記：本 BR 的證據來源與覆核

RCA 由 subagent `ses_033be5769` 產出（conclusion-only 調查，raw context 未進 dispatcher 主線）。

---

## 修復紀錄（2026-08-31，handler `ses_fa7af3a78ffeUqSLw5dMA12hQj`）

依「修法」三點，只動宣告側，**未改 `load_symbol` 回傳值**：

1. `kicad_emit.py` `load_symbol` 型別註解 → `tuple[str, dict[str, tuple[float, float, float]]]`
2. 同函式 docstring → `{pin_number: (x, y, rotation)}`，補上 rotation 語義
   （0=+x/right, 90=+y, 180=-x/left, 270=-y）與指向 `_pin_endpoints` 的 DD-26/27 理由
3. `tests/test_kicad_emit.py::test_load_symbol_returns_definition_and_pin_endpoints`
   斷言改成完整 3-tuple：`(0.0, 3.81, 270.0)` / `(0.0, -3.81, 90.0)`
   **未用 `pins["1"][:2]` 切片轉綠**——rotation 算錯時這個測試仍必須紅。

### 驗證（先清 `__pycache__`，非僅靠 `python3 -B`）

| 項目 | 修復前 | 修復後 |
|---|---|---|
| `tests.test_kicad_emit.KiCadEmitTests.test_load_symbol_returns_definition_and_pin_endpoints` | `FAILED (failures=1)` rc=1，`(0.0, 3.81) != (0.0, 3.81, 270.0)` | `Ran 1 test … OK` rc=0 |
| `tests.test_kicad_emit`（全模組 29 tests） | 未量 | `Ran 29 tests … OK` rc=0 |

**負控制組**：`python3 -m unittest tests.test_NON_EXISTENT_MODULE_CONTROL`
→ `ModuleNotFoundError` / `FAILED (errors=1)` rc=1。
證明此 runner 的缺席態（模組不存在）不會靜默回綠，故上面兩個 `OK, rc=0` 是真的通過。

**未量**：端到端 render／`packages/` 以外消費端／rotation ≠ 0 元件在真實頁的分布
——與本 BR 原「我沒量什麼」節相同的邊界，本次修復未擴充。
**dispatcher 親手覆核了它引用的每一個行號**，雙向控制組：已知 token `def load_symbol` 命中 1、
bogus token 回 0（證明探針能回空，非全命中）。

subagent 自報的控制組亦記錄在案：它跑了一個不存在的測試名，得 `errors=1` 而非靜默通過——
**證明該 harness 的缺席態與失敗態不共用輸出**，故真實測試的 `failures=1` 是真的斷言失敗。
