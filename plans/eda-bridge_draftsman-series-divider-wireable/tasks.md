# Tasks: eda-bridge_draftsman-series-divider-wireable

## 1. 第一刀 — `divider` + `bridge` 兩個原語打通到 compose（最小可用版）

**選這一刀的理由**：`divider` 是本包 slug 的字面來源（series-divider），
也是 `BR_20260905` §3.2 逐字點名的驗收範例（「串聯分壓」）；
`bridge` 是真實板子上數量最多的形狀（btdongle 45 元件裡 28 顆被動件多半是這個）。
兩者合起來能跑通一個完整的可辨識子電路，而**不需要碰任何既有繪圖程式碼**。

- [x] 1.1 新模組 `packages/eda-bridge/bodesign_eda_bridge/declare.py`，純函式，零 I/O，
      不 import `composer` / `kicad_emit`（避免循環依賴，也讓它可被單獨 unittest）
      —— `kicad_emit.load_symbol` 為**函式內 lazy import**，模組層仍為零耦合
- [x] 1.2 實作 `Decl_divider` 展開：top/tap/bottom 三條 net + `load` 併入 tap
- [x] 1.3 實作 `Decl_bridge` 展開：兩條既有 net 各加一個 node
- [x] 1.4 實作 provenance map（DD-6）與 `E_PROVENANCE_ORPHAN` 內部斷言
- [x] 1.5 實作完整性 gate 三態（`pass`/`fail`/`unknown`），含 `E_PIN_UNASSIGNED`
      與 `E_PIN_MULTI_NET`，**全部缺項一次列出**
      —— 實作為**五態**：另加 `vacuous`（零元件，跑了但無腳可檢）與 `not_run`
      （gate 從未被呼叫）。三態會讓「零元件全綠」與「檢查過全綠」共用同一個值，
      那正是 BR_20260730b 的形狀
- [x] 1.6 實作 status codomain 五值的排放點（`errors.md` §Outcome Codomain 那張表逐格對應）
- [x] 1.7 單元測試：`tests/test_declare_circuit.py`，涵蓋 TV-1..TV-8（見 `test-vectors.json`）
- [x] 1.8 端到端：把 btdongle 的 R13/R14/C13 電池分壓 + 一組去耦，
      用 `declare_circuit` 產出 spec → 餵 `compose_schematic` → 確認
      `junction > 0` 且該分壓被畫成連通實線

**Phase 1 的完成判準（可機檢）**：
```
declare_circuit(btdongle 分壓宣告).status == "ok"
產出的 spec 餵 compose_schematic 後，VBAT_SENSE 這條 net 是 drawn 不是 label
該子電路的 junction 數 > 0
控制組：把 tap 改成等於 top => status == "rejected" 且 code == E_DIVIDER_TAP_DEGENERATE
```

## 2. 其餘四個原語 + MCP verb 註冊

- [x] 2.1 `Decl_connect` 展開
- [x] 2.2 `Decl_series` 展開，含中間節點衍生命名（DD-3）與 `pins` 極性映射
      —— 中間節點 `<decl_id>_nN`，N 條 part 產出 N-1 個衍生節點；
      `_pin_lists` 拿得到時取 symbol 兩腳，拿不到才退 `["1","2"]`
- [x] 2.3 `Decl_no_connect` 展開至 `nc[]`
- [x] 2.4 `Decl_rail` 展開（**只做電氣部分**，`render` 欄先收下但不接線，
      回 `W_RENDER_HINT_IGNORED` + `render_source:"default"`）
      —— warning **實際排放**且回顯 `[decl_id, rail_name, render_mode]`；
      對照組（未給 hint）warnings 為空。刻意的無操作若無痕跡，
      「讀了但忽略」與「根本沒讀」共用同一份輸出，Phase 3 將無從驗證接線是否生效
- [x] 2.5 `services/mcp/server.py` 註冊 `bodesign_declare_circuit`（handler `_h_*` + schema 兩處）
      —— handler 走 `bodesign_eda_bridge.declare` **直接子模組 import**，不經 `__init__`
      （後者拉 kiutils；宣告層必須在無 KiCad 的主機上可用）；
      刻意**不列入** `_EE_GROUP_TOOLS`，同理
- [x] 2.6 `E_NET_NAME_COLLISION` / `E_SERIES_TOO_SHORT` / `E_RAIL_SCOPE_UNKNOWN` 三個錯誤碼
      —— 三者的錯誤物件都回顯它拒絕的識別符（chain 內容 / 撞名 net / 未知 ref），
      且 scope 一次列出全部未知 ref 而非只報第一個
- [x] 2.7 補齊 TV-9..TV-14

