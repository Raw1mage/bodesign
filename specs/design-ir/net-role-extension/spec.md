# Spec: design-ir_net-role-extension

## Purpose

保證 design IR 的 `Net` 攜帶一個**明確供給、可選、閉集**的 `role` 分類，且每個 role 值皆帶
provenance（來源錨點），使 verify-checker 的 placement 類 checker 能以 role 而非 net 名 heuristic
篩選 net。role 缺失時一律為 `None`（fail-fast，不預設、不臆造），落實 no-fabrication 天條；role
的來源對齊 `verify-checker-skillification` 的 `ValidationEvidence` `source_anchor` grounding 契約，
確保每個依 role 產出的 verdict 皆可回溯至 schematic net-class / 使用者標註。

## Requirements

### Requirement: Net Role Is Optional Closed-Enum With Provenance

`Net` SHALL 提供一個 `role` 欄位，其值域為閉集 `{power, ground, high_current, rf, signal,
differential}` 或 `None`；default 為 `None`。當 `role` 非 `None` 時，`Net` SHALL 同時攜帶對應
的 role provenance（`EvidenceRef`），標示該 role 的來源錨點。既有不帶 role 的 `Net` 呼叫端
SHALL 不受影響（向後相容）。

#### Scenario: Explicit Role Supplied With Provenance

- **WHEN** 上游 schematic net-class 映射或使用者標註以閉集內的 token 明確供給某 net 的 role，並附來源錨點
- **THEN** `Net.role` 等於該閉集值，且 `Net` 的 role provenance 欄位攜帶對應 `EvidenceRef`

#### Scenario: Role Token Outside Closed Enum Is Rejected

- **WHEN** 供給的 role token 不在閉集內
- **THEN** `Net.role` 保持 `None`，且不套用任何預設或推測值

### Requirement: Missing Role Yields None Without Guessing

當上游未明確供給 role（net 無 net-class、net-class 未列於映射表、或無使用者標註）時，`Net.role`
SHALL 為 `None`。系統 SHALL NOT 以 net 名 heuristic 或任何 LLM 推測補齊 role。

#### Scenario: No Upstream Role Assignment

- **WHEN** 一條 net 在 schematic 無 net-class 亦無使用者標註
- **THEN** `Net.role` 為 `None`，且系統不依 net 名（如 VBUS/GND）猜測 role

### Requirement: Role-Aware Query Returns Only Explicitly-Roled Nets

design IR SHALL 提供一個 role-aware 查詢介面，接受一個 role 值並回傳 `role` 恰等於該值的 net 子集。
`role is None` 的 net SHALL NOT 出現在任何 role 查詢結果中。查詢 SHALL 為確定性（同輸入
byte-identical 輸出），純 python，不引入 worker-only 依賴。

#### Scenario: Placement Checker Filters By Role

- **WHEN** placement 類 checker 以 role `high_current` 查詢某 `BoardDesign`
- **THEN** 僅回傳 `role == "high_current"` 的 net；所有 `role is None` 的 net 被排除

## Acceptance Checks

- [ ] `Net` 具 `role` 欄位，值域為閉集 `{power, ground, high_current, rf, signal, differential}` 或 `None`，default `None`
- [ ] `Net` 具 role provenance 欄位（`EvidenceRef | None`），`role is not None` 時該欄位非 `None`
- [ ] 供給不在閉集的 role token 時 `role` 保持 `None`，無預設/推測
- [ ] 無上游 role 供給時 `role` 為 `None`，且無 net 名 heuristic 介入
- [ ] role-aware 查詢回傳的 net 集合中無任何 `role is None` 的 net
- [ ] 既有不帶 role 的 `Net` 建構呼叫端不受破壞（向後相容）
- [ ] role provenance 語義對齊 `ValidationEvidence` 的 `source_anchor` grounding 契約
