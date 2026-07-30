# BR_20260730b — compose facade 參數被多編碼 / 空 spec 四閘齊綠 / busy gate 被 zombie 永久卡住

- Status: **CLOSED** — commit `1884668`（全 12 檔）。reporter 分兩輪走 facade 真 client 自驗全通過：round=11 驗 N1/N2/round=8/金標準/豁免閘，round=13 驗 §P/§Q/金標準並授權 commit。
- Closed: 2026-07-30 by `ses_0c87bab06fferQ0umBs2Nybb5U`（dispatcher 自驗通過且已生效，無 scoped 殘留）
- Filed by: `ses_0c87bab06fferQ0umBs2Nybb5U`（platform owner；N1/N2 由 aiguard consumer session `ses_073a93d09ffeRTpR9TwIdofhb3` 提報證據，§M 與 lazy-import 為 owner 自行發現）
- Owner: `ses_0c87bab06fferQ0umBs2Nybb5U`
- Family: `control.quality.no-silent-degradation`（BR_20260729 §A–§L + BR_20260730 F1–F5/R6 的延續；本件貢獻 **V8 / V9 / V10 / V11 / V12** 五個變體）
- Fix venue: `/home/pkcs12/projects/bodesign`
- Relates: `BR_20260730`（同一 fix surface，兩者同時歸檔）、`BR_20260730c`（`export_bom` 静默排除 DNP，**跨關注點獨立 file、未修**，留頂層）

---

## 摘要

七條缺陷，全部是「呼叫端拿到一個正面回覆，而它要的事沒有發生」：

| § | 缺陷 | KB 變體 |
|---|---|---|
| N1 | `symbol_dirs` 在 MCP facade schema 宣告為 `{}`（無型別）→ client 把陣列序列化成文字 → 9 個自訂 symbol 全載不到，stdlib 照樣載入 | **V8** 參數被接成另一型別 |
| N2 | 無 `components` 的 spec → 213 bytes、0 symbol 的空白 `.kicad_sch`，而 draftsman gate / ERC / validation / 回傳值**四個都回綠** | **V9** 每個 gate 都誠實回綠而交付物是空的 |
| §M | `mcpctl.sh` busy gate 把 `[Xvfb] <defunct>` zombie 讀成「正在工作」→ 三具 12 小時前就死掉的屍體讓它**無限期**拒絕每一次 restart | **V10** ops 層 |
| §N | `eda-bridge/__init__.py` eager import `block_drafter` → `kiutils`，讓只用 stdlib 的 `composer` 在乾淨 host 上無法匯入 | 與 BR_20260730 **F1 同一缺陷**，另一個 package |
| §O | `netlist_path` / `covers_boards` 未進 facade schema 也未被 handler 轉發 → **R5/R6 整組規則對每一個 MCP 呼叫端不可觸及**，永遠回 `not_run` | 與 BR_20260730 **§3 同一族**（import 可達性 → facade 可達性） |
| §P | `anyOf: [array, string]` **本身就是 stringify 觸發條件**——N1 的 schema 補救因此只做了一半，呼叫端拿到 loud typed error 卻**無法遵從它**（多值呼叫無路可走） | **V11** 修復本身複製了它要修的缺陷 |
| §Q | `covers_boards` 宣告得越窄 gate 越綠：宣告排除一塊**已被觀測到畫在 netlist 裡**的板，其未畫的列整批進 unassessable → `PASS blocking=0` | **V12** 呼叫端可控的靜音鈕 |

外加 **round=8** 對 BR_20260730 R5 的兩項修正。

**§O 是本 BR 最值得記的一條**：它是我在修好 §3（可達性）的**同一次修復裡**留下的同族缺陷，而且是我在要求 reporter 驗證 round=8 之前自查部署是否活著時才發現的——若未自查，它會拿著一個永遠 `not_run` 的 gate 得出反向結論。

**§P/§Q 由 reporter 在 round=11 自驗四項全通過之後另行發現，兩條都在「修復 N1 / round=8 的那批改動本身」裡**——即：

> 前五條講的是「平台給了呼叫端一個假的正面回覆」。§P/§Q 講的是**修那五條的動作，各自生出一條同族缺陷**：§P 讓錯誤訊息變成無法遵從的命令，§Q 讓降級規則長出一個靜音鈕。這是本家族第三、第四次「修復自身複製了缺陷形狀」（前兩次是 §O、以及 round=8 的分類順序）。

---

## N1 — `symbol_dirs` 陣列被多編碼一層 JSON

### 症狀（reporter 一手）

兩次 `bodesign_compose_schematic`，**只差 `symbol_dirs` 的型別**，同一個 dir、同一顆 symbol：

```
symbol_dirs: ["/work/experiments/aiguard_c03_compose/symbols"]   ← JSON 陣列
  → placed=0
  → warnings: ["U_3V3B: KiCad symbol library 'buck_3v3.kicad_sym' not found in:
       ['[\"/work/experiments/aiguard_c03_compose/symbols\"]', '/usr/share/kicad/symbols']"]
                ^ 第一個「路徑」是一個內容為 JSON 陣列文字的字串

symbol_dirs: "/work/experiments/aiguard_c03_compose/symbols"      ← 裸字串
  → placed=1, warnings=[]
```

