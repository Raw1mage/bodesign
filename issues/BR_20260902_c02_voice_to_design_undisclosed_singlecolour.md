# BR: `c02_voice_to_design` 是第二個 colour 入口，卻沒有揭露單色限制

Status: **FIXED** — description 已補、契約測試已擴充並通過；VANS 獨立複現六格全成立（`ses_f9f944eb7`）+ dispatcher 親驗 landed bytes 後授權 commit。
Filed: 2026-09-02
Filed-by: ses_fa07b2259ffeD5z7ypgsboPkxj（BRNS handler，葉節點實作者）
Owner: bodesign 值星官 ses_04db7a1c5ffelvbxyLP1p6xlRH
Family: `(default)` — 依 `issues/OWNERS.md`，`services/mcp/server.py` 是 **shared surface 不是 family surface**
（該檔 §「Shared surfaces」明列 `_h_*` handler 區塊「each family edits its own handlers」），
且本輪只動 tool description 字串、不動 `run_tool` dispatcher（該檔標為 shared-hotspot，動它須先 A2A 公告）。
本檔無對應具名 family，依該檔 §「Why `(default)` exists」規則 §4.3.2 路由至 `(default)`——
與上一輪 BR_20260901 的 Owner 一致（同一顆 coordinator），非新開 family。
Resolution class: **C（documented limitation）** — 與上一輪同一裁決，非新裁決。

**Related**: `issues/closed/BR_20260901_c02_render_per_part_color.md` — 依據有四，逐條可引用，非「同一主題」這種散文邊：

1. **同一條執行路徑。** `services/mcp/server.py:325-328` `_h_c02_voice_to_design` 在 `status == "approved"`
   後直接呼叫 `render_enclosure_model(...)`，也就是 `_h_c02_render_enclosure`（`:303-308`）呼叫的**同一個函式**。
   顏色在兩條路徑上都終結於同一個 `color=` 參數。
2. **同一失效類別**：「呼叫端必須燒一個 round-trip 才知道限制」。上一輪 BR `:52-54` 由外部客人（thesmart_products）
   明確提出這個成本，裁決採 C 就是為了消除它；本格未修 ⇒ 該成本在第二個入口原封不動存在。
3. **時序因果 + 明記為未關邊界。** 上一輪歸檔章節 `:178-190`「歸檔時未關的邊界」逐字寫下
   「`bodesign_c02_voice_to_design`（`services/mcp/server.py:1212-1217` 的 description）未寫單色限制」，
   並註明「本輪不處理系 dispatcher 明示裁定（範圍限於 C02 render tool description），非遺漏」。
   ⇒ 本 BR 是那筆已登記債務的兌現，不是新發現。
4. **判準可直接重用（該 BR 自己這樣寫）。** `:188-190` 明記
   `tests/test_c02_render_singlecolour_contract.py` 的 `_REQUIRED_FACTS` / `missing_facts()`
   「可直接重用於第二個工具名，不需新建判準」。本輪照做，並實測它對第二個工具的語料**有判別力**（見下）。

---

## 缺陷

`bodesign_c02_voice_to_design` 是 C02 render 的**第二個使用者可見 colour 入口**：

- schema（`server.py:1216`）就有 `color` 欄位，呼叫端看得到、給得進去。
- handler `:322-324`：`color` 未給時，會**自行**從 `plan.gen_params.cmf_color` 取色。
- handler `:325-328`：把該色傳給 `render_enclosure_model`。

但它 pre-fix 的 description（`:1213`）**整句沒有出現 colour 這個概念**。
於是從 voice loop 進來的呼叫端看不到上一輪新增的單色說明，仍可能抱持 per-part 上色的期待——
而那個期待在架構上做不到（STL 不承載顏色、`force="mesh"` 抹除 part 邊界，理由見上一輪 BR `:101-115`）。

## 量到的（動刀前重驗前提，非引述上一輪）

用**既有** predicate 對**現行磁碟上**的 description 跑一次：

