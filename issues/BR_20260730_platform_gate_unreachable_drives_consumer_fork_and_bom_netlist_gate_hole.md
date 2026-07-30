# BR_20260730 — 平台 gate 在 consumer 端不可執行 → 逼出產品 repo fork；且 BOM↔netlist 一致性無 gate 覆蓋

- Status: FIXED-UNVERIFIED（F1–F5 + R6 已落地平台側，**未 commit**；等 reporter 依 §7 自驗；未經對方驗證故不歸檔 `closed/`）
- Filed by: aiguard consumer session `ses_073a93d09ffeRTpR9TwIdofhb3`（**consumer 只提報證據，不擁有修復**，依 a2a-d2d-protocol §3.1.1）
- Owner: `ses_0c87bab06fferQ0umBs2Nybb5U` (bodesign platform coordinator) — 繼承 BR_20260729 家族 owner
- Family: `control.quality.no-silent-degradation`（BR_20260729 §A–§L 的延續；本件為 **V7 候選變體**）
- Fix order: 本 BR 內部有依賴方向（F1 → F2/F3 → F4），見 §6；家族內與其他 BR 的排序由 owner 裁決（§4.3）
- Fix venue: `/home/pkcs12/projects/bodesign`
- Trigger: consumer 在 C03 BOM breakout（麥克風/LED 改外接模組）時，手改 BOM 新增兩個連接器，**gate 回 PASS**——但那兩個連接器在 netlist 裡不存在。

---

## V7 變體命名（供 KB ingest）

> **「gate 回答的不是你問的那個問題」** — a gate whose verdict is trusted as
> answering question Q, while its implementation answers a narrower question Q'.
> 前六個變體（V1 元素丟棄 / V2 量測降級 / V3 status 不反映 / V4 基準分散 /
> V5 判決未帶預算 / V6 未查證前提）都假設「gate 本身是對的、只是資訊有損」。
> V7 是**更前面一層**：consumer 拿到的 PASS 來自一個**它自己手寫的替代品**，
> 而那個替代品與平台 gate 的判準**互相矛盾**。

---

## §1 缺陷 1（觸發點）：BOM↔netlist 一致性**無任何 gate 覆蓋**

### Symptom（verbatim）

consumer 手改 BOM 新增 `J_MIC` / `J_LED` 兩個連接器後跑 gate：

```
C03_BOM.csv: 34 rows | status: {'design-ready': 20, 'finalized': 14}
PASS — C04-ready（全列 finalized/design-ready 且 symbol 來源有證據）
```

同一時刻的實況：

```
$ grep -n 'J_MIC\|J_LED' 03.aiguard/C03-EE/03_input/C03_BOM.csv
25:PRODUCT,J_MIC,Mic array FPC 4-pin 0.5mm,...
29:PRODUCT,J_LED,LED FPC 4-pin 1.0mm,...

$ grep -c 'J_MIC\|J_LED' 03.aiguard/C03-EE/03_input/C03_aiguard_power_frontend.net
0
```

**BOM 宣告了兩個電路圖裡不存在的元件，gate 放行進 C04。**

### RCA（evidence-anchored）

`check_c03` 的簽章根本沒有 netlist 參數：

```python
# packages/workflow-core/bodesign_workflow_core/check_c03.py:190
def check_c03(bom_csv: str, *, pin_allocation_csv: str | None = None,
              frozen_pad_counts: dict | None = None,
              out_dir: str | None = None) -> CheckC03Result:
```

R1–R4 全部只在 CSV 之間交叉（BOM schema / readiness / drawability / BOM↔Pin_Allocation），
**沒有任何一條規則碰 `.net`**。

鄰居 gate 也補不上這個洞：

| gate | 讀 netlist? | 檢查什麼 | 覆蓋 BOM↔netlist? |
|---|---|---|---|
| `check_c03` | ❌ 無此參數 | BOM↔Pin_Allocation CSV | ❌ |
| `prd_bom_crosscheck` | ✅ `netlist_path` | **PRD role manifest** ↔ netlist | ❌（問「PRD 要的角色到齊了嗎」，不問「BOM 每一行都畫出來了嗎」） |

`prd_bom_crosscheck` 是 role-level（「有沒有一顆 regulator」），BOM↔netlist 是 ref-level
（「`J_MIC` 這一行有沒有對應的 schematic symbol + net」）。兩者不互相取代。

### 為何這正是 no-silent-degradation 家族

