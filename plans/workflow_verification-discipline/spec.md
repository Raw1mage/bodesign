# Spec: workflow_verification-discipline

## Purpose

把 bodesign 的「需求 → 設計 → 驗證」迴圈從 prose 報告升級為機器可查的合約與證據鏈：需求帶 oracle、實作前有審查 gate、對照輸出結構化 diff、驗證證據統一格式並回流 C00 編排 spine。每一項都修補 bodesign 自身程式碼的已知缺口（行號證據見 `proposal.md` Why 段）。

## Requirements

### Requirement: RequirementContract（G1）

需求抽取結果必須可升級為可驗證合約：每個品質目標帶 metric、threshold、measurement_method、oracle_tool；無法量測者顯式標記並升級使用者決策。

#### Scenario: 可量測需求收斂為合約
- **GIVEN** 使用者規格含「USB-C 供電、板長 ≤ 60mm」
- **WHEN** `plan_design_intent` 抽取需求並由使用者補答
- **THEN** 產出的 requirement 帶 `metric="board_length_mm"`、`threshold="<=60"`、`oracle_tool="drc_gate"`、`verification_status="unverified"`
- **THEN** 該合約綁定 C00 PRD template 既有欄位（沿用 `C00_REQUIREMENT_FIELD_BINDINGS`），`validate_requirement_bindings` fail-fast 模式不變

#### Scenario: 不可量測需求 fail fast
- **GIVEN** 需求「外觀要好看」無可用 oracle
- **WHEN** 合約收斂執行
- **THEN** 該項標記 `verification_status="unverifiable"` 並出現在 open_questions（升級使用者決策），不得 silent skip、不得自動指派 oracle

#### Scenario: 每輪驗證輸出 pass/fail 對表
- **GIVEN** 一份含 N 項合約的 plan 與一輪驗證執行（DRC/ERC/crosscheck）
- **WHEN** 驗證完成
- **THEN** 輸出 per-requirement 表：每項 `pass|fail|unverified|unverifiable` + 證據 anchor；缺 oracle 工具執行記錄的項目維持 `unverified`，不得推定為 pass

### Requirement: Debug 成本排序紀律（G6）

驗證失敗時，工作流先產出廉價假設清單，全部排除後才允許結構性修改提案。

#### Scenario: DRC 失敗先列簡單解釋
- **GIVEN** DRC gate 回報 clearance violation
- **WHEN** blocker 進入工作流回報
- **THEN** blocker 附 `simple_fix_candidates[]`（如：規則參數設定錯、單一 net 例外、footprint 引腳定義錯），每項帶檢查方法
- **THEN** 結構性提案（重佈局、改層數）在 `simple_fix_candidates` 全部標記 `ruled_out`（附證據）之前不得成為建議動作

### Requirement: Design Review Gate（G2）

reference-board / generated-design workflow 在「propose-layout-intent」與「deterministic-validation」之間必須有 `design-review` 節點。

#### Scenario: 子系統設計審查產出裁決
- **GIVEN** 一份 layout intent 提案（子系統組成 + 介面）
- **WHEN** design-review 節點執行
- **THEN** 產出 review 文檔：情境清單（電源時序、reset 鏈、I2C 位址衝突、電平相容、差分對拓撲等適用項）、逐情境推演結論、CRITICAL/MAJOR/MINOR 計數、`APPROVE|APPROVE_WITH_CONCERNS|REJECT` 裁決
- **THEN** review 文檔以 evidence 落盤（client 專案資料夾），`REJECT` 時 deterministic-validation 階段維持 blocked

#### Scenario: review 不可被跳過
- **GIVEN** workflow plan 推進到 deterministic-validation
- **WHEN** design-review 節點無產出記錄
- **THEN** validation 階段回報 blocker「design-review 未完成」，fail fast

### Requirement: 結構化 diff 與 root-cause 報告（G3/A4）

參考板對照輸出結構化差異清單（多維度、severity、第一分歧點），root-cause 報告採四段式 schema。

#### Scenario: crosscheck 輸出 CrossCheckDiff
- **GIVEN** 生成設計與參考板 evidence（nets、可用時含 pads/元件值/layout rules）
- **WHEN** 交叉檢核執行
- **THEN** 輸出 `CrossCheckDiff`：`items[]` 各帶 `{dimension, key, status: matched|missing|extra, severity, evidence_refs}`，並標記 `first_divergence`（severity 排序後第一筆非 matched）
- **THEN** 既有 prose verdict 與 markdown 渲染保留（雙軌），coverage% 計算不變

#### Scenario: root-cause 報告標準化
- **GIVEN** 一筆需要解釋的關鍵分歧（或驗證失敗）
- **WHEN** root-cause 分析完成
- **THEN** 報告含四段：`methodology`（步驟清單）、`findings`、`evidence[]`（每筆帶 anchor：檔案/net/座標/工具輸出）、`fix`；寫入 events

### Requirement: Evidence backflow（A3）

orchestration spine 增加第三類 artifact `evidence_returns/`，驗證量測證據回流 C00。

