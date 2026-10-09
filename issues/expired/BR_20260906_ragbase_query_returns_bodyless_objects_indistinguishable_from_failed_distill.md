# BR_20260906 — `ragbase_query` 把「這一型從不帶內文」與「這一則的內文沒落地」回成同一個結果

- **Family**: G13-harness-disclosure
- **Status**: open（僅立案，本輪不修）
- **Filed by**: `ses_f8a9e2c35ffewY7uZ5UDWQi7xw`（BRNS handler，c03-schematic-total-rca round 2 順手發現）
- **Repo**: `/home/pkcs12/projects/bodesign`
- **Related**: `docs/research/rca_20260906_c03_schematic_total_root_cause.md` §8（未量邊界第 2 條）

## 1. 症狀

撰寫 C03 RCA 時要引用 KB 裡的引擎 postmortem，`ragbase_query` 明確回了它：

```
objectId: source.engine.plan.group.failure.postmortem.2026.07.layered.pipeline.scale.coherence.draftsman.v2
type:     source
title:    engine plan-group failure postmortem 2026-07 (layered-pipeline + scale-coherence + draftsman-v2)
score:    -4
ageDays:  52
```

標題讀起來完全像一則可引用的知識。實際取回時 `body_md` 長度為 **0**。

## 2. 量測（可重跑，含控制組）

```bash
python3 - <<'PYEOF'
import sqlite3
c=sqlite3.connect("/home/pkcs12/projects/bodesign/.specbase/ragbase.sqlite"); cur=c.cursor()
cur.execute("SELECT type, COUNT(*), SUM(CASE WHEN COALESCE(body_md,'')='' THEN 1 ELSE 0 END) "
            "FROM ragbase_objects GROUP BY type ORDER BY 2 DESC")
for r in cur.fetchall(): print(r)
PYEOF
```

| type | 總數 | body_md 為空 |
|---|---|---|
| extract | 99 | **99** |
| asset | 95 | **95** |
| concept | 86 | 3 |
| control | 73 | 0 |
| source | 57 | **57** |
| issue | 41 | 0 |
| workflow | 35 | 1 |
| failure-mode | 30 | 0 |
| role | 6 | 0 |
| step | 4 | 0 |

**控制組（決定性）**：同一支查詢在 `concept` 型上取回非空內文——
`concept.lifecycle-c00-c07`(903)、`concept.honesty-provenance-model`(1547)、
`concept.feasibility-tier`(1245)。所以「`body_md` 長度為 0」不是我讀錯欄位、
不是 DB 壞了，而是 `source`/`extract`/`asset` 這三型**全體 251 筆**確實沒有內文。

## 3. RCA — 缺陷在揭露，不在資料

`source` / `extract` / `asset` 是 ragbase 蒸餾鏈的**前三步**
（`ragbase_ingest_source` → `ragbase_register_asset` → `ragbase_record_extract`），
它們的語意本來就是**指標**（指向磁碟上的檔案 / 一段 locator），不是知識實體。
知識實體是第四步 `ragbase_distill` 產出的 `concept` / `control` / `failure-mode` / `workflow`。
**所以 251 筆沒有內文，多半是設計如此，不是資料遺失。**

缺陷在於：**`ragbase_query` 的回傳沒有任何一格說明這件事。**
它把三種完全不同的狀態壓成同一個外觀：

| 真實狀態 | 呼叫端看到的 |
|---|---|
| 這一型本來就不帶內文（指標型），要往下游找 distilled object | `objectId` + `title` + `score`，`body_md` 空 |
| 這一則的蒸餾**沒做**（登記了 source 就沒有下文） | 同上，逐字相同 |
| 這一則蒸餾**做了但寫壞**（`body_md` 寫入失敗 / 被覆寫成空） | 同上，逐字相同 |

而 `title` 欄位加劇了誤導——`source` 型的 title 是人類可讀的知識名稱
（"engine plan-group failure postmortem 2026-07 …"），讀起來與一則 `concept` 的 title
無法區分。呼叫端拿到它、以為撈到了知識、取內文取到空字串，
**唯一能得到的結論是「這則知識是空的」——三種狀態裡最不可能的那一種。**

這正是 `code-thinker` §8 的形狀：缺席態與失敗態共用同一個輸出。
也是 §12 的形狀：`ragbase_query` 的結束狀態 codomain 裡缺 `not-run`
（「這一則從未被蒸餾」）與 `n/a`（「這一型不帶內文，去找它的下游」）這兩格。

## 4. 佐證：本 repo 已經知道這個形狀

`AGENTS.md` §6 的知識蒸餾段自己寫著

> **建檔 ≠ 蒸餾**：`issues/` 的 BR 給人修（repo-local），全域 KB 的 concept 給人查（跨 repo）。
> **禁止整份複製 BR 進 KB**（死鏡像比沒有更糟——本 fleet 有 149 個 `type=issue` 死鏡像前例）