`check_c03` 的 docstring 自述是 **"C03→C04 stage-entry readiness gate"**，
且 c03-ee GUIDE:47 對外宣稱它做 **"BOM schema/readiness/drawability/SSOT crosscheck
before C04 entry"**。consumer 讀到 "drawability" 合理推論「可繪」已被驗證——
但實作只檢查 **BOM 那一列有沒有寫 symbol 來源字串**（R3，`_SYMBOL_SOURCES` 正則），
**不檢查那個 symbol 是否真的被畫進 schematic**。

> 一列 BOM 寫 `symbol=official Connector_FFC-FPC 類` 就通過 R3 drawability，
> 即使 schematic 從未新增該元件。**「宣稱可繪」被當成「已繪」。**

---

## §2 缺陷 2：status vocabulary 分裂 — 兩個 gate 對**同一份 BOM** 給**相反判決**

### 證據

```python
# 平台 packages/workflow-core/bodesign_workflow_core/check_c03.py:46
_STATUS_ENUM = {"finalized", "draft", "blocked", "proposed", "alternate"}
```

```
$ grep -rc 'design-ready\|design_ready' 平台 packages/ skills/
（0 — "design-ready" 對平台完全是未知詞彙）

$ grep -c 'design-ready' 產品 C03_BOM.csv
21
```

產品 repo 手寫的替代 gate 卻把它當合法值：

```python
# 產品 03.aiguard/C03-EE/03_input/check_bom.py:43
if d["status"] not in ("finalized", "design-ready"):
```

### 後果（這是本 BR 最危險的一條）

同一份 `C03_BOM.csv`：
- 產品 fork gate → **PASS**（21 列 `design-ready` 視為就緒）
- 平台 `check_c03` → 21 列全部撞 **R1_SCHEMA**（`status not in _STATUS_ENUM`）→ **FAIL**

consumer 手上那句 `PASS — C04-ready` **從來不是平台的判決**。C04 已經在這個
PASS 上跑了整輪 routing（89/111）。

> 這與 §D（`plane_layers` key 比對失敗靜默丟棄）同型：
> **兩份配置各自自洽、彼此矛盾、沒有任何一方報錯。**

---

## §3 缺陷 3（機制性根因）：平台 gate **在 consumer 端無法執行**

這條是 §1/§2 的**根因**，不是並列缺陷——它解釋了 fork 為何會出現，
所以修 §4 之前必須先修這條，否則 consumer 會再 fork 一次。

### Symptom（verbatim）

```
$ PYTHONPATH=packages/workflow-core python3 -c "from bodesign_workflow_core import check_c03"
Traceback (most recent call last):
  File "<string>", line 2, in <module>
  File ".../bodesign_workflow_core/__init__.py", line 80, in <module>
    from .checkers import (
  File ".../checkers/__init__.py", line 19, in <module>
    from .registry import CheckerBinding, CheckerRegistry, build_pilot_registry
  File ".../checkers/registry.py", line 31, in <module>
    from .copper_clearance import check_copper_clearance
  File ".../checkers/copper_clearance.py", line 29, in <module>
    from bodesign_design_ir import NET_ROLES
ModuleNotFoundError: No module named 'bodesign_design_ir'
```

### RCA

`check_c03` 本身是**純 python、零依賴**（docstring 明言 "pure function, no LLM,
no fallback"，只 import `csv/io/json/os/re/dataclasses/pathlib`）。
但 `bodesign_workflow_core/__init__.py:80` **eager import** 整個 `checkers` 套件，
而 `checkers/registry.py:31` → `copper_clearance.py:29` 需要 `bodesign_design_ir`
（PCB IR，只在 ee worker 容器裡）。

於是：**一個零依賴的 CSV gate，因為 package `__init__` 的 eager import chain，
繼承了 pcbnew-side 的依賴。** consumer 沒有 ee worker 環境 → 無法本地執行 →
只剩 MCP facade 一條路 → **摩擦足夠大時就自己手寫一份**（這就是 §2 的 fork 誕生過程）。

這與 §A（`autoroute_preflight` 誤分派到 core group）**同型**：
**能力存在，但在呼叫者實際站的位置上不可達。**

---

## §4 缺陷 4：C04 tool forks 凍結在修復前版本 → §A–§L 十二個修復**全部到不了產品 repo**

### 證據

