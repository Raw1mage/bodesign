# Handoff: eda-bridge_draftsman-series-divider-wireable

## Execution Contract

執行者交付 `packages/eda-bridge/bodesign_eda_bridge/declare.py` 與其測試，
使 `tasks.md` Phase 1 的四條完成判準全綠：

```
declare_circuit(btdongle 分壓宣告).status == "ok"
產出的 spec 餵 compose_schematic 後，VBAT_SENSE 是 drawn 不是 label
該子電路 junction > 0
CONTROL：tap 改成等於 top => status == "rejected" 且 code == E_DIVIDER_TAP_DEGENERATE
```

**Done 的定義**：上面四格逐格貼出實際輸出（不是「測試通過」的轉述），
且 `errors.md` §Outcome Codomain 的五個狀態各自在測試中被觸發過至少一次。

**未完成即未完成**：若 Phase 1.8 的端到端因既有引擎缺陷（見 §Stop Gates）跑不出
`junction > 0`，**不得**調整判準來讓它綠，回報 blocked 並指名是哪一格擋住。

## Required Reads

執行前必讀，順序即依賴順序：

1. `plans/eda-bridge_draftsman-series-divider-wireable/{proposal,design,errors,spec}.md`
   —— 本包自己。`design.md` §Context 那段「與 KB 禁令的關係」**必讀**，
   否則會把本包誤實作成 netlist 合成器（那是被明文禁止的）。
2. `data-schema.json` + `test-vectors.json` —— I/O 契約與 14 個測試向量。
3. `issues/BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm_on_non_label_friendly_topology.md`
   —— 特別是 **§8.5.2**（power clustering 修法為何失敗）與 **§8.5.5**（門檻的 scale 依賴：
   合成語料會給出假未達標，驗收一律用真 spec）。
4. `packages/eda-bridge/bodesign_eda_bridge/composer.py:1887`（`compose_schematic` 簽名）
   與 `:2181-2231`（現行 label/wire 判定）。**Phase 1-2 只讀不改。**
5. `AGENTS.md` §5（測試怎麼跑：`./scripts/run_tests.sh`，讀 `Ran N tests` 的 N 不是 rc）
   與 §6.1（共用工作樹紀律——這棵樹有多顆 session 並行且大量未 commit）。

## Stop Gates In Force

- **Phase 3 有硬前置，不得跳過**：`try_reserve` 目前 71 次嘗試 0 次成功
  （round 1 實測，`reserve_wire_conflict_kind_body 84 / pin_extent 58`），
  導致 ledger 的 wire 層恆空、wire-vs-wire 碰撞偵測是死的。
  在 `reserve_wire_ok > 0` 之前**不要動 `render` hint 接線**——
  `BR_20260905` §8.5.2 記載那條路會讓 fidelity `moved` 從 10 爆到 67。
- **不得為了讓判準變綠而關 fidelity gate**。`BR_20260905` §8.5.2 的教訓逐字：
  幾何判準（junction 數、短樁比例、子電路數）**全部大幅達標的同時把 net 接錯**，
  而擋住它的唯一一格就是 fidelity。**格式綠燈不授權任何電氣正確性宣稱。**
- **真板 fidelity 在本包範圍內不會轉綠**（`BR_20260905` §8.5.4）：
  HEAD 在 btdongle 上本來就 `moved=10`，signature 屬於另外兩張 BR
  （multi-unit 壓平 + VBUS/CC 熔合）。不要試圖在本包內讓它 PASS。
  本包的幾何數字在真板上一律是 fidelity OFF 下量的，**且必須明講這一點**。
- **commit 授權在 dispatcher**。改完、跑完測試、停在未提交狀態。

## Execution-Ready Checklist

- [ ] `.state.json` 的 `profile` 目前是 `[]`（空）。推 `designed` 之前需
      `plan_set_profile`，否則 gate 會要求全套 artifact 而本包的
      `idef0.json` / `grafcet.json` 仍是 scaffold。**這格由 dispatcher 裁決**，
      執行者不得自行改 `.state.json` 逃 gate（`BR_20260628`）。
