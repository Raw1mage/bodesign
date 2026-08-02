---
slug: control/no-silent-degradation
title: No Silent Degradation — 部分失敗不得讀成完全成功
layer: ragbase
type: control
confidence: verified
locator: issues/KB_20260729_silent_degradation_antipattern_invariant_and_lint.md / checkers/no_silent_degradation.py
---
# No Silent Degradation

**一個操作若只完成了它被要求的一部分，回傳的狀態必須讓呼叫端無法把它讀成「完全成功」。**

判準句（review 時問這一句就夠）：

> **若呼叫端只讀 `ok` 或只讀一個計數就會得出錯誤結論，這個 API 就違反本 invariant。**

`no-silent-fallback` 管的是「缺輸入時不要猜」；本 control 管的是「處理過程掉東西時不要裝沒事」。
兩者是同一種誠實的兩面，但**測試覆蓋率高完全擋不住後者**——2026-07-29 一輪 C04 交付連續撞出
5 個實例，全部通過了當時的全部測試，因為測試都在測 happy path 的正確性，沒有一個斷言
「當 8 顆元件掉了，回傳值必須讓呼叫端知道」。

## 具體要求

任何「輸入元素集合 → 處理 → 輸出」的操作，若集合中任一元素被跳過、丟棄、無法解析、
或以降級方式處理，則：

1. 該事實必須出現在**回傳值**（不只 log、不只 warning 字串），且
2. 必須有一個**呼叫端會檢查的欄位**因此改變（`ok:false` / `status != "ok"` /
   `dropped[]` / `unresolved[]` / `basis` 非預設值），且
3. `expected` 與 `actual` 的計數必須同時可見（讓「84 vs 92」這種落差無法被單看一個數字掩蓋）。

## 變體家族

（標題不寫數量：這張表每次長大，一個寫死的「五種」就是下一個 V4-c 手抄副本。）

| 變體 | 定義 | 實例（BR_20260729） |
|---|---|---|
| **V1 元素靜默丟棄** | 迴圈內 skip 掉無法處理的元素，計數器不涵蓋此類 | §B `net2pcb` footprint、§D `plane_layers` key |
| **V2 量測降級無標記** | 首選量測法不可用時 fallback 到語意不同的次選法，回傳不標 basis | §C `courtyard → 含絲印 bbox` |
| **V3 狀態欄位不反映降級** | 降級資訊有收集也有傳出（誠實），但 `status`/`ok` 恆為成功 | S2 `layout.py unresolved_footprints` |
| **V4 量測基準分散** | 同一物理量在多處各自實作，修正只落其中一處 | §E `_extract_part_geoms` vs `placement_preflight` |
| **V4-b 參考系不一致** | 只有一份實作，但跨模組對同一座標的**參考系**假設不同 | §F origin vs courtyard-centre |
| **V4-c 事實雙重記錄** | 同一個事實被記在**權威來源**與**手抄副本**兩處，而沒有任何機制強迫兩者一致 | §A/§I `_need_pcbnew()` vs `_EE_GROUP_TOOLS` |
| **V5 判決未帶產生它的預算** | 回傳值**完全誠實**，但它是 (標的, 呼叫端給的預算) 的函數，而讀起來像只是標的的屬性 | §J `autoroute` 不 echo `-mp` |
| **V6 判決依賴未檢驗的前提** | 判決的算式默認了一個實際可檢查的前提，而工具既不查也不說 | §K escape gate 乘 `len(signal_layers)` 卻未查 router 開不開得了 via |
| **V11 修復複製了缺陷** | 修法本身落入它要修的同一類型，於是錯誤訊息變成**無法遵從的命令** | §P `anyOf` 本身即 stringify 觸發條件 |
| **V12 呼叫端可控的靜音鈕** | 降級/豁免機制讓被檢查方能把**已觀測到**的問題宣告成不被檢查 | §Q `covers_boards` 寫窄 → `PASS blocking=0` |
| **V13 空輸入讀作通過** | 零筆輸入使閘門回報成功，且**措辭與真通過完全相同** | BR_20260731 `audit_claims([])` → `publishable:true` |

**V4/V4-b 與 V1–V3 的關鍵差異（勿混淆，修法不同）**：V1–V3 是**假綠**（靜默成功，違反天條）；
V4/V4-b 是**假紅**（gate 大聲失敗且訊息精確，*沒有*違反 no-silent-fallback，壞的是餵給它的量測）。
V1–V3 靠「加欄位讓降級可見」解；V4 靠**收斂實作到單一 helper**解；V4-b 靠**在型別/docstring 上
明確化參考系**解。把 V4 當 V2 修（加個 `basis` 欄位）不會解決任何事。

### V4-c：實作沒分散，但「事實」被抄了一份

V4 是同一物理量有兩份實作；V4-c 只有一份實作，但它的一個**屬性**被手抄到別處。
實例：「這個工具需要 pcbnew」這個事實，權威來源是函式體內的 `_need_pcbnew()` 呼叫；
`_EE_GROUP_TOOLS` 是它的手維護抄本，而 `_group_of()` 對未列名者一律回 `core`。兩者不一致時，
工具被送到一個**從來不可能執行它**的環境。

**這個漏失發生過兩次**：§A（兩個 preflight 漏列 → gate 在 facade 探一個住在 worker 的 toolchain，
`ready:false` 但 toolchain 一直都在）、§I（`clean_micro_stubs` 漏列 → 在 facade 拋
「pcbnew not importable」）。**兩次就不是「有人忘了一個名字」，是這個形狀保證還會有第三次。**

**修法：從權威來源推導，而非平行維護。** `tests/test_worker_group_routing.py` 把推導鏈寫成測試：

    eda_bridge fn 呼叫 _need_pcbnew()          （AST 掃 package）
      → 哪個 _h_* handler import 了它        （AST 掃 server.py）
        → 哪個 TOOLS entry 指向那個 handler  （AST 掃 server.py）
          → 該工具名必須在 _EE_GROUP_TOOLS

測試檔裡**一個工具名都沒寫死**，所以它自己不會 drift；新增一個 pcbnew 工具而忘了加進清單，
推導會把它點名。另有一條反向測試（拿掉一個真成員，推導**必須**報它）確保推導真的有鑑別力，
而不是因為集合過寬或 AST walk 壞掉而永遠綠。

**邊界誠實記一筆**：`_need_pcbnew()` 是 packages 內**唯一**的這類哨兵，`_ME_GROUP_TOOLS`（OpenSCAD/
pyrender/build123d）沒有等價標記，**所以這條守衛涵蓋不到 ME group**，它仍是手維護的。
測試裡有一條斷言「哨兵只有這一個」，新增哨兵時會紅，提醒把推導延伸過去——把缺口寫成
會爆的測試，而不是寫成注解。

### V5：沒人說謊、沒東西被丟，卻仍造成錯結論

V5 是本 control 的**邊境**，認真區別它與 V1–V3 很重要：沒有任何元素被丟、沒有降級、也沒有 `except`
吃錯。`unconnected: 138` 是**正確的量測**。缺陷在於它被讀成「這塊板佈不通」，而它真正的語意是
「這塊板 **在這個搜尋預算下** 佈不通」。

實例（§J）：呼叫端將 freerouting 節流到 `-mp 10`（預設 40），連續四轮拿到的低佈通率被它定性成
「freerouting 搜尋能力不足」這種**外生限制**，並寫進了交付文件。回預設重跑：74 → 81/111。

**判別句**：

> 這個數字是不是只要呼叫端沒改標的、只改了一個參數，就會變？
> 若是，而那個參數**不在回傳裏**，就是 V5。

這也讓 V2 的位置更清楚：**V2 是 V5 的特例**——差別只在「影響判決的那個輸入是誰選的」：V2（`basis`）
是**工具自己**降級時選了別的量測法；V5（`passes_limit`）是**呼叫端**選了較低的努力。兩者修法同形：
把產生判決的那個輸入寫進回傳。§C 之前呼叫端不知道 `1008.8` 是用 courtyard 還是含絲印 bbox 量的；
§J 之前呼叫端不知道 `unconnected:138` 是用幾 pass 跑出來的。

**「呼叫端自己帶的參數，它自己知道」是最常見的反駁，但經驗上站不住**：
1. 參數在上游設定、幾十分鐘後才讀結果，中間隔了 pour / DRC / 分類，**人不會把兩端連起來**；
2. 判決往下游流动時參數不跟著跑——寫進交付文件的只有 `74/111`，沒有 `-mp 10`；
3. 從一開始就帶錯的參數，呼叫端永遠不會回頭懷疑它——四轮都在改別的東西（netclass、板子尺寸、keep_rings）。