**Phase 2 的完成判準（已量，見 handoff.md §Phase 2 Evidence）**：
```
六個原語各自至少一個 vector 走到 ok        connect/bridge/series/divider/rail/no_connect 全數 status=ok gate=pass
三個新錯誤碼各自被觸發且回顯識別符          E_SERIES_TOO_SHORT / E_NET_NAME_COLLISION / E_RAIL_SCOPE_UNKNOWN
五個 status 值各自被 Phase 2 輸入觸發過      ok / rejected / not_run / empty / indeterminate 五值互異
verb 可達（非僅字串存在）                   NEGCTRL 回顯我送的假名，TREATMENT 經同一 dispatch 回 ok
回歸 NEW_failures_caused_by_me              [] （treatment 46 / baseline 46，集合逐字相同）
```

## 3. `render` hint 接線（DD-4，61 顆 power glyph 問題）

**前置條件（硬）**：round 1 發現的 `try_reserve` 71/71 全失敗必須先修。
理由見 `design.md` DD-4 —— `BR_20260905` §8.5.2 記載 power clustering 修法
讓 `moved` 從 10 爆到 67，而 round 1 定位到那道 anti-fusion 防護
（`_guard_route` 只對「已註冊 wire segment」防護）**其集合恆為空集**。
**在那格修好之前不要動這個 Phase。**

- [x] 3.1 確認前置：`reserve_wire_ok > 0`（round 7 treatment 量到 40，原 0/71）
      —— **但這一格不足以授權 3.2–3.4**，見下方 3.0。
- [ ] 3.0 **（round 11 新增的硬前置）** 先解 daisy_chain 的跨 net 熔接根因。
      round 11 在 scratch tree 重測（產品碼未改）：power rail 改走 drawn path 後
      `moved 0 → 20`（fused 15 / disconnected 5），歸因逐項量到
      **SIG_A 的 R1.1 R2.1 被熔進 GND**，熔接點 (161.29,96.52) / (161.29,120.65) /
      (184.15,120.65) 逐一指認為 **GND 的 pin site C2.2 / R4.2 / R3.2**。
      ⇒ 這正是 `BR_20260905` §8.5.2 的 open-circuit 缺陷，**在 wire 帳本修好之後
      仍然成立**。`_foreign_pin_points` 已在 HEAD（`kicad_emit.py:1902/1940`）
      卻沒擋住它——原因待查（本輪只量測不修）。
      **3.2/3.3 在這格綠之前不要動。**
- [ ] 3.0-obs **（round 17 觀察項，不要修）** `route_stats.wired_nets = 0` 這個
      讀數**同時代表兩件事**，而前面每一輪都拿它做判斷。
      round 16 插樁（branch entry marker + 逐個 wire/junction 產出點，
      `tracebacks=0 stderr_lines=0`）在 13 顆合成板量到：

          branch  Bmultinode = [GND, VCC]      B2pin = [SIG_A, SIG_B]
          wire    L2046 multinode drawn = 19（GND×16 + VCC×3）
                  L2249/L2273 power stub = 2
          junction L2050 multinode      = 11（全部）

      也就是 `wired_nets=0` 的同時，**L2046 真的畫了 19 條線與 11 個 junction**。
      成因：composer 的 `_build_route_stats` 按 net `kind` 歸類，power net 一律
      計入 `labelled`，與 emitter 實際畫了什麼無關。
      ⇒ **「一條都沒畫」與「畫了但按 kind 不算」共用同一個 `0`。**
      任何用 `wired_nets` 判斷「有沒有走 drawn 路徑」的推論都不成立。

      ⚠ **round 15 的 transcript 在這一格有錯，下一個人會讀到它**：round 15
      回報「21 條 wire + 11 個 junction 全部出自 power-stub 路徑」，實際是
      **19/21 出自 multinode drawn**。該錯誤結論導致當輪誤判
      `_route_clears_points` 不在畫線路徑上；round 16 的 site×branch 歸屬
      推翻它——**guard 確實在那條路上**（`kicad_emit.py:1979`，multinode 分支內）。
