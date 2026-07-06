# BR_20260704 — 客戶端知識提取窗口應暴露「KB skill」而非知識源本體

- **類型**：workflow / MCP-integration standard 改版（feature request，非 bug）
- **來源 session**：aiguard C00–C07 設計專案（scope=aiguard；本 BR 是設計討論的固化，實作屬 bodesign）
- **狀態**：proposed / 待 bodesign 端排程；**基本先行、慢慢迭代**（使用者定調：電路設計每案情景不同，永遠寫不出萬用 skill）

---

## 現象（含硬證據）

### 觸發脈絡
aiguard session 收尾時，使用者連續追問三件事，逼出一個架構缺口：
1. 「有沒有把工作經驗寫回 bodesign 的 ragbase」→ 稽核發現只做一半（issue 物件有、failure-mode 蒸餾與 references edge 缺），已於本 session 補完。
2. 「bodesign 今天湧進大量新知識，你工作中調用得到嗎」→ 實測**調用得到**，但過程中我一度誤報 `n=0`。
3. 「未來每個 MCP 都自帶 ragbase 時，怎麼設計標準知識提取窗口？這牽涉 mcp-integration standard spec 改版」。

### 硬證據 1：知識庫是 host-side，docker 邊界被繞過（非打通）
`docker inspect` bodesign 三個 container（bodesign / bodesign-me / bodesign-ee）所有 mount：
```
/home/pkcs12/projects/bodesign/.run -> /run/bodesign (bind,rw)
bodesign-sessions volume -> /var/cache/bodesign/sessions
bodesign-vault volume    -> /var/lib/bodesign/vault
```
`ragbase.sqlite` **未掛進任何 container**。知識庫實體純 host-side：
- repo tier：`<repo>/.specbase/ragbase.sqlite`
- user central tier：`~/projects/ragbase/.specbase/ragbase.sqlite`

存取全走 specbase 的 host-side landing script（`gate.ts` / `producer.ts`，DD-12），**零 MCP round-trip**。specbase container 只暴露 3 個 diagram-proxy tool，同樣不碰 ragbase。
→ 結論：docker MCP 與知識串接的關係是「知識存取被拉回 host landing 而繞過 docker 邊界」，不是「透過 MCP 協議打通 docker 邊界」。

### 硬證據 2：直接暴露知識源本體 → 客戶端易誤判（我自己就踩了）
實測 `ragbase_query` 時，我依直覺假設結果在 `data.hits`，實際結構是 `data.tiers[].hits[]`（雙層 tier 陣列）。解析路徑猜錯 → 一度回報 `matchMode=and-tokens n=0`，差點誤判「今天的知識查不到」。dump 真實 JSON 後才發現知識一直都在、可召回（`failure-mode.pcbnew-scripting-segfault` 等命中，repo+user 兩層皆可查）。
→ 一個熟悉 ragbase 的 agent 都會因 schema 細節誤判；若要求每個外部工作 agent 直接懂九型物件 / 十型 edge / trigram FTS / 兩層 tier / `data.tiers[].hits[]`，這類誤判會遍地都是。

### 硬證據 3：`specbase-kb` skill 已登記、未落地
enablement snapshot（`prompts/enablement.json`）列有 `specbase-kb`，但 `skill()` 解析池無此 skill；`refresh_capability_layer(remcp=true)`（epoch 7→8）後仍載不到。
→ 「用一個 KB skill 當知識介面」的方向早已是 specbase 既定意圖（registry 宣告了），只是 SKILL.md 實體尚未建。本 BR 是把它從「specbase 自己一個」升級為「每個自帶 KB 的 MCP 都要有一個、且共用骨架」的**標準**。

---

## RCA（設計層根因）

先前對「標準知識提取窗口」的兩個候選（A: file-plane broker；B: tool-plane federation）**都錯在同一層**：它們爭論的是「知識源本體怎麼被存取」（sqlite 掛哪、schema 誰定、走 landing 還是 tool）。但客戶端 agent 根本不該看到知識源本體。

正確抽象（使用者洞見）：**bodesign 這端要事先吐出可用的 skill——對客戶端暴露 skill，而不是知識源本體。**

| | 暴露知識源本體（A/B 兩案） | 暴露 skill（採用） |
|---|---|---|
| 客戶端拿到 | sqlite 路徑 / query tool / schema 契約 | 一份「在此 MCP 情境下 recall→deposit→distill」的工作說明 |
| 客戶端要懂 | 九型物件、十型 edge、FTS、兩層 tier、結果 JSON 結構 | 什麼都不用懂，skill 教它 |
| 耦合點 | schema（一改全炸） | skill 語意介面（schema 可自由演化） |
| 誤判風險 | 高（見硬證據 2） | 低（讀結果的慣例被 skill 包掉） |

