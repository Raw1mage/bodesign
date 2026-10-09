# BR_20260901c — verb 層無法「給定 id 取回 `body_md`」：48 個 verb 裡沒有 `ragbase_get`

- **Status**: OPEN
**Severity**: MEDIUM (capability gap — 迫使每個做蒸餾的 agent 各自發明 `sqlite3` 直讀，繞過工具層)
**Family**: tool-layer-capability-gap / recall-before-write-is-mandated-but-unsupported
**Filed**: 2026-09-01 by ses_fa73bab76ffeM0Dhhz9pK0Xln2 (bodesign BRNS leaf handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`)
**Owning repo**: **`~/projects/specbase`**（verb 註冊與 runner 實作在那裡）
**Discovered by**: `~/projects/bodesign`（**發現者兼 guest**）
**Originally hit by**: handler `ses_fa746a21d`（做 recall-before-crawl 時撞到）

**Related**: `code-thinker` §10 Failmode KB 的 recall 紀律（「**寫指令前先查**，踩到新坑就寫回去」）
＋ `plan-builder` Working-KB 迴圈 Stage 2 的 **recall-before-crawl**（「先 `ragbase_query`
scope=repo，只 crawl delta」）——**同一條執行路徑**：兩份規約都要求 agent 在寫入前**讀既有條目全文**
以判斷「這是擴充還是新增」，而本 BR 指出**該路徑上缺一個 verb**，規約要求的動作在工具層做不到。
同批建檔的鄰居：`BR_20260901b`（同一次蒸餾工作、同一個 runner 家族撞出的另一個缺陷；
**不同 family**——那則是參數被吃掉，本則是能力根本不存在）。

---

## 1. 一句話

`ragbase_query` 只吃 `q / limit / scope / repo`——**只能關鍵字搜**。
給定一個**已知的 object id**，48 個 runner verb 裡**沒有任何一個**能回傳它的 `body_md` 全文。

## 2. 重現：全 verb 列舉（本輪實跑，2026-09-01）

### 2.1 方法（含一次**自我修正**，這一段本身就是證據）

**第一版方法（錯的，但錯得有價值）**：對三個 runner 各跑 `--help`，`grep -i 'verbs\?:'`
抓那一行。結果：

```
control_ragbase_query=0          ← 已知存在的 verb 竟然沒被找到
control_ragbase_record_extract=1
TARGET_ragbase_get=0
```

**正向控制組當場否決了這個方法**：`ragbase_query` 確定存在（我上一格才用過它的家族），
卻回 0。原因是 `gate.ts --help` **不印 `Verbs:` 這個字串**，它用的是散文式清單
（`Accepts (a) every READ-ONLY verb …`）。若沒有這格控制組，我會拿著
「`ragbase_get` 找不到」這個**看起來完全正常的 0**去下結論——而那個 0 當時只證明
**我的列舉方法沒跑到 gate.ts**。

> 這正是派工單第 ① 條硬判準所防的東西：**回空不得單獨作為結論依據**。
> 記錄在此，因為「控制組真的擋下了一次錯誤結論」比控制組本身更值得留檔。

**第二版方法（採用）**：捕捉三個 runner 的**完整** `--help` 輸出，合併後用
`grep -oE '\b(ragbase|wiki|event|spec|plan)_[a-z_]+'` 抽 token 去重。

```
producer_help_rc=2  gate_help_rc=2  lifecycle_help_rc=2      (--help 走 usage 路徑，rc=2 為正常)
TOTAL_DISTINCT_VERBS=48
```

### 2.2 完整 48 verb 清單（本輪實測輸出）

```
event_query                  ragbase_emit_view            spec_add_code_anchor
event_record                 ragbase_gaps                 spec_amend
event_search                 ragbase_ingest_source        spec_record_decision
plan_check                   ragbase_link                 spec_record_event
plan_closeout                ragbase_link_batch           spec_record_handoff
plan_graduate                ragbase_project_issues       spec_sync
ragbase_br_diff              ragbase_promote              spec_tick_task
ragbase_closeout_check       ragbase_publish_skill        spec_translate
ragbase_confirm_coordinates  ragbase_query                wiki_get
ragbase_context              ragbase_query_lineage        wiki_graph
ragbase_detect_stale         ragbase_record_extract       wiki_list
ragbase_distill              ragbase_register_asset       wiki_query
ragbase_distill_batch        ragbase_rescope              wiki_rebuild_index
ragbase_emit_all             ragbase_rewrite_entry_bodies wiki_search
ragbase_emit_grafcet         ragbase_validate             wiki_validate
ragbase_emit_idef            ragbase_emit_refresh         ragbase_emit_skill
```
（`ragbase_emit_idef` 為 token 抽取結果，原文是 `ragbase_emit_idef0`——數字被 `[a-z_]+`
截斷。**據實記錄此一已知的抽取瑕疵**；它不影響本 BR 的結論，因為它只影響**已存在** verb 的
名稱完整度，不會讓一個存在的 `get` 類 verb 消失。）

### 2.3 控制組（判別力驗證）

**正向控制** — 已知存在的 verb 必須被這個方法找到：

| verb | 命中數 |
| --- | --- |
| `ragbase_query` | **1** ✅（第一版方法給 0，第二版修正） |
| `ragbase_record_extract` | **1** ✅ |
| `wiki_get` | **1** ✅ |
| `ragbase_context` | **1** ✅ |

**反向控制** — 目標與捏造名稱皆須為 0（證明這支 grep 不是恆真）：

| 查詢 | 命中數 |
| --- | --- |
| `ragbase_get` | **0** ← 目標 |
| `ragbase_fetch` | 0 |
| `ragbase_read` | 0 |
| `ragbase_show` | 0 |
| `zzqq_nonexistent_verb` | 0（純粹捏造，作為 grep 未壞掉的證明） |

> 正向 4/4 命中 + 反向 5/5 為 0 ⇒ **這個 0 是「不存在」，不是「沒查到」**。

## 3. 為什麼現有的替代品都不是替代品

| 候選 | 為什麼不行 |
| --- | --- |
| `ragbase_query` | inputSchema 只有 `q/limit/scope/repo`。**關鍵字搜 ≠ id 取值**：搜得到不代表拿得到全文，且無法保證命中的就是你手上那個 id |
| `wiki_get` | **不同命名空間**。wiki entry ≠ ragbase object；它取不到 ragbase 的 `body_md` |
| `ragbase_context` | 是情境投影，不是 by-id 取回 |
| `ragbase_query_lineage` | 回的是血緣關係，不是 body |
| `ragbase_emit_*` | 是 SSOT→artifact 的**投影**，輸出是整份視圖不是單一物件全文 |
| `--json '{"id":…}'` 硬塞給 query | 被 arg 契約擋下 —— **fail-loud，這是好的，不是缺陷**。這裡明確記下來，免得未來讀者把它誤讀成第二個缺陷 |

## 4. 代價（已實際發生，不是假設）

`code-thinker` §10 與 `plan-builder` Stage 2 都把「先查再寫、讀既有條目全文判斷擴充 vs 新增」
訂為**紀律**。verb 層做不到，於是每個做蒸餾的 agent 各自發明一套
`sqlite3 -readonly …` 直讀 `.specbase/ragbase.sqlite`。後果：

1. **繞過工具層**——直讀路徑沒有任何契約保證，schema 一改就靜默壞掉（且是**讀**壞掉：
   拿到空結果，而空結果與「這條知識不存在」不可區分 ⇒ **會直接製造重複條目**）；
2. **各寫各的**——每個 agent 的 SQL 不同，取到的欄位範圍不同，沒有一致的「全文」定義；
3. **紀律與能力脫節**——規約要求的動作在工具層不存在，於是紀律的遵守率取決於
   agent 願不願意手刻 SQL，而不取決於它是否想遵守。

> 這也是為什麼本 BR 的 severity 不是 LOW：它讓**另外兩份規約**在執行面失效。

## 5. 建議修法（給 specbase owner，我們是 guest 不動手）

新增一個 read-only verb（歸 `gate.ts`，因 `mutates !== true`），形狀對齊既有 `wiki_get`：

```
ragbase_get --repo <abs> --arg id=<object_id>
  → { ok:true, data:{ id, type, title, body_md, confidence, scope, … } }
  → id 不存在時 { ok:false, error:"not_found", detail:{ id } }   ← 必須 fail-loud
```

**最後一行是硬要求**：若 id 不存在時回 `ok:true` + 空 body，就是在新的 verb 上
複製 BR_20260901b 的失效形狀——「查無此物」與「有此物但 body 為空」不得共用同一個輸出。

## 6. 驗收判準（給未來修這張的人）

1. 對一個**確定存在**的 object id 呼叫 → 回傳的 `body_md` 非空，且與 `ragbase_query`
   搜到同一條時的 title 一致；
2. **控制組（必跑）**：對一個**捏造的** id 呼叫 → 必須 `ok:false` / `not_found`，
   **不得**是 `ok:true` 配空 body；
3. **控制組（方法層，必跑）**：重跑 §2.2 的列舉，`ragbase_get` 命中數須由 0 變 1，
   且 §2.3 的 4 個正向控制仍全部為 1 ——證明列舉方法本身沒被改壞。

## 7. 本輪沒有量什麼

- **沒有讀 specbase 的原始碼**確認 verb registry 的真實形狀（boundary：guest 只用公開的
  `--help` 介面）。因此本 BR 的斷言精確範圍是：**「三個 runner 的 `--help` 所公告的 48 個 verb 裡
  沒有 id→body_md」**，而非「specbase 內部絕對不存在這個能力」。
  若有未在 `--help` 公告的內部能力，那本身就是另一種揭露缺陷。
- 沒有實測 `sqlite3 -readonly` 直讀路徑（§4 的代價敘述來自規約要求與 dispatcher 提供的線索，
  本輪**未親自複現**那條繞道；此處據實標明）。
- 沒有測試 `ragbase_context` 是否能以某種間接方式湊出全文。
