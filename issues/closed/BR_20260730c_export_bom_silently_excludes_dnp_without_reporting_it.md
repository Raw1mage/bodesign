# BR_20260730c — `export_bom` 靜默排除 DNP 料，回傳值無任何欄位反映它

- Status: **CLOSED** — commit `9e61629`（4 檔，+351/-4）。實作時**推翻了本 RCA 的兩個前提**、發現**第二條未被記載的靜默排除**，見 §實作發現。
- Closed: 2026-07-30 by `ses_0c87bab06fferQ0umBs2Nybb5U`（歸檔 commit `b7ce0a2`）
- Filed by: `ses_0c87bab06fferQ0umBs2Nybb5U`（platform owner；在 §O 之後做全 repo facade 可達性盤查時順手發現）
- Family: `control.quality.no-silent-degradation`（**V5** 判決未帶產生它的預算/基準）
- Fix venue: `/home/pkcs12/projects/bodesign`
- Priority: 中——不擋任何進行中工作，但下游是**採購**，誤讀代價是缺料

---

## 症狀

`export_bom(schematic_path, out_dir)` 的預設值 `exclude_dnp=True` 會把 DNP（Do Not Populate）料**從 BOM 中移除**：

```python
# packages/eda-bridge/bodesign_eda_bridge/bom_export.py:68-69
if exclude_dnp:
    cmd.append("--exclude-dnp")     # 真實傳給 kicad-cli 的旗標
```

而 `BomResult` 的欄位是：

```python
# bom_export.py:21-28
status: str
csv_path / xlsx_path / netlist_path: str | None
line_count: int          # 排除「之後」的行數
component_count: int
warnings: list[str]
```

**沒有任何欄位說明「排除了什麼」或「排除了幾筆」。**

## 為什麼這是缺陷

呼叫端拿到一份 BOM 與 `line_count=42`，**無法從回傳分辨**：

- 這塊板就是 42 個零件；
- 還是有 5 個 DNP 料被靜默濾掉，實際 47 個。

兩者的 `status="ok"`、`line_count=42` **完全相同**。這正是本 control 的 invariant 判別句：

> **呼叫端只讀一個數就會得出錯誤結論 = 違反。**

DNP 的語意本身讓它更危險：DNP 料通常是**刻意不焊但保留 footprint** 的選配／除錯／替代件。它在板上有 footprint、有 pad、佔面積，只是不上件。一份「乾淨」的採購 BOM 確實不該包含它們——**所以預設值 `True` 是對的**，錯的是「排除這件事沒有留下痕跡」。

下游是採購。若有人拿這份 CSV 直接下單，DNP 料不會出現在缺料清單上——而它們的 footprint 仍在板上，後續要補焊時才發現從未被叫料。

## 這與 §J / V5 是同一形狀

`autoroute` 的 `unconnected` 曾經同時是「板子的屬性」與「搜尋預算的屬性」，修法是 echo `passes_limit`。這裡的 `line_count` 同時是「板子有幾個零件」與「過濾規則排除了多少」，修法對稱：

| §J | 本件 |
|---|---|
| `unconnected` 不帶 `passes_limit` | `line_count` 不帶 `exclude_dnp` 與被排除清單 |
| 判決未帶產生它的**搜尋預算** | 判決未帶產生它的**過濾規則** |

## Fix proposal

1. **回傳 `exclude_dnp` 的實際值**（呼叫端傳的、或預設的）——判決帶著產生它的規則。
2. **回傳被排除的 refs 清單**（`excluded_dnp: [refs]`），比照 `plane_layers_applied` / `removed_stubs` 的 positive pattern：**呼叫端能稽核到底排除了什麼，而不是相信一個計數**。
   - 取得方式：以 `exclude_dnp=False` 再跑一次 kicad-cli 取全集後做差集，或直接解析 schematic 的 DNP 屬性。前者簡單但多一次 CLI 呼叫；後者需要 schematic 解析。**實作前需量測 kicad-cli 的成本**。
3. **facade 暴露 `exclude_dnp`**（目前 schema 未宣告，見下），且 description 明說預設會排除 DNP 料。

## 附帶：facade 可達性（§O 同族，但這筆是 by-design 邊界待裁）

全 repo 盤查（`services/mcp/server.py` 的 handler ↔ 目標函式簽章 AST 對照）顯示 13 個工具有「目標函式參數在 facade 上觸及不到」。**逐筆取證後只有本件符合 §O 的形狀**，其餘均為合理設計：

