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