reporter 另附一個乾淨的 A/B：同一份 spec 走 facade 回 `SymbolLoadError`（9 個自訂 symbol 全滅、stdlib 全通），在 ee worker 內 direct call `compose_schematic(..., symbol_dirs=[...])` 卻 `placed=134 nets=84` 全部載入。**差別只在有沒有經過 facade。**

### RCA（owner 自驗，逐條排除）

server 端全部排除：

| 候選 | 排除依據 |
|---|---|
| `_h_compose` 改寫 arg | `server.py:157` 原樣傳遞（`**{"symbol_dirs": a["symbol_dirs"]}`） |
| `_forward_to_worker` | `server.py:1388` 用 httpx `json=` 正確序列化 |
| token 路徑解析 | `server.py:1676-1685` 在 `if token:` 內，reporter 未帶 token → **從未執行** |
| 任何 args 的 `json.dumps` | 全檔 grep：只有 3 處，都是 response 側 |

**決定性證據 1 — 同一次呼叫內的不對稱**（owner 的 probeC）：

```
spec         宣告 {"type": "object"}  → 真 dict 抵達，components 正確解析 placed=1
symbol_dirs  宣告 {}                  → 被 stringify 成 '["/work/.../symbols"]'
```

同一 client、同一 transport、同一 request：**宣告型別的存活、未宣告的被序列化。**

**決定性證據 2 — 兩元素探針**（probeD）把機制釘死：

```
symbol_dirs: ["/work/.../symbols", "/work/.../probeA"]
→ not found in: ['["/work/.../symbols", "/work/.../probeA"]', '/usr/share/kicad/symbols']
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 整個陣列 → 一個字串
```

**決定性證據 3 — `/invoke` 直打**（繞過 MCP client）：同一個乾淨 JSON list → `placed=2`、零 warning。故障域切在**進入 server 之前**。

因果鏈：

```
server.py:1110  "symbol_dirs": {}           ← 無型別約束
  → MCP client 把 array 序列化成 JSON 文字
  → composer.py:1670  isinstance(symbol_dirs, str) 為真
  → _user_dirs = ['["/work/.../symbols"]']   ← 一個永不存在的「路徑」
  → 每顆自訂 symbol FileNotFoundError；stdlib 仍在 list 裡 → 部分成功掩護了它
```

### 為什麼它比一般型別錯誤難抓

1. **殘存的部分成功掩護了它。** stdlib 元件照樣載入、`nets` 照樣算、`placed` 是正整數。
2. **錯誤訊息把歸因指向錯的層。** 真相（那個「路徑」是一段 JSON 文字）**已經印在畫面上**，但沒人會往「上游多編碼」讀——它讀起來是「被呼叫方的磁碟上沒有這個檔」。reporter 因此花了一整輪相信自己的 symbol library 壞了。
3. **fail-loud 攔對了，卻攔在錯的層。** 同一路徑上的 `SymbolLoadError`（BR_20260723d）確實擋住了交付，這是正面案例——但它把**上游的型別錯誤**報成**下游的 symbol 找不到**。

> **fail-loud 只保證「不會靜默交付錯的東西」，不保證「歸因指向真正的那一層」。**

### 修法（兩半，缺一不可）

- **接收端** `composer.py`：偵測「首字元是 `[` 且 JSON 解析出 list」的字串 → 拋 `SymbolDirsEncodingError`，訊息同時帶 raw 與 decoded。**刻意不自動解碼**——自動解碼會無聲修好呼叫端的 bug，連帶掩蓋產生它的 schema 缺陷（那才是新增 fallback）。
- **產生端** `server.py` schema：宣告 `anyOf: [array<string>, string]` + description 說明這個失敗模式。沒有這一半，呼叫端得到 loud error 卻**仍然無法發出正確呼叫**——§J 的教訓：**schema 是 MCP 呼叫端在呼叫當下唯一看得到的文件**。

偵測器刻意窄：只認「首字元 `[`」+「JSON 合法」+「解出 list」。反向鑑別力鎖住四種必須放行的輸入——真陣列、裸路徑字串、**目錄名以 `[` 開頭的真路徑**、`'{"a": 1}'`（是 JSON 但不是 list，不屬本缺陷）。

### 順帶查明的第三件事（不是缺陷，是閘的門檻）

reporter 得到 `SymbolLoadError`、owner 的 probeC 只得到 `ok:true` + warning。差別不是旗標，是 `_is_active_ic`（`composer.py:1764-1767`）用 **net 裡的 distinct pin 數 > 2** 判定。probeC 的 U9 只宣告 2 個 pin，所以不算 active IC → 跳過 fail-loud 閘。

這代表：**一顆 symbol 載不到的元件，若在 spec 裡剛好只宣告 ≤2 pin，就從 error 降級成 warning。** 以「passive 缺 symbol 可合法退化成小方塊」的既有邊界（BR_20260723d 明文的 NOT-bug）而言這是刻意設計，但**判準是 spec 宣告的 pin 數而非零件實際 pin 數**——一顆 100-pin 的 IC 在 spec 裡只接 2 條線時會落在錯的那一邊。**本輪不改**（reporter 未被它咬到，且改動會觸及既有 NOT-bug 邊界），記錄於此供後續裁決。