| 工具 / 參數 | 判定 |
|---|---|
| `api_key`（c01 concept image） | **絕不該進 schema**（憑證） |
| `kicad_skill` / `emc_skill` / `spice_skill` | 內部引擎路徑覆寫，非呼叫端旋鈕 |
| `footprint_dir`（emit_layout） | facade 已用 `fpdir` / `fp_dirs` 暴露，**只是名字不同**，非不可達 |
| `columns` / `page_scale` / `macro_compact` … （compose 11 個） | 排版旋鈕；省略只是用預設樣式，不改變電氣判決 |
| `ps_per_mm` / `z0` / `rs`（si_check） | **已有 `effective` 回傳實際採用值**——正是 §J 的 positive pattern |
| `mpns` / `repo` / `category_of`（materialize_model_cards） | 內部呼叫鏈，非 MCP 入口 |
| `exclude_dnp`（export_bom） | **本件** |

**這個盤查本身值得記**：13 筆裡 12 筆是合理設計。若把「參數沒暴露」當成缺陷判準直接報 13 筆，就是 cry-wolf——正確判準是 §O 的形狀：**省略它會靜默停用一條驗證規則、或改變交付物內容**。

## Explicitly NOT bugs

1. **`exclude_dnp=True` 這個預設值本身沒錯**。乾淨的採購 BOM 不該含 DNP 料。缺陷是排除沒有留下痕跡，不是排除。
2. **`si_check` 的 `ps_per_mm` 等參數未進 schema 不是缺陷**——它 echo `effective`，呼叫端讀得到實際採用值。這是正解，不是漏洞。
3. **`api_key` 未進 schema 是資安要求**，不得「修正」。

## Validation plan

1. 建一份含 DNP 料的 schematic fixture。
2. `export_bom` 預設呼叫 → 斷言回傳帶 `exclude_dnp=True` 與非空 `excluded_dnp` 清單，且清單內容與 fixture 的 DNP refs 逐筆相符。
3. **反向鑑別力**：`exclude_dnp=False` → `excluded_dnp` 必須為空且 `line_count` 增加對應筆數。少了這條，一個恆回空清單的實作會通過上一條。
4. 無 DNP 料的 schematic → `excluded_dnp` 為空但欄位仍存在（**「沒有東西被排除」與「沒有檢查」必須可分辨**）。

## 實作發現（三條 RCA 推不出來的事）

RCA 只憑讀碼寫成，實作時三條都被實測推翻或補足。**這正是「fix proposal 不等於 fix」的實例**——提案說「取得方式：跑兩次做差集，或解析 schematic。實作前需量測成本」，而真正的答案兩者都不是。

### 1. `${DNP}` 是 kicad-cli 內建欄位替換（RCA 沒看到的第三條路）

`kicad-cli sch export bom --help` 列出 `${DNP}` 與 `${EXCLUDE_FROM_BOM}` 兩個欄位替換。所以不需要解析 schematic，也不需要「跑一次含 DNP 再做集合差」——直接請 kicad-cli 自報每個 refdes 的旗標即可。

### 2. 分組會污染旗標，所以稽核**必須** ungrouped（決定性實測）

這條若沒實測就會寫出一個會誣告零件的實作：

```
R1 = 10k 正常   R3 = 10k 且 DNP   --group-by Value
→ "R1,R3","10k","2","DNP"        ← 整組繼承 DNP 旗標
```

**在分組輸出上做事後過濾，會把已出貨的 `R1` 報成「被排除」**——送人去重複下單一顆本來就在板上的料。故稽核走**獨立的第二次 ungrouped pass**（`--group-by ""` + `--include-excluded-from-bom`，不排除任何東西）。實測成本 **~260ms/次**，對一份採購文件而言，正確點名遠比這個代價值錢。

### 3. 還有**第二條**靜默排除，而它從未被任何地方提過

RCA 只寫了 DNP。實測發現 `in_bom no`（Excluded from BOM）的零件**同樣從預設 BOM 消失**：

```
R9 標記 in_bom=no  →  預設 export_bom 輸出裡 0 命中
--include-excluded-from-bom 是 opt-IN（預設關閉）
```

兩條規則的方向還相反——`--exclude-dnp` 是 opt-out（我們主動加旗標），`--include-excluded-from-bom` 是 opt-in（我們不加，於是預設就在排除）。**後者更隱蔽：它不需要任何人做決定就在濾東西。**

### 4. power symbol 不會污染清單（但這是 kicad-cli 的行為，不是我的保證）

每張 schematic 都有一堆 `#PWR`/`#FLG`，全部 `in_bom=no`。若它們進入 `excluded_from_bom`，真實板上的清單會是幾十個 power flag 埋著一顆真正被省略的料——**一份沒人讀的清單就是 cry-wolf**。實測 kicad-cli 9.0.9 在 exclude-from-BOM 階段**之前**就濾掉 power symbol，故清單乾淨。已用測試釘住：這是上游行為，未來版本若改變，我要立刻知道。

---

