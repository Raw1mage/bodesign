# Proposal: eda-bridge_multi-sheet-subsystem-schematics

> **狀態：`proposed`。本包停在提案，未進 designed。**
> 本包的射程是「**一個 root 下面開一堆子分支**」——把重點電路的連接原理，
> 依功能子系統分張展開。**不是**「在單張紙上把線畫對」（那是舊包
> `eda-bridge_draftsman-series-divider-wireable`，本包不取代它）。

## Why

bodesign 走了三個月、~40 張圖層 BR，全部落在**同一張紙**上。
2026-09-07 使用者裁示指出這個框架本身是錯的：

> 「電路原理圖本來就沒辦法用一張圖來表達全部 pinout 的電路原理，
> 一次只能挑一部份的 pinout 連接原理出來畫。」
> 「電路原理圖是給人看的，當然不可能把一個板子的全部 routing 都畫出來。
> 只需要分門別類，以局部子分區或子功能的方式展開重點電路的連接原理設計就好。
> 就是一個 root 下面開一堆子分支。」

**這句話取代的是什麼問題**：先前 30 輪的主線是「`M6-8d` 這條 cross-IC 政策要不要放寬，
好讓更多 net 被畫成線而不是掛 label」。使用者的回答不是 yes/no，而是**這個問題問錯了**
——它預設了輸出形狀是單張紙，於是所有討論被鎖在「一張紙上該塞多少」。
量測記錄保留在舊包 `label-policy-for-user-ruling.md`（該檔開頭已標註「問題已被取代」）。

### 我們現在離目標多遠：形狀，不是數量

| 維度 | 真板（btdongle v2.4，人工設計） | bodesign HEAD `2ff0837` | 差距性質 |
|---|---|---|---|
| `.kicad_sch` 檔數 | **4**（1 root + 3 葉） | **1** | 能力不存在 |
| root 的 `(sheet …)` block | **3** | **0** | 能力不存在 |
| `hierarchical_label` | **0** | 0 | 一致（真板不用它） |
| local label | **0** | 0 | 一致 |
| `global_label` | **18**（power 3 / mcu 7 / io 8） | 有此原語，欄位同構 | **已具備** |
| wire 段數 | 426（248+94+84） | 120 | 見下方「不追 426」 |

**「數量差距」已在 round 29 被解消，不是本包的目標。** 判準與偏差方向在量測前宣告：
K 個 pin 在同一條 net 上至少需要 K−1 條 edge（下界），正交佈線每條 edge 最多 2 段（上界）
⇒ 真板 426 段裡屬於「連接原理」的含量是 **105~210 段**，我們畫 124 段，**已落在區間內**。
426 減去 210 的餘量是**手繪風格**（GND 一條就佔 144 段、2.94 段/pin）。
**所以本包不追 426，追的是把那 124 段分門別類攤到多張紙上，並補齊沒被表達的子系統。**

## Original Requirement Wording (Baseline)

- 2026-09-07：「電路原理圖本來就沒辦法用一張圖來表達全部 pinout 的電路原理，一次只能挑一部份的 pinout 連接原理出來畫。」
- 2026-09-07：「電路原理圖是給人看的，當然不可能把一個板子的全部 routing 都畫出來。只需要分門別類，以局部子分區或子功能的方式展開重點電路的連接原理設計就好。如同你所說，就是一個 root 下面開一堆子分支。」
- 2026-09-07：「bodesign 就是一個提供 mcp, tool, cli, skill, KB 讓 agent 設計電路的 harness，搞半天沒有人設計電路！」

## Requirement Revision History

- 2026-09-07: 本包建立。射程來自使用者裁示的框架換位（單張 → 多張子分支），
  是 **scope shift 而非舊包的 amend**：舊包問「這條線該怎麼畫」，本包問「這張圖該切成幾張、
  每張放什麼」。兩者的失效模式、驗收標的、受影響模組都不重疊。

## Effective Requirement Description

1. bodesign 必須能產出**多檔 hierarchical schematic**：1 個 root `.kicad_sch` 帶 N 個
   `(sheet …)` block，各指向一個葉 `.kicad_sch`。
2. 切分軸是**功能子系統**（power / mcu / io …），不是元件類型。
   證據：真板 R1–R7 全在 power、R8 在 mcu、R9–R14 全在 io——同一種元件被拆到三張紙。
3. 元件→sheet 是**嚴格 partition**：每顆元件恰好出現在一張葉紙上。
   量測：45 顆有編號 ref，每張紙 22/9/14，Σ=45=distinct，跨紙重複 **0**。
