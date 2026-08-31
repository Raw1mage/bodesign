# BR_20260901d — `power_ports` / `power_port_gate` 從 MCP 層根本傳不進去：顯式參數轉發清單漏了它們

- **Status**: OPEN
- **Severity**: HIGH — 走 MCP 的 consumer 無法關閉 power-port 幾何；`power_ports=False` 被靜默丟棄，callee 取預設 `True`。**「參數被丟棄」與「參數生效了但行為不變」共用同一個輸出。**
- **Family**: silent-parameter-drop / explicit-forwarding-list-omission
- **Filed**: 2026-09-01 by `ses_fa6f9f3a7ffe0H4aZC7l8lSsfx`（bodesign BRNS leaf handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`）
- **Owning repo**: `~/projects/bodesign`
- **Fix surface**: `services/mcp/server.py:149-183`（`_h_compose`）＋ 同檔的 `compose_schematic` tool schema
- **Related**: `BR_20260723b_power_ports_false_not_bypassed.md` — **同一條執行路徑**。723b 的作者觀測到「傳了 `power_ports=False` 卻仍撞 `POWER_PORT_INSIDE_SYMBOL_BODY`」，並據此推論 guard 層有缺陷；本輪已證明 guard 層 5/5 完整（723b §更正 A），而本 BR 指出**那個 `False` 從來沒有抵達 callee**。兩張 BR 指向同一次觀測的兩個層：723b 錯歸因到 `kicad_emit.py` 的控制流，真正的斷點在 `server.py` 的參數轉發清單。723b 已據此改標 `PARTIAL`（主張① STALE）。

---

## 1. 一句話

`services/mcp/server.py` 的 `_h_compose` 用**逐項顯式轉發**呼叫 `compose_schematic`，
清單裡**沒有** `power_ports`，也**沒有** `power_port_gate`。
沒有 `**kwargs` splat 兜底 ⇒ MCP 客戶端傳什麼都無效，callee 一律取簽章預設 `True`。

## 2. Fail mode

呼叫端（MCP client / agent）在 `compose_schematic` 的 arguments 裡放 `power_ports=false`：

- **它期待**：power-port 幾何被完全抑制。
- **實際發生**：該 key 落在 `a` dict 裡從未被讀取；`compose_schematic` 以預設 `power_ports=True` 執行。
- **呼叫端看到的**：一次正常的 compose 回傳，或一次 `POWER_PORT_INSIDE_SYMBOL_BODY` raise。

**兩種截然不同的世界共用同一個輸出**：

| 真實情況 | 呼叫端觀測 |
| --- | --- |
| 參數被靜默丟棄，引擎跑了 power-port 幾何 | 一樣的回傳／一樣的 raise |
| 參數生效了，但行為本來就不受它影響 | 一樣的回傳／一樣的 raise |

回傳裡沒有任何欄位說「你給的 `power_ports` 我沒收」。這正是 723b 作者被誤導的機制。

## 3. 證據（本輪實跑，2026-09-01，HEAD on `main`）

### 3.1 零命中 + 控制組

```
# 問：services/ 與 skills/ 底下有沒有任何 power_ports / power_port_gate 字樣？
grep -rn 'power_ports\|power_port_gate' services/ skills/
  → rc=1，零輸出

# CONTROL（正向，同一支指令、同一範圍、對確定存在的字串）
grep -rn 'compose_schematic' services/ skills/
  → rc=0，21 行命中
```

**這個 0 是真的 0，不是探針沒跑。** 控制組證明：同一支 `grep -rn`、同一組目錄，
對一個確定存在的符號回傳 21 行。所以第一格的空不是「範圍打錯」「權限不足」「工具沒啟動」，
而是「這兩個識別符在 `services/` 與 `skills/` 底下真的一次都沒出現」。

### 3.2 `power_ports=` 在全 repo 的分布

```
grep -rn --include='*.py' 'power_ports=' .        rc=0
  ./packages/eda-bridge/bodesign_eda_bridge/composer.py:2441   ← 唯一的生產轉發（composer → kicad_emit）
  ./packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py:1597 ← 註解
  ./tests/test_composer_draftsman.py:222/627/787/816           ← True
  ./tests/test_composer_draftsman.py:831                       ← False（唯一測到 False 的地方）
  ./issues/assets_20260706_c03_session/gen_ccm_pages.py:702/710/713  ← 一次性 session 腳本，直呼 Python API

# CONTROL：grep -rn --include='*.py' 'power_portsZZQ=' .   → rc=1
```

⇒ **repo 內每一個成功把 `power_ports=False` 傳進去的呼叫端，都是直呼 Python API 的**
（測試、或 `issues/assets_.../gen_ccm_pages.py` 這類本機腳本）。**沒有任何一個走 MCP。**

### 3.3 `_h_compose` 的實際參數清單（`services/mcp/server.py:149-163` 逐字）

```python
def _h_compose(a: dict) -> Any:
    import bodesign_eda_bridge as _eb
    from bodesign_eda_bridge import compose_schematic
    # symbol_dirs pass-through: ... (BR_20260723)
    r = compose_schematic(a["out_dir"], a["project_name"], a["spec"],
                          **({"symbol_dirs": a["symbol_dirs"]} if a.get("symbol_dirs") is not None else {}),
                          validate=a.get("validate", True),
                          connection_style=a.get("connection_style"),
                          style=a.get("style", "netlist"),
                          measure_ink=a.get("measure_ink", False),
                          fidelity=a.get("fidelity", False),
                          **({"expect_sha": a["expect_sha"]} if a.get("expect_sha") else {}))