## Reporter 提供的 fleet 事實（我讀碼推不出來的那塊）

BR filed 時我寫「對 DNP 在此 fleet 的採購語意沒把握」。reporter（`ses_073a93d09ffeRTpR9TwIdofhb3`）round=15 給了答案，而它**推翻了本 BR §症狀 的隱含前提**：

> 這個 fleet 的「不上件」根本不走 schematic 的 `dnp` 屬性，走的是 BOM 的 `qty=0` + `block` 文字。

實測：`03.aiguard` 全域 `dnp` 屬性 **0 個**、`export_bom` 呼叫 **0 處**；唯一的「不上件」料 `MIC1_ALT` 是 `qty=0`，且**在 schematic 裡完全不存在**（generator 沒畫它）——不是 §症狀 說的「有 footprint、有 pad、只是不上件」。

**這對修法有一個具體後果**：在他們的真實輸入上，`excluded_dnp` 永遠是空的，**而空是正確答案**。所以 Validation plan 第 4 條（「沒有東西被排除」必須與「沒有檢查」可分辨）不是邊角案例，**是他們唯一會走到的路徑**。若只實作前三條，那條路徑會零覆蓋。`exclusion_audit` 欄位正是為此而存在，並已有專屬測試。

### 交叉引用：`qty_zero` 豁免遮住了另一個維度的分歧（不在本 BR scope）

reporter 同時指出一個**我不主張現在修**的觀察，但值得記：

兩套「不上件」編碼並存——schematic 的 `dnp` 屬性 vs BOM 的 `qty=0`——而沒有任何 gate 對照它們。`check_c03` R5 的 `exempted: {qty_zero: [MIC1_ALT]}` 豁免**發得完全正確**（qty=0 的料本來就不該要求它被畫），但那個正確的豁免恰好把兩套編碼的分歧吸收掉了。

> 這是本家族唯一「豁免正確、但豁免本身遮住了另一個維度的分歧」的實例。
> 不同於 §Q（豁免發錯、可控靜音），這個豁免發對了，遮住的是**別的東西**。

修它需要 fleet 級「不上件語意 SSOT」裁決（該用 `dnp` 屬性還是 `qty=0`），那是產品決定，不是平台能裁的。reporter 已在 aiguard 側記為待裁項。

---

## 修法（已實作）

| 項 | 內容 |
|---|---|
| echo 規則 | `exclude_dnp` / `include_excluded_from_bom` 回傳實際生效值 |
| 點名傷亡 | `excluded_dnp` / `excluded_from_bom` 列出每個被移除的 refdes |
| 可分辨「沒排除」與「沒檢查」 | `exclusion_audit`：`"run"` / `"failed:<reason>"`。稽核失敗時**不回空清單**，改發 loud warning 說「UNKNOWN, not empty」 |
| 只報本次真的排除的 | `exclude_dnp=False` 時 `excluded_dnp` 為空——否則就是對「要求保留這些料」的呼叫端謊報 |
| warning 帶計數脈絡 | `line_count=N counts only what survived` 與傷亡清單並列 |
| facade | schema 暴露兩個參數 + handler 轉發（**§O 同族：不轉發等於兩條過濾規則對每個 MCP 呼叫端都是無條件的**） |

## 驗證

| 項 | 結果 |
|---|---|
| `tests/test_bom_export.py` | **14/14**（原 3 + 新 11） |
| `test_compose_facade_arg_encoding` + `test_check_c03_...` | 86/86 |
| `test_mcp_server` | 5 筆與已坐實 HEAD 基線同名同數 |
| 部署 | pid1 `04:42:10Z` > 最後 mtime `04:41:26Z` |
| facade 真 client 三態 | 預設 → `excluded_dnp=['R3']` / `excluded_from_bom=['R9']` / `audit=run`；兩參數皆反轉 → `line_count` 2→3、兩清單皆空、零 warning |

測試含四條反向鑑別力：fixture 本身真的被 kicad-cli 過濾、關閉規則後不得謊報、稽核失敗不得讀成乾淨、power symbol 不得污染清單。

## Source evidence

- `packages/eda-bridge/bodesign_eda_bridge/bom_export.py:44-53`（簽章）、`:68-69`（旗標）、`:21-28`（`BomResult` 欄位）、`:74`（`line_count` 取自排除後的 CSV）
- `services/mcp/server.py` — `bodesign_export_bom` 的 schema 未宣告 `exclude_dnp` / `fields` / `labels`

## Related

- `BR_20260730b` §O — facade 可達性（本件由該盤查發現，但屬不同關注點）
- `BR_20260729` §J — 判決必須帶著產生它的預算（同一 invariant 的前一個實例）
- `ragbase/control/no-silent-degradation/README.md` — V5 變體
