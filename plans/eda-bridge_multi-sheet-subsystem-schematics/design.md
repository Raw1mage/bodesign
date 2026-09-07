# Design: eda-bridge_multi-sheet-subsystem-schematics

## Context

bodesign 的 C03 原理圖輸出至今**只會產出一個 `.kicad_sch` 檔**。使用者 2026-09-07 裁示
把交付形狀從「單張紙」換成「一個 root 下面開一堆子分支」，本包實作那個換位。

**所有引用的讀數都帶母體宣告。** 母體不同的數字不可互相比較——這是本線多次踩過的坑
（舊包 `errors.md` §369-470 記錄了五格「讀數看起來像資料，其實是判準或母體壞掉」）。

### 已知數（round 28–37 量測，直接引用，不重量）

| # | 讀數 | 母體 |
|---|---|---|
| K1 | 真板 = 1 root + 3 葉 sheet；`hierarchical_label=0`、local label=0、`global_label=18` | btdongle v2.4 人工設計的 `generated/sch/*.kicad_sch`，同一支 parser pass |
| K2 | `18 = Σ(每條 net 跨幾張紙)` | 同 K1，27 條 net 逐條算 sheet 集合大小 |
| K3 | 元件→sheet 是**嚴格 partition**：22/9/14，Σ=distinct=45，跨紙重複 0 | 同 K1，過濾掉 `lib_symbols` 裸前綴後（未過濾 34 vs 過濾 22 ⇒ 過濾有作用） |
| K4 | 分派來源：`design.py:49 SHEETS` + `COMPONENTS` 第 5 欄 → `mk_sch_bodesign.py:67` `"group": sheet` → `composer.py:640-667` 已消費 | GUEST 唯讀，sha `0c2efef7…`；五環證據鏈 |
| K5 | 我們的寫檔點 = **1** 處（`kicad_emit.py:2452-2453`）；`sheet_instances` 是寫死的 `(path "/" (page "1"))`（`:3930`） | bodesign HEAD `2ff0837`，`packages/eda-bridge/` |
| K6 | `global_label` 原語**已具備**，欄位與真板逐字同構（只差字型 scale） | 同 K5，`kicad_emit.py:2532`/`:3176`、`declare.py:53-54` |
| K7 | 連接原理含量 105~210 段，我們畫 124 段，**已落在區間內** | 真板 426 段；下界 K−1 edge、上界每 edge ≤2 段，宣告於量測前 |
| K8 | **`M6-8d` 存活**：整圖+政策OFF=83 交叉、分紙+政策OFF=66，C 是 B 的 80%。**四基準全表**：**A** 分紙+政策ON=**8**（power 7 / mcu 1 / io 0）、**A'** 整圖+政策ON=**8**、**B** 整圖+政策OFF=**83**、**C** 分紙+政策OFF=**66**（power **43** / mcu **20** / io **3**）；伴隨讀數線數 62→92、junction 4→19 | 全表同一母體：with-group 構法、真板第 5 欄分派、政策兩處都攔、同一支 `count_interior_crossings`；單調性控制組 B≥A' 成立 |
| K12 | **母體錯配的實例**：A/A' 的 8 **不可**拿去比 `M6-8d` 聲稱的「12+」——前者是「那些線一條都沒畫」的狀態，後者是「畫出來之後」。**可比的只有 B vs C** | 本線 round 35 曾做過這個無效比較，round 36 才發現。**此列是 `observability.md` 母體宣告紀律的來源** |
| K9 | 9 條單紙 net（`BAT_EXT CC1 CC2 ENPPB NTC SWCLK SWDIO VBUS VBUS_CON`）+ 4 條跨紙 = 13 條被 label 的 net | 全部 27 net 中被 `label_nets` 標走的 13 條，用真板第 5 欄分派算 sheet 集合 |
| K10 | Q3 衝擊面：A 類單檔路徑字面值 **13** 處、C 類 `result.schematic_path` 單數語意 **29** 處、`glob("*.kicad_sch")` **0**、`sheet_instances`/`page` 字面值 **0**、`WIRE_GEOM_SHA` 在 `tests/` **0** | `tests/` 153 個模組，grep tool；控制組換檔後仍成立 |
| K11 | `group` 語意衝突：33 筆 spec fixture 中 **21 筆**的值是佈局佔位標籤（`a`/`p`/`g`/`g0`/`g1`），非子系統名 | `tests/test_composer_draftsman.py`；MCP tool-registry 的同名 `group` 已分開數，不混入 |

