# BR: C03→C04 入口閘只問「C03 跑過嗎」不問「C03 交付合格嗎」——C03 準備不齊即進 C04，全靠下游衝撞試誤才暴露

- Date: 2026-07-07（Root Cause 於 2026-08-02 重寫——原文前提已過期，見下）
- Severity: **high**（工業製程紀律缺口；aiguard 當日 C04 時間浪費的直接根因）
- Component: `packages/workflow-core/bodesign_workflow_core/{c04_layout_constraints,check_c03}.py` + `stages/{c03-ee,c04-layout}` GUIDE
- Reporter: thesmart_products session（aiguard C03/C04）
- Status: **FIXED-UNDEPLOYED**（2026-08-02，`c03-stage-discipline` handler；commit ff7bbbf 已落地並經派發者覆核。**依賴未解除**：`check_c03` 尚非 landing verb，在它註冊前本閘會擋住所有既有專案，故不進 `issues/closed/`）

## Symptom

aiguard 當日在 C04 燒掉大量時間，事後回溯根因是 C03 輸入不齊全就進了 C04：

- BOM 仍有 draft / blocked / UNDECIDED 列（U4 無線、J_X pad 數）
- BOM 與 `Pin_Allocation.csv` SSOT 互相衝突（U4 提案 Murata 模組 vs 既有 owner DD-2 雙晶片裁決）
- J_X pad 數已由 owner 凍結（72 pads, 2026-07-06）但 BOM 未同步，仍標 blocked

這些缺口**沒有任何機器閘在 C04 入口擋下**，全靠下游撞牆逐一暴露。

## Root Cause（2026-08-02 重寫）

> **原文的兩個前提都已過期，且第二個前提錯得會導向錯誤的修法。以下為 HEAD 實況，每條經覆核。**

### 過期前提 ①：「只有 C04 產出閘（`check_c04.sh`）」

**`check_c04` 不存在。** 全 repo 唯一命中是 `services/mcp/server.py:1164` **它自己的 description 字串**（那句話自稱是 "the entry counterpart to check_c04's output gate"，指涉一個從未存在的東西）。控制組：同樣的 pattern 形狀對 `check_c03` 回 7 個命中，證明搜尋有鑑別力。

C04 的產出面實際由 `bodesign_layout_drc_gate` + `c04_readiness` 承擔，不是 `check_c04.sh`。

### 過期前提 ②：「沒有 C04 入口閘」——**錯，有閘，但它問錯問題**

`c04_layout_constraints.py:144` 的 `_assess_upstream_fulfilment`，於 `:321`/`:359` 被呼叫，`:369-372` 真的會擋（`status = "blocked_upstream_c03_missing"`），註解自稱 "The load-bearing fix"。

**但它只檢查三個檔案存不存在**：`C03-EE/`、`.net` netlist、`Mechanical_Constraint_Export.json`。

| | `_assess_upstream_fulfilment`（**已接上**） | `check_c03`（**未接上**） |
|---|---|---|
| 問的 | C03 **跑過嗎**（檔案在不在） | C03 **交付合格嗎**（BOM schema / readiness / drawability / SSOT） |
| 擋不擋 | 會 | 不會——零呼叫端 |
| 涵蓋本 BR 四條 AC | **零條** | 四條全涵蓋 |

**關鍵**：本 BR 的 symptom 類別（BOM 有 draft/blocked 列、與 Pin_Allocation 衝突、pad 數未同步）**發生時那三個檔案全都在**，所以閘回 `fulfilled: true` 放行。

> **一個存在檢查，站在一個合格檢查該站的位置上。**

### 真正的根因（一句話）

**不是「沒有閘」，是「C03 端的判決沒有被 C04 端消費」。**

`check_c03` 早已存在且會簽出一份確定性判決 `check_c03.report.json`（`check_c03.py:60`/`:924`，`sort_keys` 決定性，有既有測試驗 byte-identical）。C03 GUIDE 也早已把它列為必交付物 #10，並在 `GUIDE.md:507-508` 用文字寫死了 C04 的入口規則：

> the **C03 stage-entry gate PASS** (`check_c03.report.json`) — C04 entry is refused while … `FAIL` **or the gate has not run**

**這句話在修復前是純散文，沒有任何程式碼執行它。** 同一句話對 #9 `prd_bom_crosscheck.report.json`（`GUIDE.md:505-506`）同樣成立，而 `prd_bom_crosscheck` 同樣零 C04 呼叫端。**兩個閘、同一個洞。**

### 為什麼「把 `check_c03` 接上」不是接線工作

`check_c03` **無法**被 C04 入口直接呼叫——不是接線問題，是**簽章不相容**：

```
check_c03(bom_csv, *, pin_allocation_csv, netlist_path, covers_boards,
          frozen_pad_counts, out_dir)          # 六個顯式輸入
assess_c04_layout_readiness(folder, feasibility_signals)   # 只有一個 root 路徑
```

C04 入口手上只有一個資料夾路徑。要在那裡呼叫 `check_c03`，就得從資料夾**猜**哪個 CSV 是 BOM、哪些 `.net` 該當 netlist、`covers_boards` 是哪幾片板。而 `check_c03` 自己的 docstring（`:768-777`）明寫：省略 `covers_boards` 時覆蓋範圍是 INFERRED，且該推論**無法區分「沒有 netlist 涵蓋這片板」與「這片板上每一列都沒被畫」**。

**讓 C04 猜，就是為了接上一個 no-silent-fallback 的閘而在入口閘裡新增一個 silent fallback。** 依 repo 天條，這需要使用者明確批准；已提請裁決並被明確駁回。

