# BR_20260804f — `power_port_intrusions` 宣告了、docstring 承諾了、從未被賦值

- **Status**: FIXED
**Severity**: MEDIUM (instrument defect — 讀者拿到的空清單與「沒有缺陷」無法區分)
**Family**: schematic-engine / G13-harness-disclosure
**Filed**: 2026-08-04 by ses_03408d1faffeKuPkQZ9Zj6gWO2 (schematic-engine owner)
**Fixed**: 2026-08-04 in `05dce34` *fix(guard-c): conditional inset degrade + assign the intrusion field it promised*
**Verified**: 2026-08-31 by ses_fa798c57bffeLSUo93QIpLDdCx (BRNS handler; mutation proof M1–M3 + negative control, §6)
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

> **行號時效聲明**：§2–§5 的行號是 **2026-08-04 建檔當下（05dce34 之前）** 的快照，
> 修復後已位移。修復後的位置見 §6.1。建檔敘述保留原樣（過去式的事實不會爛掉），
> 不回頭改寫。

### 2.1 宣告與承諾（`kicad_emit.py:93-100`，pre-fix）

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

---

## 6. 修復紀錄（2026-08-31 驗證 by ses_fa798c57bffeLSUo93QIpLDdCx）

### 6.1 修復落地處

`05dce34` *fix(guard-c): conditional inset degrade + assign the intrusion field it promised*
（Tue Aug 4 21:13:26 2026 +0800；`git show --numstat`：`kicad_emit.py` +96/-4、
`tests/test_kicad_emit.py` +176/-0）。該 commit 同時處理 BR_20260804b 的 conditional
inset，本 BR 對應的是其中的欄位賦值與其測試。

**賦值**（`kicad_emit.py:1884-1887`，在 `SchematicEmitResult(...)` 建構參數內，
緊接 `wire_body_intrusions=` 之後）：

```python
        wire_body_intrusions=wire_body_intrusions,
        # BR_20260804f: the lossless carrier for guard C. The warning string
        # truncates at 12; this does not. Assigned unconditionally so "empty"
        # means "none found" and never "nobody wrote it".
        power_port_intrusions=list(_port_intrusions),
```

賦值是**無條件**的（不在 `if power_port_gate == "warn":` 分支內），所以它的值只由
`_port_intrusions`（`:1808-1821` 的 guard C 掃描結果）決定，與 gate 模式無關。
warn 路徑上 `list(_port_intrusions)` 與 warning 字串來自**同一個** list，因此兩者
不可能不一致——這正是 §6.3 M2 要證的性質。

**docstring 已同步修正**（`kicad_emit.py:94-116`）。§4 建議的兩處都做了：

1. 加入 lossless-channel 段落（`:101-103`：「the warning string truncates at 12 entries
   and appends "(+N more)", so entries 13.. are unrecoverable from it. Read this field,
   not the warning」）；
2. **刪掉了 §4 指出的不可觀察承諾**。原文「Empty on the default fail-loud path
   (it raised) OR when there were no intrusions」已改為 `:110` 的
   「Empty now means exactly one thing: no intrusions were found.」加上 `:112-115`
   顯式說明「Observable ONLY on the warn path. On the default fail-loud path emit
   raises, so no result object exists to carry it — the previous wording described a
   state nobody can observe, which is the same defect one level down.」
   ⇒ §4「建議前者」被採納。

### 6.2 測試對應表

| BR §4 驗收要求 | 落地測試 | 位置 |
| --- | --- | --- |
| ① warn 模式下欄位必須被填、且與實際 intrusion 一致 | `PowerPortIntrusionsFieldTests.test_field_is_populated_and_agrees_with_the_warning` | `tests/test_kicad_emit.py:686-702` |
| ② 拿掉賦值該斷言必須紅（mutation proof） | M1，見 §6.3 | — |
| ③ 控制組：沒有 intrusion 時該欄位為 `[]` | `GuardCNoRectFallbackTests.test_far_port_placement_reports_nothing`（port 距 body 150 mm，斷言 `found == []`） | `tests/test_kicad_emit.py:809-817` |

**主測試的三層判別力**（`:686-702`），逐條說明它各自擋掉什麼：

- `assertGreater(warned, 0, "page no longer trips guard C; fixture needs revisiting")`
  — **反 vacuity 控制**。若 fixture 頁面哪天不再觸發 guard C，`len(field) == warned`
  會退化成 `0 == 0` 而恆綠。這一行讓那種情況變成**紅燈而非假綠燈**（M3 證實）。
- `assertEqual(len(field), warned, ...)` — **主斷言**。warning 計數由 `_warning_count()`
  （`:675-684`）從 warning 字串反解（含 `(+N more)` 的截斷還原），與欄位互為獨立來源。
- `assertRegex(entry, r"^.+@\(.+,.+\) inside .+$")` — **形狀斷言**。擋掉「有填但填了
  錯的東西」（例如填成 dict、或填成 warning 整串）。

額外覆蓋：`GuardCNoRectFallbackTests`（`:797-817`）用 `power_port_intrusions`
作為 end-to-end 讀取管道，共 2 個正向 + 1 個反向控制組——這使欄位**從零讀者變成
有 4 個測試讀者**，§2.3「沒有讀者的欄位錯了也不會有人發現」的存活條件被移除。

### 6.3 Mutation proof（三個 mutation，全部在 stale-pyc 清除後執行）

依 AGENTS.md §6.3：每次 mutate 前後都跑
`find . -name __pycache__ -prune -exec rm -rf {} +`，因為 `python3 -B` 擋不掉既有
stale `.pyc`。

