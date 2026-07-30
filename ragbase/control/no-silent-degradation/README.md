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

> **如果呼叫端只讀 `ok` 或只讀一個計數就會得出錯誤結論，這個 API 就違反本 invariant。**

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

推論：**驗證工具的輸出也是「回傳值」，同樣受本 invariant 約束。**
- 掃描/檢查類工具必須回報實際覆蓋範圍（這就是 L10 的由來——README 記 11 筆但預設只跑 5 筆 = CI 假綠）。
- 守衛測試必須有**反向鑑別力**：拿掉一個真成員，主檢查必須紅。沒有這條，一個過寬的集合或壞掉的
  AST walk 會讓主檢查永遠綠——**守衛自己就變成本 control 要修的東西**。
  `tests/test_worker_group_routing.py` 的反向測試即為此而設。

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
而不可中斷的工作**（例如剛啟動 5 秒的 `pour_planes`）。**刻意不降低門檻**：門檻越低，對正常呼叫的
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
| L1 | 19 | 19 | **T-C** | 迴圈內 `continue` 未記錄被跳過的元素 |
| L10 | — | — | **設計規則** | 掃描/檢查類工具必須回報實際覆蓋範圍（見下） |

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