**修法的三條約束**（`autoroute_budget_report`）：
- **預算無條件 echo**（`passes_limit` / `passes_limit_default` / `throttled`）；advisory 才是有條件的那一半。
- **advisory 只在「預算被削」且「結果不利」時響。** 三種刻意的沉默：全預算仍未佈通（那是**真的**幾何/疊層
  發現，不能被一句「你是不是沒付夠錢」稀释）、已完全佈通（便宜搜尋成功就是贏）、以及 `unconnected is None`
  （**連結果都沒量到卻断言預算是原因，是傑造歸因**——同一缺陷反向）。
- **advisory 永不翻轉判決。** routing 數字本來就正確，缺的是**歸因**。

**命名上的守則**：欄位叫 `passes_limit` 而不是 `passes`。freerouting 自己的 `command_line_help` 寫的是
「Sets the **upper limit** of the number of auto-router passes」，而它把 per-pass log（jar 內
`@BatchAutorouter.autoroute_pass #`）閘在 TestLevel 後面，預設 log level 根本不印——**實際跑了幾 pass 是
拿不到的**。叫 `passes` 會被讀成「跑了 40 pass」，那是拿一個誤導數字換成另一個。
**命名必須反映你真的量到什麼，不是呼叫端希望你量到什麼。**

**機制面的暴露面不是 docstring。** 呼叫端是 MCP client，它看不到 Python docstring，只看得到 JSON
schema。所以除了回傳值之外，`passes` 的 schema `description` 必須自己把「upper limit」、「節流後
`unconnected` 同時量你的預算」講完——否則這條知識對實際的使用者不存在。

### V6：算式沒錯，但它乘了一個沒人驗過的因子

V5 是「影響判決的**輸入**沒 echo 出來」；V6 是「判決靠一個**前提**成立，而那個前提從未被檢查」。
兩者共享同一個後果（呼叫端拿到一個自信的數字卻不知道它何時失效），但修法不同：V5 把輸入寫進回傳，
V6 必須**真的去檢查那個前提**（因為它可檢查——這才是 V6 成罪的理由；不可檢查的前提只能寫進 docstring）。

實例（§K）：`bga_escape_capacity` 的 `capacity = perimeter_channels × per_gap × len(signal_layers)`。
乘 `len(signal_layers)` 默認了**router 換得了層**，而 router 換層的唯一手段是自己開一個 via。實測的真相：
Default netclass 只授權 0.6mm via，而 ball pitch 是 0.5mm——**相鄰 via 邊緣間距 −0.1mm，router 在球陣內根本
開不了孔**。所以那 4 個訊號層裡有 2 個對它不可達，`capacity=288`（167 需求的 1.7× 餘裕）是建立在
一個假前提上的安心數字。後果：B.Cu 只承載 10% segments、282 個 via 全是貫穿孔，呼叫端側則一路往
「加層、加大板、再加層」走，**從不懷疑現有資源根本沒用滿**。

**判別句**：

> 把判決的算式拆成因子，逐個問「這個因子成立需要什麼前提？我查了嗎？」
> 有任何一個因子靠未查證的前提，而那個前提**本來查得到**，就是 V6。

**一個同族的陣形：「有什麼」與「被授權做什麼」是兩件事。** `via_in_pad` 直接在 `PCB_VIA` 上寫幾何，
從不碰板檔規則；所以同一塊板上可以**存在** 168 個 0.3mm via，而 router 被**授權**的仍是 0.6mm。
呼叫端看到小 via 就以為「小 via 可用」，這是兩個不同事實被讀成一個。不是 V4-c（同一事實被抄兩份），
而是**兩個相鄰事實被混為一講**——修法是兩者同時入回傳（`router_via_mm` 與 `existing_via_mm_counts`），
且明記 `router_via_matches_existing`。

**同一條底線的下游面：產物違法要在當場說，不能等三步後由別人背黑鍋。** `via_in_pad` 打的 168 個
0.3mm/0.15mm via 低於那塊板自己的 `min_via_diameter=0.5`，每個 via 產生 3 筆 DRC finding，
**504 筆在三個步驟後的 `drc_gate` 才浮現，讀起來像「這塊板的設計規則有問題」而不是「我剛叫的 fanout 在這塊板上
非法」**——呼叫端真的就把它自我歸因成自己的板檔問題了。這不是騙人，是**把自己的副作用審計責任候給下游**。
進一步的紀律：偵測到違規也**不得自動「修好」**（不改使用者規則、也不偷改 via 尺寸）——那是 fallback；
正解是列出衝突、預告 DRC 筆數、把決定還給呼叫端。

### V7：gate 回答的不是呼叫端問的那個問題

V1–V6 都假設「gate 本身是對的，只是資訊有損」。V7 在更前面一層：**呼叫端信任一個判決在回答問題 Q，
而它的實作回答的是更窄的 Q'。** 兩者在正常情況下讀起來一樣，只在 Q\Q' 那塊差異上默默放行。

實例（BR_20260730 §1）：`check_c03` 的 docstring 自述 "C03→C04 stage-entry readiness gate"，
GUIDE 對外寫 "BOM schema/readiness/**drawability**/SSOT crosscheck"。呼叫端讀到 drawability
合理推論「可繪已驗證」。實作的 R3 只檢查 **BOM 那一列有沒有寫 symbol 來源字串**，
從不檢查那個 symbol 是否真的被畫進 schematic——`check_c03` 的簽章根本沒有 netlist 參數。
於是手改 BOM 新增 `J_MIC` / `J_LED` 兩個連接器、schematic 完全沒動，gate 照樣 PASS 放行進 C04。

**「宣稱可繪」被當成「已繪」。** 修法不是改 R3（它問的問題本身是合理的），而是**補上真正回答 Q 的
那條規則**（R5 BOM↔netlist ref 一致性），並在文件上把 Q 與 Q' 明確分開：

> R3 檢查那一列**宣稱**了 symbol 來源；R5 檢查那個 symbol **真的被畫**了。R3 單獨通過永不代表元件存在。

**判別句**：

> 讀 gate 的**名字與文件**寫下它承諾回答的問題，再讀它的**簽章**——
> 它拿得到回答那個問題所需的輸入嗎？拿不到，就是 V7。

`check_c03(bom_csv, pin_allocation_csv, frozen_pad_counts, out_dir)` 沒有 netlist 參數，
所以它**在結構上不可能**回答「BOM 每一行都畫出來了嗎」。這個判別不需要讀實作，看簽章就成立。

#### V7 的兩個衍生陣形（都在同一個 gate 裡實測到）

**(a) 零鑑別力的假紅——「我找不到要檢查的欄位」被回報成「那裡沒東西」。**
R3 的欄位別名是 `(symbol_source, symbol, sym_source, drawability)`，而每一份產品 BOM 與 c03-ee GUIDE
實際用的欄名是 `deck_status`。`_col_index` 回 `None` → `symbol_name=None` → `marker=""` →
**34 列全部 fail R3**。同型的孿生：`_load_pin_alloc_refs` 對「沒有 ref 欄」與「ref 欄是空的」都回空集合，
於是 **26 個 active 件全部**被報成 `BOM↔SSOT conflict — owner must reconcile`，讀起來像 26 件真實待裁決。

> **全紅與全綠的鑑別力相同：零。** 一個 gate 若對每一列都給同一個答案，它就沒有在檢查任何東西。
> 「我看不到」必須與「那裡沒東西」分開回報——前者是 gate 的輸入缺陷，後者是被檢物的內容缺陷，修法不同。

修法：欄位缺席時報**一筆** schema 級 finding（不冤枉 N 列）；不適用時報 `status: "not_run"` 並列出
**未被驗證**的清單（`active_parts_unverified`），而不是把「不適用」轉成 N 個 finding。

**(b) 診斷歸因錯誤——把合法慣例報成不存在的 bug。**
`_read_csv_rows` 不跳過 `#` 開頭行，而每份產品 BOM 都用 `# ==== CORE STAMP MODULE ====` 分隔模組。
28 個 banner 每一個都變成 `R1_SCHEMA: likely CSV quoting breakage`——**28 筆全是誤診，
把呼叫端指向一個不存在的 quoting bug**。

**這兩個衍生陣形合起來就是 fork 的成因。** 平台 gate 對真實 BOM 輸出 82 筆 blocking，其中 **81 筆是
gate 自身缺陷產生的噪音**（48 個 R1 + 33 個假紅 R3）。呼叫端於是手寫了一份自己的 gate——那不是紀律問題，
是**對一個不可用工具的合理反應**。V7 的完整因果鏈：

```
gate 回答錯問題 + 對真實輸入噴 81 筆假 finding
  → 呼叫端無法使用 → 手寫替代品
  → 兩份 gate 詞彙分歧（design-ready / 裸 LCSC id）
  → 對同一份檔案給相反判決，兩邊各自自洽、無人報錯   ← §D 的同型，只是升到工具層
```

