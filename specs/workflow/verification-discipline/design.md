# Design: workflow_verification-discipline

## Context

bodesign 的需求抽取（`requirement_planning.py`）、編排（`contracts.py` 靜態 plan + `orchestration.py` runtime spine）、對照（`reference_crosscheck.py`）、驗證工具（si_check / DRC gate / crosscheck）四個層面各自存在已驗證的程式碼缺口（行號證據見 `proposal.md` Why）。本設計把它們收斂為一條「需求合約 → 審查 gate → 結構化證據 → spine 回流 → 編排狀態推導」的閉環，全部建立在既有基礎設施上，不新建平行機制。

## Goals / Non-Goals

### Goals

- 需求可升級為機器可查合約（metric/threshold/oracle），驗證輸出 per-requirement pass/fail 表
- 實作前 design-review gate 成為 workflow 的一等節點
- 對照輸出結構化 diff（多維度、severity、first_divergence）+ 四段式 root-cause 報告
- 驗證證據經統一 envelope 回流 C00 spine（`evidence_returns/`）
- `/workflow/reference-board` 的 stage 狀態由 spine 推導（單一事實來源）

### Non-Goals

- 自主長程編排 / 全自主迴圈（PCB 無可執行整板 golden model）
- 移除或弱化任何 approval gate
- 改變 client-owned storage 邊界
- 重寫既有驗證工具的內部邏輯（只包裝輸出）

## Decisions

- **DD-1** RequirementContract **擴充 `ExtractedRequirement` 而非新建平行 schema**：在既有 dataclass 加 `metric` / `threshold` / `measurement_method` / `oracle_tool` / `verification_status` 可選欄位。理由：`C00_REQUIREMENT_FIELD_BINDINGS` 已綁定 C00 PRD template 並有 `validate_requirement_bindings` fail-fast 驗證；平行 schema 會製造雙事實來源。向後相容：新欄位有預設值（`verification_status="unverified"`），既有呼叫端不破。
- **DD-2** oracle_tool 是**封閉枚舉**，不是自由字串：`drc_gate | erc | crosscheck | si_check | gerber_compare | spice | user_judgment | none`。`none` 即 `unverifiable`，強制進 open_questions。理由：自由字串會讓「指了一個不存在的 oracle」silent 通過；枚舉 + fail-fast 校驗符合天條。
- **DD-3** `simple_fix_candidates` 掛在 **blocker 結構上**（擴充 `BlockerReturn`），不是獨立報告：blocker 增加可選 `simple_fix_candidates[]`（`{hypothesis, check_method, ruled_out, evidence_ref}`）。理由：G6 的觸發點就是驗證失敗產生 blocker 的瞬間；分開放會脫鉤。結構性提案的 gate 由消費端（skills/bodesign 紀律 + C00 ingest 邏輯）檢查 `all ruled_out` 條件。
- **DD-4** design-review 是 **workflow stage + evidence 落盤**，不是新 MCP 工具：在 stage 序列插入 `design-review`（介於 propose-layout-intent 與 deterministic-validation 之間），review 文檔由 AI（skill 方法論驅動）產出並落盤 client 專案資料夾，stage 狀態依文檔存在性 + 裁決欄位推導。理由：審查本身是推演工作（LLM 強項），工具只需要驗證「審查發生過且有裁決」。
- **DD-5** `CrossCheckDiff` 是 `ReferenceCheck` 的**泛化而非替換**：保留 `crosscheck_nets` 函式與 markdown 渲染；新增 `crosscheck_diff()` 回傳 `items[]`（`{dimension, key, status, severity, evidence_refs}`）+ `first_divergence`。net 維度先行，pad/元件值/規則維度依 evidence 可用性逐步加入（缺 evidence 的維度顯式回報 `dimension-unavailable`，不假裝比對過）。
- **DD-6** `ValidationEvidence` envelope 是**包裝層**：定義 `wrap_validation_evidence(tool, raw_result, ...)` adapter，各工具原生回傳保留。新工具強制原生輸出 envelope；舊工具（si_check / DRC gate / crosscheck）在 MCP 工具層包裝。理由：避免一次性重寫所有工具的回傳契約（打擊半徑控制）。
- **DD-7** `evidence_returns/` 完全複製 spine 既有模式：count-based ID（`<LAYER>-EV-0001`）、JSON 檔落盤、append-only `log.jsonl` 事件、malformed 即 `OrchestrationError`。schema `bodesign.c00.evidence_return.v1` 欄位：`{evidence_id, packet_id, source_layer, envelope: ValidationEvidence, requirement_verdicts[], resolved}`。理由：spine 的持久化/審計/fail-fast 模式已驗證，三類 artifact（packets/blockers/evidence）對稱。
- **DD-8** A1 的推導採**顯式初始化策略**：`_orchestration/` 不存在時回報 `spine-not-initialized` blocker，**不 fallback** 回參數快照行為。既有純函式 `plan_reference_board_workflow()` 保留為「模板產生器」（提供 stage 骨架與 gate 定義），新函式 `derive_workflow_plan(folder)` 負責用 spine 狀態填 status/blockers。理由：天條禁止 silent fallback；模板/推導分離讓 stage 定義仍可單元測試。
- **DD-9** requirement_verdicts 的 pass 判定**只能由 oracle 工具執行記錄支撐**：無對應 evidence return 的合約項永遠是 `unverified`。不存在「預設通過」。
- **DD-10**（G7）comparator 落點 = **`packages/design-ir` 子模組**（如 `design_ir/compare/`），非新 package、非 workflow-core：comparator 只依賴 IR schema，放 design-ir 內零新增依賴邊界，且與 IR schema 演進同步。v1 為 library API only，MCP tool 包裝另案（使用者確認決策，2026-06-12）。
- **DD-11**（G7）comparator 輸出**收斂進本 plan 既有契約**而非自定平行格式：mismatch 明細以 `CrossCheckDiffItem` 表達（`dimension` 枚舉擴充 `component` / `pin`），整體結果可包裝為 `ValidationEvidence` envelope（`tool="crosscheck"`，子分數放 `inputs`/`raw_result`）。理由：避免「comparator 報告」與「crosscheck diff」兩套 mismatch schema 並存的雙事實來源。
- **DD-12**（G7）演算法骨架沿用 pcbGPT (arXiv 2606.01188)：required/optional 兩段式元件匹配 → pin 鄰域簽名相似度矩陣 → Hungarian 全域指派 → `S = 0.4·S_comp(Dice) + 0.2·S_attr + 0.4·S_conn`。權重與閾值集中單一 config（不散落硬編碼）；對稱兩腳被動件 pin 正規化 `__sym__`；`flexible_pin_group` 任一成員匹配即計分。確定性保證：tie-breaking 規則明確化（如相同分數按 ref designator 字典序），同輸入必同輸出，無 LLM 參與。
- **DD-13**（G7）IR schema 最小擴充：`optional`（元件級布林，預設 false）與 `flexible_pin_group`（pin 等效集合標記）。僅在 design 確認 comparator 必要時加入，欄位可選、既有 IR 不破。輸入 IR 校驗失敗即 `CMP_IR_INVALID` fail fast，不做部分比對（天條）。