產品 repo `03.aiguard/C04-Layout/02_build/generated/tools/` 有 **22 個檔案**，
其中 6 個與平台 `routing.py` 的函式**一對一重複**：

| 產品 fork | 行數 | mtime | 平台等價 | 暴露為 MCP tool |
|---|---|---|---|---|
| `net2pcb.py` | 129 | 2026-07-07 | `def net2pcb_board` | `bodesign_route_net2pcb` |
| `viainpad.py` | 52 | — | `def via_in_pad` | `bodesign_via_in_pad` |
| `pour.py` | 47 | — | `def pour_planes` | `bodesign_pour_planes` |
| `widen.py` | 37 | — | `def widen` | `bodesign_widen_bus_tracks` |
| `si_check.py` | 75 | — | `def si_check` | `bodesign_si_check` |
| `length_match.py` | 135 | — | `def length_match` | `bodesign_length_match_bus` |

**fork 凍結在 §B 修復之前：**

```
$ grep -c 'footprint_lib_unresolved' 產品 tools/net2pcb.py      → 0
$ grep -c 'footprint_lib_unresolved' 平台 routing.py            → 2
```

`net2pcb.py` mtime = **2026-07-07**；§B（`net2pcb` 靜默丟棄 8 顆主動 IC）
是 2026-07-29 修的（`1269a20`）。**產品 repo 跑的那份仍會靜默丟棄 IC。**
§C/§D/§E/§F/§G/§H/§I/§J/§K 同理——十二個修復一個都沒到。

### 這些 fork 在**活躍路徑**上，不是死參考

```
$ grep -n 'pour\.py' 產品 C04-Layout/02_build/generated/tools/build_c04.sh
46:python3 "$TD/pour.py" "$PCB" "$RT/${B}_pour.kicad_pcb" F.Cu:GND B.Cu:GND >/dev/null 2>&1
```

而且 `>/dev/null 2>&1` ——**連失敗都看不到**（a2a-d2d-protocol §5.3 的同型錯誤，
只是這次在 build script 裡）。

### 只有 2/22 進版控

```
$ git ls-files 03.aiguard/C04-Layout/02_build/generated/tools/
build_two_boards.py
split_two_boards.py
```

**20 個未追蹤的 scratch 檔在驅動 C04 gate 判決。**

### 是重複發生的模式，不是一次性

```
$ ls 01.openmv/C04-Layout/02_build/generated/tools/ | wc -l   → 19
```

`01.openmv` 有同一批 fork。這是**架構層缺口**（平台沒給 consumer 一條可執行的路），
不是某個 agent 的個別疏失。

---

## §5 Explicitly NOT bugs（已鑑別，勿誤修）

1. **`gen_product.py` 不是 fork，是合法的產品側 spec producer。**
   它 `from bodesign_eda_bridge import compose_schematic`（:296）並呼叫平台
   compose（:302）——產品 repo 提供**設計意圖**（spec dict），平台做**產生**。
   這正是應有的分工，**不要動它**。

2. **`generated/tools/` 作為 worked-example 參考是 GUIDE 明文允許的。**
   c04-layout GUIDE:104 / :394 把它稱為 "worked example / reference"。
   問題**不是它存在**，而是產品 repo **執行**它而非執行 MCP tool
   （GUIDE:157-176 才是正規路徑）。修復方向是「讓正規路徑可達且好用」，
   不是「刪掉參考檔」。

3. **`prd_bom_crosscheck` 沒壞。** 它正確履行 role-level PRD 履行檢查。
   §1 的洞不在它的責任範圍內，不要把 BOM↔netlist 塞進它。

4. **`check_c03` 的 R1–R4 邏輯本身沒壞。** 缺的是第五條規則 + 一個 netlist 參數
   + 一個可達的執行路徑。不要重寫它。

---

## §6 Fix proposal（依修復順序；順序有依賴方向）

> **順序理由（a2a-d2d-protocol §4.3）**：先修 §3（可達性），
> 否則 §1/§2 的修復 consumer 依然碰不到，會第三次 fork。

### F1（先做）— 讓 `check_c03` 真的零依賴可達（修 §3）

`bodesign_workflow_core/__init__.py:80` 的 eager `from .checkers import (...)`
改為 lazy（`__getattr__` 延遲，或把 pure-CSV gate 移到不經 `checkers` 的
import 路徑）。驗收：