---

## N2 — 無 components 的 spec，四個 gate 齊綠而交付物是空的

### 症狀（reporter 一手）

呼叫端誤以為 `spec` 可以傳檔案路徑，傳了 `{"__spec_file__": "/work/.../spec.json"}`：

```json
{"ok": true, "placed": 0, "nets": 0,
 "warnings": ["[gate] page=aiguard_product paper=A4 intra_overlap=0 label_overlap=0 rects=0 PASS"],
 "validation": {"status": "validated", "erc_violations": 0, "erc_errors": 0,
                "netlist_components": 0, "netlist_nets": []}}
```

產出一張 **213 bytes、0 個 symbol** 的空白 `.kicad_sch`。

### 為什麼四個 gate 都是對的

| gate | 回報 | 為什麼它沒說謊 |
|---|---|---|
| draftsman gate | `PASS rects=0` | 沒有東西**不可能**重疊 |
| ERC | `erc_violations=0` | 沒有東西**不可能**接錯 |
| validation | `status="validated"` | 檔案結構合法 |
| 呼叫回傳 | `ok:true placed:0` | 沒有任何一步失敗 |

**四個綠燈，每一個都內部正確，合起來什麼都沒保證**——它們全部在回答「這張圖有沒有問題」，而那張圖不存在。`0 violations` 同時是「這張圖沒問題」與「沒有圖」的正確答案，**呼叫端無法從判決本身分辨這兩者**。

### RCA

`composer.py:2202` 有一個 sibling 守衛：「宣告了 components 但**每一個都被跳過**」→ `COMPOSE_ALL_COMPONENTS_SKIPPED`。缺的是另一半：**components 從未宣告**。`spec.get("components", [])` 回 `[]`，一路暢行。

觸發它的是一個合理的猜測：`spec` 的 schema 只寫 `{"type": "object"}`，沒有任何線索說明它要的是**內容**而非**檔案參照**。（又是 §J：schema 是唯一的文件。）

### 修法

在**任何 gate 有機會祝福它之前**拋 `EmptySpecError`。三個設計決定：

1. **錯誤訊息同時列出「收到的 key」與「compose 實際讀的 key」**——這個缺陷的本質永遠是 key 名不匹配，把兩邊並排就在一行內回答完，而不是把呼叫端送去讀 composer 原始碼（實際發生過）。
2. **明說「為什麼你剛才看到的綠燈沒有幫上你」**。碰到這個錯誤的人剛看過 `ok:true` 與 `PASS`；訊息若不解釋那些綠燈，讀起來像在跟他觀察到的事實矛盾。
3. **`KNOWN_KEYS` 自帶 AST 對照測試**（雙向：讀了卻沒宣告 / 宣告了卻沒讀）——它是 `spec.get(...)` 呼叫點的手抄副本，正是 V4-c。

> 那條 AST 測試**當場就抓到我自己漏了 `l6_avoidance`**：我最初盤查用的 grep pattern 寫成 `[a-z_]*`（**不含數字**），把唯一帶數字的 key 靜默漏掉。這是本線第六次「驗證工具靜默偏窄」，而這次是寫 KB 的人在寫那一節時犯的。

---

## §M — busy gate 把「已經死掉」讀成「正在工作」

### 症狀（owner 自己撞到）

要部署 N1 修復時，我自己在 §L 建的 gate 擋住了我：

```
bodesign-...-ee-1  BUSY  399    43495s  [Xvfb] <defunct>
bodesign-...-ee-1  BUSY  3322   40780s  [Xvfb] <defunct>
bodesign-...-ee-1  BUSY  14303  23208s  [Xvfb] <defunct>
EXIT=3
```

實況：容器 CPU **0.16%**、無 java、無 freerouting、`ps STAT` 三個都是 **`Z`**。`xvfb-run` 每跑一次 freerouting 就漏一具 defunct Xvfb，而 **zombie 的 `etimes` 會一直累加**。

### 為什麼它比「不方便」嚴重

zombie 已經 exit：不佔 CPU、不佔記憶體、不持有 fd。**restart 不可能摧毀一個已經死掉的 process**——這反轉了 gate 自己的契約（它存在的理由是「restart 會摧毀進行中的運算」）。

而唯一的出路是 `BODESIGN_FORCE=1`：

> **守衛的失敗模式若是「永遠拒絕」，它就在教人拆掉自己。**
> 一個會誤擋到讓人習慣性 force 的 gate，比沒有 gate 更危險：force 的那一天，它剛好真的在保護一個 165 分鐘的運算。

### 這不是放寬 fail-safe

§L 的「UNKNOWN 一律擋」仍然成立，因為那條的依據是**代價不對稱**（誤擋損失一次等待，誤放損失 165 分鐘運算）。而 zombie 沒有這個不對稱——**已經沒有運算可以損失了**。fail-safe 的正確方向來自代價結構，不是「一律選擇拒絕」。

### 修法