本 repo 的 `type=issue` 有 41 筆且 `body_md` 全部非空——即那 41 筆**是**死鏡像。
與本 BR 合看：ragbase 裡同時存在「有內文但不該有」（issue 死鏡像）與
「沒內文但看起來該有」（source/extract/asset），
而 `ragbase_query` 對這兩種偏差**都不表態**。

## 5. 可能的修法（不裁示，供 owner 決定）

1. **最小**：`ragbase_query` 的每一筆 hit 加一格 `bodyPresence`，
   值域 `{present, structural-none, distill-missing}`——第二與第三格靠 `ragbase_lineage`
   判斷（有下游 distilled object ⇒ structural-none；沒有 ⇒ distill-missing）。
2. **中**：查詢預設不回 `source`/`extract`/`asset`，除非呼叫端明確要求
   （它們是蒸餾鏈的內部狀態，不是消費面）。
3. **大**：`ragbase_query` 對指標型自動解析到其 distilled 下游並回傳那一則，
   在結果裡標明是經由哪一則 source 到達的。

## 6. 未量邊界

- 本輪只量了 `/home/pkcs12/projects/bodesign/.specbase/ragbase.sqlite`（repo tier）。
  **中央 user tier 未量**——那 149 個死鏡像的說法引自 `AGENTS.md`，本輪未獨立驗證。
- 未讀 `ragbase_query` 的實作（`specbase` repo 的 `gate.ts` / ragbase runner），
  所以「回傳沒有 `bodyPresence` 這格」是從**輸出**觀察到的，不是從**程式碼**確認的。
  若實作其實有這格而只是 CLI 沒印，本 BR 的修法建議 1 會落空，但症狀仍成立。
- 未量 `source.engine.plan.group.failure...` 這一則是否**有**下游 distilled object。
  若有，它屬第一態（structural-none），本 BR 就純粹是揭露缺陷；
  若沒有，它同時是一則**未完成的蒸餾**，那是第二個獨立缺陷。**本輪未查 lineage 表。**

---

## 7. 姊妹缺陷（2026-09-06 追加）：`ragbase_query` 撈不到剛剛 distill 成功的條目

同一天、同一條 KB 蒸餾線上長出的第二個「缺席態與失敗態共用輸出」。
與 §1–§6 的差別：那邊是**取回的內文是空的**，這邊是**根本取不回來**，
而兩者的呼叫端表現一模一樣——`hits: []`。

### 7.1 觸發

`ragbase_distill` 回 `ok:true`、`confidence:"verified"`、`segments[0].body_md` 非空
（2679 bytes），落地 `tooling-failmodes.failure-mode.fix-lands-on-parallel-pipeline-off-delivery-path`。
隨即 dispatcher 回查：

```
ragbase_query --repo $HOME/projects/ragbase '{"q":"fix-lands-on-parallel-pipeline-off-delivery-path"}'
  → matchMode=and-tokens, fallbackApplied=false, repo hits=[] user hits=[]
```

**`fallbackApplied=false` 是這格最誤導的地方**：它表示查詢**沒有**降級成 or-token，
即「這是一次乾淨的 and-token 查詢，結果就是沒有」——讀起來像權威的否定答案。

### 7.2 三態判定 = **(iii) query 形狀，不是寫入失敗**

**(i) 寫進 sqlite 但 FTS 未索引 → 排除。** 兩層都在：

```
ragbase_objects:         id 存在，body_md 長度 2679
ragbase_object_segments: seq=0，長度 2679
rowid = 1585
SELECT count(*) FROM ragbase_fts WHERE rowid=1585  →  1     ← FTS 索引裡有它
```

`ragbase_fts` 是 `content='ragbase_objects'` 的 external-content FTS5，
且有三個維護 trigger（`ragbase_objects_ai` / `_ad` / `_au`），索引是同步的。

**(ii) 寫進別的 tier/db → 排除。** `--repo $HOME/projects/ragbase` 的
`dbPath` 就是 `/home/pkcs12/projects/ragbase/.specbase/ragbase.sqlite`，
上述 rowid 即在該檔測得。

**(iii) 成立，而且是三個原因疊加。**

### 7.3 決定性證據

正向控制組——用一個**已驗證存在於 body 的 3 字詞**跑 runner 層查詢：

```
ragbase_query --repo $HOME/projects/ragbase '{"q":"可達性","limit":6}'
  → matchMode="and-tokens", fallbackApplied=false
  → 第一筆命中: tooling-failmodes.failure-mode.fix-lands-on-parallel-pipeline-off-delivery-path
```

**同一支 runner、同一個 db、非降級查詢，條目排第一。** 所以 §7.1 的空結果
不是寫入問題，是查詢詞問題。

負向控制組（證明探針不是萬能命中）：`zzz_not_present_marker` n=0、
`量子色動力學` n=0——兩者皆不在 body，皆不命中。

### 7.4 三個疊加原因

**原因 1 — `id` 欄位是 `UNINDEXED`，用 id 查永遠不會命中。**

```sql
CREATE VIRTUAL TABLE ragbase_fts USING fts5(
  id UNINDEXED,          -- ← 這個
  title,
  body_md,
  content='ragbase_objects',
  content_rowid='rowid',
  tokenize='trigram'
)
```