```bash
PYTHONPATH=packages/workflow-core python3 -c \
  "from bodesign_workflow_core import check_c03; print('ok')"
# 必須在沒有 bodesign_design_ir / pcbnew 的環境成功
```

### F2 — `check_c03` 新增 R5：BOM↔netlist ref 一致性（修 §1）

新增 `netlist_path: str | None = None` 參數 + `R5_NETLIST` finding code：

- BOM 有、netlist 無 → `R5_NETLIST` **BLOCKING**（本 BR 的 `J_MIC`/`J_LED` 情形）
- netlist 有、BOM 無 → **BLOCKING**（反向漏帳，同等危險）
- `netlist_path` 未提供 → **報告必須自報 `netlist_crosscheck: "not_run"`**，
  絕不可讓 `gate: PASS` 讀起來像已檢查
  （§J 教訓：判決必須帶預算/範圍；`passes_limit` 的同型 positive pattern）
- `qty=0` 的 alternate 列（如 `MIC1_ALT`）應豁免——需要一條明確的豁免規則，
  不是靜默跳過

### F3 — status vocabulary 收斂為單一 SSOT（修 §2）

`design-ready` 這個詞彙**必須有裁決**，二選一（平台 owner 決定）：

- (a) 納入 `_STATUS_ENUM`（承認它是合法生命週期狀態，並定義它與 `finalized`
  在 gate 上的差異）
- (b) 明確拒絕（則 consumer 的 21 列必須改詞，且 gate 要給可行動的錯誤訊息，
  例如 `did you mean 'proposed'?`）

**不可接受的結果是現狀**：兩個 gate 各自自洽、判決相反、無人報錯。

### F4 — 提供 consumer 一條「不需 fork」的 C04 tool 路徑（修 §4）

問題本質：consumer 需要在**本地、無 MCP round-trip** 的情況下跑 pour/widen/
si_check，才會去 fork。可能方向（平台 owner 選）：

- (a) `bodesign_emit_stage_tools(stage, out_dir)` — 由平台**產生**當前版本的
   tool wrapper 到產品 repo，且**內嵌版本戳**；配一個
   `bodesign_check_tool_staleness` 偵測產品 repo 的 fork 落後平台幾個修復
- (b) 讓 `generated/tools/*.py` 變成**薄 wrapper**，實作一律 delegate 回
   `bodesign_eda_bridge.routing`，fork 就不可能凍結
- (c) 最小版：新增一條 lint（比照 `no_silent_degradation.py` 的 L1–L10），
   偵測 consumer repo 出現與平台函式同名的獨立實作 → 報 drift

**至少要有 (c)**：否則第三個產品 repo 會再 fork 一次，而沒有任何機制會發現。

### F5 — GUIDE 修正「drawability」的語意

c03-ee GUIDE:47 對 `check_c03` 的描述會讓讀者以為 drawability 已驗證可繪。
應改為明確語意：**R3 檢查的是「BOM 列是否宣稱了 symbol 來源」，
不是「symbol 是否已存在於 schematic」**——後者由 F2 的 R5 覆蓋。

---

## §7 Validation plan（每條 fix 對應可機檢的反向鑑別力測試）

1. **F1**：在**沒有** `bodesign_design_ir`、**沒有** pcbnew 的乾淨 venv 匯入
   `check_c03` 成功。反向：故意留 eager import → 測試必須失敗。
2. **F2 正向**：拿**本 BR 的真實 BOM**
   (`03.aiguard/C03-EE/03_input/C03_BOM.csv`) + 真實 netlist
   (`03_input/C03_aiguard_power_frontend.net`) 跑 `check_c03`，
   **必須** FAIL 並列出 `J_MIC` / `J_LED` 為 `R5_NETLIST`。
   **這是本 BR 的驗收金標準**——修好後這組輸入不得再回 PASS。
3. **F2 反向鑑別力**：把 R5 註解掉 → 測試必須失敗
   （比照 §I 的反向鑑別力測試紀律，防 CI 假綠）。
4. **F2 not_run**：不給 `netlist_path` → 報告必須含
   `netlist_crosscheck: "not_run"`，且不得出現讓人誤讀為已檢查的 PASS 措辭。
5. **F3**：同一份 BOM 對兩個 gate 的判決**必須一致**（或產品 fork 已刪除，
   則此測試改為「產品 repo 不存在替代 gate」的 lint）。
6. **F4**：對 `03.aiguard` + `01.openmv` 兩個 repo 跑 staleness/drift 偵測，
   **必須**報出 `net2pcb.py` 缺 §B 修復。