- [ ] 確認 `./scripts/run_tests.sh test_declare_circuit` 可跑（新測試檔尚不存在時
      預期 `Ran 1 test / FAILED (errors=1)`——**那是模組沒載入的外觀，不是回歸**）
- [ ] 確認 btdongle 真 spec 可取：
      `/home/pkcs12/products/thesmart_products/04.btdongle/C03-EE/02_build/sch_gen/design.py`
      （**注意有 `sch_gen/` 一層**，少這層會 rc=1 而「查錯路徑」與「檔案不存在」共用同一個輸出）
- [ ] 開工前先做工作錨定（`AGENTS.md` §6.1 的 `refs/wip/<session-id>` 配方），
      並逐檔 `git show <ref>:<path>` 驗過——**「ref 建好了」不等於「內容在裡面」**

## Round 1 診斷的可用產出（下一輪要用）

- `generated/sch_bodesign/btdongle.kicad_sch`（消費端 repo，未 commit）——
  HEAD 引擎跑真 spec 的產物，wire=116 / junction=6 / short=71.6% / power glyph=61。
  **這是 Phase 1 的 before 基線。**
- `mk_sch_bodesign.py` 現在是可跑的（`style=draftsman validate=True fidelity=True` 通過）。
- 插樁副本在 `$XDG_RUNTIME_DIR/schdiag/pkg2/`（scratch，非 repo）——
  若要重量 router 呼叫/降級計數可直接重跑 `run_instr.py`。

## Open Questions for Dispatcher

三題均已裁決（round 3 dispatch），保留原文以便追溯理由：

1. ~~**verb 命名**：`bodesign_declare_circuit` 是否可用？~~
   → **核准**。既有 60 verb 慣例為動詞開頭（compose_schematic / export_netlist / emit_symbol），逐字符合。
2. ~~**落點**：`declare.py` 放 `eda-bridge` 還是 `workflow-core`？~~
   → **`eda-bridge`**。採納「輸出契約綁著 composer.py，放 workflow-core 會讓契約跨包」。
3. ~~**profile**：`software` 全套還是 `docs`？~~
   → **`software`**。idef0/grafcet 已是有內容的真檔，邊際成本只剩跑一次 diagram validate。

---

## Phase 1 Evidence

四格完成判準全綠（round 3）。兩格判準在執行中被證實無判別力、當場換掉並向 dispatcher 明講（均獲採納）：

- **格 2 原文「VBAT_SENSE 是 drawn 不是 label」無判別力**：`(label "VBAT_SENSE")` 在檔案裡確實存在，
  但那是「畫成實線並掛識別標籤」而非「畫不出來所以掛旗」——兩者共用同一個字串。
  改用 `route_stats.label_fallback_reasons`（只列 `BATT`，不含 `VBAT_SENSE`）作為判準。
- **POSCTRL 13 → 14**：`.state.json` 是 dotfile，`ls` 看不到。

## Phase 2 Evidence

四格完成判準逐格實測（round 4）。下列數字皆為 `python3` 直驅 `declare_circuit` 的實際輸出，
不是「測試通過」的轉述。

**格 1 — 六個原語各自至少一個 vector 走到 `ok`**

```
connect     status=ok gate=pass errors=[]
bridge      status=ok gate=pass errors=[]
series      status=ok gate=pass errors=[]
divider     status=ok gate=pass errors=[]
rail        status=ok gate=pass errors=[]
no_connect  status=ok gate=pass errors=[]
```

**格 2 — 三個新錯誤碼各自被觸發，且錯誤物件回顯它拒絕的識別符**

```
E_SERIES_TOO_SHORT    status=not_run
  s: series.chain has 2 entries (['+3V3', 'GND']); a series is <net> <part>+ <net>,
     so it needs at least 3. Two nets and no part is a `connect`.

E_NET_NAME_COLLISION  status=rejected
  derived net name 'd7_n1' collides with a declared net name | refs: ['d7_n1']

E_RAIL_SCOPE_UNKNOWN  status=not_run
  d10: rail.scope names 'C2', not in components[] | refs: ['C2']
  d10: rail.scope names 'C3', not in components[] | refs: ['C3']
```