- [ ] 3.0-obs-b **（round 21-23 母體歸屬，不要修）** defect 1（label 貼在他 net
      線上導致跨 net 熔接）**在本 repo 的 HEAD 上不發生**。三輪量測的最終讀數：

          全套 107 次 emit 呼叫
          STATE A（pin 落他 net 線段中段 AND 該點有 junction）= 0
          STATE B（落中段、無 junction）                      = 34
            └ 22 筆 pin 不屬於任何宣告 net（另立觀察項，見下）
            └ 12 筆 pin 有 own_net —— 這 12 筆才是 defect 1 的母體

      12 筆**全量**送 KiCad netlist 仲裁（round 23，非抽樣）：
      **FUSED=0、SEPARATE=9、ABSENT=3**（ABSENT ＝ 該 foreign net 未出現在
      匯出 netlist 中，undecidable，不計為證據）。
      控制組：POS（pin 必在自己 net 內）ok=10 bad=2；NEG（不在他 net 線上的
      控制 pin 對該 net）NOT_IN=13 IN=5；parser 逐檔 `parsed_nets == raw
      '(net (code' block count` 全 True。**兩組控制組都會紅，不是恆真探針。**

      ⇒ T1/T2 的「無 junction ⇒ 不熔」在真實母體上成立（9 個獨立判決）。

      ⚠ **round 21 回報的 `B=55` 已作廢，正確值是 34。** 作廢原因是探針 bug：
      `_all_pin_points` 的 id 是 `'REF.PIN'` **字串**，而 `net.nodes` 裝的是
      `('REF','PIN')` **tuple**，歸屬判定 `_nid in own_members` **恆為 False**，
      於是每一支 pin 都被算成「不屬於任何 net」＝對每個 net 都外來。
      修正後 `ctlpins` 從 0 次非空變成 98 次非空、`own` 欄從全 `None` 變成有值。
      **下一個人若讀到 round 21 的 transcript，那裡的 55 是錯的。**

- [ ] 3.0-obs-c **（round 23 新觀察項，與 defect 1 不同病，本輪未查）**
      上面 34 筆裡有 **22 筆的 pin 不屬於任何宣告 net**。那是 **spec 完整性**
      問題（宣告漏了腳），不是「pin 落在他 net 幹線上」。兩者症狀相鄰、成因無關，
      **不要合併處理**。未量：這 22 筆是 fixture 刻意造的殘缺 spec，還是
      `declare.py` 完整性 gate 的漏網，尚未歸因。

- [ ] 3.0-obs-d **（round 21-22 自我更正，逐字保留；不是記過）**
      下一個人會拿 round 10-22 的 transcript 當依據，所以錯誤歸屬必須留在這裡：

      1. **round 11 宣稱「`_POWER_CLUSTER_MM` 從未進過版控（`git log -S` 全歷史
         空）」是錯的。** 它進過 `c3019f6`，但**只在 `.md` 裡**，從未進過 `.py`
         （`git log --all -S'_POWER_CLUSTER_MM' -- '*.py'` count=0；控制組同形狀
         打 `drawn_fragments` count=2）。當時的 pickaxe **沒有指定窗口**，於是
         「只存在於文件」與「完全不存在」共用同一個空結果。
      2. **round 11 在 scratch 建的東西不是 BR §8.5.2 的 clustering。** 它是 6 行
         env-flag early-continue（讓 power net 跳過 label 分類）。我用了 BR 裡
         那個**被否決方案**的詞去命名它，於是後續十輪的每一次引用，都在把三個
         不同的東西當成同一件：(i) BR §8.5.2 記載的 clustering（只活在 .md）、
         (ii) 這 6 行 early-continue（只活在 scratch）、(iii) repo HEAD 的實際行為。
      3. **dispatcher round 10 的裁決是對的**（「`moved=67` 是一份沒有落地的實驗的
         讀數」），錯在後續十輪沒有照它行動，繼續拿那棵樹當母體。
      4. **「第五個缺陷：功能消失且無人察覺」撤銷。** 曾懷疑的理由：BR §8.5.2
         詳述了一套 clustering 的量測數字，而 repo 裡找不到它 ⇒ 疑似功能被刪。
         撤銷的理由：那一節標題逐字寫著「**被否決的修法**」——它記錄的是一個
         寫過、量過、然後被丟棄的候選方案。**功能沒有消失，它從未存在。**
         BR 沒說謊，是我們讀成了現況。不開 BR。

- [ ] 3.2 `composer.py` 的 power net 分支讀 `render_plan`
- [ ] 3.3 `local_star` / `daisy_chain` 兩種展開的幾何實作
      —— ⚠ 這會是 `_PERPENDICULAR_OK_KINDS` / `path_clear` perp 豁免的
      **第一個非既有呼叫端**。若 hop 不經 `_guard_route`，T 接觸會漏成跨 net
      短路且無任何告警（見 `occupancy.py` `path_clear` docstring 第 3 句）。
- [ ] 3.4 真板驗收：btdongle GND `daisy_chain` 後，`#PWR` glyph 數下降、
      junction 上升，且 **fidelity `moved` 維持 10**（不得因此惡化）
      —— **狀態：`not-run`，不是 `pass`。** 本 repo **無 btdongle fixture**
      （round 11 量測：`find . -iname '*btdongle*'` → 0 命中；控制組
      `find tests -name 'test_fidelity*'` → 5 檔，證明搜尋窗口是真的）。
      `btdongle` 只以**字串**存在於 `PROVENANCE.md` / `readability_gate.py` /
      `test_consumer_fork_drift.py` 與本包四份 md。
      **判準不降級**（dispatcher round 11 裁決）：真板 fixture 的取得歸
      dispatcher（`thesmart_products` 為 GUEST repo，本包不得碰）。
