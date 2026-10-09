# BR: BOM 提案工作流缺 SSOT 必讀清單——提案與既有 owner 裁決衝突未被攔截，誤寫入 BOM 一輪

- **Status**: PARTIAL — criteria ①② 已落地；③ 機器兜底在生產 SSOT 形狀下 inert（見 §端對端跑證 2026-08-05）
- Date: 2026-07-07
- Severity: medium-high
- Component: bodesign skill `stages/c03-ee` GUIDE + BOM 提案委派模板
- Reporter: thesmart_products session（aiguard C03）

## Symptom

`BOM_定案提案_v01` 對 U4 提出 Murata LBEE5KL1YN 模組候選，與**前一日** owner DD-2（nRF7002 + MDBT53-P1M 雙晶片於 CCM，rockbox 實證 U801/U-MOD）互斥，且牴觸以雙晶片於 CCM 為前提的 72-pad 凍結。主 agent 首輪 review 也未攔截，誤寫入 BOM 一輪後，才在讀 `Pin_Allocation.csv` 時發現衝突，需使用者再次裁決撤回。

## Root Cause

1. 提案子棒的 dispatch prompt **沒有強制必讀** `Pin_Allocation.csv`（SSOT）、既有 DD、凍結精算表——子棒冷 context 只憑 deck + BOM csv 提案
2. **無機器交叉核對**提案 vs SSOT——人工 review 是唯一防線，且本次失效

## 建議修法（acceptance criteria）

1. `stages/c03-ee/GUIDE.md` 增「BOM 提案必讀清單」：`Pin_Allocation.csv`、既有 DD / 凍結表、event log 近期裁決（`event_search`）
2. 提案產出格式**強制附「SSOT 衝突自查」段**：逐項宣告 checked / 無衝突 / 有衝突待裁決——缺此段的提案視為不完整
3. 機器面由姊妹 BR 的 `check_c03` 閘交叉核對兜底（縱深防禦：上游 preread + 下游 gate）

## Evidence

- thesmart_products event：`aiguard-c03/event_2026-07-07_u4-lbee5kl1yn-owner-dd-2-nrf7002-mdbt53-ccm-j-x-ow_a0jd5z`（衝突發現、撤回、零連鎖重算全記錄）

## 關聯

- `BR_20260707_c03_stage_entry_gate_missing_machine_readiness_check_before_c04.md`

---

## 2026-08-04 覆核（by `ses_04db7a1c5ffelvbxyLP1p6xlRH`）

**本檔原本沒有 Status 行**——不是寫成別的格式，是真的一行都沒有
（控制組：40 張頂層 BR 裡 37 張含 `status` 字樣，這張是三張例外之一）。
此缺口已另行建檔為 `BR_20260804l`（`issues/` 帳本沒有 Status schema）。

三項 acceptance criteria 逐條驗證（我親手跑，非採信轉述）：

| criteria | 現況 | 證據 |
| --- | --- | --- |
| ① GUIDE 增「BOM 提案必讀清單」 | 已落地 | `skills/bodesign/stages/c03-ee/GUIDE.md:222` 「### 3c. BOM 提案必讀清單 + SSOT 衝突自查段（MANDATORY，先讀後提）」 |
| ② 強制附「SSOT 衝突自查」段 | 已落地 | 同檔 `:250` 「BOM 交付必附「SSOT 衝突自查」段（固定格式、逐項填、不得留空）」 |
| ③ 下游機檢兌底 | 已存在 | `skills/bodesign/scripts/gate.py:232` `check_c03` ・`:239` `prd_bom_crosscheck` |

**控制組**：同一支 grep 對假 section `ZZZNOSUCHSECTION` 回 0、對假 verb `"check_c99"` 回 0
⇒ 上述非零命中不是 grep 恆真。

### ~~未量（不得讀成已驗）~~ **本節已被取代——見 §「端對端跑證（2026-08-05，獨立驗證員）」**

> **2026-08-05 SUPERSEDED**：本節列為「未量」的那一項——端對端跑一次衝突 BOM 看 `check_c03` 是否真的回 `gate=FAIL`——**已補跑完成**，結論見 §「端對端跑證（2026-08-05，獨立驗證員）」：criteria ③ 判 **STILL-BROKEN**，且根因不是 R4 有 bug，而是**它永遠不執行**（真實 `Pin_Allocation.csv` 為 ball/peripheral 形狀、無 `ref` 欄 ⇒ `_load_pin_alloc_refs()` 回 `None` ⇒ R4 整條 `not_run`，而 `GUIDE.md:230-238` 裁決無 ref 欄才是交付物合約的正常形狀）⇒ 縱深防禦第二層在生產輸入上 **inert**。
> 保留原文不刪：「當時未量」這個事實本身是方法論證據。
> **但不要停在本節就下結論**——本節末句「若日後發現閘攔不住，那是新的缺陷而非本張回退」已被下節推翻：閘確實攔不住，且那正是本張 criteria ③ 的問題。