## Goals / Non-Goals

**Goals**

- 產出 1 root + N 葉的 hierarchical schematic，root 帶合法 `(sheet …)` block。
- 元件依**功能子系統**嚴格 partition 到葉紙；重複或遺漏都是缺陷。
- 跨紙連通靠**同名 `global_label`**，且該連通性被 `kicad-cli` netlist **實測**過，不靠原語存在推定。
- 五組目前完全沒被表達的子系統各自成為一張可讀的子分支。

**Non-Goals**

- 不追真板 426 段（K7：我們的 124 已在 105~210 區間內）。
- 不引入 `hierarchical_label`（K1：真板為 0）。
- 不改單張紙的幾何判準（anti-fusion / `interior_retry` / `_segment_fuses` 留在舊包）。
- 不保證版面美學。本包管分張與跨頁連接的正確性。
- 不接管舊包的 `ENPPB` / `CHG_LED_A` 兩條 anti-fusion 未畫 net，不追 29 筆 reserve conflict。

## Architecture — 掛在 IDEF0 骨架上

本節的結構**來自 `idef0.json`**，不是事後回填。五個 top-level activity 逐一對應下面五段，
射程四格 (a)(b)(c-verify)(d) 與 (e) 全部落在其中。

### A1 分派元件到功能子系統 —— 射程 (d)

輸入 circuit spec，輸出 `SheetMap{sheet: [refs]}`。控制是「嚴格 partition，無 catch-all」，
機制是新的純函式 `partition_components()`。

分派**資料**已存在（K4：`group` 欄已被 `composer.py:640-667` 完全消費，真板橋接
`mk_sch_bodesign.py:67` 已把 sheet 名餵進去）；缺的是把它解釋成「上哪張紙」。
所以 A1 是**改既有**而非新增資料通道——但語意擴張需使用者裁決（Q1）。

### A2 逐紙佈局與繪線 —— 射程 (e)

輸入 `SheetMap`，輸出 per-sheet geometry。控制是「政策 `scope=sheet`，**`M6-8d` 不放寬**」。

座標決定點今日在 `composer.py:2367-2380`，emitter 只消費不計算；A2 要讓那個決定
**先知道元件屬於哪張紙**，才能逐紙分別佈局。

### A3 產生跨紙連接 —— 射程 (c-verify)

輸入 per-sheet geometry，輸出帶跨紙標籤的紙組。控制是「只用 `global_label`，禁
`hierarchical_label`」（K1：真板 `hierarchical_label=0`）。機制 `_global_label_block()` **已存在**（K6）。

### A4 組裝 root 與葉檔 —— 射程 (a)(b)

輸入帶標籤的紙組，輸出 root + N 葉 `.kicad_sch`。控制是 KiCad 9 的 sheet block 必填欄位
（逐欄抄自真板 root，見 `data-schema.json` §RootSheetBlock）。

現況寫檔點 1 處、`sheet_instances` 是寫死字串（K5）⇒ 兩者都是**新增能力**。

### A5 仲裁跨檔連通性 —— (c-verify) 的驗收

輸入檔組，機制 `kicad-cli sch export netlist`，控制是 **treatment 同名 / control 不同名兩格**。
輸出「已仲裁的多紙原理圖檔組」。`kicad-cli` 不可用時輸出 `indeterminate`，**不得記為 ok**。

## Decisions

- **DD-1 分派來源用既有 `group` 欄，不新增宣告管道。** 依據 K4 的五環證據鏈：欄位已存在、
  已被消費、真板已在用、橋接已接線。原候選「agent 另外宣告」被吐掉（管道已存在），
  原候選「拓撲自動分群」被拒（那是 `_cluster()` 的 fallback，拿它當分紙依據正是
  silent-fabrication 風險來源）。**`group` 與 `sheet` 是否合一（C-1/C-2）待使用者裁決**，
  兩案並列於 `data-schema.json` §ComponentSheetAssignment。

