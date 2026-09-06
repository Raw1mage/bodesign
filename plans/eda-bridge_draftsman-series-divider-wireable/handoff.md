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