## Risks / Trade-offs

| 風險 | 等級 | 緩解 |
|---|---|---|
| A1 重構破壞既有 `/workflow/reference-board` 呼叫端 | 中 | 回傳 shape 不變（DD-8 模板/推導分離）；既有測試做相容性 gate |
| envelope 包裝層與工具原生欄位語義漂移 | 中 | adapter 單向映射 + fixture 測試逐工具鎖定；envelope 欄位不重新解釋原生值 |
| design-review 變成形式主義（空文檔過 gate） | 中 | gate 檢查裁決欄位 + 情境清單非空；review 方法論在 skills/bodesign 規範最低情境集 |
| diff 維度擴展時 evidence 不足導致假比對 | 高 | DD-5 的 `dimension-unavailable` 顯式回報；禁止對缺 evidence 維度輸出 matched |
| oracle 枚舉過窄阻擋合法需求 | 低 | `user_judgment` 收人工裁決類；枚舉擴充走 amend mode |

## Critical Files

- `packages/workflow-core/bodesign_workflow_core/requirement_planning.py` — DD-1/DD-2：`ExtractedRequirement` 擴充、oracle 枚舉、合約收斂
- `packages/workflow-core/bodesign_workflow_core/orchestration.py` — DD-3/DD-7：`BlockerReturn.simple_fix_candidates`、`EvidenceReturn` + `evidence_returns/` 持久化
- `packages/workflow-core/bodesign_workflow_core/contracts.py` — DD-4/DD-8：design-review stage、`derive_workflow_plan()`
- `packages/workflow-core/bodesign_workflow_core/reference_crosscheck.py` — DD-5：`CrossCheckDiff` / `crosscheck_diff()`
- `packages/workflow-core/bodesign_workflow_core/validation_evidence.py`（新檔）— DD-6：envelope dataclass + `wrap_validation_evidence` adapters
- `packages/design-ir/`（compare 子模組，新增）— DD-10~DD-13：comparator 演算法 + scoring config + IR 最小 schema 擴充
- `services/mcp/`（工具註冊處）— envelope 包裝接線、design-review 狀態查詢
- `skills/bodesign/` — G6 debug 紀律 + G2 review 方法論段落
- `tests/` — 各 scenario 的 fixture-driven 測試

## Code anchors

- `packages/workflow-core/bodesign_workflow_core/requirement_planning.py:83-89` — `ExtractedRequirement` 現況（G1 缺口）
- `packages/workflow-core/bodesign_workflow_core/requirement_planning.py:31-41` — `C00_REQUIREMENT_FIELD_BINDINGS`（DD-1 沿用）
- `packages/workflow-core/bodesign_workflow_core/contracts.py:46-120` — 靜態 plan（A1 重構對象）
- `packages/workflow-core/bodesign_workflow_core/orchestration.py:93-109` — `BlockerReturn`（DD-3 擴充點）
- `packages/workflow-core/bodesign_workflow_core/reference_crosscheck.py:45-58` — `crosscheck_nets`（DD-5 泛化基礎）
- `packages/workflow-core/bodesign_workflow_core/agent_registry.py:58-71` — 下游授權封套（evidence return 的授權沿用）