- `ps` 加 `stat` 欄，`STAT` 以 `Z` 開頭者分類為 `ZOMBIE`，**per-process 判定而非 per-container**。
- `guard_busy` 改讀 `blocking_report`（排除 ZOMBIE）；`busy` 仍**顯示** ZOMBIE 列——靜默過濾掉它們會隱藏 `xvfb-run` 沒有 reap 子行程這個真缺陷。報告，但不阻擋。
- 關鍵反向鑑別力：**一具 zombie 旁邊坐著一個真 job 時，仍必須擋**。若規則寫成「有 zombie ⇒ 容器閒置」，restart 就會直接穿透一個正在跑的 165 分鐘 route。

順帶一筆同族 V4-c：測試 fixture 是 `ps -eo` 欄位規格的**手抄副本**。加上 `stat` 欄後 fixture 仍是舊的 3 欄，awk 把 `etimes` 讀成 `STAT`、`args` 讀成 `etimes`，於是 6 條測試以令人困惑的 rc 不符失敗，而不是說「你的 fixture 欄數錯了」。已加一條從腳本 regex 推導欄序的測試。

---

## §N — eda-bridge 的 eager import（BR_20260730 F1 同一缺陷）

寫 N1/N2 測試時，16 條全部 `ModuleNotFoundError: kiutils`。根因不是缺套件：

```
eda-bridge/__init__.py:34  from .block_drafter import ...
  → block_drafter.py:25    from kiutils.schematic import Schematic
  → 只用 stdlib 的 composer 在乾淨 host 上無法匯入
```

盤查：~30 個子模組裡只有 2 個需要 kiutils（`block_drafter` / `block_qa`）。這**正是 BR_20260730 F1 修過的缺陷**（一個 stdlib-only 的東西被 sibling 的重依賴弄成不可達），只是換了一個 package。

修法同 F1：PEP 562 `__getattr__` 惰性解析那 5 個符號。**刻意不用 try/except ImportError 降級成 None**——要 `draw_block` 而環境沒有 kiutils 時，必須照樣拋真正的 `ModuleNotFoundError`。這是延遲匯入，不是吞掉它。反向鑑別力：不存在的屬性仍須拋 `AttributeError`（不是被猜成某個模組的 ImportError）。

**這條缺陷是被測試逼出來的**——沒有那 16 條在乾淨 host 上跑的測試，它會繼續存在。

---

## round=8 — 對 BR_20260730 R5 的兩項修正

reporter round=8 報：R5 對真實多板產品輸出 11 筆 blocking，其中 **0 筆可行動**，並正確引用了 owner 自己 round=5 的判準：「一份喊狼 31 次的 gate 會被忽略，那比沒有 gate 更糟。」

### 修正一：未覆蓋 board 的列不是 finding

一份產品 BOM 涵蓋 6 塊板，一份 `.net` 只涵蓋一張 schematic，而 5 塊外接模組板的 schematic 根本還沒開始畫。

> **判別句**：一個 finding 被報出來之前先問——**「我有沒有可以拿來比對的基準？」** 沒有基準時報出的不是缺陷，是**我這邊的覆蓋缺口**。

reporter 自己指出這與 `consumer_fork_drift` 的 `forks_unassessable` 是同一句話，對：「沒有屬於該函式的 sentinel 是我的表缺口」＝「沒有覆蓋該板的 netlist 是基準缺口」。移進 `rows_unassessable_board_not_captured`，照實回報但不計入 finding。

**但降級規則有一個必須擋住的自我沉默路徑**：

> **一個能讓自己閉嘴的降級規則，就是一台假綠產生器。**

若「未覆蓋就豁免」無條件成立，傳一份完全無關的 netlist 會讓整份 BOM 全數豁免、gate 直接變綠。所以豁免只在**至少有一塊板真的被匹配到**時才發放（`exemptions_granted`）。這同時解決了兩個結構上完全相同的案例：單列 BOM 且該列未畫（零覆蓋 → 真缺口）vs 6 板 BOM 有 2 板被覆蓋（→ 其餘無基準）。

**推論限度誠實標記**：「這塊板有沒有被覆蓋」原本是從「有幾個 ref 解析到」**推論**的，而那個推論**無法分辨**「沒有 netlist 覆蓋這塊板」與「有覆蓋但每一列都真的沒畫」。**歧義存在於輸入本身，只有呼叫端知道**。故新增 `covers_boards` 明示參數，**並且永遠回報判定基準** `board_coverage_basis: "declared" | "inferred_from_drawn_refs"`——這正是 §C `basis` 的手法：推論出的豁免不得與宣告的豁免混為一談。`covers_boards` 打錯字時報 `boards_declared_not_in_bom`，否則一個 typo 會讓呼叫端相信自己已經限縮了範圍。

### 修正二：reporter 的前提被推翻——兩筆不是 by-design

reporter 斷言那 11 筆「每一筆都是設計上正確不在 netlist 裡」。**其中兩筆不是（owner 自驗）**：

```
BOM U4A (nRF7002-QFAA-R)  ←→ aiguard_ccm.net UW1 (value "nRF7002 WiFi")
BOM U4B (MDBT53-P1M)      ←→ aiguard_ccm.net UB1 (value "MDBT53-P1M BLE")
BOM J_X1/J_X2 (36 pads)   ←→ JSA/JSB（各 36 distinct pins）
UW1 / UB1 / JSA / JSB 出現在 BOM 的筆數：0
```