**所以 V7 的修復順序有依賴方向**：先修可達性與假紅（讓工具真的能用），再談詞彙收斂。
反過來做，呼叫端會第三次 fork。

#### 一個相鄰但不同的陣形：兩邊一致地都錯

BOM 寫錯 pin 定義 → 施工者**忠實照 BOM** 施工 → netlist 與 BOM **一致地都錯**。
一致性檢查（R5）在這一刻**完全通過**，而且**原則上抓不到**——它檢查的正是「兩者是否一致」。
拿這種案例當一致性檢查的正向測試，會得到 PASS，然後那條測試就變成一個假綠斷言。

實例（BR_20260730 round=2）：`J_LED` 的 BOM 規格寫 `(R/G/B/GND)`，而 LED 是**共陽**；
pin 4 被接到 `GND`、三個陽極失去供電，**LED 永遠不亮**。而 `J_LED.4 ∈ GND` 電氣上完全合法，
**ERC/DRC 全綠**。

要抓到它必須引入**第三個來源**（此處：那個自由文字 pin 規格本身，對上 netlist 的實際極性），
且判準必須挑得住「正確答案的措辭差異」——修正後的 `(K_R/K_G/K_B/+3V3 common-anode)` 與其 net
`+3V3_PB` **字面不相等**，逐 token 精確比對會 flag 正確答案。

> **一個會 flag 正確答案的檢查，比沒有檢查更糟**——它會被關掉，連帶關掉它本來能抓的真缺陷。

正解是只認**不可能是命名風格差異**的那一類矛盾：GND ↔ power 的極性反轉（R6）。
positional 對齊（第 N 個 token = pin N）是必要假設，但 token 數與實際 pin 數不符時**報 unaligned 而非硬對**。

#### V7 的收尾：喊狼的另一半在「基準的缺口」，不在「被檢物的缺陷」

上面說「先修可達性與假紅，再談詞彙收斂」。可達性修完、假紅從 82 降到 1 之後，
**同一個 gate 又從另一個方向開始喊狼**——這次不是實作缺陷，而是**比對基準本身不完整**。

R5（BOM↔netlist）對真實多板產品輸出 11 筆 blocking，其中 **0 筆可行動**：一份產品 BOM 涵蓋 6 塊板，
而一份 `.net` 只涵蓋一張 schematic，那 5 塊外接模組板的 schematic **根本還沒開始畫**。

> **判別句**：一個 finding 被報出來之前先問——
> **「我有沒有可以拿來比對的基準？」** 沒有基準時報出的不是缺陷，是**我這邊的覆蓋缺口**。

這與 `consumer_fork_drift` 的 `forks_unassessable` 是同一條規則的兩個實例：
「**沒有屬於該函式的 sentinel** 是我的表缺口，不是對方的缺陷」＝「**沒有覆蓋該板的 netlist** 是基準缺口，
不是 BOM 的缺陷」。兩者的正解都是移進 coverage 欄位、**照實回報但不計入 finding**。

但降級規則有一個**必須擋住的自我沉默路徑**：

> **一個能讓自己閉嘴的降級規則，就是一台假綠產生器。**
> 若「未覆蓋就豁免」無條件成立，那麼**傳一份完全無關的 netlist**（解析不到任何一塊板）
> 會讓整份 BOM 全數豁免、gate 直接變綠。

所以豁免只在**至少有一塊板真的被匹配到**時才發放（`exemptions_granted`）。
這同時解決了兩個結構上完全相同的案例：單列 BOM 且該列未畫（零覆蓋 → 真缺口）
vs 6 板 BOM 有 2 板被覆蓋（→ 其餘無基準）。

**還有一個推論限度必須誠實標記。** 「這塊板有沒有被覆蓋」原本是從「有幾個 ref 解析到」**推論**的，
而那個推論**無法分辨**「沒有 netlist 覆蓋這塊板」與「有覆蓋但這塊板每一列都真的沒畫」——
**歧義存在於輸入本身，再聰明的推論都解不開，只有呼叫端知道**。正解是兩件事一起做：
給呼叫端一個 `covers_boards` 明示參數，**並且永遠回報判定基準**
（`board_coverage_basis: "declared" | "inferred_from_drawn_refs"`）——
這正是 §C `basis` 的手法：**判決要帶著產生它的量測基準**，推論出的豁免不得與宣告的豁免混為一談。

#### 同一輪的反向教訓：訊息措辭讓一個真 finding 被讀成 by-design

那 11 筆裡 coordinator 斷言「每一筆都是設計上正確不在 netlist 裡」。**其中兩筆不是。**

```
BOM U4A (nRF7002-QFAA-R)  ←→ netlist UW1 (value "nRF7002 WiFi")
BOM U4B (MDBT53-P1M)      ←→ netlist UB1 (value "MDBT53-P1M BLE")
UW1 / UB1 出現在 BOM 的筆數：0
```

那兩顆料**確實被畫了**，只是 schematic 與 BOM 對它叫什麼名字**不一致**——這是真實的文件分歧，
而 R5 的訊息寫「declared in BOM but **never drawn**」。

> **finding 是對的，措辭把讀者送去做錯的修復。** 「never drawn」指向「去把它畫出來」，
> 而正解是「去把兩份文件的命名對齊」。呼叫端讀到「沒畫」但自知那顆料畫了，
> 於是把整條 finding 歸類成 gate 誤報——**一個歸因錯誤的正確 finding，會被當成假紅丟掉**。

修法是分出獨立的 `R5_REFDES_DIVERGENCE`，並在 detail 裡指名它被畫成什麼 refdes、比對依據是什麼。
判定改用 **mpn（料號）** 而非 refdes，因為 mpn 才是跨文件識別「同一顆實體零件」的依據。

**分類順序是這裡最容易寫錯的一行**：mpn 命中是**正面證據**（這顆料存在於 schematic），
而 board 未覆蓋只是**證據不存在**。

> **正面證據必須優先於證據不存在。**

把豁免排在前面，會讓「一塊板上每個 refdes 都分歧」的情況整批消失——
那正是 CORE 的實況（`J_X1`/`J_X2`/`U4A`/`U4B` 被畫成 `JSA`/`JSB`/`UW1`/`UB1`，
於是 CORE **按 refdes 看起來完全未 capture**，事實上它被畫得很完整）。

mpn 比對必須保守，因為**假的 divergence 宣告比漏報更糟**——它告訴呼叫端某顆料存在，而它可能不存在：
mpn 長度下限（1–2 字元的 mpn 命中一切）、排除 placeholder token、由長到短試 stem
（`nRF7002-QFAA-R` 優先於家族級 `nRF7002`）、**候選 ≥2 筆時回 None 而不猜**。

### V8：呼叫端傳了一個參數，被接成另一個型別

V1–V7 都假設「參數本身抵達了，只是處理有損」。V8 在更前面一層：**參數在跨越介面時被重新編碼，
而接收端把編碼後的形狀當成一個合法值。**

實例（BR_20260730b N1）。MCP facade 的 `bodesign_compose_schematic` schema 把 `symbol_dirs`
宣告成 **`{}`（完全無型別）**，於是某些 MCP client 會把陣列序列化成文字：

```
呼叫端傳:  symbol_dirs = ["/work/experiments/symbols"]        ← JSON 陣列
composer 收到: '["/work/experiments/symbols"]'                 ← 17 字元的字串
            → isinstance(symbol_dirs, str) 為真
            → _user_dirs = [那個字串]                        ← 一個永不存在的「路徑」
            → 9 個自訂 symbol 全部載不到，KiCad stdlib 照樣載入
```

**決定性證據是同一次呼叫內的不對稱**：`spec` 宣告 `{"type": "object"}` → 真 dict 抵達、components
正確解析；`symbol_dirs` 宣告 `{}` → 被 stringify。**同一 client、同一 transport、同一 request，
宣告型別的存活、未宣告的被序列化。** 兩元素探針把機制釘死：`["/a", "/b"]` 變成一個含 JSON 文字的
「單一路徑」，而非兩條路徑。

為什麼它比一般型別錯誤難抓：

1. **殘存的部分成功掩護了它。** stdlib 元件照樣載入、`nets` 照樣算、`placed` 是正整數。
   回傳讀起來像「大致健康，只是我的自訂 symbol 有問題」。
2. **錯誤訊息把歸因指向錯的層。** 下游誠實回報
   `library 'buck_3v3.kicad_sym' not found in: ['["/work/.../symbols"]', '/usr/share/kicad/symbols']`
   ——真相（那個「路徑」是一段 JSON 文字）**已經印在畫面上**，但沒人會往「上游多編碼」讀，
   它讀起來是「被呼叫方的磁碟上沒有這個檔」。呼叫端因此花了一整輪相信自己的 symbol library 壞了。