- **DD-2 跨紙連通只用 `global_label`，不引入 `hierarchical_label`。** 依據 K1：真板
  `hierarchical_label=0`、local label=0、`global_label=18`。K6 已確認我們的原語與真板欄位
  逐字同構。**但「原語存在」不等於「跨檔連得起來」**——單檔內同名連通是平凡的，
  它與跨檔連通共用「有 global_label」這個外觀，所以 A5 的實驗是必須而非可選。

- **DD-3 root sheet block 欄位逐欄抄自真板，不憑記憶。** 六個必填欄位記錄於
  `data-schema.json` §RootSheetBlock。`page` 從 2 起算是否 KiCad 強制屬未決（Q2，僅一份樣本）。

- **DD-4 (e) 的射程縮小為「判定範圍降到 sheet 層級」，不含放寬政策。** 依據 K8：
  母體宣告後實測整圖+政策OFF=83 交叉、分紙+政策OFF=66，**C 是 B 的 80%**。
  `M6-8d` 的「12+ 條無序交叉」不但未被推翻，實測值高一個量級（單 power 紙 43）。
  **⇒ 多 sheet 不解決交叉問題，那是另一件事。**

- **DD-5 政策改動必須同時改兩處實作。** `composer.py:2175-2231` 算一次 `label_nets`，
  `kicad_emit.py:1274-1282` 收到後又呼叫 `decide_route_policy` 重算並 OR 回去——
  而後者的註解逐字自稱 `SINGLE SOURCE OF TRUTH`。只改一處會得到「看起來合理但錯」的讀數
  （舊包 `errors.md` ⑤，兩輪帶控制組的答案互相矛盾即由此而來）。

- **DD-6 N=1 走原路徑且 byte-stable。** 否則舊包 30 輪的量測基線全部作廢。
  K10 的有利條件：`WIRE_GEOM_SHA` 在 `tests/` 命中 **0**（只活在 plan 文件與 BR 敘述裡），
  主要成本是 C 類 29 處 `result.schematic_path` 的單數語意，與 N=1 保持原義相容。

## Risks / Trade-offs

- **R1 跨檔連通性可能根本不成立。** 目前只有「原語存在且欄位同構」，沒有任何一次跨檔實測。
  — 緩解：A5 排在 Phase 1，**整包最先做**；若不成立，(a)(b)(d) 全部白做，及早知道。

- **R2 C-1 是破壞性變更。** K11：33 筆 spec fixture 中 21 筆的 `group` 值是佈局佔位標籤
  （`a`/`p`/`g`/`g0`/`g1`），採納 C-1 會生出名為 `g0`/`g1` 的紙，而那些測試量的正是單張紙佈局幾何。
  — 緩解：Q1 列為 stop gate；裁決前不得選定，也不得「先做 C-1 之後再改」。

- **R3 多檔輸出打到既有測試。** K10 已量：A 類單檔路徑字面值 13 處、C 類 29 處。
  — 緩解：DD-6 的 N=1 原路徑；tasks 6.2 逐 test-id 比對 NEW RED（**讀 `Ran N tests` 的 N，不讀 rc**）。

- **R4 分派錯誤會靜默產生錯圖。** 元件掉到錯的紙上，圖仍然畫得出來、看起來正常。
  — 緩解：嚴格 partition + fail-fast（`E_UNASSIGNED_REFS` / `E_REF_ON_MULTIPLE_SHEETS`），
  各配一組負向控制（TV-4）；repo 天條 §2.1 禁止靜默丟進 catch-all。

- **R5 分張後「可讀性」無自動判準。** AC-5（五組子系統各成一張可讀葉紙）是人眼判斷，
  計數器不回答它。 — 緩解：明記為人工驗收，不假裝有機器判準。

## Critical Files

- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` — 寫檔點 `:2452-2453`（現況單數形）、
  `sheet_instances` 寫死字串 `:3930`、`_global_label_block` `:2532` 與呼叫點 `:3176`、
  政策第二實作 `:1274-1282`。A3/A4 的主要改動面。
- `packages/eda-bridge/bodesign_eda_bridge/composer.py` — 座標決定 `:2367-2380`、
  `group` 消費 `:640-667`、政策第一實作 `:2175-2231`（`M6-8d (user 03a ruling)`）。A1/A2 的改動面。
- `packages/eda-bridge/bodesign_eda_bridge/partition.py` — **待建**，A1 的純函式落點。
- `packages/eda-bridge/bodesign_eda_bridge/declare.py` — `RENDER_MODES` `:53-54`（`global_label`
  已是 `DEFAULT_RENDER`）。**唯讀，本包不改。**
- `packages/eda-bridge/bodesign_eda_bridge/fidelity.py` — `:676` 已支援 `rglob("*.kicad_sch")`
  目錄模式，是多檔輸出的既有有利條件。
- `plans/eda-bridge_draftsman-series-divider-wireable/errors.md` — 舊包失效模式庫，
  ⑤ 與 ⑦ 是 tasks 5.2 / 5.4 的直接依據。**跨包可讀，本包不複製。**

## Open Questions

| # | 問題 | 狀態 |
|---|---|---|
| Q1 | `group` 語意 C-1 合一 vs C-2 新增 `sheet` 欄 | **待使用者裁決**（已在使用者手上） |
| Q2 | `page` 從 2 起算是 KiCad 強制或作者選擇 | 未答，只有一份樣本 |
| Q3 | 29 處 `result.schematic_path` 在 N=1 保持原義是否真的免改 | 部分已答（K10 給出母數），逐處確認未做 |
| Q4 | A1 三選項代價（維持現況／關閉豁免／復活 A1） | **未量完，屬舊包範圍**。已知：復活條件 2 成立；關閉豁免在 power 紙可行但代價未量 |

### Q4 的證據：復活條件 2 的 falsification 四格（round 36-37）

下表是「復活條件 2 成立」這句結論的全部證據。**保留在本包是因為它同時是
舊包 `errors.md` ⑦-b（閉包不可 patch 時，改從唯一消費者讀出雙條件等價）那個
技巧的驗證實例**——技巧在舊包，它產生的讀數在這裡。

| 格 | 量測 | 讀數（`fuses_calls / exempt_calls / shorts`） | **母體** |
|---|---|---|---|
| 正控制 | 確定會走豁免的路徑 | `13 / 2 / 0` | btdongle **整圖**（不分紙）、政策 ON、with-group 構法 |
| treatment | 重現短路的那一格 | `12 / 3 / 1`，短路點 `SYS@(330.2, 165.1)` 落在 `USB_DET` 線上 | **power 葉紙**、政策 ON、**no-group 構法**（即 round 35 的構法） |
| falsification | 強制關閉豁免，其餘逐字相同 | `27 / 0 / 0` —— **短路消失**，`changed_verdict` 3→0 | 同 treatment（power 葉紙、政策 ON、no-group），**僅豁免旗標不同** |
| 負控制 | 確定不短路的那張紙 | `0 / — / 0` | **io 葉紙**、政策 ON、no-group 構法 |

**判準**：正控制非零 ⇒ recorder 真的接上了（舊包 ⑦ 的直接修正）；
負控制為 0 ⇒ 這支探針分得出「會短路的紙」與「不會的紙」；
**falsification 才是因果證明**——只改豁免旗標這一個变量，短路就消失。

**這張表不能拿來說什麼**：treatment/falsification/負控制三格的母體都是 **no-group 構法**，
而 round 36 已判定那是 `(B)`（非自然構法：拿掉 `group` 欄、其餘逐字相同）。
用真板第 5 欄原始分派（with-group）重組 power 紙**不復現**，乾淨產出 62 wire / 4 junction。
⇒ **復活條件 2 成立於 no-group 母體，不等於它在自然構法上也成立。** Q4 因此仍未結案。