| # | Mutation | 預期 | 實測 rc | 實測訊息 |
| --- | --- | --- | --- | --- |
| M1 | 刪掉 `power_port_intrusions=list(_port_intrusions),`（**還原成本 BR 建檔時的狀態**） | 紅 | 1 | `AssertionError: 0 != 1 : field disagrees with the warning it is supposed to mirror` |
| M2 | 保留賦值但改成 `power_port_intrusions=[]`（「有賦值但值是錯的」） | 紅 | 1 | 同上（`0 != 1`） |
| M3 | `if False and bx0 < ex_pt < bx1 ...` 讓 guard C 全盲（**vacuity 控制**） | 紅，且必須紅在 `assertGreater` 那一行 | 1 | `AssertionError: 0 not greater than 0 : page no longer trips guard C; fixture needs revisiting` |

**M3 是這組裡最重要的一格**：它證明測試分得出「欄位是空的（缺陷）」與「本來就沒有
intrusion 可填（fixture 失效）」——若沒有 `assertGreater`，M3 會與 M1 走到同一個
`0 == 0` 而**通過**，那時 M1 的紅燈就無法歸因。三個 mutation 的失敗訊息**互不相同**
（M1/M2 停在 `assertEqual`、M3 停在 `assertGreater`），所以這組測試不只會紅，
**紅的位置本身帶有診斷資訊**。

M1 同時讓 `GuardCNoRectFallbackTests.test_norect_symbol_actually_reports_an_intrusion`
變紅（`AssertionError: 0 != 1 : expected exactly one intrusion inside C1, got []`），
確認第二條讀取管道也真的依賴該賦值，不是各自持有副本。

**還原驗證**：三次 mutation 後 `cmp <備份> <原檔>` rc=0、
`git status --porcelain -- kicad_emit.py tests/test_kicad_emit.py` 回空
（同一輪的控制組 `git status --porcelain -- AGENTS.md` 回 ` M AGENTS.md` 非空，
證明該探針有判別力，空結果不是探針壞掉）。

### 6.4 驗證輸出原文

```
$ PP=$(ls -d packages/*/ | tr '\n' ':')
$ find . -name __pycache__ -prune -exec rm -rf {} +        # rc=0

$ PYTHONPATH="$PP" python3 -m unittest tests.test_kicad_emit.PowerPortIntrusionsFieldTests -v
test_field_is_populated_and_agrees_with_the_warning (tests.test_kicad_emit.PowerPortIntrusionsFieldTests.test_field_is_populated_and_agrees_with_the_warning) ... ok
----------------------------------------------------------------------
Ran 1 test in 0.064s
OK                                                          # rc=0

$ PYTHONPATH="$PP" python3 -m unittest tests.test_kicad_emit
....................................
----------------------------------------------------------------------
Ran 36 tests in 3.305s
OK                                                          # rc=0

NEGATIVE CONTROL (unittest 對不存在的模組是否真的會紅):
$ PYTHONPATH="$PP" python3 -m unittest tests.test_NON_EXISTENT_MODULE_CONTROL
ModuleNotFoundError: No module named 'tests.test_NON_EXISTENT_MODULE_CONTROL'
----------------------------------------------------------------------
Ran 1 test in 0.000s
FAILED (errors=1)                                           # rc=1
```

負控制組 rc=1 ⇒ 上面兩個 `rc=0 / OK` 是**真的跑過並通過**，不是「模組沒被載入
所以沒有東西失敗」。（36 個測試「全綠」與「一個都沒跑」在裸 rc 上會共用 0；
這一格把它們分開。）

**`git log -S` 原探針的事後複驗**（§2.2 的探針，現在應該非空）：

```
$ git log -S 'power_port_intrusions=' --oneline -- packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py
05dce34 fix(guard-c): conditional inset degrade + assign the intrusion field it promised
```

建檔時該探針回空、控制組（`wire_body_intrusions=`）非空；現在它自己非空。
**同一支探針、同一個對象、結論反轉** ⇒ 修復確實進了版控，不是只活在工作區。

### 6.5 誠實邊界（本次驗證量了什麼 / 沒量什麼）

**量了**：

- 賦值存在、無條件、來源與 warning 同一個 list（讀 code + M2 反證）。
- 測試在賦值被移除／被填錯／guard C 全盲三種情況下都會紅，且紅在不同的斷言。
- 全模組 36 測試綠，且負控制組證明綠不是空跑。
- 工作樹在驗證前後 byte-identical（`cmp` rc=0）。

**沒量**：

- **超過 12 筆 intrusion 的實際頁面**。§3 的核心論點是「第 13 筆之後只剩計數」，
  而現有 fixture 只產生 1 筆。`_warning_count()` 有解析 `(+N more)` 的邏輯，
  但那條路徑在本次驗證中**從未被執行**——lossless 的宣稱在 N>12 上仍是
  **推論而非量測**。這是本 BR 修復後最大的一個未覆蓋區。
- **`power_port_gate="error"` 路徑**。docstring 現在誠實地說該路徑不可觀察，
  但沒有測試把這件事鎖住（沒有測試斷言 error 模式會 raise）。
- §5 原有的三個開放問題**全部維持開放**：`wire_body_intrusions` 的內容完整性、
  其他 `EmitResult` 欄位是否有同樣的「宣告未賦值」、error 路徑的替代管道。
  本次只修 `power_port_intrusions` 一欄，**沒有做逐欄掃描**。
- **沒有 commit**。本次驗證未取得 dispatcher 的 commit 授權，工作樹維持原狀
  （本 BR 檔案是唯一新增的修改）。