7. **回歸**：`no_silent_degradation.py` 的 L1–L10 全綠、既有 c03 gate 測試不退。

---

## §8 consumer 側自承的殘留（不屬平台責任，記錄以免混淆責任邊界）

以下由 consumer（aiguard）自己負責，**不要**放進本 BR 的修復範圍：

- `gen_product.py` 尚未新增 `J_MIC`/`J_LED` 的實際 netlist 節點
  （即 §1 症狀的**產品側成因**）；`MIC1` footprint 仍是舊值
  `Infineon_PG-LLGA-5-1`，需改 MP23DB01HP 封裝。
  → 已登錄於 `plans/aiguard_c01-c04-autonomous-delivery/tasks.md` 3.6a
- 產品 repo 那份 `check_bom.py` 的去留，待 F3 裁決 `design-ready` 後才能定案
  （現在刪掉會讓 consumer 完全沒有 gate；留著則繼續分裂）。
  **這是 F3 的下游動作，需要平台先裁決。**

---

## §9 為何由 consumer 提報而非平台自查

這四條缺陷全部**只在 consumer 實際站的位置上可見**：

- §3 只有在「沒有 ee worker 環境的 repo 裡 import」時才炸
- §2 只有在「兩個 gate 對同一份檔案都跑過」時才顯形
- §4 只有在「比對產品 fork 與平台 routing.py 的修復狀態」時才顯形
- §1 只有在「手改 BOM 後看 gate 依然 PASS」時才顯形

平台在自己的容器裡自查，四條全部看不見——這本身就是
`no-silent-degradation` 的元層級實例：**驗證環境與使用環境不同，
驗證就會系統性錯過一整類缺陷**（比照 BR_20260729 §A 的
facade-vs-worker 容器混淆）。

---

## §10 Owner 裁決與落地（2026-07-30，platform owner 補記）

> 本節由 owner 寫入。**裁決若只活在 session 對話與 event log 裡，下一個讀這張 BR 的人看不到**——
> 那正是這條線一路在修的形狀（待辦/決策託付給會蒸發的載體）。

### 10.1 F3 裁決：`design-ready` **納入**（選項 a）

`_STATUS_ENUM` 加入 `design-ready`，並新增 `_READY_STATUS = {finalized, design-ready}` 定義語意：

| status | 語意 | 足以進入 |
|---|---|---|
| `finalized` | 料件完全指定、mpn 已定案 | layout + 採購 |
| `design-ready` | 電氣/機構已決定且可繪，mpn 可為 generic | **layout only** |

**配套的刻意決定**：`design-ready` 列**不套用** placeholder-mpn 檢查（`TBC/TBD/UNDECIDED` 那條只對
`finalized`）。因為「mpn 可延後」正是它與 `finalized` 的區別；若還罰它 generic mpn，這個狀態就沒有
存在意義。採購就緒是另一個 gate 的事，不是 C03→C04 entry gate 的事。

consumer 的 21 列不需改詞。其 `check_bom.py` 的刪除時機由 consumer 定（F1 確認可用後）。

### 10.2 第二個裁決：`Pin_Allocation.csv` 的 schema 契約（§6 未列，round=4 浮現）

reporter 量到 R4_SSOT 對真實 pinmap **零鑑別力**（26 個 active 件全部被報成
`BOM↔SSOT conflict — owner must reconcile`），並指出 GUIDE 自我矛盾。裁決：

> **交付物表定義「這個檔案是什麼」，散文只描述「怎麼用它」。前者優先。**

- 交付物表三處（`:43` / `:340` / `:374`，最後一處標 `exported`）定義它是
  **ball → GPIO → peripheral function 的 pinmap**；
- **只有** §3c 散文（`:230` / `:243`）假設 ref 導向；
- fleet 4 份 `Pin_Allocation.csv` **全部**遵守交付物表。

⇒ 「沒有 ref 欄」是**合規**狀態，不是歷史欠帳。故**不採** reporter 建議的 (b) 報 schema blocker
（那會宣告 4 份合規檔案全部不合規），改為 `ssot_crosscheck.status = "not_run"` +
列出 `active_parts_unverified`。GUIDE §3c item 1 已記下此裁決，並明寫
**「本條的『必讀』義務是人工前置，不因 R4 不適用而免除」**。

### 10.3 收下 reporter 的 J_LED 實例，但**改判準**（round=2 → R6）