3. **fail-loud 攔對了，卻攔在錯的層。** 同一路徑上的 `SymbolLoadError`（BR_20260723d）確實擋住了
   交付，這是正面案例——但它把**上游的型別錯誤**報成**下游的 symbol 找不到**。

> **fail-loud 只保證「不會靜默交付錯的東西」，不保證「歸因指向真正的那一層」。**
> 一個攔在下游的 loud error，會把呼叫端送去修一個沒壞的東西。

**判別句**：

> 對每一個跨介面參數問：**它的型別在介面契約上被宣告了嗎？**
> 沒宣告 → 它可能以任何形狀抵達，而你的 `isinstance` 分支會替它選一個。

修法有兩半，缺一不可：

- **接收端**（`composer.py`）：偵測「首字元是 `[` 且 JSON 解析出 list」的字串 → 拋
  `SymbolDirsEncodingError`，訊息同時帶 raw 與 decoded。**刻意不自動解碼**——自動解碼會
  無聲修好呼叫端的 bug，連帶掩蓋產生它的 schema 缺陷（那才是新增 fallback）。
- **產生端**（`server.py` schema）：宣告 `anyOf: [array<string>, string]`。
  沒有這一半，呼叫端得到 loud error 卻**仍然無法發出正確呼叫**——這是 §J 的教訓：
  **schema 是 MCP 呼叫端在呼叫當下唯一看得到的文件**，Python docstring 對它不存在。

偵測器必須窄：只認「首字元 `[`」+「JSON 合法」+「解出 list」。反向鑑別力測試鎖住四種必須放行的
輸入——真陣列、裸路徑字串、**目錄名以 `[` 開頭的真路徑**、以及 `'{"a": 1}'`（是 JSON 但不是 list，
不屬本缺陷、不得報成本缺陷）。

### V9：每一個 gate 都誠實回綠，而交付物是空的

V8 是「參數被接錯」，V9 是**輸入根本沒有內容，而所有 gate 都對「沒有內容」給出正面判決**。

實例（BR_20260730b N2）。一份沒有 `components` 的 spec 讓 compose 產出 **213 bytes、0 個 symbol**
的空白 `.kicad_sch`，然後**四個獨立的 gate 各自誠實地放行**：

| gate | 回報 | 為什麼它是對的 |
|---|---|---|
| draftsman gate | `PASS intra_overlap=0 label_overlap=0 rects=0` | 沒有東西**不可能**重疊 |
| ERC | `erc_violations=0 erc_errors=0` | 沒有東西**不可能**接錯 |
| validation | `status="validated"` | 檔案結構合法 |
| 呼叫回傳 | `ok:true placed:0 nets:0` | 沒有任何一步失敗 |

**四個綠燈，每一個都內部正確，合起來什麼都沒保證**——因為它們全部在回答「這張圖有沒有問題」，
而那張圖不存在。這與 V7 同源（gate 回答的不是你問的那個問題），但成因在**輸入的空集合**而非
gate 的實作範圍：`0 violations` 同時是「這張圖沒問題」與「沒有圖」的正確答案，**呼叫端無法從
判決本身分辨這兩者**。

觸發它的是一個合理的猜測：呼叫端傳了 `{"__spec_file__": "/work/spec.json"}`，因為 `spec` 的 schema
只寫 `{"type": "object"}`——沒有任何線索說明它要的是**內容**而非**檔案參照**。沒有 key 命中，
spec 就靜默成了一份空設計。（又是 §J：schema 是唯一的文件。）

> **判別句**：對每一個「零違規／零 finding」的判決問——
> **「被檢查的東西是不是空的？」** 空集合對幾乎所有謂詞都真，所以
> **「檢查通過」與「沒有東西可檢查」必須在回傳裡可分辨**。

修法：在**任何 gate 有機會祝福它之前**拒絕（`EmptySpecError`）。三個設計決定：

1. **錯誤訊息同時列出「收到的 key」與「compose 實際讀的 key」**——這個缺陷的本質永遠是
   key 名不匹配，把兩邊並排就在一行內回答完，而不是把呼叫端送去讀 composer 原始碼（實際發生過）。
2. **明說「為什麼你剛才看到的綠燈沒有幫上你」**。碰到這個錯誤的人剛看過 `ok:true` 與 `PASS`；
   訊息若不解釋那些綠燈，讀起來像在跟他觀察到的事實矛盾。
3. **`KNOWN_KEYS` 那份清單自帶 AST 對照測試**——它是 `spec.get(...)` 呼叫點的手抄副本，
   正是 V4-c。雙向斷言（讀了卻沒宣告 / 宣告了卻沒讀）**當場就抓到我自己漏了 `l6_avoidance`**：
   我最初盤查用的 grep pattern 寫成 `[a-z_]*`（**不含數字**），把唯一帶數字的 key 靜默漏掉。

> 這是第六次「驗證工具靜默偏窄」，而這次是**寫 KB 的人自己**在寫這一節時犯的。
> 那條測試不是形式主義——它是唯一發現這個漏抄的東西。

### V10（ops 層）：gate 把「已經死掉」讀成「正在工作」

§L 的 busy gate 上線後，實測到它自己的反向缺陷，形狀與它在防的東西對稱。

`guard_busy` 用「process 年齡 > 30s」判定忙碌。`xvfb-run` 每跑一次 freerouting 就漏一個
**defunct（zombie）** Xvfb，而 **zombie 的 `etimes` 會一直累加**：

```
bodesign-...-ee-1  BUSY  399  43495s  [Xvfb] <defunct>     ← 12 小時前就死了
bodesign-...-ee-1  BUSY  3322 40780s  [Xvfb] <defunct>
bodesign-...-ee-1  BUSY  14303 23208s [Xvfb] <defunct>
容器 CPU 0.16%，無 java、無 freerouting
```

三具 12 小時的屍體讓 gate **無限期**拒絕每一次 restart，而沒有任何運算需要保護。
zombie 已經 exit：不佔 CPU、不佔記憶體、不持有 fd，**restart 不可能摧毀一個已經死掉的 process**。

這**反轉了 gate 自己的契約**，而它的失敗模式比「不方便」嚴重得多：唯一的出路是
`BODESIGN_FORCE=1`，所以一個永久卡住的 gate **會訓練操作者反射性地繞過它**——

> **守衛的失敗模式若是「永遠拒絕」，它就在教人拆掉自己。**
> 一個會誤擋到讓人習慣性 force 的 gate，比沒有 gate 更危險：force 的那一天，
> 它剛好真的在保護一個 165 分鐘的運算。

注意這**不是**放寬 fail-safe 姿態。§L 的「UNKNOWN 一律擋」仍然成立，因為那條的依據是
**代價不對稱**（誤擋損失一次等待，誤放損失 165 分鐘運算）。而 zombie 沒有這個不對稱——
**已經沒有運算可以損失了**。fail-safe 的正確方向來自代價結構，不是「一律選擇拒絕」。

修法：

- `ps` 加 `stat` 欄，`STAT` 以 `Z` 開頭者分類為 `ZOMBIE`，**per-process 判定而非 per-container**。
- `guard_busy` 改讀 `blocking_report`（排除 ZOMBIE），`busy` 仍**顯示** ZOMBIE 列——
  **靜默過濾掉它們會隱藏 `xvfb-run` 沒有 reap 子行程這個真缺陷**。報告，但不阻擋。
- 關鍵反向鑑別力測試：**一具 zombie 旁邊坐著一個真 job 時，仍必須擋**。
  若規則寫成「有 zombie ⇒ 容器閒置」，restart 就會直接穿透一個正在跑的 165 分鐘 route。

順帶記一筆同族的 V4-c：測試 fixture 是 `ps -eo` 欄位規格的**手抄副本**。加上 `stat` 欄後，
fixture 仍是舊的 3 欄，awk 把 `etimes` 讀成 `STAT`、`args` 讀成 `etimes`，於是 6 條測試以
令人困惑的 rc 不符失敗，而不是說「你的 fixture 欄數錯了」。已加一條從腳本 regex 推導欄序的測試。

### V11：修復本身複製了它要修的缺陷（schema 的形狀改變傳輸型別）

V8 的結論是「參數沒宣告型別 → 被 stringify」，修法是宣告 `anyOf: [array, string]`。
**那個修法自己就是同一個缺陷。**

實例（BR_20260730b §P）。同一次 tool call、同一個 client、兩個陣列參數，命運相反：