三者均配對照組（三項 chain 不報 TOO_SHORT、不撞名不報 COLLISION、
已宣告 scope 不報 SCOPE_UNKNOWN），以排除「每一範都報」這種零判別力的探針。
`E_RAIL_SCOPE_UNKNOWN` 一次列出全部未知 ref（C2 **與** C3），不只第一個，
且不包含確實存在的 `U1`。

**格 3 — 五個 status 各自被 Phase 2 輸入觸發過**

```
requested=ok            -> observed=ok             (series 正常展開)
requested=rejected      -> observed=rejected       (E_NET_NAME_COLLISION)
requested=not_run       -> observed=not_run        (E_SERIES_TOO_SHORT，展開器未跑)
requested=empty         -> observed=empty          (declarations=[])
requested=indeterminate -> observed=indeterminate  (symbol 載不到)
ALL FIVE DISTINCT: True
```

**格 4 — `W_RENDER_HINT_IGNORED` 真的排放了，不是只寫在 docstring 裡**

這格是 2.4 的重點：**刻意的無操作必須有可觀測痕跡**，否則「hint 被忽略」與「hint 沒被讀到」
共用同一份輸出，Phase 3 接線後將無法分辨接線有沒有生效。

```
TREATMENT (render="daisy_chain")
  render_plan: {'GND': {'render': 'daisy_chain', 'source': 'declared'}}
  warnings   : [{'code': 'W_RENDER_HINT_IGNORED',
                 'detail': "d: rail 'GND' declares render='daisy_chain', but render hints
                            are not wired to geometry in this build (tasks.md Phase 3).
                            The hint is recorded in render_plan and the emitted schematic
                            uses 'global_label'.",
                 'refs': ['d', 'GND', 'daisy_chain']}]

CONTROL (no render given)
  render_plan: {'GND': {'render': 'global_label', 'source': 'default'}}
  warnings   : []

DISCRIMINATES read-and-ignored vs never-read: True
```

另一格對照（`test_the_two_sources_are_DIFFERENT_values`）：顯式給 `render="global_label"`
與完全不給，**render 模式相同但 `source` 不同**（declared vs default）——
若這兩格相等，Phase 3 就分不出「hint 被醫重」與「巫合」。

**verb 註冊可達性（非僅「檔案裡有字串」）**

```
total_verbs: 61                (新增後)
declare_in_schema_list: True

NEGCTRL   送一個確定不存在的名字，錯誤必須回顯我送的那個名字：
          {"error": "unknown tool: 'bodesign_declare_circuit_NOPE_xyz'"}
          ↑ 冒號後有名字。上一輪的 {"error":"unknown tool: "} 冒號後是空的，
            意思是欄位根本沒被讀取——那是一個看起來完美實則零判別力的負控制。

TREATMENT 經同一條 dispatch 路徑：
          status=ok
          nets=[{"name":"+3V3","nodes":["C8.1"]},{"name":"GND","nodes":["C8.2"]}]
```

註冊的兩個決定且各自有理由：

- handler 走 `from bodesign_eda_bridge.declare import declare_circuit`（**直接子模組**），
  不經 `from bodesign_eda_bridge import ...`——後者的 `__init__` 會拉進 kiutils 相依模組，
  而宣告拓樸這件事不應要求使用者裝有 KiCad。
- **刻意不列入 `_EE_GROUP_TOOLS`**（同理）。它唯一的 KiCad 觸點是選配的 pin 清單讀取，
  而那一格缺席時降級為 `indeterminate` 而非失敗。

**回歸：量的，不是推的**

```
TREATMENT  Ran 2054 tests   FAILED (failures=12, errors=40, skipped=52)
BASELINE   Ran 2018 tests   FAILED (failures=12, errors=40, skipped=52)
           ↑ 差 36 則，恰好是本輪的 test_declare_circuit 全數

失敗集合比對（不只比數字，比 test id 集合）：
  treatment_failing: 46
  baseline_failing : 46
  NEW_failures_caused_by_me: []
  failures_that_DISAPPEARED: []
  sets_identical: True
  CONTROL extractor found nonzero: True   ← 否則 identical 是空洞為真
```

