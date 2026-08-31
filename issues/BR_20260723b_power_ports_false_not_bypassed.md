# BR_20260723b — power_ports=False 未真正抑制 power-port 幾何 + stub-orientation defect

- **Status**: PARTIAL — 主張① STALE（建檔當下即不成立，見 §更正）；主張② 錨點仍在但活性 UNVERIFIABLE
- **Filed by**: aiguard C03 consumer session (ses_073a93d09ffeRTpR9TwIdofhb3)
- **Repo**: bodesign (platform)
- **Severity**: medium — 純視覺 layout defect(不影響 net 連通),但擋住預設 emit
- **Fix venue**: bodesign-rooted session (platform owner，上輪已預告可接)

## Symptom (verbatim)

symbol_dirs 三個 bug 修完後(kiutils + a7fe826 + 080b454 + consumer 側 stage_dir base64 修正),
aiguard MCU core spec 的 52 元件(1 STM32 + 51 stdlib Device)**全部 resolve**,compose
前進到 emit 的 power-port 幾何階段才失敗:

```
ValueError: POWER_PORT_INSIDE_SYMBOL_BODY: power-port endpoints fell inside a
component symbol body (stub orientation defect — BR left-pin stub blind):
73 個 +1V8/GND/+3V3 power-port 端點落在 U1 symbol body 內
```

**關鍵**:consumer 傳的是 `power_ports=False`,引擎**仍執行** power-port 端點放置幾何並在
落入 U1 body 時 raise。

> **⚠ 讀本節前先讀文末 `## 更正（2026-09-01）`。** 下面主張① 已被證明在**本 BR 建檔當下就不成立**，
> 主張② 的錨點仍在但活性 UNVERIFIABLE。原文一字未刪（過去式的記載不會爛掉；刪掉會讓後人失去
> 「為何當初這樣寫」的線索），更正寫在旁邊。

## RCA（consumer 側觀察 + platform 上輪自承）

1. **`power_ports=False` 未真正 bypass**   ← **【STALE，見 §更正 A】**(新發現,比「只在 True 出現」更嚴重):
   `kicad_emit.py:1377/1390/1417/1433/1461` 有 `kind = _power_net_kind(net.name) if power_ports else None`
   ——看似 False 時 kind=None,但 power-port 端點的**幾何放置 + intrusion 檢查**(1645 `if _port_intrusions`)
   似乎不受 `power_ports` 條件保護,仍在 False 下執行並 raise。請 platform owner 確認:
   `power_ports=False` 時是否應**完全跳過** power-port 端點放置與 `_port_intrusions` 檢查?

2. **stub-orientation defect（根本 defect）**:   ← **【UNVERIFIABLE，見 §更正 B】**
   `kicad_emit.py:1647` 註解 "stub orientation defect — BR left-pin stub blind"。
   power-port 端點的 stub 方向使端點落在相鄰 U1 body 內。這是 BR_20260710 已知的純視覺 defect。

## 影響範圍

- 這是 **BR_20260710** 明確定義的**純視覺 layout defect**(power-port glyph 畫在 symbol body 上),
  `kicad_emit.py:1654-1662` 註解自承 **不影響 net 連通性**。
- 因此 `power_port_gate="warn"` 可讓乾淨電氣 spec 仍 emit(consumer 本輪即採此降級路徑產圖)。
- 但預設 `power_port_gate="error"` + `power_ports=False` **仍撞** raise,是不一致的行為契約。

## Fix proposal（platform owner 定奪，二選一或都做）

1. **`power_ports=False` 應完全抑制 power-port 幾何**:False 時跳過端點放置 + `_port_intrusions`
   檢查,讓 dense/connector 頁不受 power-port defect 影響(subagent 觀察此路徑未被保護)。
2. **修 stub-orientation defect**（根治）:讓 power-port 端點的 stub 方向使端點落在 U1 body **外**,
   則 `power_ports=True` 也能乾淨 emit 含 power-port 符號的完整電路。

## Validation plan

修後用 aiguard MCU core spec(存 `/run/user/1000/mcu-core-compose/`)重跑:
- `power_ports=False` → 不再撞 POWER_PORT_INSIDE_SYMBOL_BODY,乾淨 emit
- (root fix 後)`power_ports=True` → power-port 端點落 U1 body 外,73 個 intrusion 歸零
- placed:194、nets:18、可 render .kicad_sch

## Explicitly NOT bugs

- symbol_dirs 三個 bug — 已全修(b96263f / a7fe826 / 080b454),與本 bug 無關。
- consumer stage_dir @FILE 語法 — consumer 側已用 base64 修正,非引擎 bug。
- 本 defect **不影響 net 連通**(BR_20260710 自承),故 `power_port_gate="warn"` 是有效臨時繞道。

---