dispatcher 查的正是 object id 全串。**FTS 只索引 `title` 與 `body_md`**，
id 從不進索引。而「用 id 查一個知道 id 的物件」是回查最自然的動作。

**原因 2 — trigram tokenizer 需要 ≥3 字元，兩字中文詞一律回 0。**

實測（全部**確認存在於 body**）：

| 詞 | 字元數 | 在 body | MATCH n | 命中目標 |
|---|---|---|---|---|
| `可達性` | 3 | ✓ | 6 | **✓** |
| `68bdde1` | 7 | ✓ | 1 | **✓** |
| `PC-001` | 6 | ✓ | 1 | **✓** |
| `eda-bridge` | 10 | ✓ | 1 | **✓** |
| `管線` | **2** | ✓ | **0** | ✗ |
| `歸檔` | **2** | ✓ | **0** | ✗ |

**「管線」出現在 body 裡至少十幾次，查它回 0。** 中文技術詞大量是雙字
（管線／歸檔／驗證／閘門／契約／覆蓋），**這個 KB 的中文條目有一整類詞查不到**，
而輸出與「這個詞不存在」逐字相同。

**原因 3 — dispatcher 的英文查詢詞根本不在這則 body 裡。**
`parallel` / `pipeline` / `delivery` 三個詞在 body 中**皆不存在**（body 是中文；
這三個詞只出現在 **object id** 裡，而 id 是 UNINDEXED）。
所以那次查詢在機制上不可能命中——**不是索引壞了，是問了一個這則條目沒有的詞**。

### 7.5 RCA：資訊都在，沒有一格說出來

三個原因各自合理（UNINDEXED 省空間、trigram 對 CJK 是常見選擇、查詢詞不匹配是使用者行為），
**缺陷在於三者的失敗全部塌成同一個 `hits: []`**，而 `fallbackApplied=false`
還會被讀成「乾淨查詢、確實沒有」。呼叫端無法分辨：

| 真實狀態 | 看到的 |
|---|---|
| 這則條目不存在 | `hits: []`, `fallbackApplied: false` |
| 存在，但查詢詞只在 UNINDEXED 的 id 裡 | 同上，逐字相同 |
| 存在，查詢詞在 body 裡，但**短於 3 字元** | 同上，逐字相同 |
| 存在，但查詢詞真的不在 body（語言不匹配） | 同上，逐字相同 |

系統握有全部三格資訊：DDL 知道 `id UNINDEXED`、tokenizer 知道自己的最小長度、
runner 已經在算 token（它印得出 `sub-trigram tokens: on, on` 這種訊息——
§10 的另一次查詢就印過）。**但那則 sub-trigram 警告只在部分路徑出現，
且不說「因此這些 token 被丟棄了」。**

與 §1–§6 同族：那邊是 `body_md` 空而不說為什麼，這邊是 `hits` 空而不說為什麼。
**同一個 KB 工具，兩個位置，同一個形狀。**

### 7.6 修法建議（不裁示）

1. **最小**：查詢回傳加 `tokens_dropped: [{token, reason}]`，
   reason ∈ `{below_trigram_minimum, stopword, unindexed_column_only}`。
   `hits:[]` 配非空 `tokens_dropped` ⇒ 呼叫端立刻知道問題在問法。
2. **中**：`id` 改為索引欄（或 runner 在 FTS 查詢外**額外**跑一次
   `WHERE id LIKE '%'||?||'%'`，並在結果標 `matchedVia: "id"`）。
   「知道 id 卻查不到」是回查最常見的入口。
3. **CJK**：trigram 對 2 字詞的結構性盲區需明確揭露；
   或改用 `unicode61` + bigram 疊加。**這一格影響整個中文 KB，不只本則。**

### 7.7 本節的量測誠實記錄

**我的第一輪探針是壞的，是控制組抓到的。** 初版用
`MATCH '"parallel pipeline"'` 這類**加引號的 phrase query**，
結果目標 0、**控制組（一則已知可查到的姊妹條目）也 0**。
控制組與 treatment 同時歸零 ⇒ 該輪判別力為零，任何結論都不成立。
改用不加引號的單 token（trigram 的正確用法）後控制組恢復非零，
量測才開始有意義。

**若當時只看目標那一格、沒配控制組，我會把「探針寫錯」寫成
「條目沒寫進去」——一個反向結論。**（本 repo AGENTS.md §6.2 記載過同型事故：
控制組與 treatment 死於同一個原因，該格當場無法證明任何事。）

### 7.8 未量

- 未讀 `ragbase_query` 的 runner 實作，所以「runner 沒有 `tokens_dropped` 這格」
  是從**輸出**觀察到的，不是從程式碼確認的。
- 未量 repo tier（bodesign 的 `.specbase/ragbase.sqlite`）是否同一個 DDL——
  §7 全部量在中央 `$HOME/projects/ragbase`。
- 未驗證「`sub-trigram tokens` 警告只在部分路徑出現」——只觀察到它在一次查詢出現、
  在另一次沒出現，**未找出觸發條件**。