- [ ] 3.4a 合成 fixture 檢查（**輔助，非驗收**）：以本 repo 內合成的 power-heavy
      spec 量 `#PWR` glyph / junction / `moved`。
      **它不是 3.4、不能替代 3.4、通過它不構成 Phase 3 的驗收。**
      理由：本 repo 三個月 40 張 BR 的形狀就是「每一格都綠、板子畫不出來」；
      把真板判準改寫成合成判準，是那個模式的下一次發作。

## 4. Consumer 遷移與收尾

- [ ] 4.1 thesmart_products btdongle 改用 `declare_circuit`（分階段，不強制一次全遷）
- [ ] 4.2 `specs/architecture.md` 同步：C03 上游新增「宣告層」
- [ ] 4.3 event log 收尾一筆
- [ ] 4.4 KB 蒸餾判定：本包的跨 repo 教訓是
      「入口缺完整性檢查時，下游每個關卡各自發明容錯，而每種容錯的失效各自成為一張 BR」
      —— 這條換 repo 換題目都成立，應蒸

## 5. 觀察項（不在本包修，但下一個人需要知道）

### 5.1 繞線拒絕是零和的，不是 router 能力不足（round 24 量測，dispatcher 裁定延後）

btdongle 真板上 `wire_reserve_rejected` 的 3 條（`ISET2` / `STAT` / `BT_LED_A`），
把它們各自移到 net list 最前面（最早繞線）：

| 實驗 | 該 net 結果 | 代價 |
|---|---|---|
| `ISET2` 提前 | **畫出來了** | `ok` 68→60、wire 116→**107**（總線數反而變少） |
| `STAT` 提前 | **畫出來了** | **`SW_NODE` 改被拒 ×2**，rejected 3→4 |
| `BT_LED_A` 提前 | **畫出來了** | **`LED_BT` 改被拒**，rejected 仍 3 |

**控制組**：整份 net list 反轉 → rejected 變成 `[ISET2, LED_BT, RUN×4]`、wire 116→124。
順序確實有作用，探針不是恆真。

> **拒絕會轉移給後到的人，不會消失。**

`fusion_jogged_nets=['ISET2']` 與此一致：jog 機制有跑、對 ISET2 生效過，最後仍撞上先佔者。

**為什麼不在本包修**（dispatcher round 25）：這把問題從「router 能力不足」改寫成
「缺全域繞線順序／重試策略」，**那是設計題不是修 bug**——需要新的判準
（什麼叫「好的順序」？最大化畫線數？最小化交叉？），現在動它會變成沒有驗收標準的重構。

**未量**：沒有搜尋「存在一個順序讓 0 條被拒」；三個實驗各只跑一種排列。

### 5.2 22 筆「pin 不屬於任何宣告 net」——不同的病，另立一格

round 22 修正後的 B=34 裡，**22 筆是「這支 pin 沒有任何宣告 net」**，
不是 defect 1（pin 落在他 net 線上）。那是 **spec 完整性問題（宣告漏了）**，
與本包的繪圖層缺陷分屬不同族。dispatcher round 23 裁定：另立觀察項，本線不查。

### 5.3 `slot_observe` 是不被消費的觀察層 → 已立 BR

`issues/BR_20260907_slot_observe_skips_reads_like_a_drawing_failure_cause_but_the_layer_is_never_consumed.md`

一句話：`slot_observe_skips` 的欄位名讀起來像「這條 net 沒被畫的原因」，
但 neuter 整層後 `WIRE_GEOM_SHA` 逐字不變——**它與畫不畫得出來無因果**。
實害已發生：值星官 round 24 派工單據此寫下錯誤因果，花了一整輪才證偽。

## 6. round 25 自我更正（給下一個人看的，不是記過）

- **round 24 我建議「兩個 anti-fusion 呼叫點都加豁免」是錯的。**
  `:1994`（bus-chain hop）開了之後造出**真的跨 net 短路**，被 `ded8b95`
  那顆 assert 當場抓住（`CROSS_NET_JUNCTION_SHORT`，GND junction 在
  `(137.16,96.52)`、`(160.02,96.52)` 落在 VDD 線上）。最終只開 `:1920`。
- **dispatcher round 21 否決 (a) 的理由只對一半。**
  「junction 在決策點不可知」在 `:1920` 成立，在 `:1994` **不成立**
  （`:2046` 無條件放 junction，hop 端點就是 chain pin，當下就可預測）。
  詳見 `design.md` §同一個豁免，兩個呼叫點。
- **`ded8b95` 那顆 assert 抓到了它的作者本人。**
  這是「先 commit 儀器、再 commit 修法」這個順序的直接證據：
  反過來就是一次靜默的跨 net 短路進 main。