## 更正（2026-09-01）：主張① 在建檔當下就不成立

重驗者：bodesign BRNS leaf handler `ses_fa6f9f3a7ffe0H4aZC7l8lSsfx`（dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）。
本節**不刪除任何原文**：上面的主張是一個已發生的事實記載（某人在 2026-07-23 這樣看待這件事），
刪掉只會讓下一個 cold-context 的人失去「為何當初這樣寫」的線索。

### A. 主張①（`power_ports=False` 未真正 bypass）—— **STALE**

#### A.1 證據：guard 覆蓋率 5/5（HEAD，2026-09-01 實跑）

```
# 問：kicad_emit.py 裡 power_endpoints.append 出現幾次？
grep -c 'power_endpoints\.append' packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py
  → 5   rc=0

# 問：'if kind is not None' 出現幾次？
grep -c 'if kind is not None' …kicad_emit.py
  → 5   rc=0

# CONTROL（反向）：不存在的 pattern 必須回 0 且 rc=1
grep -c 'if kind is not NoneZZQ' …kicad_emit.py
  → 0   rc=1        ← 探針在該紅的時候真的會紅️

# CONTROL（正向）：同一支指令對確定存在的字串必須非零
grep -c 'def ' …kicad_emit.py
  → 91  rc=0        ← 探針真的有在讀這個檔
```

數量相等不等於一一對應，所以逐行確認（`grep -n -B2`）——**每個 append 的前一行都是該 guard**：

| append 行 | 前一行 |
| --- | --- |
| `:1523` | `:1522  if kind is not None:` |
| `:1536` | `:1535  if kind is not None:` |
| `:1563` | `:1562  if kind is not None:` |
| `:1579` | `:1578  if kind is not None:` |
| `:1607` | `:1606  if kind is not None:` |

#### A.2 `kind` 的賦值路徑沒有繞過 `power_ports` 的

視窗揭露：不只 grep `_power_net_kind`，而是 grep **全部** `kind = ` 賦值（否則「沒有繞過路徑」
只是「我只沒搜到」）：

```
grep -n '^\s*kind = ' …kicad_emit.py
  1520 / 1533 / 1560 / 1576 / 1604 : kind = _power_net_kind(net.name) if power_ports else None
  3285 / 3295                      : kind = _erc_short_kind(detail)   ← ERC 別的局部變數，不進 power_endpoints
  rc=0
# CONTROL：grep -n '^\s*kindZZQ = '  → rc=1
```

→ `power_endpoints` 路徑上 **5 個 `kind` 賦值全數**由 `if power_ports else None` 把關。

#### A.3 推論鏈

```
power_ports=False
  ⇒ kind 恆為 None（1520/1533/1560/1576/1604）
  ⇒ 5 個 append 全部不執行（1522/1535/1562/1578/1606 guard）
  ⇒ power_endpoints 恆空（:1173 初始化為 []）
  ⇒ :1809 `for ep in power_endpoints:` 零次迭代
  ⇒ :1808 `_port_intrusions` 恆為 []
  ⇒ :1822 `if _port_intrusions:` 為假
  ⇒ **不可能 raise POWER_PORT_INSIDE_SYMBOL_BODY**
```

#### A.4 時序證明：這不是「後來被修好」

```
git log -1 --format='%h %ad %s' --date=short 1fe46df
  → 1fe46df 2026-07-06 feat(eda-bridge): BR_20260706 五筆 BR 閉環 … rc=0
# CONTROL：git log -1 zzzzzzz → fatal: bad revision, rc=128（這支指令在該紅時真的會紅）
```

guard 由 `1fe46df`（**2026-07-06**）引入，而本 BR filed **2026-07-23** —— 早 **17 天**。

更直接的：重建 BR filed 當下的那份檔。`kicad_emit.py` 在 2026-07-23 之前最後一次改動是
`28ff2f7`（2026-07-10）：

```
git show 28ff2f7:…/kicad_emit.py > $XDG_RUNTIME_DIR/…/old.py    rc=0, 118150 bytes
grep -c 'power_endpoints\.append' old.py   → 3   rc=0
grep -c 'if kind is not None'      old.py   → 3   rc=0
grep -c 'if kind is not NoneZZQ'   old.py   → 0   rc=1     ← CONTROL 紅了
grep -c 'kind = _power_net_kind'   old.py   → 3（:981/:1008/:1034，均帶 `if power_ports else None`）
逐行：:983→:984、:1010→:1011、:1036→:1037 —— 3/3 全在 guard 下
```

⇒ **BR 建檔當天，樹上那份程式碼的 guard 覆蓋率就是 100%（3/3）**。主張① 不是「曾經成立、後來修好」，
而是**從一開始就不成立**。對它派工會變成「修一個不存在的缺陷」。