BASELINE 的取得方式：把 `tests/test_declare_circuit.py` 搬到 `$XDG_RUNTIME_DIR`，
`services/mcp/server.py` 以 `git stash push -- <精確 pathspec>` 退回 HEAD（**不是** `reset --hard`，
這棵樹有 peer 未 commit 工作，AGENTS.md §6.1），量完立即還原並驗證兩檔均在位。
兩輪 run 前均先 `rm -rf __pycache__`（AGENTS.md §6.3：`-B` 擋不掉既有 stale pyc）。

**本輪未量的（明列，不面包成已驗）**

- **UDS 端到端未驗**。本輪是原始碼層驗收；verb 的可達性是對 `server.TOOLS` 的
  in-process dispatch 量的，**不是**透過 `.run/bodesign.sock` 量的。
  容器是 baked image，`restart` 不夠，需 `rebuild`——dispatcher 已表明另行授權。
- **Phase 3 未碰**。`render` hint 仍未接線（硬 stop gate：`reserve_wire_ok > 0`）。
- **`series` 未走真板端到端**。TV-9 的驗收是展開層（net 分割與衍生名），
  未把 series 產出的 spec 餵 `compose_schematic` 量 junction——那不在 2.1–2.7 範圍內。
- **電氣正確性未驗，也驗不了**。`ok` 的讀法依舊是「宣告內部一致且完整」，
  不是「這個電路是對的」（`errors.md` §語法合法但電路錯誤 的最後三列）。

---

## Round 9 — ERC 實測與 T 接觸判定

### B — `kicad-cli sch erc`（三格判準）

`kicad-cli` **在 host 上可用**（`/usr/bin/kicad-cli`, 9.0.9），本輪在 host 跑。
（未量：core 容器內是否有 kicad-cli。本輪 compose 與 ERC 皆在 host。）

**① t3 放行交叉後的 sheet（逐字）**

```
Found 9 violations   rc=5
  error    pin_not_connected   x4   (C3.1, C1.1, C2.1, R1.2)
  warning  lib_symbol_issues   x5   ("configuration does not include the symbol library 'Device'")
```

route_stats: `wired=2 labelled=0 junctions=2 reasons=[]`

**注意：9 個 violation 全部與交叉無關。** 4 個 `pin_not_connected` 是 fixture
本身沒接的腳（t3 只宣告 2 條 net，其餘腳本來就懸空），5 個 warning 是 symbol
library 路徑未寫進 project config。**ERC 對放行的交叉本身零意見**——這正是
`.kicad_sch` 顯式連接語意的預期行為：交叉點無 junction ⇒ 不成 net。

**② 與「交叉被擋」狀態的比對 — 差集為空**

比對基線的取得**修正了 dispatch 的一格前提**：`edc6cd8` **不是**「交叉被擋」的狀態。
實測 `edc6cd8` 對同一份 spec 回 `wired=2 labelled=0 junctions=2 reasons=[]`，
與 HEAD 逐字相同——因為 `edc6cd8` 早於 round 7 的 `_reserve_wire` 修復，
帳本 wire 層是空集，**根本沒有東西擋得下來**。

真正的「交叉被擋」狀態 = HEAD 且 `_PERPENDICULAR_OK_KINDS = frozenset()`
（round 7 落點）。以該狀態實跑：

```
ROUND7 (exemption OFF): wired=1 labelled=1 junctions=2
                        reasons=[{'net':'SIG2','reason':'ledger-collision'}]
HEAD   (exemption ON) : wired=2 labelled=0 junctions=2  reasons=[]
```

兩者的 ERC 差集：

```
ROUND7 sheet: 9 violations   (error pin_not_connected x4, warning lib_symbol_issues x5)
HEAD   sheet: 9 violations   (error pin_not_connected x4, warning lib_symbol_issues x5)
only in ROUND7: (empty)
only in HEAD  : (empty)
common: 9
```

**放行交叉沒有引入任何新的 ERC violation，也沒有消除任何一個。**
SIG2 從 global label 改成實線走線，對 ERC 而言電氣拓樸不變（label 與 wire
都能構成同一條 net），所以差集為空是正確結果而非探針失效——見 ③。

