# Handoff: quality_verify-checker-skillification

## Execution Contract

- **M1 交付**：三個試點 checker 各驗證一條技能化路徑：
  1. `kicad-default-severities` → 擴充既有 `classify_erc_report`（control→擴充既有 checker）
  2. `decoupling-pdn-strategy` → 全新 IR-native checker，走完 DD-2（control-grounded evidence）+ DD-3（threshold block）完整路徑
  3. `board-edge-keepout` → T-B stub + backlog 掛帳（示範不硬編假欄位）
- **done 定義**：三試點各有可執行 code + 單元測試通過；`ValidationEvidence` 輸出帶 control_id + source_anchor；registry 記錄三者狀態；threshold block 解析層可讓門檻更新不改 checker code。
- **零 LLM / fail-fast / byte-identical**：每個 T-A checker 必須守此契約。

## Required Reads

- `design.md`（DD-1~DD-7）、`control-classification.md`（分類判準）、`data-schema.json`（三個 schema）
- `packages/workflow-core/bodesign_workflow_core/validation_evidence.py`（封套 + `_ADAPTERS`）
- `packages/workflow-core/bodesign_workflow_core/requirement_planning.py`（`ORACLE_TOOLS` 定義，line 100）
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`（`classify_erc_report` 範本）
- `packages/design-ir/bodesign_design_ir/contracts.py`（IR dataclass，decoupling checker 讀取來源）

## Stop Gates In Force

- **send-to-fab 不在範圍**：技能化不動送廠 gate。
- **partial/todo 不得硬 gate**：no-fabrication 天條，違反即停。
- **新增 ORACLE_TOOLS 成員需擴 `_ADAPTERS`**：兩處同步，否則封套建構失敗。

## Execution-Ready Checklist

- [x] designed gate 通過（IDEF0/GRAFCET drawmiat validate）
- [x] 57 control 分類完成
- [ ] PYTHONPATH 測試環境（`PP=$(ls -d packages/*/ | tr '\n' ':')`，python3）
- [ ] 試點門檻值可回溯到對應 control 的 source_anchor