4. 跨紙連接一律用 `global_label`，**不引入 `hierarchical_label`**（真板為 0）。
5. 每張葉紙必須是一個**可獨立閱讀的連接原理單元**——驗收標的是那五組目前完全沒被展開的
   子系統（見 §驗收標的），不是 wire 段數。

## Scope

### IN — 四格，逐格帶現況讀數

| # | 能力 | 現況讀數（HEAD `2ff0837`） | 證據 | 新增 or 改既有 |
|---|---|---|---|---|
| (a) | 產出 N 個 `.kicad_sch` 檔 | 寫檔點 **1** 處 | `kicad_emit.py:2452-2453`（`schematic_path = root / f"{project_name}.kicad_sch"` → `write_text`） | **新增能力**（既有寫檔點是單數形，需擴為「一組」） |
| (b) | root 檔帶 `(sheet …)` block | **0**。`sheet_instances` 是寫死字串 `(path "/" (page "1"))` | `kicad_emit.py:3930` | **新增能力**（目前無任何 sheet block 產生器） |
| (c) | 跨 sheet 連通性 | 原語**已具備**；但跨**檔**連通從未被測過 | `kicad_emit.py:2532`/`:3176`、`declare.py:53-54` | **驗證，非實作**（見下方實驗契約） |
| (d) | 元件→sheet 分派 | 分派**資料**已存在（`group` 欄）；分派**到 sheet** 不存在 | `composer.py:2072`/`:2285`/`:640-667`；座標決定點 `composer.py:2367-2380` | **改既有**（語意擴張，見 Q1） |
| (e) | 政策的 sheet-aware 重新推導 | cross-IC / power-rail / high-fanout 三條政策的判定範圍是**整張圖** | `composer.py:2175-2231`（`M6-8d (user 03a ruling)`） | **需使用者裁決**（見下） |

### (c) 的實驗契約 — 不新增原語，但必須驗證

**已具備的那一半**：我們已在產 `global_label`（`kicad_emit.py:2532` `_global_label_block`、`:3176` 呼叫點），
`declare.py:53-54` 已把它列為 `RENDER_MODES` 且是 `DEFAULT_RENDER`；欄位與真板逐字同構，唯一差異是字型 scale。
真板 `hierarchical_label=0` / local label=0 ⇒ **不需要第二種跨頁原語**。

**必須驗證的那一半**：真板三張葉紙的 global_label 是 **3/7/8=18**，而 root 檔 `global_label=0`——
**跨 sheet 連通性是靠「同名 global_label 出現在不同葉檔」建立的，與 root 檔無關。**
我們只有一個檔，所以「同名 label 在同一張紙上連得起來」是**平凡的**——
它與「跨檔連得起來」共用「有 global_label 原語」這個外觀。

**designed 的第一個實驗（契約，不可簡化）**：

```
treatment : root + 2 葉，兩葉各 1 個 **同名** global_label
            → kicad-cli 匯出 netlist → 兩端必須落在 **同一條** net
control   : 同一份，兩葉改成 **不同名**
            → 必須落在 **兩條不同** net
```

**控制組不可省**：沒有它，treatment 的 PASS 分不出「跨檔真的連通」與
「netlist 匯出把所有東西都併成一條」——兩者共用同一個「兩端同 net」的輸出。

### (e) 政策的 sheet-aware 重新推導 — **會碰 `M6-8d`，需使用者裁決**

`M6-8d` 的理由逐字是「drawn cross-IC bus 產生 12+ 條無序交叉線」。
**那個交叉是單張紙逼出來的。** 切成 power/mcu/io 三張紙之後，每張紙上的 cross-IC 對數大幅下降
⇒ **政策的前提在多 sheet 形狀下不再成立，但政策的 code 不會自己知道這件事。**

本包 designed 階段要產出的是**量測**，不是修改：

1. cross-IC / power-rail / high-fanout 三條政策的判定範圍從「整張圖」改為「單張 sheet 內」是否成立；
2. **每張紙上實際會有幾條交叉**。

**拿那個數字去問使用者，不自己改**——`M6-8d` 是使用者裁示。

### OUT

- **不改單張紙的幾何判準**。anti-fusion / `interior_retry` / `_segment_fuses` 全部留在舊包。
  （(e) 碰的是政策的**判定範圍**，不是畫線的幾何。）
- **不追真板 426 段**（理由見 §Why，105~210 區間 + 我們的 124 已落在區間內）。
- 不引入 `hierarchical_label`。
- 不碰 C04 以後任何路徑。

## Non-Goals