| 參數 | schema | 抵達形狀 |
|---|---|---|
| `covers_boards` | `{"type":"array"}` | 真 `list` ✓ |
| `netlist_path` | `anyOf[array, string]` | `'["a.net","b.net"]'` 字串 ✗ |
| `spec` | `{"type":"object"}` | 真 `dict` ✓ |
| `symbol_dirs` | `{}` | 字串 ✗ |

四列一起讀才看得出真規律：**不是「沒宣告型別」，而是「沒宣告一個單一確定的型別」**。
`{}` 與 `anyOf` 在這條 transport 上同類。V8 只看了前兩列就下結論，樣本不足。

後果比「少修一個地方」嚴重：

> **呼叫端拿到了 loud typed error，卻無法遵從它。**
> 錯誤訊息說「pass THAT as a real array」，而它的 client 對 union 參數就是會 stringify。
> 單一值還能用裸字串繞，多值**無路可走**。

一個只能報錯、不能被遵從的 typed error，對呼叫端而言與 silent failure 的差別只在於它知道自己卡住了。
而這句警告**就寫在 V8 自己的修法里**（「沒有產生端那一半，呼叫端得到 loud error 卻仍然無法發出正確呼叫」）——
知道那句話並不阻止我實作出它描述的情境。

> **§J：schema 是呼叫端唯一看得到的文件。V11 是它的下一層：**
> **schema 的形狀會改變參數的傳輸型別，不只是描述它。**

**判別句**：

> 對每一個跨介面的 array/object 參數問：**它的 schema 是不是一個單一、確定的型別？**
> union（`anyOf`/`oneOf`）與空 schema 一樣不算宣告。

修法：**schema 比 runtime 窄，不是反過來**。宣告單一 `{"type":"array"}`，runtime 仍接受裸字串。
description 必須寫明「這裡比 runtime 窄是故意的、因為 union 發不出去」——否則下一個讀者會把它當 bug 把 union 加回來。

**守衛必須編碼 transport 事實，不是 schema 合法性**：`anyOf` 在 JSON Schema 裡完全合法，
**純靜態形狀檢查永遠抓不到 V11**。規則只能是「任何包含 array 的 union 都是缺陷」，
且從**全檔掃描**而非寫死已知的兩個參數名（寫死即 V4-c；這兩個偏差本來就是一次發現一個）。

### V12：呼叫端可控的靜音鈕（宣告的缺席蓋過觀測到的存在）

V12 是降級規則自己長出的後門：**一個為了消除噹狼而加的豁免機制，把「要不要檢查」的決定權交給了被檢查方。**

實例（BR_20260730b §Q）。round=8 為了讓多板 BOM 不永遠紅，加了 `covers_boards`
讓呼叫端宣告哪些板真的有 netlist 覆蓋。同一份 netlist、CORE 實測 `drawn=2`：

```
covers_boards 省略（inferred）    → FAIL  9 blocking
covers_boards ["PRODUCT","CORE"] → FAIL  9 blocking
covers_boards ["PRODUCT"]        → PASS  0 blocking   ← 假綠
```

它反轉了同一個函式在**下一層**已經遵守的排序規則（mpn 命中排在 board 豁免之前）：

> **正面證據優先於證據不存在。**
> `drawn > 0` 是觀測到的存在；「宣告沒覆蓋」只是證據的缺席。
> 讓後者贏，就是讓呼叫端用一個字串關掉一條規則。

而且這個靜音鈕比已知的那個更好用：round=8 已經擋住「傳無關 netlist」（`exemptions_granted=False`），
卻漏了「傳對 netlist、但把 scope 寫窄」。**堵住一個自我静音路徑不代表堵住了同類的其他路徑。**

**判別句**：

> 對每一個「降級 / 豁免 / 縮小範圍」參數問：
> **呼叫端能不能用它把一個已經被觀測到的問題變成不被檢查？**
> 能 → 它是靜音鈕，不是 scope 宣告。

修法：**宣告只能 WIDEN、永遠不能 SHRINK 到觀測以下**。

```
captured = declared | observed    # 宣告可讓零目擊的板變可評估（原本的目的）
                                  # 但不能讓已目擊的板變不可評估
```

矛盾不静默向任一邊解決，而是進 `board_coverage_conflicts` +
`board_coverage_basis="declared_with_observed_conflict"`。理由：宣告與觀測對不上，
可能是宣告過時、也可能是那些識別碼屬於別的板——**這是要人裁決的事，不是可以靜默採信任一邊的事**。

**修 V12 時自曝的子形態：同一原則只套到一半層**。第一版寫成
`observed = {b for b, v in per_board.items() if v["drawn"]}`，自己的新測試馬上紅——
真實的 CORE **四筆全是 mpn 別名命中**（`U4A→UW1`），字面 `drawn=0`，
看起來「未捕獲」實則已被完整畫了。**我在 row 層認別名為正面證據，board 層卻不認。**

> 一條原則只套在想得到的那一層，另一層就是它的反例。
> **實作一條 ordering rule 時，要問「這個判斷在幾個層級發生」。**

修正後 `per_board` 多了 `drawn_as_other_refdes`，且別名解析在**同一 pass** 完成並快取給 row 迴圈——
算兩次就是 V4-c，**而那正是 board 層與 row 層一開始會不一致的成因**。

### V13：空輸入讀作通過（一個對空輸入通過的閘，不是比較弱的閘）

V1–V3 是「處理過程掉東西但裝沒事」；V13 是更彻底的一種：**什麼都沒檢查，卿回報了檢查通過的那個詞。**

實例（BR_20260731，四個站點）：

```
audit_claims([])          → publishable:true  "All asserted specs are datasheet-grounded."
crosscheck_nets(∅, ∅)     → "matches the reference exactly (0 nets)."
build_pin_allocation([])  → 一張只有標題列的 CSV，無任何訊號
values_in_range           → true（空 matching_components）
```

這四個正是 README 宣稱 bodesign 用來「**展示**而非**宣稱**」可靠度的閘門。而最可能撞上它們的
呼叫端——**抽取器沒找到東西、netlist parse 出零筆 net**——正是它會遮蔽其失敗的那些。

**判別句**：

> 對每一個回傳裁決的函式問：
> **令它的輸入集合為空，回傳值跟「真的檢查了且全部通過」區分得出來嗎？**
> 區分不出來 → V13。

**修法：第三種狀態，不是 raise。** 同 repo 有兩個相反的正確前例，選後者：

```
solve_impedance({}, [])   → raise ValueError      # 正確，但會損失合法的「真的零筆」情境
plan_design_intent("")    → needs-clarification    # 該抄的形狀：非 true 非 false，第三態
```

四個站點分別落成 `verdict:"vacuous"` / `publishable:None` / `vacuous:True`，並在 advice 明寫
「這不是通過」與**該去查哪一步**。

**`_check_rf_reference_values` 的額外一條：不要把裁決欄位做成三態 bool。**
`values_in_range` 在 vacuous 時**整個不發**，而不是給 `None`——`None` 會被
`if check["values_in_range"]` 讀成「超出範圍」（假紅），而欄位缺席兩邊都讀不成。

#### 子形狀三種（lint 只覆蓋第一種）

| 子形狀 | 裁決怎麼來的 | lint |
|---|---|---|
| **a. 累加器導出** | 空迴圈 → 累加器保持空 → 空性當成成功（`not blocking`、`len(x)==0`） | **L9 覆蓋** |
| **b. set 運算導出** | `not missing and not extra`，兩邊都來自集合差 | 不覆蓋 |
| **c. 根本沒有裁決欄位** | 回一張空表，「空表是否代表通過」是呼叫端的語意假設 | 不覆蓋 |

**lint 規則刻意不叫「V13」，叫「accumulator-derived vacuous verdict」**（L9）——因為它只抓
得到 a。若規則名叫 V13，那麼「L9 零命中」就會被讀成「V13 已清乾淨」——**而那正是
V13 本身的形狀**（一個字對兩件事說同一句話）。名稱窄到符合實際覆蓋，零命中才不是一句謊。

recall 實測 = **2/4**（抓到 `audit_claims`、`_check_rf_reference_values`；漏掉
`crosscheck_nets` 與 `build_pin_allocation`）。這個數字寫進 lint 模組 docstring 而非只存在
某次對話裡，因為下一個看到「L9 = 0」的人必須當場讀到它涵蓋不到什麼。

#### 驗證這類缺陷時，驗證工具自己最容易變成同一個形狀

修這四個站點的過程中，**驗證手段本身四度出現「回 0 當成通過」**，四次都靠控制組擋下：