```

轉發的完整集合：`out_dir` / `project_name` / `spec` / `symbol_dirs` / `validate` /
`connection_style` / `style` / `measure_ink` / `fidelity` / `expect_sha` — **共 10 項，無 `**a` splat**。

`power_ports` 與 `power_port_gate` 不在其中 ⇒ 走 MCP 的 consumer 一律取簽章預設
（`composer.py:1791`、`kicad_emit.py:931` 皆為 `power_ports: bool = True`）。

## 4. RCA（機制層）

**顯式參數轉發清單的「漏掉一項」與「刻意不轉這一項」，在程式碼上長得一模一樣。**

- 一個 splat（`**a`）會把未知 key 轉下去，多傳的 key 會在 callee 端 `TypeError` — **會叫**。
- 一個顯式清單漏掉一項，什麼都不會叫：dict 裡多一個沒人讀的 key 是完全合法的 Python。
- 而 `_h_compose` 上方那段 `symbol_dirs` 註解（BR_20260723）**恰好證明這份清單是被刻意維護過的**
  —— 於是讀者更沒有理由懷疑它不完整。**一份看起來被照顧過的清單，掩護了它的缺項。**

系統當下就握有判別這件事所需的資訊：`a` 這個 dict 裡有哪些 key、實際被讀走了哪些，
兩者相減就是「被丟棄的參數」。但**沒有任何一格會去做這個減法**，也沒有任何欄位回報它。
這是 **G13-harness-disclosure**：缺的不是資訊，是揭露。

（下游還有一層放大：`compose_schematic` 的 schema 若也沒宣告這兩個參數，
MCP 客戶端連「這個工具接不接受 `power_ports`」都無從得知——它只會靜默地不生效。）

## 5. 誠實邊界（本輪沒量什麼）

- **未實跑 compose**。本 BR 全部是靜態證據：grep（含控制組）＋ 讀 `server.py` 原始碼＋
  讀 `composer.py` / `kicad_emit.py` 的簽章預設。**未執行任何 Python**。
- **未證明 723b 作者當初那次觀測就是走 MCP 路徑**。已證明的是「MCP 路徑上 `power_ports` 不可達」；
  未證明的是「那次 raise 來自 MCP 路徑」。作者也可能是直呼 Python API 而撞到別的東西。
  §Related 的因果宣稱因此只到「**這足以解釋**那次觀測」，不到「這**就是**那次的原因」。
- **未檢查 `compose_schematic` 的 MCP tool schema 是否宣告了這兩個參數**（只證明 handler 不轉發）。
  若 schema 也沒宣告，那是同一缺陷的第二個面；若 schema 有宣告而 handler 不轉，那是更糟的形狀
  （工具自稱接受一個它會丟掉的參數）。**這一格未量。**
- **未盤點還有哪些 `compose_schematic` 參數同樣被漏掉**。本輪只查了 `power_ports` /
  `power_port_gate` 這兩個識別符；`_h_compose` 的 10 項清單 vs `compose_schematic` 完整簽章的差集**未計算**。
  這個差集很可能不只兩項——但那是推測，不是量測。

## 6. 修法選項（列出，不裁示；決策權在 dispatcher）

1. **補進顯式清單**（最小改動）：在 `_h_compose` 加
   `power_ports=a.get("power_ports", True)` 與 `power_port_gate=a.get("power_port_gate", "error")`，
   並同步 tool schema。
   - 優點：blast radius 最小，與現有風格一致。
   - 缺點：**沒有修根因**——下一個新參數還是會被漏掉，而且一樣不會叫。

2. **改為 allow-list 白名單 splat**：維護一份 `_COMPOSE_PASSTHROUGH` 集合，
   `**{k: a[k] for k in _COMPOSE_PASSTHROUGH if k in a}`。
   - 優點：新增參數只改一個地方。
   - 缺點：白名單本身仍可能漏，只是漏得比較顯眼。

3. **加「未消費參數」揭露**（治 RCA 那一層，可與 1 或 2 併行）：handler 收工前計算
   `set(a) - consumed`，非空就寫進回傳的 `warnings`（或直接 fail-loud）。
   - 優點：**把「參數被丟棄」與「參數生效了但行為不變」拆成兩個不同的輸出**——
     這正是本 BR 的 fail mode。修完之後，下一個被漏掉的參數會自己叫出來。
   - 缺點：需決定是 warn 還是 raise（AGENTS.md §2 天條 1「no silent fallback」傾向 fail fast，
     但對既有呼叫端是 breaking change）。

4. **由簽章自動導出轉發清單**（`inspect.signature(compose_schematic)`）。
   - 優點：結構上不可能漏。
   - 缺點：把 MCP 的公開介面與內部函式簽章綁死，內部重構會意外改變對外契約——
     與本 repo「顯式優於隱式」的既有風格衝突。

## 7. 驗收判準（給修完之後的人）

修完必須**兩格都紅得起來**才算有判別力：

- **正向**：MCP 呼叫傳 `power_ports=false` ⇒ 回傳的 `inputs`（或等價欄位）必須顯示 callee 真的收到 `False`，
  且 `power_endpoints` 為空（不可只看「沒 raise」——沒 raise 也可能是這張圖本來就沒 intrusion）。
- **反向控制組**：同一張圖傳 `power_ports=true` ⇒ 必須看得到 power-port 幾何被執行。
  **若反向那格也「看起來正常」，代表這張測試圖對本參數沒有判別力，換一張圖。**
- 若採選項 3：傳一個**確定不存在**的參數名（如 `power_portsZZQ=false`）必須觸發未消費揭露；
  傳一個確定存在的參數必須不觸發。