**③ NEGCTRL：`kicad-cli` 在該紅的時候會紅**

兩格，方向相反：

```
ACCEPTING CONTROL  結構合法的空 sheet          → Found 0 violations   rc=0
NEGCTRL (SHORT)    t3 + 在交叉點注入 junction  → Found 12 violations  rc=5
```

NEGCTRL 的注入點是實測出來的交叉座標：t3 的 8 條 wire 中，
seg2 `(121.92,83.82)-(172.72,83.82)` H 與 seg6 `(168.91,74.93)-(168.91,124.46)` V
在 **(168.91, 83.82)** 交叉；原 sheet 的兩個 junction 在 (121.92,83.82) 與
(172.72,83.82)，**都不在交叉點上**（所以不短路）。把 junction 注到交叉點後：

```
ONLY IN SHORTED SHEET (差集，即注入 junction 造成的):
  + ('warning', 'multiple_net_names', "Label 'GNDISH'")
  + ('warning', 'multiple_net_names', "Label 'SIG2'")
  + ('error',   'pin_not_connected',  'Symbol R1 Pin 1 [Passive, Line]')
  + ('warning', 'unconnected_wire_endpoint', 'Vertical Wire, length 0.0127 mm')
ONLY IN CLEAN SHEET: (empty)
```

**`multiple_net_names` 同時出現在 GNDISH 與 SIG2 上，逐字就是跨 net 合併的簽名。**
這格證明：(a) ERC 真的在讀這張圖而不是空轉，(b) 它抓得到本修法唯一的危險
失效模式，(c) ① 的「9 個 violation 與交叉無關」是真的無關，不是 ERC 沒檢查。

**未量**：core 容器內的 ERC（本輪 host 跑）；密板組的 ERC（dense fixture 產出
0 junction，無交叉可驗，故 ERC 對它無判別力，未列為證據）。

### C — T 接觸判定：**已被擋，且是電氣理由**

結論：**不是缺陷，不需要在 perp 豁免裡加 X-interior 條件。**

`path_clear` 的 perp 豁免確實只判軸向（dispatcher 讀 code 讀對了），但它
**不是 accept path 的唯一關卡**。`_segment_fuses`（kicad_emit.py:3283）在
`_guard_route` 的 `extra_ok` 之前先跑（:1668 / :1914 / :1982），而它明確檢查
端點落點。

**逐格量測（同一組幾何，兩層謂詞各跑一次）**

net A = 水平 `(100,80)-(150,80)`；net B 三種候選：

| 候選 | 幾何 | `_segment_fuses` | `path_clear`(perp on) | 被誰擋 |
|---|---|---|---|---|
| T 接觸 | `(125,60)-(125,80)` 端點落在 A 上 | **True（擋）** | True（放行） | `_point_on_segment` |
| X 交叉 | `(125,60)-(125,100)` 穿越內部 | False（放行） | True（放行） | 無（正確） |
| 共線疊合 | `(120,80)-(170,80)` | **True（擋）** | **False（擋）** | `_collinear_overlap` |

**指名擋它的謂詞**：`_point_on_segment(seg_endpoint, other_seg)` —— 這是
**電氣理由**，不是碰巧的 body keep-out：該函式的 docstring 逐字寫
"A shared endpoint between two nets is itself a fusion (KiCad merges a wire END
that touches another wire)"，判斷依據是端點座標與對方線段的幾何關係，
與 body / pin_extent / label 等任何佈局元素無關。換一份佈局仍然成立。

**控制組（證明它不是全面拒絕）**：同一支謂詞對 X 交叉回 False。
若 `_segment_fuses` 對 T 與 X 都回 True，那它只是在擋所有正交線段，
指認不了任何東西——實測 `T=True and X=False` 為真，故有判別力。

**真實路徑證實**：12 顆 R、12 條 net 的密板 fixture 走完整 `compose_schematic`，
`label_fallback_reasons` 回 `[{'net':'N7','reason':'anti-fusion'},
{'net':'N9',...},{'net':'N11',...}]` —— **`anti-fusion` 這個 reason 在真實
compose 路徑上真的排放了**，不是只在單元謂詞層可觸發。