reporter 建議把 J_LED 共陽誤接當 F2 正向測試輸入。**駁回，理由是機制性的**：

> R5 檢查「BOM 與 netlist 是否一致」，而那個錯誤是 **BOM 寫錯 → 施工者忠實照 BOM 施工 →
> 兩邊一致地都錯**。R5 在那一刻完全通過，而且**原則上抓不到**。
> 拿它當正向測試會得到 PASS，那條測試就變成一個宣稱「R5 能抓 pin 語意錯誤」的假綠斷言。

改收為 **R6**（第三來源：pin 規格文字 ↔ netlist 實際極性），且判準**不是** reporter 提的
逐 token / `pinfunction` 比對：

- `pinfunction` 比對需要 pre-breakout 快照，consumer 未必留著；
- **逐 token 精確比對會 flag 正確答案**——修正後的 `(K_R/K_G/K_B/+3V3 common-anode)` 與其 net
  `+3V3_PB` **字面不相等**。

> **一個會 flag 正確答案的檢查，比沒有檢查更糟**——它會被關掉，連帶關掉它本來能抓的真缺陷。

⇒ 只認**不可能是命名風格差異**的那一類矛盾：**GND ↔ power 極性反轉**。positional 對齊
（第 N 個 token = pin N）是必要假設（也正是施工者做的假設），但 token 數與實際 pin 數不符時
**報 `unaligned` 而非硬對**。

### 10.4 三條 reporter 未報的 gate 自身缺陷（owner 自驗時發現，全部零鑑別力）

| # | 缺陷 | 實測 |
|---|---|---|
| N1 | R3 欄位別名漏 `deck_status`（每份產品 BOM 與 GUIDE 實際用的欄名）→ `_col_index` 回 `None` → `symbol_name=None` | **34 列全部** fail R3 |
| N1-孿生 | `_load_pin_alloc_refs` 對「無 ref 欄」與「ref 欄空」都回空集合 | **26 件全部**報成 SSOT 衝突 |
| N2 | `_read_csv_rows` 不跳過 `#` 模組分隔 banner（BOM 慣例） | **28 筆** `R1_SCHEMA: likely CSV quoting breakage` 誤診 |

**通則**：

> 「我找不到要檢查的欄位」不是「那個欄位是空的」。前者是 **gate 輸入缺陷**，後者是
> **被檢物內容缺陷**，修法不同。**全紅與全綠的鑑別力相同：零。**

修法：欄位缺席 → 報**一筆** schema 級 finding（不冤枉 N 列）；不適用 → 報 `not_run` +
列出**未被驗證**的清單。

**聚合效果（reporter 真實 BOM）：82 blocking → 1**（後續 reporter 自行修掉 DS1 的
`symbol=manual` 後為 0）。**81/82 是 gate 自身缺陷產生的噪音**（48 個 R1 + 33 個假紅 R3）。

⇒ 這重新定義了 §2 那個 fork 的性質：**不是紀律問題，是對一個不可用工具的合理反應**。
也因此 §6 的修復順序（F1 可達性優先）是對的，但理由要補上「假紅」這一半：
**可達 + 不噴假 finding**，兩者都做到工具才真的能用。

### 10.5 第三個詞彙分歧（未咬人但同型，一併收）

```
consumer check_bom.py:47   re.search(r"symbol=|C\d{5,}|N/A", ...)   接受裸 LCSC id
平台 _SYMBOL_SOURCES        ("official","vendor","lcsc","manual","n-a","n/a")   不接受
```

真實 BOM 目前 0 列**只**依賴裸 `C#####`（11 列有 id 但也有 literal keyword），所以還沒炸。
已納入平台側。**這不是放寬**：一個 id 可被解析驗證，`lcsc` 這個字不行——接受 id 比接受字**更嚴**。
加 `>=5` 位數下限（`C1` / `C123` 不得混過，有反向測試）。

### 10.6 F4 lint 自身的兩條缺陷（owner 自曝，與上面同型）

**(1) `KNOWN_FORKS` 名字寫錯** — 平台沒有 `widen()` / `length_match()`，真名是
`widen_bus_tracks` / `length_match_bus`。錯名讓 AST fallback 命中
`01.openmv/C03-EE/02_build/sch_gen/gen_from_net.py` 一個**完全無關**的 local
`widen(block, name)` schematic helper，報成 stale fork。**用不存在的基準指控。**