- 不保證每張葉紙「好看」。本包管的是**分張與跨頁連接的正確性**，不是版面美學。
- 不追求一次涵蓋 45 元件 / 27 net。第一刀能跑通「root + 2 張葉紙 + 1 條跨頁 net」即算立住。
- 不接管舊包的 `ENPPB` / `CHG_LED_A` 兩條 anti-fusion 未畫 net，也不追那 29 筆 conflict。

## 驗收標的 — 五組從未被展開的子系統

這五組是 round 29 ③ 量出來的：**它們的連接原理在我們的輸出裡完全沒有被表達**
（不是畫錯，是根本沒有一個地方在講它）。**本包的成敗以「能不能把這五組各自攤成一張可讀的子分支」判定，
不以 wire 段數判定。**

1. **電源幹道**（power distribution trunk）
2. **USB-C 介面 + CC 偵測**
3. **電池介面 + NTC 溫度感測**
4. **充電致能 + 狀態指示**
5. **SWD 除錯介面**

真板把它們塞進 3 張紙（power 22 元件 / mcu 9 / io 14）。**我們要切幾張是未決問題**——
5 組不必然對應 5 張紙。

## Constraints

- **No silent fallback**（repo 天條 §2.1）：分派不到 sheet 的元件必須 fail-fast 列出，
  不得靜默丟進「其他」那一張。
- **No fabrication**（§2.2）：`files` 清單只列磁碟上真實存在的檔——多檔輸出時每個葉檔都要真的寫出來。
- 分派必須是**嚴格 partition**（真板為證），重複或遺漏都是缺陷而非退化。
- 產出必須讓既有四層驗證（ERC / fidelity / crosscheck / SPICE）仍可跑——
  `fidelity.py:676` 已支援 `rglob("*.kicad_sch")` 目錄模式，這是既有的有利條件。

## What Changes

- `kicad_emit.py`：單一寫檔點 → 多檔寫出 + root sheet block 產生器。
- `composer.py`：座標決定處需先知道「這顆元件屬於哪張紙」，座標才能 per-sheet 分別佈局。
- 可能新增一個分派模組（純函式：spec → {sheet_name: [refs]}）。
- **不碰** `occupancy.py` / `declare.py` / `slot_observe.py` / `design_suggest.py`。

## Capabilities

### New Capabilities
- `sheet_partition`：把一份 spec 的元件分派到 N 個功能子系統。
- `emit_hierarchical_schematic`：產出 root + N 葉，並在 root 寫出 `(sheet …)` block。

### Modified Capabilities
- `emit_kicad_schematic`：輸出從單檔變一組檔。**既有單張呼叫端必須 byte-stable**
  （N=1 時走原路徑），否則舊包 30 輪的量測基線全部作廢。

## Impact

- 受影響程式碼：`kicad_emit.py`（寫檔 + 文件組裝）、`composer.py`（座標決定的上游）。
- **⚠ 未量的衝擊面**：既有 **2068 個測試**中有多少假設「輸出恰好一個 `.kicad_sch`」。
  本輪未量（見 §未決問題 3）。
- 受影響文件：`specs/architecture.md`（C03 輸出從單檔變檔組）。
- 不受影響：C04 以後、四層驗證的判準本身。

## 未決問題（本包 `proposed` 階段刻意不答）

### Q1 — 元件→sheet 的分派規則從哪來？**候選 C 已實測成立，問題改形。**

**候選 C 成立：欄位名是 `group`，且它不只存在——它已經被消費、且真板已經在用。**
五條證據鏈（全部唯讀量測，2026-09-07 round 33）：

| 環節 | 讀數 | 證據 |
|---|---|---|
| spec 欄位定義 | `group: string`，notes 逐字寫「**功能分群**，透傳給引擎 cluster placement」 | 舊包 `data-schema.json` §Component |
| composer 讀取 | 讀進來 → 餘給 `_cluster()` | `composer.py:2072`（`comp.get("group")`）、`:2285`、`:2287` |
| 消費語意 | **`declared` 非空時完全接管分群**（`source="declared"`）；未宣告者自成 singleton `auto-<ref>`，**一顆不掉** | `composer.py:640-667` |
| 真板已在用 | `design.py:49 SHEETS = [("power",…),("mcu",…),("io",…)]`；`COMPONENTS` 每顆的**第 5 欄**就是 sheet 名 | GUEST 唯讀，45/45 欄位值皆屬已宣告 sheet 名 |
| 橋接已接線 | `"group": sheet` ——**真板的 sheet 欄已經直接餵進 bodesign 的 `group`** | `mk_sch_bodesign.py:67,69` |

