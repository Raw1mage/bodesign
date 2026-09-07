# Observability: eda-bridge_multi-sheet-subsystem-schematics

## Events

- `sheet_partition.entered` — `partition_components` 進入時無條件排放。**這是分支入口計數器，不是結果欄位**：沒有它，`empty`（跑了、沒東西分）與 `not-run`（根本沒開多紙模式）共用同一個空 `SheetMap`。
- `sheet_partition.result` — 帶 `partition_source`（`declared` / `none-declared`）、`sheets_n`、`unassigned_n`。三欄合起來才分得出 ok / empty / failed。
- `emit_hierarchical.mode` — `multi` / `single-legacy`。N=1 走原路徑時排放 `single-legacy`，讓「多紙模式沒生效」與「輸入本來就只有一紙」不共用輸出。
- `emit_hierarchical.files_written` — 逐檔絕對路徑。`files` 清單的唯一真相來源；repo 天條 §2.2 要求它與磁碟逐一相符。
- `crosssheet_link.scan_ran` — 布林。**與 `linked_nets` 分開排放**：`linked_nets=[]` 且 `scan_ran=True` 是「沒有 net 跨紙」；`scan_ran=False` 是「根本沒掃」。
- `crosssheet_link.arbitration` — `ok` / `unavailable`。`kicad-cli` 不可用時排放 `unavailable`，連通性記為 **indeterminate 而非 ok**。
- `policy_scope.evaluated` — 布林 + `scope` 值。政策 sheet-aware 分支的入口計數器。

## Metrics

- `sheets_emitted` — 產出的葉檔數。真板母體為 3。
- `components_per_sheet` — 逐紙元件數。真板母體：power 22 / mcu 9 / io 14，Σ=distinct=45。
- `crosssheet_nets` / `global_labels_emitted` — 跨紙 net 數與放出的 global_label 數。真板母體：`18 = Σ(每條 net 跨幾張紙)`（K2），所以這兩個數字有可導出關係，不是巧合。
- `wire_geom_sha_single` — N=1 時的幾何雜湊。**AC-2 的判準**：必須與 HEAD 逐字相同。
- `policy_labelled_nets_per_sheet` — 逐紙被政策標為 label 的 net 數。K9 母體：全圖 13 條（單紙 9 / 跨紙 4）。

## 讀數紀律（跨包繼承）

**每個指標在報告時必須帶母體宣告**：哪個構法（with-group / no-group）、政策 ON 或 OFF、
分紙或整圖。母體不同的數字不可互相比較——舊包 `errors.md` §369-470 記錄了五格因此失效的讀數。

### 這條紀律的來源（實例，不是儀式）

**round 35 拿「分紙 + 政策 ON = 8 條交叉」去比 `M6-8d` 聲稱的「12+ 條無序交叉」，
並據以得出「切紙後交叉守恆」。那個比較無效，round 36 才發現：**兩邊的母體不同**。**

| | 它數的是什麼 |
|---|---|
| 那個 **8** | 政策仍生效的狀態下紙上的交叉數——**`M6-8d` 攞下的線一條都沒畫** |
| `M6-8d` 的 **12+** | 把 cross-IC **改成畫線之後**產生的交叉數 |

兩者相差的正是「那些線有沒有被畫出來」——**`M6-8d` 擔心的東西在那個量測母體裡根本不存在**。
round 37 在對齊的母體上重量（B 整圖+政策OFF=83 vs C 分紙+政策OFF=66），
結論對調：**多 sheet 不解決交叉問題。**

> **所以本節不是文件義務。** 一次漏寫母體宣告，換來的是一個方向相反的結論、
> 及兩輪的重量成本。參見 `design.md` K12。