那兩顆料**確實被畫了**，只是 schematic 與 BOM 對它叫什麼名字不一致。

> **finding 是對的，措辭把讀者送去做錯的修復。** R5 的訊息寫「never drawn」，指向「去把它畫出來」，而正解是「去把兩份文件的命名對齊」。呼叫端讀到「沒畫」但自知那顆料畫了，於是把整條 finding 歸類成 gate 誤報——**一個歸因錯誤的正確 finding，會被當成假紅丟掉**。

新增 `R5_REFDES_DIVERGENCE`，detail 指名它被畫成什麼 refdes + 比對依據。判定用 **mpn** 而非 refdes（mpn 才是跨文件識別同一顆實體零件的依據）。

**分類順序是最容易寫錯的一行**（owner 第一版就寫錯，被自己的測試抓到）：

> **正面證據必須優先於證據不存在。** mpn 命中是「這顆料存在於 schematic」的正面證據；board 未覆蓋只是證據不存在。

把豁免排前面，會讓「一塊板上每個 refdes 都分歧」整批消失——那正是 CORE 的實況（`J_X1`/`J_X2`/`U4A`/`U4B` 畫成 `JSA`/`JSB`/`UW1`/`UB1`，於是 CORE 按 refdes 看起來完全未 capture，事實上畫得很完整）。

mpn 比對保守，因為**假的 divergence 宣告比漏報更糟**（它告訴呼叫端某顆料存在，而它可能不存在）：長度下限 5 字元、排除 placeholder token、由長到短試 stem（`nRF7002-QFAA-R` 優先於家族級 `nRF7002`）、**候選 ≥2 筆回 None 而不猜**。

### 實測結果

| 情境 | 修前 | 修後 |
|---|---|---|
| NEW netlists（reporter 的 11 筆） | 11 blocking | **4**（2 R5_NETLIST + 2 REFDES_DIVERGENCE） |
| 5 塊未覆蓋 board 的列 | blocking | 移進 `rows_unassessable_board_not_captured` |
| **金標準**（OLD netlists） | J_MIC/J_LED flagged | **仍 flagged** ✓ |
| 只傳無關 netlist | — | `exemptions_granted=false`、gate=FAIL ✓ |

---

## §O — R5/R6 整組規則在 MCP facade 上不可觸及（我自己在 F2 留下的洞）

**最諷刺的一條**：BR_20260730 §3/F1 修的是「一個 stdlib-only gate 因 import 鏈而不可達」。F2 在同一次修復裡把 R5（`netlist_path`）與 R6 加進 `check_c03`，round=8 又加了 `covers_boards`——**但三者都沒有加進 facade 的 inputSchema、也沒有被 `_h_check_c03` 轉發**：

```
facade schema properties: [bom_csv, pin_allocation_csv, frozen_pad_counts, out_dir]
handler forwards:         [bom_csv, pin_allocation_csv, frozen_pad_counts, out_dir]
netlist_path   in schema: False    forwarded: False
covers_boards  in schema: False    forwarded: False
```

於是**每一個 MCP 呼叫端都拿到 `netlist_crosscheck={"status":"not_run"}`**，而 `not_run` 的設計本意是誠實回報「沒看過」——它確實誠實，但呼叫端**沒有任何辦法讓它去看**。一個永遠 not_run 的規則等於不存在，而 `gate=PASS` 會被讀成「每一行都畫了」。

**為什麼沒被發現**：BR_20260730 的行為測試全部直接呼叫 Python 函式，所以一路全綠；reporter 也剛好是用 `PYTHONPATH=packages/workflow-core python3 -c` direct call 驗的。**只有走 facade 的呼叫端會撞到**，而這條線上沒有人走。

> **§3 是 import 可達性，§O 是 facade 可達性——同一族缺陷，而它出現在修好 §3 的那次修復裡。**
> 「能力存在」與「呼叫者站的位置上能不能用到它」是兩件事，第二次證實。

**修法**：handler 轉發 + schema 宣告兩者（`netlist_path` 用 `anyOf: [array, string]`，比照 N1 的教訓），且 description 明說**省略它的代價**——單純宣告參數不夠，不知道「省略就跳過 R5/R6」的呼叫端仍會把 PASS 讀成「每個零件都畫了」。

**守衛從簽章 AST 推導，不寫死參數名**：`check_c03` 的每一個參數都必須(a)出現在 schema、(b)被 handler 轉發。寫死清單就是 V4-c（`_EE_GROUP_TOOLS` 已經漂移兩次的那個形狀）；明天新增的參數會讓這條測試紅到它被暴露為止。附反向鑑別力：簽章掃描本身必須真的找到參數，否則空清單會讓斷言永遠 vacuously pass。

**實測（運行中進程，走 `/invoke`）**：帶 `netlist_path`+`covers_boards` → `status=run` / `basis=declared` / `codes=['R5_NETLIST']`；完全省略 → `status=not_run` + 原因字串。

---

## §P — `anyOf` 本身就是 stringify 觸發條件（N1 的修法只做了一半）

reporter 在 round=11 給出一組比我 round=9 更緊的 A/B——**連 request 都不用換**：