### 未量（不得讀成已驗）

**沒有端對端跑證**——三條都是「章節與 verb 存在且內容對應」，
**未實跑一次「提交一份與 SSOT 衝突的 BOM」看 `check_c03` 是否真的回 `gate=FAIL`**。
故本張標 FIXED 是對「修法已實作」而非「修法已證實有效」。
若日後發現閘攔不住，那是新的缺陷而非本張回退。

> **⚠ 2026-08-05：緊接在上的那一句已被推翻，不得單獨引用。**
> 端對端跑證顯示**閘確實攔不住**（criteria ③ 判 STILL-BROKEN），
> 且那正是本張 criteria ③ 的問題、**不是新缺陷**。
> 見本檔 §「端對端跑證（2026-08-05，獨立驗證員）」。
> 原句保留不刪：「當時這樣判」本身是方法論證據，但它的結論已作廢。

---

## 端對端跑證（2026-08-05，獨立驗證員）

上一節列為「未量」的那一項——**實跑一次「提交一份與 SSOT 衝突的 BOM」看 `check_c03`
是否真的回 `gate=FAIL`**——本輪補跑完成。結果推翻 criteria ③ 的有效性宣稱。

### 決定性結果

把本 BR Symptom 段的原始情境（U4 = Murata LBEE5KL1YN，注入真實 aiguard BOM）
直接餵給 `check_c03`：

| 量到的欄位 | 值 |
| --- | --- |
| `gate` | `PASS` |
| blocking codes | `[]` |
| U4 findings | `[]` |
| ssot status | `not_run` |

**本 BR 記錄的那一次真實事故，餵回下游閘，閘放行。**

### 根因

`check_c03.py:958-985` + `:1158-1171`。

真實的 `experiments/aiguard_c03_verify/Pin_Allocation.csv` 是 ball/peripheral 形狀，
header 為：

```
peripheral,function,interface,net_group,rail,ball_assignment,provenance,deck_status
```

**沒有 `ref` 欄** ⇒ `_load_pin_alloc_refs()` 回 `None` ⇒ R4 整條標 `not_run`，
26 個 active 件全部列入 `active_parts_unverified`。

而 `GUIDE.md:230-238` 明白裁決：**無 ref 欄的形狀才是交付物合約的正常形狀。**
所以這不是「某次資料填錯」，是合約規定形狀與閘的讀取前提互斥。

### 三組控制組

| 控制組 | 結果 |
| --- | --- |
| 合成 ref-bearing pinmap（只含 U1/U2）vs 乾淨 BOM | `gate=FAIL`, R4=24 筆 ⇒ R4 程式碼本身會開火 |
| 合成 ref-bearing pinmap（含全部 26 個真實 active ref）vs 乾淨 BOM | `gate=PASS`, R4=`[]` ⇒ 非恆真 FAIL |
| 同上 pinmap vs 注入 U4 衝突 BOM | `gate=FAIL`, R4=`[('U4','active part not in Pin_Allocation.csv SSOT…')]` ⇒ 有判別力 |

**決定性對比：同一顆 U4 衝突，餵 ref-bearing pinmap → FAIL；餵 repo 真實 pinmap → PASS。
差別 100% 來自 SSOT 檔案形狀，不是 BOM 內容。**

### 口徑聲明（不得改寫成別的意思）

這**不是**「R4 邏輯有 bug」——R4 邏輯經上表控制組證明正確且有判別力。

正確讀法是：**R4 在合約規定的 SSOT 形狀上永遠不執行，所以本 BR 的機器兜底
（criteria ③）在生產輸入上是 inert 的。**

它也**不是靜默假綠**——`not_run` + `active_parts_unverified` 有誠實揭露。
但縱深防禦的第二層在真實輸入上結構性失效，
**唯一有效防線仍是 ①② 的人工 preread。**

### 未量（不得讀成已驗）

- MCP server 路徑 / `gate.py` CLI wrapper **未驗**（本次直接呼叫 `check_c03`）。
- criteria ② 是 agent 行為，結構上無法端對端驗。
- `tests/test_check_c03*.py` **只看通過數，未讀 case 內容**。
- fleet 另 3 份 `Pin_Allocation.csv` 不在本 repo，未取得、未量。
- R5-R8 一律 `not_run`（未帶 netlist）；**本次口徑只涵蓋 R4。**

### 附帶揭露缺陷（本輪順手量到）

原 Status 行寫 `FIXED — 三項 acceptance criteria 已全數落地`，
而**同一份文件文末（:55 附近）自承「未證實有效」**。

只讀 header 的人會取得比實際更強的宣稱——這一格資訊系統當下就有，
只是被 header 蓋掉了。本次已把 Status 改為 PARTIAL 消除這個落差。