```
MEASURE  voice_to_design pre-fix missing = ['stl_carries_no_colour', 'scad_colour_lost_at_export',
                                            'one_colour_whole_model', 'no_per_part_map']   ← 四項全缺
MEASURE  voice_to_design pre-fix false_claims = []                                          ← 無假宣稱
CONTROL  render pre-fix missing (必須非空)  = ['scad_colour_lost_at_export',
                                               'one_colour_whole_model', 'no_per_part_map']
CONTROL  齊備文字 missing (必須為空)        = []
```

第一格排除「限制其實已寫在別處」；第四格排除「這支 predicate 對任何文字都回非空」（否則它只是常數）。
⇒ **predicate 對第二個工具的語料確實有判別力**，不是被套上去裝飾。

## 處置（本輪 landed，未 commit）

- `services/mcp/server.py:1213` — description 補上同一組四項事實，並明寫
  「render leg 是與 `c02_render_enclosure` **相同**的引擎，繼承其限制」，
  以及本工具特有的一格：色來源是「本工具的 `color` arg，否則 plan 的 `gen_params.cmf_color`」
  （這格在 render 那則不存在，因為 render 沒有 plan）。
- `tests/test_c02_render_singlecolour_contract.py` — **不 fork 事實表**。改為
  `_COLOUR_ENTRY_POINTS` 表：`(工具名, 它自己的 pre-fix 語料)`，五項斷言全部 loop + `subTest`。
  新增 `_PRE_FIX_VOICE_TO_DESIGN_DESCRIPTION`（逐字）與一條把四項 id 釘成字面 list 的斷言。
  **理由**：兩張事實表會讓兩個入口靜默 drift，而那正是本 BR 的缺陷類別；
  一張表 + 一張入口清單，新增第三個入口只需加一行 row。

**未改**：API 行為、schema、`_resolve_cmf_color`、`_h_c02_voice_to_design` 任何一行邏輯。零新 fallback。

## 未量測的邊界（明列，不得被讀成已驗證）

1. **實際 render 出來的圖是什麼顏色，本輪一樣沒測**（與上一輪 `:152-156` 同一格）。
   本測試守的是「描述有沒有講清楚」，不是「圖是什麼顏色」。
2. **`gen_params.cmf_color` 的值域未驗證** —— 只確認 handler 會讀它，未確認它產出的字串一定被
   `_resolve_cmf_color` 接受。不在本輪範圍（不改行為）。
3. **未跑全套測試。** 跑了 `test_c02_render_singlecolour_contract`（Ran 6 OK）與
   `test_mcp_server`（Ran 49，5 項失敗，**經控制組證明為既有失敗**：把 description 換回 pre-fix 逐字
   重跑同模組，失敗集合逐字相同；探針對人造差異回 False ⇒ 比對有判別力）。
4. **未驗證 MCP server 重啟後的線上 description** —— 本 session 無 restart 權限（葉節點）。

## 一個已核實的非缺陷觀察（VANS `ses_f9f944eb7` 提出，寫下來以免下一人踩到）

`_PRE_FIX_DESCRIPTION`（render 入口的負控制語料，635 字元）**不等於** 2026-09-02 HEAD 上的 render description（1124 字元）。
這是**正確的**：render 的揭露已於 `a7a01eb` 落地，所以那個常數是 **pre-`a7a01eb` 的歷史語料**，
不是磁碟現值的快照。對照之下，本輪新增的 `_PRE_FIX_VOICE_TO_DESIGN_DESCRIPTION`（587 字元）
**目前確實與 HEAD 逐字相同**（VANS 從 `git show HEAD:services/mcp/server.py` 抽 AST 比對證實）——
但那只是因為它的修正還沒 commit。**commit A 一落地，這兩個常數就會變成同一種東西：都是歷史語料。**

⚙ **因此：「負控制語料 == 磁碟現值」這條直覺在這裡不成立。**
若日後有人想把它自動化成 assertion（例如「斷言常數與 `TOOLS_BY_NAME` 現值一致」）會踩到：
那條斷言在修正落地的**那一刻就必然轉紅**，而它轉紅的理由恰好是「修正成功了」。
負控制語料的正確語意是**凍結的歷史快照**，不是磁碟的鏡像；測試檔 `:53-55` 註解已寫到這一點，
本段是它的 BR 側備份。（過去式敘述，code 再怎麼改都不會使它變假。）