```
covers_boards  {"type":"array","items":_STR}       (server.py:1157) → 真陣列抵達 ✓
inetlist_path  {"anyOf":[{"type":"array"},_STR]}   (server.py:1155) → 整串 JSON 文字 ✗
               → NETLIST_MISSING: ["/work/…/a.net", "/work/…/b.net"] not found
                                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 被當單一路徑
```

**我自己就是那個 client，所以這次能直接坐實**（下面兩行是同一次 tool call 的兩個參數）：

| 參數 | schema 形狀 | 抵達形狀 |
|---|---|---|
| `covers_boards` | `{"type":"array"}` | 真 `list` ✓ |
| `netlist_path` | `anyOf[array, string]` | `'["a.net","b.net"]'` 字串 ✗ |
| `spec`（N1 時） | `{"type":"object"}` | 真 `dict` ✓ |
| `symbol_dirs`（N1 時） | `{}` 無型別 | 字串 ✗ |

這四列一起讀才看得出真正的規律：**不是「沒宣告型別」導致 stringify，而是「沒宣告一個單一確定的型別」**。`{}` 與 `anyOf` 在這條 transport 上是同一類。

### 為何這比「少修一個地方」嚴重

我為 N1 加的 `anyOf` 宣告，**並沒有恢復呼叫端發出正確呼叫的能力**。reporter 拿到了我那個 loud typed error，卻**無法遵從它**——錯誤訊息叫它「pass THAT as a real array」，而它的 client 對 `anyOf` 參數就是會 stringify。單一目錄還能用裸字串繞，**多目錄無路可走**。

這正是我自己在 round=9 寫進 N1 的那句警告：

> 「沒有後者，你得到 loud error 卻仍然無法發出正確呼叫。」

只是成因不是「沒宣告 type」，而是**宣告成 union**。一個只能報錯、不能被遵從的 typed error，對呼叫端而言與 silent failure 的差別只在於它知道自己卡住了。

> **§J 學到「schema 是呼叫端唯一看得到的文件」，§P 是它的下一層：schema 的形狀會改變參數的傳輸型別，不只是描述它。**

### 修法：schema 比 runtime 窄，不是反過來

兩處（`netlist_path`、`symbol_dirs`）都改成單一 `{"type":"array","items":_STR}`，**runtime 仍接受裸字串**（back-compat 未斷）。`covers_boards` 是現成對照組：同形狀、同 transport、能用。

兩條 description 都寫明「這裡比 runtime 窄是故意的、因為 union 發不出去」——否則下一個讀者看到 schema 窄於 runtime 會當成 bug 把 union 加回來。

### 守衛：純靜態抵不住，所以把 transport 事實編進測試

reporter 指出「純 schema 靜態檢查抓不到 §P」——正確，`anyOf` 在 JSON Schema 裡完全合法。所以守衛不是「檢查 schema 合不合法」而是**把實跑得出的 transport 事實當成規則**：任何包含 array 的 union 都是缺陷。

守衛從**全檔掃描**而非寫死那兩個參數名（寫死就是 V4-c；這兩個偏差本來就是一次發現一個的），並附反向鑑別力：把一個已知違規樣本丟給同一條 regex，它必須真的採到——否則一條什麼都抓不到的掃描會讓這套測試在缺陷回歸後永遠維持綠色。

**實測（真 MCP client，非 curl）**：兩元素陣列 → `netlists:[a.net,b.net]` / `netlist_refs=4`，不再 stringify。

---

## §Q — `covers_boards` 宣告得越窄，gate 越綠（呼叫端可控的靜音鈕）

round=8 讓 declared scope 成為 authoritative，而那項改動自己長出了一個静音鈕。同一份 netlist、CORE 實測 `drawn=2`：

```
covers_boards 省略（inferred）    → FAIL  9 blocking
covers_boards ["PRODUCT","CORE"] → FAIL  9 blocking
covers_boards ["PRODUCT"]        → PASS  0 blocking   CORE 9 列全進 unassessable ← 假綠
```

我在自己的探針上重現了最小形式（CORE `drawn=2` / `U10` 未畫）：宣告 `["PRODUCT"]` → `gate=PASS blocking=0`，`U10` 進 `rows_unassessable`。

### 它反轉了我 round=9 親手立的原則

> **「正面證據必須優先於證據不存在」**

round=9 我把 mpn 比對排在 board 豁免**之前**，理由就是這句。但我只把它套在 **row 層**，沒套在 **board 層**：CORE 被**觀測到**畫在那份 netlist 裡，卻因為呼叫端**宣告**沒覆蓋它而整批豁免。宣告的缺席蓋過了觀測到的存在。

而它的形狀正是我自己寫進 KB 的那句：**一個能讓自己閉嘴的降級規則就是假綠產生器**——只是這次靜音鈕在呼叫端手上，而且比「傳無關 netlist」更好用（後者我 round=8 已經擋住了，`exemptions_granted=False`）。

### 修法：宣告只能 WIDEN，永遠不能 SHRINK 到觀測以下

```
captured = declared | observed        # 宣告可以讓零目擊的板變可評估（round=8 的本意）
                                      # 但不能讓已目擊的板變不可評估
```