| 現象 | 不是零失敗，而是… |
|---|---|
| 全套比對 baseline 回 `failing_names=0` 且 exit=1 | `unittest discover` 因 `tests/` 無 `__init__.py` **根本沒啟動** |
| lint 探針對修前/修後都回 0 | 探針只認 `ast.Assign`，而站點用 `ast.AnnAssign`（`x: list[dict] = []`） |
| 控制組只命中 1 筆（應為 2） | 拿 `HEAD^` 當修前版，但修復 commit 上面已經又疊了一個 commit |
| 單類測試回 `errors=1` | 類名打錯（`L6GetWithoutElse` vs `L6SilentKeyLookup`），與真失敗共用同一輸出 |

**這張表自己就是證據**：在修一個「空輸入讀作通過」的缺陷時，我自己的驗證工具四度出現
同一個形狀。可操作的結論：

> **任何「回空／exit 0 即通過」的判準，使用前先證明它在該失敗時真的會非空／非零。**
> 具體到控制組：實作一個檢測器時，**先拿已知的真缺陷餵它**；回 0 就代表檢測器壞了，
> 不代表程式干淨。這條已寫成測試：`L9AnchoredToBr20260731`，其中
> `test_the_control_group_is_genuinely_pre_fix` 是**守衛那個守衛**的（防止未來某次 rebase
> 讓控組自己包含了修復，兩條斷言變成 0 == 0 的空轉）。

### V14：探針沒壞，只是定義域比讀者以為的窄——而它不說（BR_20260802）

前面十三個變體都是**探針壞了**：R4_SSOT 零鑑別力、R3 別名不含 `deck_status`、
空輸入讀成 verified、`grep -c` 誤報。修法都是把探針修好。

V14 是第一個**探針完全正常**的變體：

```
真正的語意：  R1..R6 通過        ⇒ 「netlist 的連接性與 refdes/BOM 一致」
呈現的語意：  gate=PASS blocking=0 ⇒ 讀者理解為「這張電路圖沒問題」
```

中間那段落差從未被寫出來。實證（aiguard CCM，兩個缺陷同一塊板）：

| 缺陷 | 為什麼所有既有檢查都看不見 |
|---|---|
| `VLXSMPS`×5 + `VFBSMPS` 併進 `+1V8` | 那是一條**完全合法**的 6-pad net。ERC 沒有理由抱怨；只有知道那幾隻腳**是做什麼的**才看得出錯——而那正是 `pinfunction` 記錄的東西 |
| adjustable buck 缺前饋電容 | 它**連一條接錯的線都不是，是一顆不存在的元件**。ERC 的定義域裡沒有「應該存在但不存在的零件」這種東西 |

兩者都在 gate 全綠 + ERC 零告警下存活，最後靠人**恰好去讀了 datasheet §8.2.2.2** 才發現。
用回報者自己的話：**這不是流程，這是運氣。**

**判別句（與 V13 的空輸入判準互補）**：

> 對每一個回傳裁決的閘問：
> **它的綠，和「這件事不在我的檢查範圍內」，讀者分得出來嗎？**
> 分不出來 → V14。

#### 修法的主從關係：規則是次要的，邊界宣告才是主要的

直覺會想「那就把規則補齊」。但規則永遠追不完——電路正確性的缺陷空間是開放的，
而**「我沒檢查什麼」是封閉且今天就能窮舉的**。所以修法的主體是：

```
not_checked: [...]   恆存在、不可為空、PASS 與 FAIL 都出現
```

判準是**位置**而非內容：**讀者看到 PASS 的同一秒必須也看到它**。
寫在 GUIDE 裡不算——那是「需要時去查」，而失效那環正是「沒想到要去查」。
（同一條位置判準見 §8.1 的推論：把陷阱寫進當下會被載入的地方。）

R7/R8 兩條新規則只是**把兩個已知的洞補上**，且各自帶 `status: run|not_run`：

- **R7** datasheet-mandated passive 存在性——查不到的料號一律進 `parts_not_covered`
  **列名**，絕不因為表裡沒有就回綠（那是 R4_SSOT 零鑑別力的重演）
- **R8** 開關/回授節點不得坐在 power rail——沒有 `pinfunction` 標註時回 `not_run`，
  因為那時它**根本無法辨識**哪隻腳是開關節點，回「run, clean」就是本變體的自我複製

#### 每條規則必須帶 mutation proof

一條**永遠回綠的規則和沒有規則是同一件事**，而兩者在 CI 上長得一模一樣。
所以 R7/R8 的測試各有一組成對 fixture，唯一差異就是那顆電容 / 那條 net 的名字：

```
缺 C_FF → FAIL(R7)     補上 C_FF → PASS      ← 差異僅此一顆零件
SW 在 +1V8 → FAIL(R8)  SW 獨立 net → PASS    ← 差異僅此一個 net 名
```

**沒有這組配對，一條卡死的紅或永遠的綠都無法察覺。**

#### 反向：規則不得誤傷正確的工作

`_fn_matches` 刻意用**精確 token 比對**而非子字串：`VSW_SENSE` 含有 `sw`，
子字串規則會 flag 它。這與 R6 拒絕逐 token 比對是同一個判斷——
**一個會 flag 正確答案的檢查，比沒有檢查更糟**，因為它教會讀者忽略這條規則。

## 正確樣態（positive pattern，KB 只有反例不夠）

- **`plane_layers_applied: [{spec, layer, net, type}]`**（`routing.py net2pcb_board`）——
  呼叫端傳入的每一個元素，回傳裡都有一筆說明它的**實際去向**。這是要求 2 的教科書實作。
- **`basis: "courtyard" | "bbox_no_text" | "mixed"` + `courtyard_missing: [refs]`**
  （`routing.py placement_preflight`）——量測降級時，判決的基準本身是回傳的一部分。
- **`implausible_measurement`**（同上）——物理量超出定義域（占用率 > 1.0 = 元件面積大於板面積）
  時回 `passed:false` 並在 reason 明說此判決 **UNUSABLE**，而不是給一個自信的 `false`
  害呼叫端去「修」一塊從未被正確量測的板。這是 V2 的通用防線：即使降級邏輯沒被 lint 抓到，
  荒謬的結果會自己爆掉。
- **`PartGeom` 的 REFERENCE FRAME docstring**（`preplace.py`）——明寫 placement entry 是
  ORIGIN（因為那是 `pcbnew.SetPosition()` 寫的）、`pads` 從 origin 量、`anchor_dx_mm` 是
  courtyard-centre 減 origin 且為 part-local 未旋轉座標。V4-b 的正解是讓參考系**無法被誤會**，
  不是讓每個 caller 自己猜對。
- **`unconnected` + `complete: (unconnected == 0) if unconnected is not None else None`**
  （`routing.py autoroute`，BR_20260708）——routing 只完成 22/111 個網路時，回傳**沒有**把它
  報成成功；`complete` 的三態（True/False/None）還把「無法判定」與「判定為失敗」分開，
  不用 `False` 冒充「我不知道」。
- **`vias_per_ref: {ref: n}` + `refs_requested`**（`routing.py via_in_pad`，§G）——呼叫端點名的
  每一個 ref 都能被稽核：一個成功解析卻貢獻 0 個 via 的 ref（全部球都在 keep_rings 內、或沒接網路）
  在這裡是可見的，而不是被平均進一個看似合理的 `vias_added` 總數。
- **`advisories: [surface_escape_infeasible: …]`**（`routing.py bga_escape_capacity`，round=12）——
  **「資訊有給」與「資訊有用」是兩件事。** `traces_per_gap_computed: 0` 從第一版就在回傳裡，
  形式上完全合規；但它要求讀者自己重做 `n*w+(n+1)*c <= gap` 的算術才知道「表面逃逸在這個線寬下
  物理上不可能」。一個呼叫端因此用錯 `keep_rings`，花了 50 分鐘 routing 才回頭讀懂那個 0。
  修法是把**算術的結論**也講出來（需要 0.416mm、gap 只有 0.22mm、所以容量用的是樂觀 floor），
  而不是只給原始數字。**invariant 說呼叫端必須能稽核，而能稽核的前提是看得懂。**
  兩個配套約束：(a) advisory **永不翻轉 `blocking`**——樂觀 floor 正是讓這個 gate 不誤擋 fab
  天天在做的 fine-pitch 板的設計；(b) 措辭**不得指定動作**（用「only viable if the inner layers
  have the capacity」條件句，不寫 `keep_rings=1`），因為這個 gate 不評估內層容量，讀起來像
  指令就會把一個未評估的假設變成建議。有測試分別鎖這兩點。