#### A.5 根因：**引用了符號的行號，卻沒讀它的語義**—— 與姊妹張 723e 同形

本 BR 主張① 寫「`kicad_emit.py:1377/1390/1417/1433/1461` 有 `kind = _power_net_kind(…) if power_ports else None`」。
實測那五個行號在 `28ff2f7`（建檔當下的樹）上是：

```
1377: return None
1390: vector (angle-steered), so the box extends toward (nx, ny) rather than always
1417: # dozens of single-pin GND/+1V8/+3V3 net endpoints; drawing a global label
1433: _PWR_MIN_PITCH_MM = 4.0
1461:     Geometry mirrors KiCad's stock power ports:
```

—— **一行都不是那個賦值**（真正的賦值在 `:981/:1008/:1034`，而且只有 3 個不是 5 個）。
同樣地，主張② 引用的 `:1647`（「註解 stub orientation defect」）在那份上是 label 防撞的註解，
不是那句訊息。

**這與姊妹張 `BR_20260723e` §重驗附註① 是完全相同的形狀**：

> 作者引用了符號（行號、字串），卻沒有讀它的語義。

這是**可重用的教訓，不是一次筆誤**：

- 行號是一個**會漂移且不發出任何訊號**的錨點。引用它時，「我讀到的那行」與「我寫下的那個號碼」
  可能來自不同快照（工作區 vs HEAD vs 某個 commit）——而三者的輸出形狀完全一樣。
- 一個符號**存在**不等於它**被執行**。`_port_intrusions` 的字串在檔裡，不代表它那條路徑跑得到；
  而 grep 對這兩者回傳完全相同的輸出。
- **可機械套用的防護**：寫下行號前，先列出它的 guard/控制流上下文（`grep -B2`），
  並声明「我讀的是哪一份快照」（AGENTS.md §6.1 快照歧義陷阱）。

#### A.6 真正的缺陷在參數傳遞層，不在 guard 層

作者當初的觀測「我傳了 `power_ports=False` 卻仍 raise」**本身可能是真的**——
只是原因不在 guard，而在那個 `False` **從來沒有抵達**：MCP 層的顯式參數轉發清單根本不含
`power_ports`，callee 取簽章預設 `True`。

→ **見 `BR_20260901d_power_ports_unreachable_from_mcp_layer.md`**（同一條執行路徑）。

### B. 主張②（stub-orientation defect）—— **UNVERIFIABLE**

錨點**仍在**，但行號已位移，且量測基線已非原來那份：

```
# 問："stub orientation defect" 字串還在嗎？
grep -n 'stub orientation defect' …kicad_emit.py
  → 1825:  "component symbol body (stub orientation defect — BR left-pin stub "   rc=0
# CONTROL：grep -n 'stub orientation defectZZQ' → rc=1
```

行號自 BR 寫的 `:1647` 位移到 `:1825`。

**為何 UNVERIFIABLE（不是 「仍成立」也不是「已修」）**：

1. 「**73 個 +1V8/GND/+3V3 端點落在 U1 body 內**」是一個**執行期量測**，只能用那份 aiguard MCU core
   spec 實跑 compose 重驗。本輪**未實跑**（派工單限定只動 `issues/` markdown）。
2. **guard C 幾何自本 BR filed 後已被三個 commit 改過**（實跑 `git log -1 <sha> -- kicad_emit.py`，三個都 rc=0）：

   | commit | 日期 | 要旨 |
   | --- | --- | --- |
   | `05dce34` | 2026-08-04 | guard C: conditional inset degrade + assign the intrusion field it promised |
   | `b1fde6b` | 2026-08-04 | guard C falls back to graphics bbox when symbol has no rectangle |
   | `d64bbd0` | 2026-08-05 | guard C: treat a span within one ULP of 2*inset as not wide enough |

   另外 `:1817 if ref == host_ref: continue`（跳過端點自己的 host）現在在路徑上——
   這直接影響「幾個 intrusion」的計數。

   ⇒ **即使重跑拿到一個數字，它也不能與當初的 73 直接比較**：量測儀器本身改過，
   「73→0 因為修好了」與「73→0 因為 host_ref 跳過規則把它們都算成合法」**共用同一個輸出**。

→ 要重驗主張②，必須先定義「什麼叫修好了」（在新的 guard C 語義下），不能只看數字有沒有變小。

### C. 本輪沒量什麼（誠實邊界）

- **未實跑 compose**。本輪全部是靜態證據（grep / git / 控制流推論）。
- **未證明作者當初那次觀測走的是哪條路徑**。A.6 只證明了「MCP 路徑上 `power_ports` 不可達」，
  沒證明「那次就是走 MCP 路徑」。
- **未重驗 73 這個數字**（見 B）。
- 未檢查 `power_port_gate="warn"` 降級路徑現在是否仍有效。
