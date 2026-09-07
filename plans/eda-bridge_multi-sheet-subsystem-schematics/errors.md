# Errors: eda-bridge_multi-sheet-subsystem-schematics

## Outcome Codomain

每個功能模組宣告它**完整**的結束狀態集合。`ok` / `failed` / `not-run` 是裸 status 會塌在
一起的三格，必備；`empty` 與 `indeterminate` 必須表態（給值，或明寫 `n/a (<理由>)`）。
每個狀態指名它的排放點——沒人排放的狀態是註解。

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| `sheet_partition` | `SheetMap{name: [refs]}` 非空 | ok | 每顆元件恰好分到一張紙 | `partition.py::partition_components` 回傳值 |
| `sheet_partition` | `E_UNASSIGNED_REFS` | failed | 有元件不屬於任何已宣告子系統 | 同上，raise + ref 清單 |
| `sheet_partition` | `E_REF_ON_MULTIPLE_SHEETS` | failed | 同一 ref 出現在 >1 張紙（違反 K3 嚴格 partition） | 同上，raise + ref 清單 |
| `sheet_partition` | `SheetMap` 恰 1 張、名為 `__single__` | empty | spec 未宣告任何分派 ⇒ 退回單張紙語意（**不是錯誤**，是 N=1 路徑） | 同上，`partition_source="none-declared"` 欄位 |
| `sheet_partition` | 不呼叫（`multi_sheet=False`） | not-run | 呼叫端未開啟多紙模式 | `composer.compose_schematic` 的 `multi_sheet` 分支入口計數器 |
| `sheet_partition` | `n/a (純函式，輸入決定輸出)` | indeterminate | 無外部依賴、無時序，不存在「跑了但判不出來」 | n/a |
| `emit_hierarchical` | `files=[root, leaf…]` 長度 N+1 | ok | root 與每張葉檔都已寫出且在磁碟上存在 | `kicad_emit::emit_hierarchical_schematic` 回傳 `files` |
| `emit_hierarchical` | `E_LEAF_WRITE_FAILED` | failed | 某葉檔寫入失敗 | 同上，raise + 失敗路徑 |
| `emit_hierarchical` | `E_ROOT_SHEET_BLOCK_INVALID` | failed | root 的 `(sheet …)` 缺必填欄位 | 同上，raise + 缺欄清單 |
| `emit_hierarchical` | `files=[single]` 長度 1 | empty | N=1，走原單檔路徑（**byte-stable**，見 AC-2） | 同上，`emit_mode="single-legacy"` 欄位 |
| `emit_hierarchical` | 不呼叫 | not-run | `sheet_partition` 回 `not-run` 或 `failed`，未進入 emit | `composer` 的 emit 分支入口計數器 |
| `emit_hierarchical` | `n/a (寫檔成敗二元)` | indeterminate | 檔案寫出與否由 OS 回報，無第三態 | n/a |
| `crosssheet_link` | `linked_nets=[…]` 非空 | ok | 每條跨紙 net 在其跨到的每張紙上都放了同名 global_label | `kicad_emit` 跨紙 label 佈放迴圈出口 |
| `crosssheet_link` | `E_LABEL_NAME_COLLISION` | failed | 兩條不同 net 產生同名 global_label（會靜默短路） | 同上，raise + 兩 net 名 |
| `crosssheet_link` | `linked_nets=[]` | empty | 沒有任何 net 跨紙（全部單紙）——**與 not-run 必須分開** | 同上，`crosssheet_scan_ran=True` 旗標 |
| `crosssheet_link` | 不呼叫 | not-run | 單張紙模式，無跨紙概念 | 同上，`crosssheet_scan_ran=False` |
| `crosssheet_link` | `E_NETLIST_ARBITRATION_UNAVAILABLE` | indeterminate | `kicad-cli` 不可用 ⇒ 連通性**未被仲裁**，不得報 ok | 驗證層，回 `indeterminate` 而非 `ok` |
| `policy_scope` | `scope="sheet"` 生效，逐紙 label_nets | ok | 政策判定範圍已降到 sheet 層級 | `composer.py` 政策段的 scope 分支入口計數器 |
| `policy_scope` | `E_SCOPE_UNKNOWN` | failed | 傳入非 `whole`/`sheet` 的範圍值 | 同上，raise |
| `policy_scope` | `label_nets=set()` | empty | 該紙上沒有任何 net 命中三條政策 | 同上，`policy_evaluated=True` 旗標 |
| `policy_scope` | 不呼叫 | not-run | `scope="whole"`（現況預設），未進 sheet 分支 | 同上，`policy_evaluated=False` |
| `policy_scope` | `n/a (純判定，無外部依賴)` | indeterminate | 判定只讀 spec 與 pin count | n/a |

