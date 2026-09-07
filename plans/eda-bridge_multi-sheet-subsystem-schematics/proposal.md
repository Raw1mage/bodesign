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

### IN — 三格，逐格帶現況讀數

| # | 能力 | 現況讀數（HEAD `2ff0837`） | 證據 | 新增 or 改既有 |
|---|---|---|---|---|
| (a) | 產出 N 個 `.kicad_sch` 檔 | 寫檔點 **1** 處 | `kicad_emit.py:2452-2453`（`schematic_path = root / f"{project_name}.kicad_sch"` → `write_text`） | **新增能力**（既有寫檔點是單數形，需擴為「一組」） |
| (b) | root 檔帶 `(sheet …)` block | **0**。`sheet_instances` 是寫死字串 `(path "/" (page "1"))` | `kicad_emit.py:3930` | **新增能力**（目前無任何 sheet block 產生器） |
| (d) | 元件→sheet 分派 | **不存在**。座標在 composer 決定，emitter 只消費 | 決定點 `composer.py:2367-2380`（`_page_fill_distribute` → `abs_pos` → `EmitComponent(x, y)`）；emitter 端只讀 `c.x/c.y` | **新增能力**（且它是唯一需要新政策的一格） |

### (c) 明確排除 — `global_label` 已具備

本輪最省事的發現：**跨 sheet 不需要新原語。**

- 我們已在產 `global_label`：`kicad_emit.py:2532`（`_global_label_block`）、`:3176` 呼叫點；
  `declare.py:53-54` 已把 `global_label` 列為 `RENDER_MODES` 且是 `DEFAULT_RENDER`。
- 欄位與真板逐字同構，**唯一差異是字型 scale**（我們帶 `text_scale=page_scale`）。
- 真板 `hierarchical_label=0`、local label=0 ⇒ 不需要補第二種跨頁原語。

**⚠ 未量**：同構是**文字比對**。沒有實際產一份多 sheet 檔丟給 KiCad，驗證跨 sheet 的
`global_label` 真的在 netlist 層連得起來。這一格是 designed 階段的第一個實驗。

### OUT

- **不改單張紙的佈線判準**。`M6-8d` / anti-fusion / `interior_retry` 全部留在舊包。
- **不追真板 426 段**（理由見 §Why，105~210 區間 + 我們的 124 已落在區間內）。
- 不引入 `hierarchical_label`。
- 不做元件自動分群演算法的選型——本包 `proposed` 階段**只列候選不預選**（見 §未決問題）。
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

### Q1 — 元件→sheet 的分派規則從哪來？**三個候選，不預選。**

| 候選 | 形狀 | 已知的代價 |
|---|---|---|
| **A. agent 在 `declare_circuit` 時宣告** | spec 多一個 `sheet` 欄，設計者自己說 | 把負擔丟回呼叫端；但符合本 repo「系統不自己發明電路」的天條 |
| **B. 從 net 拓撲自動分群** | 用連通度/社群偵測切 | **有 silent-fabrication 風險**——系統自己決定了功能邊界。KB `netlist-synthesis-gap` 的禁令可能適用，需辨析 |
| **C. 從既有 spec 的某個既有欄位推導** | 例如從 `value` / `footprint` / 既有分組欄位反推 | 需先確認那個欄位存在且語意穩定；本輪未查 |

**我不預選，因為 B 可能直接撞上本 repo 的天條，那是設計裁決不是實作偏好。**

### Q2 — `page` 從 2 起算，是 KiCad 強制還是作者選擇？

真板 root 是 `(sheet_instances (path "/" (page "1")))`，三張葉紙分別 `page "2"/"3"/"4"`。
**只有一份樣本**，無法區分「KiCad 要求 root 佔 page 1」與「作者的慣例」。
證據：`btdongle.kicad_sch:7,11,15`。

### Q3 — 多次 emit 對既有 2068 個測試的衝擊面有多大？

**本輪未量。** 需要知道：有多少測試斷言「恰好一個 `.kicad_sch`」、有多少斷言
`WIRE_GEOM_SHA` 這類全域雜湊（多檔後語意改變）。

## 與舊包的關係

**本包不取代 `eda-bridge_draftsman-series-divider-wireable`。** 留在舊包的：

- `ENPPB` / `CHG_LED_A` 兩條因 **anti-fusion**（非政策）而 0 段的 net
  ——round 30 的 POLICYOFF 控制組推翻了原本的 cross-IC 歸因。
- 29 筆 reserve conflict。
- `M6-8d` 本身與 `label-policy-for-user-ruling.md` 的 baseline 記錄。
- `errors.md` 的 8 則失效模式（跨包可讀，本包不複製）。

舊包現況：`state=planned`，`plan-validate` **PASS**（12 required artifacts），
但報 **STATE DRIFT**——tasks.md 進度已到 `implementing`。**本輪未 advance，唯讀。**

