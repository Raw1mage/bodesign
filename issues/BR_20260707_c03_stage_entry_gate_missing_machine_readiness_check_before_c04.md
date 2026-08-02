# BR: C03→C04 缺 stage-entry 機檢閘——C03 準備不齊即進 C04，全靠下游衝撞試誤才暴露

- Date: 2026-07-07
- Severity: **high**（工業製程紀律缺口；aiguard 今日 C04 時間浪費的直接根因）
- Component: bodesign skill `stages/c03-ee` + `stages/c04-layout` 工作流
- Reporter: thesmart_products session（aiguard C03/C04）

## Symptom

aiguard 今日在 C04 燒掉大量時間，事後回溯根因是 C03 輸入不齊全就進了 C04：

- BOM 仍有 draft / blocked / UNDECIDED 列（U4 無線、J_X pad 數）
- BOM 與 `Pin_Allocation.csv` SSOT 互相衝突（U4 提案 Murata 模組 vs 既有 owner DD-2 雙晶片裁決）
- J_X pad 數已由 owner 凍結（72 pads, 2026-07-06）但 BOM 未同步，仍標 blocked

這些缺口**沒有任何機器閘在 C04 入口擋下**，全靠下游撞牆逐一暴露。

## Root Cause

bodesign 生命週期只有 C04 **產出**閘（`check_c04.sh`：copper / unconnected / unmapped / SI hard-fail），**沒有 C04 入口閘**檢查 C03 交付物完備性。C03 readiness 目前是純人工判斷——違反「缺少條件不往下推進」的工業製程紀律。

## Evidence

- thesmart_products event log（scope `aiguard-c03`, 2026-07-07）：U4 誤寫/撤回、J_X blocked→finalized 補同步、BT1 CSV quoting latent 缺陷
- `thesmart_products/03.aiguard/C03-EE/03_input/check_bom.py`：本次臨時自建的最小 BOM 機檢（R1–R5），**首跑即抓到 U4A/U4B（nRF7002/MDBT53）symbol 來源未取證**——證明機檢閘可行且必要

## 建議修法（acceptance criteria）

在 bodesign skill 增 `check_c03`（sh 或 python），C04 任何 build 入口強制先跑，hard-fail 條件：

1. **BOM schema lint**：欄數一致（quoting 破損即抓）/ status enum / board+ref 唯一
2. **BOM readiness**：0 draft / 0 blocked；finalized 列 mpn 禁含 TBC/TBD/UNDECIDED
3. **可繪性**：每列須有 symbol 來源標記（official / vendor+LCSC id / manual / N-A）
4. **SSOT 交叉核對**：BOM 主動件 ↔ Pin_Allocation.csv 無衝突（無線/介面方案一致）；J_X pad 數與凍結精算表一致
5. warn（不擋）：現貨=0、機構型號 TBC 等採購層註記

比照 `check_c04.sh` 先例（AGENTS.md §3 floating-PSRAM false-pass 教訓）：**閘門值禁止為過關而放寬**。

## 關聯

- 姊妹 BR：`BR_20260707_bom_proposal_workflow_no_ssot_preread_conflicted_owner_dd.md`（提案工作流缺必讀清單——上游預防；本 BR 是下游兜底）
- `BR_20260707_ccm_workflow_bypasses_webdav_cache_docker_exec_gdrive_entanglement.md`（同日、同一 C03 工作流的傳輸面缺陷）
