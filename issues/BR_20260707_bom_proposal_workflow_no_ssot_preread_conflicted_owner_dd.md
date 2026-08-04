# BR: BOM 提案工作流缺 SSOT 必讀清單——提案與既有 owner 裁決衝突未被攔截，誤寫入 BOM 一輪

- **Status**: FIXED — 三項 acceptance criteria 已全數落地（見文末「2026-08-04 覆核」）
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

### 未量（不得讀成已驗）

**沒有端對端跑證**——三條都是「章節與 verb 存在且內容對應」，
**未實跑一次「提交一份與 SSOT 衝突的 BOM」看 `check_c03` 是否真的回 `gate=FAIL`**。
故本張標 FIXED 是對「修法已實作」而非「修法已證實有效」。
若日後發現閘攔不住，那是新的缺陷而非本張回退。