---

## 建議修復（基本先行、慢慢迭代）

**核心契約**：任何自帶知識庫的 MCP，除了 compute tool，必須額外交付一個 `<mcp>-kb` skill 作為客戶端的**唯一知識介面**；不得把 sqlite / schema / 直接查詢 tool 暴露給客戶端 agent。

標準四動作骨架（沿用 ragbase skill §14 + plan-builder working-KB 既有循環）：
```
每個 MCP 交付 = compute tools + 一個 <mcp>-kb skill
                                 └─ recall-before-work   查已知，只做 delta
                                    deposit-on-learn     把理解 sink 回去
                                    distill-on-closeout  蒸餾成 durable
                                    promote-if-reusable  跨庫上升到 central
```

**這樣三個問題一次解**：
1. docker 邊界：客戶端全程不碰 sqlite / socket，只 `skill()` 載說明 → 邊界天然無關。
2. N 個 MCP 聯邦化：不需 federation resolver；每 MCP 一個 `<mcp>-kb` skill，共用骨架 + 同一 central tier；要用哪庫載哪 skill。
3. schema 演化：改版只需同步 skill 內文，客戶端零改動（從不依賴 schema）。

**對 mcp-integration standard spec 的具體改版**：現有知識層只有 `token-file-model` / `r2-file-transfer`（檔案傳輸 plane）。新增一章高一層的 **「KB-skill exposure contract」**：
> 任何自帶知識庫的 MCP，必須交付一個遵守標準四動作骨架的 `<mcp>-kb` skill 作為客戶端唯一知識介面；禁止暴露知識源本體（sqlite / schema / 直接查詢 tool）給客戶端 agent。

**迭代原則（使用者明確定調）**：
- 每個電路設計案的實際情景都不同，**永遠寫不出萬用 skill**。
- 所以先做**最基本的骨架**（四動作 + honesty/refs-first 紀律），隨真實案例慢慢迭代加厚，**不追求一次到位的通用性**。
- 第一個落地目標：把已登記未落地的 `specbase-kb` SKILL.md 建出來當骨架範本；bodesign 隨後產出 `bodesign-kb`。

---

## 待決設計張力（留給 bodesign 排程時定，本 session 不定）

**骨架「單一模板 vs 各 MCP 客製」**：
- 單一模板（specbase 發同一份骨架，只換名與領域詞）→ 跨 MCP 一致，但較僵。
- 只發 contract（各 MCP 自寫符合契約的 skill 內文）→ 彈性高，但可能各家漂移。
- 傾向：specbase 當「發骨架模板 + 認證 contract」的混合角色；先出模板，容許各案在模板上長出案例特化章節。與「基本先行慢慢迭代」一致。

---

## 影響範圍

- **specbase**：需落地 `specbase-kb` SKILL.md（骨架範本）；`gate.ts`/`producer.ts` landing 介面維持不變（skill 只是其語意封裝層）。
- **bodesign**：需在交付中新增 `bodesign-kb` skill；mcp-integration standard spec 新增 KB-skill exposure contract 章節。
- **客戶端工作 agent（如本 aiguard session）**：未來只需 `skill(<mcp>-kb)` 即可正確 recall/deposit，不再直接碰 ragbase schema，消除硬證據 2 類誤判。
- **不影響**：現有 host-side landing 架構、docker mount 拓撲、ragbase schema 本身。

## 驗證手段

- 落地後：客戶端 agent 僅憑 `skill(<mcp>-kb)` 完成一輪 recall→deposit→distill，全程未直接呼叫 `gate.ts`/`producer.ts`、未讀 sqlite 結構，且知識正確寫入 + 可召回。
- 迴歸：`refresh_capability_layer` 後 enablement 登記的 KB skill 均可 `skill()` 載入（修掉硬證據 3 的登記/落地落差）。
- 跨 MCP：兩個以上 MCP 各自的 `<mcp>-kb` skill 遵守同一四動作骨架，且 promote 至同一 central tier 後可跨庫 query 聚合。

## Resolution（2026-07-06 closed — bodesign 端）

- **`bodesign-kb` skill 已交付**：`skills/bodesign-kb/SKILL.md`——客戶端唯一知識介面（refs-derived 契約：refs 迴圈 6 步 + typed error 對照表 + landing verb quick-ref），客戶端不需懂 ragbase schema / sqlite / gate.py 內部（EPIC task 4.3）。
- **殘留（cross-repo，非 bodesign）**：`specbase-kb` 骨架範本落地、mcp-integration standard spec 新增 KB-skill exposure contract 章節、ragbase producer id 契約 / query accessor 直覺化——均屬 specbase/opencode repo，該側已有對應 BR 追蹤（specbase `issues/BR_2026070*_ragbase_*`）。bodesign 端無剩餘動作。