- **`_load_board()` 這個 helper 本身**（`routing.py`，§H）——`pcbnew.LoadBoard()` 對不存在的路徑
  **回 `None` 而不 raise**，下游任何 pcbnew 呼叫拿到 null `BOARD*` 就 **SIGSEGV（exit 139）**，
  呼叫端只看到連線斷、連 Python 例外都沒有。正解是把「唯一開板方式」收斂成一個會 fail-loud 的
  helper（`BOARD_NOT_FOUND` 帶 resolved 絕對路徑 + worker cwd，因為觸發條件通常是呼叫端傳了
  相對於**自己** cwd 的路徑），並用一條 **AST 守衛測試**斷言模組內沒有任何 call site 繞過它。
  這是 V4（量測基準分散）的解法用在**資源取得**上：SSOT + 機械化防復發，而不是靠每個新 call site
  的作者記得檢查 `None`。
- **`removed_stubs: [{net, len_mm}]` 而非只回 `removed: 17`**（`routing.py clean_micro_stubs`）——
  破壞性操作（刪東西）尤其不能只回計數。逐筆列出後，呼叫端一眼看出 17 筆裡混了兩類：
  `0.00014mm` 那幾筆是 SES import 的浮點殘渣、`0.0198mm` 那幾筆才是真 stub。**這個區分只有
  逐筆列出才看得見**；一個 `removed:17` 在兩種情況下長得一模一樣——刪對了、以及刪掉了不該刪的。

## 這條 invariant 一樣適用於「驗證工具」本身

**同一輪裡，platform 與 consumer 兩側各自被自己的驗證工具騙了一次**（BR_20260729 round=14/16），
兩個獨立事件、同一個形狀：

| | 工具 | 壞掉時的表現 |
|---|---|---|
| platform | 驗證腳本把 `docker cp` 的 stderr 導進 `/dev/null` | 容器 restart 後測試檔根本沒複製進去，卻報成「4 errors」——一個看起來像**測試失敗**的訊號，實際是**測試沒跑** |
| consumer | 核 §I 用的 grep parse 寫壞 | 吐出「13 個工具全部不在 EE group」，含 `bodesign__load_board` 這種不存在的名字——一個看起來合理的清單 |

consumer 抓到自己的錯，靠的是「這與我剛才實測成功的 `route_net2pcb` 矛盾」，**不是靠檢索本身有防呆**。
若當時沒有那個矛盾，它會拿著壞掉的檢索去指控工具。

### 偏窄會漏拓，偏寬會驅使你修改沒壞的東西（BR_20260730b 收尾）

前面所有實例都是驗證工具**靜默偏窄**（漏抓）。同一條 invariant 還有另一個方向，而它更隱蔽：

我一路用來檔住簡體/日文漢字混入的字集模式是 `[却実験如结构对齐问题]`——
而 **`如` 是正體中文完全合法的字**（`如果`、`例如`），不是簡體、也不是日文新字體。它混在一串
真違規字中間，而檢查器只回一個計數（`grep -c`），於是「2 筆命中」看起來完全可信。

後果不是「白忙一場」而是**它驅使我去改一個沒壞的東西**：我把 KB 兩句話重寫成
`如果`→`若`、`例如`→`以…為例`，只為了讓一個壞掉的檢查器閉嘴。

> **偏窄的驗證工具讓你漏掉真缺陷；偏寬的讓你修改本來正確的程式碼與文字。**
> 後者更隱蔽，因為它產生的是「我修好了一個問題」的成就感，而不是一個空白結果帶來的怀疑。

這也是 `§Q`/`F4 sentinel`/`R5 反向檢查` 一路在說的 cry-wolf，只是發生在**我自己的工具鏈上**：
一個會誤報的檢查器，會讓使用者把正確的東西改成符合它的形狀。

修正後的模式（移除 `如`）：`[却実験结构对齐问题]`。
**且檢查器不得只回計數**——`grep -n` 列出命中行才能讓人當場看出「這個字根本沒問題」，
而 `-c` 把判斷所需的證據死在工具裡（這本身就是要求 2：判決必須帶著產生它的證據）。

推論：**驗證工具的輸出也是「回傳值」，同樣受本 invariant 約束。**
- 掃描/檢查類工具必須回報實際覆蓋範圍（這就是 L10 的由來——README 記 11 筆但預設只跑 5 筆 = CI 假綠）。
- 守衛測試必須有**反向鑑別力**：拿掉一個真成員，主檢查必須紅。沒有這條，一個過寬的集合或壞掉的
  AST walk 會讓主檢查永遠綠——**守衛自己就變成本 control 要修的東西**。
  `tests/test_worker_group_routing.py` 的反向測試即為此而設。

### 偏窄與偏寬的共同上游：用單向的工具去量一個雙向的判決

上面兩個方向（漏抓 / 誤抓）不是兩個問題，是同一個問題的兩面。consumer 在同一輪回報了一個
**形狀完全一致但發生在 git 上**的獨立實例，並排放在這裡：

它 commit 時誤刪了 11 個磁碟上仍然存在的檔案（根因是 FUSE stat-cache 報假 `deleted`），
而它自驗那次 commit 時**只數了新增行數、沒看 `D` 那半邊**。那次自驗回給它的是
「+10029 行，內容都對」——一個看起來非常紮實的結果，而它系統性地只看了單一方向。

| | 判決是雙向的 | 工具只量了一向 | 於是 |
|---|---|---|---|
| 我的字集檢查器 | 哪些字命中、命中在哪 | `grep -c` 只回計數 | 「2 筆」看起來可信，我改了沒壞的文字 |
| consumer 的 commit 自驗 | 新增了什麼 / 刪除了什麼 | 只看 `A` 半邊 | 「+10029 行」看起來紮實，11 個誤刪過關 |

> **兩者都不是懶惰**——都是把一個雙向的判決，用一個單向的工具去量。
> 而單向工具的輸出永遠是「乾淨的一半」，它不會告訴你另一半沒被看。

所以修法是同一條規則的兩個實例：`grep -c` → `grep -n`（列出證據行）、
`git diff --stat` → `git diff --name-status`（兩個方向都列）。

**推廣到任何驗證動作**：動手前先問「這個判決有幾個方向？我的工具量到了幾個？」
差額不是零時，那個差額就是你將要靜默通過的東西。

## 這條 invariant 一樣適用於「維運指令」本身（§L）

**成功訊息報的是指令的*意圖*，不是它的*後果*。** `mcpctl.sh restart` 重建容器，然後印
`bodesign MCP restarted; socket -> ...`——這句話在兩種情況下**長得一模一樣**：容器本來就閒著、
以及容器裡正跑著一個 165 分鐘的 freerouting 而它剛被殺掉。實際發生的是後者，兩次
（BR_20260729 round=22，consumer 側的 routing 被腰斬 13:11 / 13:33，`exit=0` 非崩潰）。

這與 V1 同構，只是換了層：**被丟棄的元素不在一個 list 裡，而在一個容器裡**；`removed:17` 的位置
站著 `restarted`。判別句照樣成立——呼叫端只讀那句成功訊息，就會把「我摧毀了別人的運算」讀成「重啟完成」。

**為什麼修法不能是約定。** 自然的回應是「restart 前先問一聲」。但那把守衛託付給**人的記憶**，
而記憶會蒸發（code-thinker §7 的同一條）。共用一個 worker 的兩方之中，只要有一方某次忘了，
損失照樣發生，而且**恰好發生在最忙、最容易忘的時候**。所以 gate 必須在指令自己身上：

- `restart` / `rebuild` / `stop` 動手前探測容器內的長跑 process，**列出它將殺掉什麼**並 exit 3；
- `BODESIGN_FORCE=1` 可覆寫，但**仍然把犧牲品名字印出來**（覆寫不等於閉嘴）；
- 新增 `mcpctl.sh busy` 子命令，讓共用 worker 的另一方能**無副作用地**問「現在動安全嗎」。

**這裡最容易寫錯的一行，正是本 control 本身：**

> `docker exec <c> ps` 失敗時，回傳空清單 ≡「沒有 process 在跑」≡ 放行。

**「我看不到」不是「那裡沒東西」。** 探測失敗必須回報 `UNKNOWN` 並**同樣擋下**——這是 L2 在 ops 層的
實例（`except` 吞掉失敗後回一個看似正常的值）。若寫成放行，則每次探測故障都變成一張摧毀運算的通行證，
而且**故障與閒置在輸出上無法區分**，正是這條 invariant 禁止的事。對應測試
`tests/test_mcpctl_busy_gate.py::test_an_unprobeable_container_blocks_rather_than_reads_as_idle`。

**門檻本身是取捨，而取捨值必須在回傳裡可見。** busy gate 用 30 秒界定「長跑」，所以它**擋不住短命
而不可中斷的工作**（以剛啟動 5 秒的 `pour_planes` 為例）。**刻意不降低門檻**：門檻越低，對正常呼叫的
誤擋越多，而誤擋一個進行中的互動式工作階段比偶爾殺掉一個 5 秒運算更糟。這是取捨，不是疏漏——
但因此 `BUSY 402 1282s` **必須帶著秒數**，呼叫端才能自己判斷 30 秒門檻對它的工作夠不夠用，
而不是拿到一個不帶依據的 busy/idle 布林。**任何門檻型判決都適用這條：門檻值本身就是 V5 說的
「產生判決的預算」。**