矛盾本身不静默向任一邊解決，而是進 `board_coverage_conflicts` + `board_coverage_basis="declared_with_observed_conflict"`。理由：宣告與觀測對不上，可能是宣告過時，也可能是那些 refdes 屬於別的板——**這是要人裁決的事，不是可以靜默採信任一邊的事**。

### 修 §Q 時自曝的更深缺口：`observed` 只認 refdes 字面命中

我先寫的版本是 `observed = {b for b, v in per_board.items() if v["drawn"]}`，自己的測試馬上紅。因為真實的 CORE **四筆全是 mpn 別名命中**（`U4A→UW1`、`J_X1→JSA` …），字面 `drawn=0`——那種板看起來「未捕獲」，實際上被完整畫了。

同一個原則沒貫役到底：我在 row 層認別名為正面證據，board 層卻不認。修正後 `per_board` 多了 `drawn_as_other_refdes`，且別名解析在**同一 pass** 完成並快取給 row 迴圈——算兩次就是 V4-c（兩份「這零件畫了嗎」會在編輯中漂開，**而那正是 board 層與 row 層一開始會不一致的成因**）。

順帶修正了一條 round=8 就寫歪的既有測試 fixture：`test_covers_boards_makes_coverage_authoritative` 把 `U7X` 放在 CORE，而 CORE 因 `U4A→UW1` 已被觀測到。改用 `LED_MODULE`（真的零目擊）才是宣告機制還剩下的真鑑別力：**讓零目擊的板變可評估**。

**實測（真 MCP client）**：宣告排除已觀測的 CORE → `FAIL` + `U10` blocking + `declared_with_observed_conflict` + conflict 列出「2 by refdes, 0 diverged」。

---

## 驗證

| 驗證 | 結果 |
|---|---|
| `tests/test_compose_facade_arg_encoding.py`（新，22 條；§P 後兩條 anyOf 斷言反轉） | OK |
| `tests/test_mcpctl_busy_gate.py`（+7；共 18） | OK |
| `tests/test_check_c03_gate_reachability_and_netlist.py`（+11 §P/§Q；共 **64**） | OK |
| `tests/test_consumer_fork_drift.py` | 15/15 OK |
| N1 facade 實測 | JSON-encoded → typed error；真陣列/裸字串 → `placed=2` 零 warning |
| **§P 真 client 實測** | 修前：兩元素陣列 → `NETLIST_MISSING: ["a.net","b.net"]` 當單一路徑；修後：`netlists:[a.net,b.net]` / `netlist_refs=4` ✓ |
| **§Q 真 client 實測** | 修前：宣告排除已觀測的 CORE → `PASS blocking=0`；修後：`FAIL` + U10 blocking + `declared_with_observed_conflict` ✓ |
| 金標準（BR_20260730 §7.2） | J_MIC/J_LED 仍被 R5 點名 ✓（reporter round=11 亦自驗） |
| 部署判準（reporter round=11 提供） | pid1 `12:12:02` > 最後原始碼 mtime `12:09:35` ✓ |
| 完整 host sweep vs HEAD | HEAD 73 failures / 跑 1181 條；本版 37 failures / 跑 **1576** 條 |

### 那 8 筆「看起來新增」的失敗是 HEAD 既有（隔離 A/B 坐實）

直接比對清單會誤讀：HEAD 有 31 筆 `kiutils` error，`test_composer` / `test_kicad_emit` / `test_layout` / `test_fidelity_gate` **整個模組載不進去**，裡面的真失敗被壓縮成 1 筆 `_FailedTest`。所以「本版多出 8 筆」實際是「那 8 筆在 HEAD 根本沒機會跑」。

隔離手法：在主 repo 還原 `composer.py` + `server.py` 到 HEAD、**保留 lazy `__init__.py`**（固定「模組可載入」這個變數）→ 同一批 5 個模組跑出 **6 fail + 2 error，逐筆對上**。故非回歸。（用 `trap` 確保中斷不會把工作留在還原態；md5 已驗回復。）

worktree 隔離一度失敗，原因無關：HEAD 的 tests 引用 `_vendor_sym_scale`，而 HEAD 的 `kicad_emit.py` 沒有它（只存於 CCM 未 commit 殘留），所以 worktree 永遠載不進去。

---

## Explicitly NOT bugs

1. **`SymbolLoadError` 本身沒壞**——它擋住了一個由上游多編碼造成的錯誤交付，是正面案例。問題只在歸因指向的層。
2. **`prd_bom_crosscheck` 的 `MANIFEST_MISSING` 不是缺陷**。reporter 實跑得到 typed error 並**刻意不自行生成** manifest（錯誤訊息自己要求 "have a human audit it before running this gate"）。由 AI 生成 role manifest 再餵給驗證該 manifest 的 gate 是自證。**這條錯誤訊息寫得對**：typed error 帶「該由誰做什麼」而非只說找不到檔。收為 positive pattern。
3. **`gen_product.py` 在 host 跑不動是 by-design**（reporter 自己劃的界，正確）：`gen_product.py:25` 硬寫 `FB = "/work/aiguard/..."`，本來就設計在容器內跑。與 §N（宣稱零依賴卻不零依賴）是兩件事。
4. **`_is_active_ic` 的 >2 pin 門檻本輪不改**（見 N1 末段）。
5. **`experiments/aiguard_c03_compose/` 不清**——probeA/probeB 是 N1/N2 的最小重現，owner 明示保留。