**兩層謂詞的分工（給下一個人）**：

- `_segment_fuses`：**電氣**層。管 net-vs-net 的融合（共線疊合 + 端點落點）。
  T 接觸由它擋。
- `path_clear` perp 豁免：**版面**層。管候選線段與帳本 rect 的碰撞。
  它不判 X-interior 是**可接受的**，因為電氣層已先擋掉 T。

**但這個分工是隱性的**：`path_clear` 的 docstring 沒說「T 接觸由上游擋」。
若未來有呼叫端**只**用 `path_clear` 而不經 `_guard_route`，T 接觸就會漏。
目前 `_PERPENDICULAR_OK_KINDS` 只有一個呼叫端（kicad_emit.py:1796）且在
`_guard_route` 之後，所以現況安全——**這是一個依賴呼叫順序的保證，不是
謂詞自身的保證**。

### 回歸

```
TREATMENT (HEAD 7af9f71)  test_composer_draftsman: 11 failing ids
BASELINE  (edc6cd8 tree)  test_composer_draftsman: 11 failing ids
NEW_failures_caused_by_round9: (empty)
CONTROL: id 擷取器回非空（前三筆已列印）  ← 否則 empty 是空洞為真
full suite: Ran 2063 tests  FAILED (failures=12, errors=40, skipped=52)  ← 與既有基線同
tests/test_wire_crossing_guard.py 單獨: Ran 9 tests  OK
```

BASELINE tree 的真實性已逐位元證明：`sha256(before/kicad_emit.py)` 前 16 碼
`373471f8b2b914a3` == `git show edc6cd8:` 同值，且 != HEAD 的 `3ee256f5cea1349e`；
round-8 標記 `perpendicular_ok_kinds` 在 before tree 計數 0、在 HEAD 計數 7。
兩側 run 前均清 `__pycache__`（AGENTS.md §6.3）。

---

## Round 33 — 帳面修正與一則 PASS 的閱讀限制

### 狀態已由 `planned` 推至 `implementing`

`plan-validate` / `plan-promote` 兩者都在報 **STATE DRIFT**（`tasks.md` 進度隱含
`implementing`，`.state.json` 卻停在 `planned`），並明文要求 `Run plan-promote NOW
(not at close-out)`。dispatcher `ses_04db7a1c5ffe` 於 round 33 授權修正。

作法：`plan-promote.ts --dry-run` 先取 `nextStateFile`（DD-15：runner 只裁決合法性，
由 agent 自行套用），確認它**只動 `.state.json`**（state 欄 + history 一筆）之後才寫入。
dry-run 後 `git status --porcelain` 對本包回空、對全 repo 非空——證明 dry-run 真的沒寫，
且該探針不是瞎的。

### ⚠ 這個包的 `plan-validate` PASS，對兩份圖檔什麼都沒說

```
⚠ execution-contract layer DID NOT RUN (no .state.json.execution_contract)
  — 2 manifest(s) present but UNVALIDATED: idef0.json, grafcet.json
PASS — state=implementing: 12 required, 1 optional
  [execution-contract: NOT RUN — package has not opted in]
```

本包**未 opt in** execution-contract layer，所以那六個驗證器一次都沒跑。
`idef0.json` / `grafcet.json` 是 **present but UNVALIDATED**。

**這是「檔案存在」與「檔案通過驗證」共用同一個 PASS 外觀的一個實例**——
與本包 `errors.md` 收錄的失效模式同族：閱讀者會把整體 PASS 讀成對每一份 artifact 的背書。

**判準**：日後任何地方（含新包 `eda-bridge_multi-sheet-subsystem-schematics`）
若要引用本包的 IDEF0 / GRAFCET，**不得以「本包 plan-validate PASS」作為它們的背書**。
要背書就得先 opt in（在 `.state.json` 加 `"execution_contract": {"version":"1.0.0","marking":[]}`）
再跑一次。**本輪只落帳，未 opt in、未跑。**
