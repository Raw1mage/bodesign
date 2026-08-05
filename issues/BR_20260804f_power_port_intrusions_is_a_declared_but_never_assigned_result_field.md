# BR_20260804f — `power_port_intrusions` 宣告了、docstring 承諾了、從未被賦值

- **Status**: OPEN
**Severity**: MEDIUM (instrument defect — 讀者拿到的空清單與「沒有缺陷」無法區分)
**Family**: schematic-engine / G13-harness-disclosure
**Filed**: 2026-08-04 by ses_03408d1faffeKuPkQZ9Zj6gWO2 (schematic-engine owner)
**Fix surface**: `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`

**Related**: `issues/closed/BR_20260710_netlist_emission_hostage_to_draftsman_layout_gate.md`
(temporal causality — 該 BR 引入 `power_port_gate="warn"` 這條路徑並**同時**宣告了本欄位
作為 warn 模式的觀測載體；欄位與其 docstring 是那次變更加入的，賦值不是。本 BR 是那次
變更的殘留)。同族失敗形狀：`BR_20260804_bus_route_docstring_promises_a_channel_router_the_code_does_not_implement.md`
(same failure class — docstring 描述一個 executable code 裡不存在的行為；差別是那張的
承諾在散文，這張的承諾有一個真實存在的欄位背書，因此更難察覺)。

---

## 1. 一句話

`EmitResult.power_port_intrusions` 在 `:100` 宣告、由 11 行 docstring 明確承諾
「the intrusions are recorded here」，但**程式碼從未對它賦值**。任何依照 docstring
讀取它的呼叫端，在 warn 模式下都會拿到 `[]` —— 而 `[]` 同時也是「這頁沒有 intrusion」
的正確答案。

## 2. 證據

### 2.1 宣告與承諾（`kicad_emit.py:93-100`）

```
# BR_20260710: power-port endpoints that fell inside a NON-host symbol body
# (guard C, POWER_PORT_INSIDE_SYMBOL_BODY). By default this defect is fail-loud
# (raises in emit). When the caller opts into `power_port_gate="warn"` — the
# ERC-only / netlist-only path that must not be held hostage by a purely-visual
# layout defect — the intrusions are recorded here (observation, same pattern as
# wire_body_intrusions) and a warning is appended instead of raising. Empty on
# the default fail-loud path (it raised) OR when there were no intrusions.
power_port_intrusions: list[str] = field(default_factory=list)
```

docstring 明寫兩件事，其中第二件是本 BR 的核心：
1. warn 模式下 intrusion **記在這裡**
2. 空值的合法成因**只有兩個**（raise 過、或真的沒有）

**實際上有第三個成因，而 docstring 排除了它**：這個欄位永遠是空的。

### 2.2 從未被賦值（探針 + 控制組）

```
$ grep -n "power_port_intrusions" packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py
100:    power_port_intrusions: list[str] = field(default_factory=list)      <- 只有宣告

$ git log -S 'power_port_intrusions=' --oneline -- .../kicad_emit.py
(空)                                                                        <- 從未有 commit 引入賦值

CONTROL (同一個探針，對一個確實有賦值的姊妹欄位):
$ git log -S 'wire_body_intrusions=' --oneline -- .../kicad_emit.py
3c019df fix(draftsman): obstacle-avoiding wire routing + machine check, ...
```

控制組非空 ⇒ **`git log -S` 這個探針抓得到賦值**，所以對 `power_port_intrusions`
回空是「真的沒有」而非「探針壞掉」。

`EmitResult(...)` 建構處（`:1710-1726`）逐欄列出 15 個具名參數，`wire_body_intrusions=`
在 `:1723`，**`power_port_intrusions=` 不在其中** —— 它靠 dataclass 預設值成為空清單。

### 2.3 零讀者（全 repo）

```
$ grep -rn "power_port_intrusions" --include=*.py packages/ tests/ experiments/ scripts/
packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:100
```

唯一一筆就是宣告本身。**沒有任何測試、任何呼叫端讀它** —— 這是它能存活的原因：
一個沒有讀者的欄位，錯了也不會有人發現。