#### Scenario: 驗證證據回流並持久化
- **GIVEN** 一個 dispatched work packet（C04 layout）與一輪完成的驗證
- **WHEN** 下游回傳 evidence return
- **THEN** `_orchestration/evidence_returns/<evidence_id>.json` 落盤（schema `bodesign.c00.evidence_return.v1`），ID 為 count-based（`<LAYER>-EV-0001…`），事件 append 進 `log.jsonl`
- **THEN** evidence return 引用 packet_id 與 requirement ids；malformed payload 依 spine 既有模式 fail fast（`OrchestrationError`）

#### Scenario: C00 消費 evidence
- **GIVEN** 一筆含 per-requirement pass/fail 的 evidence return
- **WHEN** C00 ingest
- **THEN** 對應 requirement 的 `verification_status` 更新；fail 項可由 C00 開新 work packet（沿用既有 dispatch 流程），不自動執行任何修改

### Requirement: ValidationEvidence envelope（A5）

跨工具統一驗證輸出格式。

#### Scenario: 工具輸出包裝為 envelope
- **GIVEN** si_check / DRC gate / crosscheck 任一工具完成執行
- **WHEN** 結果輸出
- **THEN** 結果可表示為 `{tool, inputs, findings[], severity, anchors[], requirement_refs[]}`；findings 各帶 `{id, severity, message, anchor}`
- **THEN** 既有工具的原生回傳欄位保留（envelope 是包裝不是替換）；新工具強制原生輸出 envelope

### Requirement: Reference Comparator（G7）

確定性 IR-vs-IR 比對引擎（`packages/design-ir` 子模組，v1 library API only）：輸入 candidate 與 golden reference 兩份 `BoardDesign IR`，輸出三項子分數 + 加權總分 + component/pin/net 級匹配明細；明細以 `CrossCheckDiffItem` 表達、整體可包裝為 `ValidationEvidence` envelope。無 LLM 參與，同輸入必同輸出。

#### Scenario: 良品自比對得滿分
- **GIVEN** 同一份合法 `BoardDesign IR` 同時作為 candidate 與 reference
- **WHEN** comparator 執行
- **THEN** `S_comp = S_attr = S_conn = 1.0`，總分 `S = 1.0`，`items[]` 全部 `matched`，`first_divergence = null`

#### Scenario: 擾動設計輸出分級退化分數與明細
- **GIVEN** reference 與一份移除一顆 required 元件、改一個電阻值、調換一對 net 的 candidate
- **WHEN** comparator 執行
- **THEN** 總分 `S = 0.4·S_comp(Dice) + 0.2·S_attr + 0.4·S_conn`（權重由集中 config 提供，預設 0.4/0.2/0.4）按各項受損程度退化
- **THEN** mismatch 明細逐筆定位：缺件 → `{dimension: "component", status: "missing"}`；值差 → `{dimension: "component_value", status: "extra|missing"}` 帶兩側值；net 錯接 → `{dimension: "pin", status: ...}` 帶 pin 級 anchor——不得只回 binary pass/fail 或單一總分

#### Scenario: 元件匹配採兩段式 + Hungarian 全域指派
- **GIVEN** reference 中標記 `optional` 的元件在 candidate 缺席
- **WHEN** 元件匹配執行
- **THEN** required 元件先以 pin 鄰域簽名相似度矩陣 + Hungarian 演算法全域匹配；optional 元件後匹配且缺席不扣分
- **THEN** 對稱兩腳被動件（R/C/L）pin 正規化為 `__sym__`；`flexible_pin_group` 成員任一匹配皆計分

#### Scenario: 輸入 IR 不合法即 fail fast
- **GIVEN** candidate IR 缺 comparator 必要欄位（如元件無 pin 定義）
- **WHEN** comparator 執行
- **THEN** 顯式拋錯（`CMP_IR_INVALID`），不做部分比對、不 silent skip 缺損元件

### Requirement: 編排表面統一（A1）

`ReferenceBoardWorkflowPlan` stage 狀態由 `_orchestration/` spine 推導。

#### Scenario: stage 狀態從 spine 推導
- **GIVEN** 專案資料夾含 `_orchestration/`（work packets、blockers、evidence returns）
- **WHEN** `/workflow/reference-board` 查詢
- **THEN** 各 stage 的 status/blockers 由 spine 狀態計算（open blockers → blocked；evidence pass → 可推進），不再由函式參數快照決定
- **THEN** 無 `_orchestration/` 狀態時顯式回報「spine 未初始化」，不得 fallback 回舊參數快照行為

#### Scenario: API 向後相容
- **GIVEN** 既有 `/workflow/reference-board` 呼叫端
- **WHEN** A1 落地後查詢
- **THEN** 回傳 shape（`ReferenceBoardWorkflowPlan` 欄位）不變，僅狀態來源改變

## Acceptance Checks

- [ ] 全部 scenario 有對應 fixture-driven 測試（pytest，乾淨 clone 可跑）
- [ ] `data-schema.json` 覆蓋 RequirementContract / ValidationEvidence / CrossCheckDiff / evidence_return.v1 四個契約
- [ ] 既有測試全綠（API 向後相容驗證）
- [ ] 無新增 fallback：所有錯誤路徑 fail fast 並有對應 error code（見 `errors.md`，planned 階段補）
- [ ] `specs/architecture.md` 同步（A1/A3 動到模組邊界與資料流）