---

## 收尾註記：`drawn_as_other_refdes` 已失去真實資料覆蓋（reporter round=13 報）

§Q 的 board 層別名解析是因為真實 CORE 四筆全靠 mpn 別名命中（字面 `drawn=0`）才被發現的。但 reporter 在 round=11 依 DD-21 把 BOM 改名（`U4A→UW1` 等）之後：

```
改名前 CORE: drawn=0   drawn_as_other_refdes=4   ← 別名路徑被真實資料走到
改名後 CORE: drawn=11  drawn_as_other_refdes=0   ← 不再被走到
```

**這不是缺陷**——別名解析本來就該在兩份文件命名分歧時才啟用，而分歧已被修掉。但值得記一筆：

> 它是本線上唯一「因為下游把問題修好而失去真實輸入」的機制。
> 往後若有人重構那段，**真實資料不會替他報警**——合成 fixture（`_MULTIBOARD_NET` 的 `UW1` + `_MB_ROWS` 的 `U4A`）是它唯一的守衛。

順帶：這也讓 round=12 把 `test_covers_boards_makes_coverage_authoritative` 改用 `LED_MODULE` 變得更必要——CORE 現在連字面都命中，拿它當「零目擊板」會是第二次前提錯誤。

---

## 本 BR 自曝（同一形狀發生在 owner 自己身上）

每一筆都是被自己寫的測試或機檢抓到，不是事後回想：

| 事件 | 形狀 |
|---|---|
| `KNOWN_KEYS` 漏了 `l6_avoidance` | 盤查用的 grep pattern 寫 `[a-z_]*` **不含數字**，靜默漏掉——驗證工具靜默偏窄第六次 |
| busy gate fixture 欄數錯 | 加 `stat` 欄後 fixture 仍舊 3 欄，awk 欄位錯移——V4-c |
| R5 分類順序寫反 | 豁免排在 divergence 前面，會吞掉整塊板的分歧 |
| `covers_boards` 未接公開簽名 | 測試承諾了一個公開邊界上不存在的參數——placeholder 形狀 |
| **§P：用 `anyOf` 修 N1** | 修復本身複製了缺陷——而且我 round=9 就寫下「沒有後者你會拿到無法遵從的 error」這句警告 |
| **§Q：declared 覆蓋 observed** | 我 round=9 親手立「正面證據優先」並套在 row 層，卻沒套在 board 層 |
| **§Q 修復的第一版** | `observed` 只認 refdes 字面命中，真實 CORE 四筆全是別名命中——同一原則沒貫役到底，**被我自己的新測試當場抓到** |
| **round=8 的 fixture 選錯** | `test_covers_boards_makes_coverage_authoritative` 把 U7X 放 CORE，而 CORE 已因 U4A→UW1 被觀測到——鑑別力實際來自錯的前提 |

---

## 改動集（未 commit）

```
packages/eda-bridge/bodesign_eda_bridge/composer.py       N1 + N2 守衛 + 兩個 typed error
packages/eda-bridge/bodesign_eda_bridge/__init__.py       §N lazy __getattr__
packages/workflow-core/bodesign_workflow_core/check_c03.py  round=8 分類 + covers_boards + §Q observed≻declared
services/mcp/server.py                                    §P 兩處 schema 改單一 array + §O handler 轉發
mcpctl.sh                                                 §M zombie 分類 + blocking_report
tests/test_compose_facade_arg_encoding.py                 新，22 條（§P 後 anyOf 斷言反轉）
tests/test_mcpctl_busy_gate.py                            +7
tests/test_check_c03_gate_reachability_and_netlist.py     +28（round=8 13 + §O 4 + §P/§Q 11）；共 64
ragbase/control/no-silent-degradation/README.md           V8/V9/V10/V11/V12 + round=8/11 各節
issues/BR_20260730_...md                                  標 PARTIAL
issues/BR_20260730b_...md                                 本檔
```

## 給 reporter 的驗證建議

1. **N1**：重跑你那兩次呼叫。JSON 陣列形式現在該回 `SymbolDirsEncodingError`（帶 raw + decoded）而非 `placed=0`；裸字串仍該正常。
2. **N2**：重傳你那份 `{"__spec_file__": ...}`，該回 `COMPOSE_EMPTY_SPEC` 並同時列出 `__spec_file__` 與 compose 實際讀的 key。
3. **round=8**：重跑你的 11 筆。該降至 4（其中 2 筆是 `R5_REFDES_DIVERGENCE` 指名 `UW1`/`UB1`），5 塊未覆蓋 board 移到 `rows_unassessable_board_not_captured`。**順帶請你確認 `U4A`↔`UW1` / `U4B`↔`UB1` / `J_X1`↔`JSA` 這三組到底該以哪邊為準**——那是你的設計決定，不是平台能裁的。
4. **金標準回測**：用舊 netlist 重跑，`J_MIC`/`J_LED` 必須仍被 R5 點名（我的降級不得 un-flag 它們）。
