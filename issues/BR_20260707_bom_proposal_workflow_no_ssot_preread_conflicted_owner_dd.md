# BR: BOM 提案工作流缺 SSOT 必讀清單——提案與既有 owner 裁決衝突未被攔截，誤寫入 BOM 一輪

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