**反向鑑別力同樣不可省**：只測「忙碌時會拒絕」的話，一個無條件拒絕的 gate 會全綠並讓工具不可用。
必須同時鎖住「閒置放行」「pid 1 的 server 自己不算 work」「未達門檻的短命 process 不擋」
「容器已停止 = 真的閒置」。另有一條測試在**接線層**把關：任何會 `--force-recreate` 或 `down` 的
case arm 都必須呼叫 `guard_busy`，且該檢查自帶「拿掉一個 guard 必須被點名」的反向測試——
否則 parser 靜默匹配不到任何東西時，它會永遠綠。

## §G：裸崩不是 silent degradation，但同樣讓呼叫端拿不到可行動資訊

§G（`via_in_pad` 對 castellated/LGA 模組的數字 pad 名拋 `max() iterable argument is empty`）
**不是**本 control 的變體：它沒有騙人，它大聲失敗了。但它與 V1–V3 共有同一個**後果**——
呼叫端拿不到可行動資訊（訊息未指出哪個 ref、哪個欄位、該怎麼修）。定性為 **L2 的反面案例**：

> `except` 吞掉失敗是一種病；**完全不 guard、讓底層 API 的裸錯冒到呼叫端**是它的鏡像。
> 兩者都讓呼叫端無法行動。修法對稱：前者要「把吞掉的講出來」，後者要「把底層錯誤翻譯成
> 領域錯誤」（哪個輸入、為什麼不適用、該怎麼辦）。

§G 修復時另外挖出兩個**真** V1（都已一併修）：(a) `refs` 中不在板上的 ref 原本靜默 no-op；
(b) **混合命名**（部分 `A1`、部分 `1`）原本不崩，但每個非網格 pad 都繞過 `keep_rings` 保護
被塞 via——`cols` 非空所以沒人發現，呼叫端只看到一個合理的 `vias_added`。**裸崩其實是在
遮蔽一個更糟的靜默缺陷**：只有「全部 pad 都非網格」才崩，混合命名反而安靜地毀掉板邊 pad。

## 可執行的閘

`packages/workflow-core/bodesign_workflow_core/checkers/no_silent_degradation.py`。
tier **由實測訊噪比決定**（對 §B–§F 修復前後的 `routing.py` 各掃一次，看是否「修前命中、修後歸零」）：

| 規則 | 修前 | 修後 | tier | 內容 |
|---|---|---|---|---|
| L2 | 2 | 0 | **T-A** | `except` 只有 pass/log 而函式有回傳值 |
| L6 | 1 | 0 | **T-A** | 呼叫端傳入的 key 查找失敗即靜默跳過（§D 直接規則） |
| L8 | 1 | 0 | **T-A** | 同一量測 API 在 >1 個函式各自實作（§E 直接規則） |
| L9 | 2 | 0 | **T-A** | 累加器導出的裁決，無零長度 guard（V13 子形狀 a，見上） |
| L1 | 19 | 19 | **T-C** | 迴圈內 `continue` 未記錄被跳過的元素 |
| L10 | — | — | **設計規則** | 掃描/檢查類工具必須回報實際覆蓋範圍（見下） |

**L9 不降 advisory 的理由**：實測誤報 0（`packages/` 0、`services/` 0、`skills/` 0），
修前 2 筆命中全是真缺陷。L1 降 T-C 是因為 19/19 全是雜訊；把一個零雜訊偵測器標成
advisory（預設不輸出）等於把它丟掉。證據強度與 L6/L8（各 1 筆修前命中）同級。

**L1 誠實降為 advisory**（預設不輸出）：它修復前後都報 19 筆，命中的是 regex 不匹配、
keep-ring 篩選這類**正常 filter 語意**——那些 `continue` 不是在丟棄呼叫端交付的元素，
而是在表達「這一項本來就不該處理」。AST 分不出「篩掉」與「丟掉」，硬當 T-A 會讓 19 筆雜訊
淹掉 3 筆真訊號，最後沒人跑這條 lint。

**誠實未實作**（不假裝覆蓋）：L3（expected vs actual 計數，需回傳 schema 對照）、
L4（primary/fallback 標記，需語意判斷）、L5（荒謬值 tripwire——**runtime domain 檢查，
靜態不可判**，它是設計規則不是 lint，見上方 `implausible_measurement`）、L7（key 正規化，advisory）。

## L10：掃描/檢查類工具必須回報實際覆蓋範圍

> 一個只回 findings 的 checker，**本身就是它所執行的反模式**：回報「0 findings」時，
> 呼叫端無法區分**真的乾淨**與**根本沒掃到那裡**。掃描範圍必須是回傳值的一部分。

這不是假設性風險，而是**本 checker 自己犯過的錯**：它的 `__main__` default roots 曾只有
`[packages/eda-bridge, packages/workflow-core]`，漏掃 `services/`——文件記載基線 11 筆，
預設指令印出 5 筆，**CI 若照預設跑會在從未被檢查的 code 上拿到假綠**。

實作（checker 自己先合規）：`check_paths(..., with_coverage=True)` 回 `Coverage`，
`__main__` 無條件印在 finding 數旁邊：

- `roots` / `files_scanned` / `files_skipped`——這個數字是由哪些檔支撐的
- `missing_roots`——**不存在的 root 是覆蓋缺口，不是空結果**（打錯的路徑否則會以「0 findings」冒充乾淨）
- `unparsable`——parse 不了的檔**不計入 `files_scanned`**：把規則從未真正跑過的檔算進已掃描數，
  正是這個 coverage 要阻止的不誠實
- 有缺口時 `exit 2`，CI 不會把「沒掃到」當成通過

一個順帶的發現：實作時我先寫了 `except SyntaxError` 來採集 `unparsable`，測試才曝出
`check_file` **從不拋** SyntaxError——它回一筆 `L0` finding 繼續（那才是對的：讀不了的檔
是 findings 不是 skip）。我那個 `except` 是**永不觸發的死碼**，已改成從 L0 finding 推導。
這條規則對**未來所有 checker** 適用，不只這一個。

**為何不進 `checkers/registry.py`**：那張表的每一列是「control → **design-IR** checker」
（`ir_fields` 是 IR 路徑、`stage` 是 C00–C04 管線階段、evidence 走 `ORACLE_TOOLS` envelope）。
本 control 檢的是 **Python 原始碼**，沒有 IR 輸入、不屬於任何管線階段、不產生板級 evidence。
硬註冊會逼我們在 `ir_fields` 填假路徑——那正是本 control 自己禁止的捏造。它改由 CI /
開發期直接呼叫（`python3 -m ...no_silent_degradation packages services/mcp`）。

## 全 repo 基線（2026-07-29，T-A）

11 筆真陽性：`L2`×8（`c01_id_package._emit_doc_pdf`、`c02_me_package._parse_connector_answer`、
`guide_dod.assess_guide_dod`、`mcp_delegate.resolve_mcp_server`、`server._h_kb_get`、
`server._produced_meta`、`token_store._reap_ephemeral`、`token_store.resolve`）、
`L6`×3（`spice_card._select_value`、`kicad_emit.emit_kicad_schematic`、`l4_check.check`）。
未修，登記為已知基線。

**這個數字必須由無參數的預設指令重現**（`python3 .../no_silent_degradation.py`）。§G 時發現
`__main__` 的 default roots 只有 `[packages/eda-bridge, packages/workflow-core]`，漏掃 `services/`
少報 6 筆——文件寫 11、預設跑出 5，CI 若照預設跑會拿到假綠。已改為 `[packages, services]`。
**一條 lint 的預設掃描範圍自己就是一個「回傳值是否反映實際做了什麼」問題**：它回報「0 findings」
時，呼叫端無法區分「真的干淨」與「沒掃到那裡」。

## Source evidence

- `distilled_from` → `issues/KB_20260729_silent_degradation_antipattern_invariant_and_lint.md`
  （aiguard C04 consumer 提案，四實例全帶實測數據）
- `distilled_from` → BR_20260729 五實例：commit `1269a20`（§B）、`cdbcb02`（§C/§D/S2）、
  `f958e68`（§E）、`a25d898`（§F）

## Related

- ← `refines` [[control/no-silent-fallback|No Silent Fallback]]（缺輸入不猜 ⊥ 掉東西不裝沒事）
- → `constrains` [[workflow/c04-layout|C04 Layout — placement → routing → fab outputs]]
- ← `references` [[concept/impl-evidence-gaps|Evidence-Linked Knowledge, Explicit Gaps]]