**(2) 8 個 sentinel 無差別套到每個 fork** — `pour.py` 被報「缺 8/8 修復」，而
`footprint_lib_unresolved` 屬於 `net2pcb_board`。**11 個 finding 裡真正相關的只有 4 個**——
與 §6 F2 提案被駁回的 cry-wolf 同型，在 lint 自己身上重演一次。

修法：sentinel 加 owner 欄（由原始碼實測，非推測），只套給擁有它的函式；
**沒有 owned sentinel 的 fork 從 findings 移進 `coverage.forks_unassessable`**——
那是 lint 自己的表缺口，不是 consumer 的缺陷，記成 per-file finding 等於把自己的不完整
記在對方帳上並灌水 finding 數。

修後：`7 finding(s): D1=2, D3=5` + `UNASSESSABLE 4`。

### 10.7 落地清單（8 檔，**未 commit**）

| 檔案 | 內容 |
|---|---|
| `packages/workflow-core/bodesign_workflow_core/__init__.py` | F1 PEP 562 lazy（8 符號；揭露**第二個** eager 違規者 `package_readiness` → `bodesign_reverse_core`，BR 原文未及） |
| `packages/workflow-core/bodesign_workflow_core/check_c03.py` | F3 / R5 / R6 / N1 / N2 / R4-not_run / LCSC |
| `packages/workflow-core/bodesign_workflow_core/checkers/consumer_fork_drift.py` | F4（新） |
| `tests/test_check_c03_gate_reachability_and_netlist.py` | 36 條（新） |
| `tests/test_consumer_fork_drift.py` | 15 條（新） |
| `ragbase/control/no-silent-degradation/README.md` | **V7** + 兩個衍生陣形 + 「一致地都錯」 |
| `skills/bodesign/stages/c03-ee/GUIDE.md` | F5 + §10.2 裁決 |
| `specs/architecture.md` | 三筆同步 |

### 10.8 驗證

```
tests.test_check_c03_gate_reachability_and_netlist   36 pass
tests.test_consumer_fork_drift                       15 pass
tests.test_check_c03（既有，回歸）                     14 pass
tests.test_prd_bom_crosscheck                        10 pass
tests.test_no_silent_degradation                     19 pass
no_silent_degradation 基線                            11 findings (L2=8, L6=3) — 與修前一致
```

**Mutation 驗證（三條主修都真紅，防 CI 假綠）**：

| 還原的修復 | 結果 |
|---|---|
| R4 `return None` → `return set()` | `test_ball_oriented_pinmap_reports_not_run` RED |
| `#` 註解跳過 | `test_comment_banner_rows_are_not_quoting_breakage` RED |
| `deck_status` 別名 | **5 條** RED |

**R6 雙向坐實**（合成 fixture；reporter 的真實 BOM 已自行修好）：

```
BUGGY  (R/G/B/GND)                     → R6 flagged pin 4: GND vs +3V3_PB
FIXED  (K_R/K_G/K_B/+3V3 common-anode) → PASS   ← 沒有 flag 正確答案
J_MIC  (CLK/DATA0/VDD/GND)             → PASS   ← VDD↔+1V8 不算衝突
```

**金標準（§7.2 item 2）達成**：真實 BOM + 兩份真實 netlist → `J_MIC` / `J_LED` 皆被列為
`R5_NETLIST`。⚠ 只給 `C03_aiguard_power_frontend.net` 也會抓到，但 R5 finding 會多很多
（那份只涵蓋 13 個 ref）——`netlist_scopes` 欄位會說明判決的基準。

**Sentinel provenance**：8 個 token 全部經 `git log -S` 追到所標 commit；
6 個 `KNOWN_FORKS` 名字全部驗證是平台真實 `def`。

### 10.9 未做 / 邊界

- **不動 `gen_product.py`**（§5.1，reporter 劃界正確）
- **不寫進 `.work/`**（reporter 走 `bodesign_stage_dir` 是對的）
- **不刪 reporter 的 `check_bom.py`**（時機歸 reporter）
- **§8 consumer 側殘留全部不屬本 BR 修復範圍**
- **`_LAZY_EXTERNAL_DEP_EXPORTS` 是手寫清單 = V4-c 形狀**，故
  `test_no_third_eager_offender_appears` 從原始碼**重新推導** audit，出現第三個
  eager 違規者即紅（該測試自身另有反向鑑別力測試）