### 2.4 實際被騙的量測（本 BR 的觸發事件）

在跑 `BR_20260804b` guard C 曝險量測時，我依 docstring 寫的儀器：

```
r = compose_schematic(..., power_port_gate="warn")
pi = list(getattr(r.emit, "power_port_intrusions", []) or [])
print("INTRUSIONS_N=%d" % len(pi))
```

輸出：

```
MODE=warn  placed=45 nets=15
INTRUSIONS_N=0                 <- 儀器讀到的
WARNINGS_N=1
  W: POWER_PORT_INSIDE_SYMBOL_BODY: ... GND@(35.56,83.82) inside J1
```

**同一次 compose 裡，欄位說 0、warning 說有一個。** 若我沒有順手把 warnings 也印出來，
這次量測的基線會被記成 0，而後續「clamp 修法新增多少 intrusion」的差值會全部
以錯的基線計算。

> 這正是「缺席態與失敗態共用同一個輸出」（code-thinker §8.1）的實例，
> 且它發生在一個**被 docstring 明確背書**的欄位上。散文承諾的東西不存在時，
> 讀者還會懷疑；一個真實存在、型別正確、有 11 行說明的欄位回 `[]`，沒有人會懷疑。

## 3. 為什麼這比一般的死欄位嚴重

warning 字串是目前**唯一**的載體，而它的資訊是有損的：

```
f"...blind): {'; '.join(_port_intrusions[:12])}"
+ (f" (+{len(_port_intrusions) - 12} more)" if len(_port_intrusions) > 12 else "")
```

超過 12 筆時，第 13 筆之後**只剩一個計數**，個別的 `ref@(x,y) inside ref` 不可恢復。
所以呼叫端若要程式化處理 intrusion（例如「哪些元件被侵入」），目前必須
**parse 一個為人類閱讀而截斷的字串** —— 那正是這個欄位當初要避免的事。

## 4. 修法

`:1662` 的 `if _port_intrusions:` 區塊內，兩條分支之前先賦值，並加入建構參數：

```python
if _port_intrusions:
    _pp_msg = (...)
    if power_port_gate == "warn":
        warnings.append(_pp_msg)
    else:
        raise ValueError(_pp_msg)
```

⇒ `_port_intrusions` 需傳進 `EmitResult(...)`（`:1723` 旁）：

```python
power_port_intrusions=list(_port_intrusions),
```

**注意 raise 路徑**：docstring 說「Empty on the default fail-loud path (it raised)」——
raise 時根本沒有 result 物件，所以那句話描述的狀態不可觀察。修法時應把 docstring
這句改掉，或改為在 raise 前也記錄（若日後有 caller 捕捉例外後仍想讀）。**建議前者**：
承諾一個不可觀察的狀態，與本 BR 是同一個病。

### 驗收（mutation proof）

1. 加上賦值後，對本 BR §2.4 的同一頁跑 warn 模式，`power_port_intrusions` 必須
   等於 `["GND@(35.56,83.82) inside J1"]`（長度 1）
2. **拿掉賦值，該斷言必須紅** —— 否則測試沒有判別力
3. 控制組：一頁沒有 intrusion 的 spec，該欄位必須是 `[]` 且 warnings 無
   `POWER_PORT_INSIDE_SYMBOL_BODY` —— 證明「空」在該空的時候也是空的

## 5. 誠實邊界（我沒量的）

- **沒量**：`wire_body_intrusions`（姊妹欄位）是否也有類似的截斷/失真問題。
  它在 `:1723` 確實有賦值，但我只驗了「有賦值」，沒驗它的內容在所有路徑上都完整。
- **沒量**：是否有其他 `EmitResult` 欄位同樣宣告但未賦值。本 BR 只針對
  `power_port_intrusions` 一個。**這是一個具名的開放問題** —— 同一個
  `git log -S '<field>='` 探針可以逐欄掃，成本很低，但我沒做。
- **沒量**：`power_port_gate="error"` 路徑下 caller 捕捉 `ValueError` 後
  是否有其他管道取得結構化 intrusion 清單（我只確認 result 物件那條沒有）。