## Evidence

- thesmart_products event log（scope `aiguard-c03`, 2026-07-07）：U4 誤寫/撤回、J_X blocked→finalized 補同步、BT1 CSV quoting latent 缺陷
- `thesmart_products/03.aiguard/C03-EE/03_input/check_bom.py`：當時臨時自建的最小 BOM 機檢（R1–R5），**首跑即抓到 U4A/U4B（nRF7002/MDBT53）symbol 來源未取證**——證明機檢閘可行且必要
- （2026-08-02 補）`check_c03` 不是 landing verb：`skills/bodesign/scripts/gate.py` 對 `check_c03` **零命中**（控制組：同檔 `grep -c "def \|verb\|c0"` → 235，證明 grep 有效）。它只活在 MCP 容器工具面（`server.py:479` handler + `:1163` schema），連「在 host 上手動跑一次」的低摩擦路徑都沒有——**這正是「沒人跑這個閘」的摩擦根因。**

## 修法（2026-08-02 實作，方案 A：producer-signs / consumer-reads）

保留 `_assess_upstream_fulfilment` 為 **tier-0**（C03 跑過嗎），新增 `_assess_c03_acceptance(root)` 為 **tier-1**（C03 交付合格嗎——讀 C03 已簽名的兩份判決）。

**C04 不重跑 C03 的閘。** 那些輸入是只有 C03 才知道的知識；重建它們等於在此植入 silent fallback。C04 只消費簽名，或拒絕。

報告路徑**釘死不搜尋**（搜尋鏈本身就是 fallback）：`C03-EE/check_c03.report.json`、`C03-EE/prd_bom_crosscheck.report.json`。找不到時的錯誤同時給出**期待的絕對路徑**與**產生它的具體指令**——避免「閘擋住了但沒人知道怎麼過」變成繞過閘的動機。

四個 status 各自可辨（每個對應不同的第一動作，永不合併成一個 `blocked`）：

| status | 意義 | 第一動作 |
|---|---|---|
| `blocked_c03_entry_gate_not_run` | 報告缺席——閘**沒跑過**，不等於通過 | 在 C03 跑它（錯誤訊息直接給指令） |
| `blocked_c03_entry_gate_report_unusable` | 報告在但壞了／無 `gate` 欄位 | 重新產生；讀不了的報告不帶任何判決 |
| `blocked_c03_entry_gate_failed` | `gate: FAIL` | 回 C03 修設計/BOM。**閘門值永不放寬** |
| `blocked_c03_entry_gate_scope_incomplete` | `gate: PASS` 但 `netlist_crosscheck.status=not_run` | 帶 `netlist_path` + `covers_boards` 重跑 |

**為什麼 PASS 仍可能被拒（且這不是 C04 擅自加嚴）**：`check_c03` 自己的 docstring（`:764-766`）聲明——沒帶 netlist 的 `gate=PASS` **"must NOT be read as 'every BOM row is drawn'"**。C04 佈局正是靠這條保證，所以 C04 不是推翻 C03 的判決，而是**拒絕把「沒檢查過」當成「檢查過且乾淨」**——那就是本 BR 的本體。`ssot_crosscheck` / `pin_polarity` 是品質訊號而非開工前提，**只 warn**（且在放行路徑上同樣附帶，因為範圍限縮在放行時與阻擋時一樣為真）。

`c03_accepted` 為三態：`None` = tier-0 已擋、tier-1 從未被詢問；`False` = 詢問過且拒絕。兩者不可合併。

## ⚠ 已知依賴（未解除前不可視為完整生效）

**本修復在 `check_c03` 成為 landing verb 之前，實務上會把所有既有專案擋在 C04 外。** 因為 `check_c03` 目前只活在 MCP 容器工具面，host 上跑不了 → 沒有人能產出通過所需的報告。

一個沒有任何人能通過的閘，不是嚴格，是把 C04 磚掉；第一個撞上的人最合理的反應會是繞過它或改回去——**閘會死在它保護的東西之前。**

`gate.py` 的 `check_c03` 註冊由派發者接管（該檔正被另一顆 handler 佔用）。**未加任何過渡期 warn-only 開關**——那會是一個新的 fallback 開關，需使用者批准。

## 驗證

- `tests/test_c04_layout_constraints.py` 新增 `C04EntryAcceptanceTests`（12 例），既有 7 例補上簽名報告 fixture 後回綠 → **19 pass**
- 迴歸 `tests.test_check_c03` + `tests.test_check_c03_gate_reachability_and_netlist` + `tests.test_readiness_invisible_path` + `tests.test_prd_bom_crosscheck` → **97 pass**
- **放行控制組** `test_signed_passing_reports_release_entry`：證明閘在證據充分時**真的會開**。缺此控制組，其餘每一條測試都可被一個「無條件拒絕一切」的閘滿足——那與焊死的閘無法區分。
- `test_tier0_passes_while_tier1_refuses`：tier-0 回 `fulfilled: true` 的同時 tier-1 拒絕——即本 BR 核心缺陷的直接複現。

## 關聯

- 姊妹 BR：`BR_20260707_bom_proposal_workflow_no_ssot_preread_conflicted_owner_dd.md`（提案工作流缺必讀清單——上游預防；本 BR 是下游兜底）
- `BR_20260730_platform_gate_unreachable_drives_consumer_fork_and_bom_netlist_gate_hole.md`（`check_c03` 的 R5/R6/`covers_boards` 語意來源；本 BR 消費其 `netlist_crosscheck.status` 契約）