> **「進行中」狀態不存在**：四個模組都是同步純轉換或一次性寫檔，無長時任務，
> 故不需要單調新鮮度戳記。

> **排放點紀律**：上表每一格的 `not-run` 都指名一個**分支入口計數器**，不是結果欄位。
> instrument 結果只包得住已經會被呼叫的東西；instrument 分支才分得出「沒走」與「沒接上」。
> （舊包 `errors.md` ⑦ 記錄了這格失效的實例。）

## 判準（自舊包複製，因為本包已經踩到）

### 「踩到政策」與「因為政策而沒被畫」是兩件事

一張「哪些 net 命中了哪條政策」的表，**只能證明命中（相關），不能證明因果**。
一條 net 可以同時命中政策、而它沒被畫出來的真正原因是別的。

**本包已經發生這件事，不是預防性複製**：

| 位置 | 寫了什麼 | 問題 |
|---|---|---|
| `test-vectors.json:95` | 「ENPPB 已知因 anti-fusion 而非政策而未畫」 | 正確 |
| `design.md` K9 | 把 `ENPPB` 列入「9 條單紙 net（多 sheet 下有機會改畫線）」 | **同一個包裡兩個不一致的叙述** |

`ENPPB` 確實命中 cross-IC 政策，但 round 30 的 POLICYOFF 控制組已證：
**政策全關之後它仍然是 0 段** ⇒ 它沒被畫的原因是 anti-fusion，不是政策。
所以把它算進「改政策就能畫出來」的名單是錯的。

- **控制組的形狀**：要宣稱「X 因為政策 P 而沒被畫」，必須把 **P 關掉**再量一次；
  X 仍為 0 ⇒ 原因不是 P。光看「X 在 P 的命中名單裡」永遠不夠。
- **適用範圍（本包）**：(e) 要拿「哪些 net 可以改畫線」去問使用者，
  **那張名單必須是成因名單不是命中名單**，否則改完政策會發現幾條根本沒動。
- **來源**：舊包 `label-policy-for-user-ruling.md:68`。
  那裡是政策表的自我限制，這裡是驗收名單的組成規則，**兩邊都承重**。

## Error Catalogue

上表 `failed` 區的細節。

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `E_UNASSIGNED_REFS` | 元件不屬於任何已宣告子系統 | `ValueError`，訊息列出全部未分派 ref | 呼叫端補 `group`/`sheet` 欄，或明確宣告一張 catch-all 紙（**不得由引擎代為決定**） |
| `E_REF_ON_MULTIPLE_SHEETS` | 同一 ref 分到 >1 張紙 | `ValueError`，列出重複 ref 與它們的紙 | 修正 spec；K3 已證真板是嚴格 partition，重複即缺陷 |
| `E_LEAF_WRITE_FAILED` | 葉檔寫入失敗（權限／磁碟） | `OSError` 包裝，帶失敗路徑 | 檢查 `out_dir`；**不得留下半套檔組**，失敗時清除已寫出的檔 |
| `E_ROOT_SHEET_BLOCK_INVALID` | root `(sheet …)` 缺必填欄位 | `ValueError` + 缺欄清單 | 對照真板 root 逐欄補齊（欄位來源見 `design.md` DD-3） |
| `E_LABEL_NAME_COLLISION` | 兩條不同 net 產生同名 global_label | `ValueError` + 兩 net 名與所在紙 | 這是**靜默短路**的來源，必須 fail-fast；修正 net 命名 |
| `E_SCOPE_UNKNOWN` | 政策範圍值非 `whole`/`sheet` | `ValueError` | 呼叫端傳合法值；**不得靜默退回 `whole`**（repo 天條 §2.1） |
| `E_NETLIST_ARBITRATION_UNAVAILABLE` | `kicad-cli` 不存在或匯出失敗 | 回 `indeterminate`，**不是** `ok` | 安裝 kicad-cli 後重跑；在它可用前，跨檔連通性是**未驗證**而非**已驗證** |