**交叉印證（決定性）**：`design.py` 第 5 欄的分佈是 **power 22 / mcu 9 / io 14**，
與獨立從三個 `.kicad_sch` 檔數出來的每張紙元件數**逐格相符**（Σ=45=distinct）。
兩條互不相干的路徑得到同一組數字。

**所以 Q1 不再是「規則從哪來」，而是一個更窄、但仍需裁決的問題：**

> **`group` 目前的語意是「版面上要不要摆在一起」（cluster placement）。
> 把它直接當成「上哪張紙」來用，這兩個語意可以合一嗎？**

兩個選項，**不預選**：

- **C-1 語意合一**：`group` 同時意味分群與分紙。零新欄位、零 schema 變更、consumer 零修改
  （真板橋接已經在餵 sheet 名進去了）。**代價：以後想表達「同一張紙上分兩群」就說不出來了。**
- **C-2 新增 `sheet` 欄，`group` 維持原意**：兩個維度可分別表達。
  **代價：新欄位 + 兩欄的一致性規則（同一 group 能不能跨 sheet？）又是一條要訂的政策。**

**原候選 A（agent 另外宣告）實質上已被 C 吐揉掉**——宣告管道已經存在。
**原候選 B（拓撲自動分群）不需要了**：它本來就只是 `_cluster()` 在 `declared` 為空時的 fallback
（`composer.py:669+`，net-degree connected-components），**而且拿它當分紙依據正是 silent-fabrication 風險的來源**。

**⚠ 本輪未量**：`group` 在**既有呼叫端**裡的實際使用情形——除了 btdongle 以外，還有誰在帶這個欄，
以及他們帶的值能不能当 sheet 名。**C-1 若被採納，這一格必須先量**。

### Q2 — `page` 從 2 起算，是 KiCad 強制還是作者選擇？

真板 root 是 `(sheet_instances (path "/" (page "1")))`，三張葉紙分別 `page "2"/"3"/"4"`。
**只有一份樣本**，無法區分「KiCad 要求 root 佔 page 1」與「作者的慣例」。
證據：`btdongle.kicad_sch:7,11,15`。

### Q3 — 多次 emit 對既有 2068 個測試的衝擊面有多大？

**本輪未量。** 需要知道：有多少測試斷言「恰好一個 `.kicad_sch`」、有多少斷言
`WIRE_GEOM_SHA` 這類全域雜湊（多檔後語意改變）。

## 與舊包的關係

**本包不接手「宣告入口」那個空缺——因為它已經被填補了。**

舊包 `proposal.md` §Why 開頭寫的「61 個 verb、讓 agent 宣告電路拓撲的入口 0 個」，
**已於本線 `23df9ad` / `fe5278b` 建好 `declare_circuit`**。生效的證據是 round 29 ③ 的
**堆 3 = 0**：27/27 spec net 以 node-set 身分精確對應，**那些連接原理已經進到系統裡了**。

> **⚠ 文件裡的問題陳述不會因為問題被解決而自動更新。**
> 舊包 `proposal.md` §Why 至今逐字寫著那個已經不存在的空缺。本包在 round 33 差一點因此把
> 「宣告入口」列進射程，即重做一件三週前已完成的事。
> **實際的缺口是 (e)**：那 12 條被 label 政策攔在繪圖之外，
> 而那條政策的正當性建立在「只有一張紙」這個前提上。

**本包不取代 `eda-bridge_draftsman-series-divider-wireable`。** 留在舊包的：

- `ENPPB` / `CHG_LED_A` 兩條因 **anti-fusion**（非政策）而 0 段的 net
  ——round 30 的 POLICYOFF 控制組推翻了原本的 cross-IC 歸因。
- 29 筆 reserve conflict。
- `M6-8d` 本身與 `label-policy-for-user-ruling.md` 的 baseline 記錄。
- `errors.md` 的 8 則失效模式（跨包可讀，本包不複製）。

舊包現況（round 33 量）：`plan-validate` **PASS**（12 required artifacts）。
帳面已於 round 33 由 `planned` 推至 **`implementing`**（修正 STATE DRIFT，dispatcher 授權）。

**舊包的 PASS 有一個必須連帶讀的限制**：`execution-contract layer DID NOT RUN`（該包未 opt in），
所以它的 `idef0.json` / `grafcet.json` 是 **present but UNVALIDATED**——
**那個 PASS 對這兩份檔什麼都沒說。** 本包若日後要引用舊包的圖，不得把那個 PASS 當成它們的背書。

