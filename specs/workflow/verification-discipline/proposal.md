# Proposal: workflow_verification-discipline

## Why

每一項依據都是 **bodesign 自身原始碼的缺口**，附行號證據；不依賴任何外部領域（晶片設計）專業：

- **G1 Requirement Contract**：`requirement_planning.py:83-89` 的 `ExtractedRequirement` 只有 `{key, label, state, evidence}`，state 僅 `stated|answered|missing`——需求被「抽取」但從未變成「可驗證合約」（無 metric / threshold / oracle 欄位）。oracle 全部是 bodesign 既有工具（DRC/ERC/crosscheck/SI），無新領域依賴。
- **G6 Debug 成本排序紀律**：bodesign 的 DRC/SI 失敗處理目前無「先列簡單解釋候選（規則參數、單一 net、footprint 錯誤）→ 排除後才允許結構性重佈局」的工作流 gate。這是通用 agent debug 紀律，與 code-thinker 的「先驗證前提再追加手段」同源。
- **G2 Design Review Gate**：workflow-core 的 reference-board plan（`contracts.py:57-106`）從「propose-layout-intent」直接跳「deterministic-validation」，中間沒有實作前的情境推演審查節點（電源時序、reset 鏈、位址衝突、電平相容——全部是 PCB 領域情境）。
- **G3 結構化 diff / root-cause 報告**：`reference_crosscheck.py:45-58` 的 `crosscheck_nets` 已輸出 matched/missing/extra + coverage%，但只有 net 名稱單一維度、verdict 是 prose 字串——缺 severity、第一分歧點標記、多維度（pad/元件值/規則），root-cause 報告也無標準 schema。
- **A1 編排表面統一**：`contracts.py:46-120` 的靜態 6-stage plan 與 `orchestration.py` 的 C00 work-packet/blocker runtime spine **無資料流連接**——API 回報的 stage 狀態是函式參數快照（`artifact_count`、`net_count`…），不是 spine 狀態推導。雙事實來源是架構債。
- **A3 Evidence backflow**：`orchestration.py` 的下游→C00 回流通道只有 blocker（問題/決策需求），**量測證據（ERC/DRC/SI/crosscheck 結果）沒有回流通道**——驗證結果是終端報告，無法驅動 C00 更新 PRD answer_state 或開新 work packet。
- **A5 ValidationEvidence envelope**：各驗證工具回傳結構各異（si_check 回 effective values、DRC gate 另一格式、crosscheck 又一格式），agent 跨工具彙整證據需逐一適配。
- **G7 Reference Comparator**：bodesign 的「對照已知良品交叉檢核」（驗證第 2 層）目前只有 net 名稱單維比對（`crosscheck_nets`），**缺確定性的 IR-vs-IR 比對演算法**——無元件級匹配、無 pin 級連接性比對、無可重現的相似度評分。arXiv 調研（`docs/research/arxiv/workflow-analysis.md` P0-3）找到完整可借鏡演算法：pcbGPT (2606.01188) 的 reference-first comparator（兩段式元件匹配 + pin 鄰域簽名 + Hungarian 全域指派 + Dice/attr/connectivity 0.4/0.2/0.4 加權 + 對稱被動件 pin 正規化 + FlexiblePin）。

> 出處註腳：本 plan 的偵查由 Design Conductor 論文（arXiv 2603.08716，晶片設計領域）觸發——該論文的領域專業（RTL/timing/PDK）與 PCB 設計**零轉移**，且其核心前提（Spike 這種可執行 cycle-accurate golden model）在 PCB 領域不存在。論文僅作為「對自己的 workflow 提問」的透鏡；上列每一項缺口獨立站在 bodesign 程式碼證據上，與論文無依賴。拆解與分析存檔於 `docs/research/design-conductor/`。

## Original Requirement Wording (Baseline)

- "拆解他的文件成為詳細的src文檔，再分析值得借鏡學習的部份來強化bodesign workflow。如果有需要，也可以開plan來擴充工具"
- Scope 收斂（question 工具）：使用者選擇「開 plan：P1+P2 四項」（G1 + G6 + G2 + G3）。
- 第二輪（"如果有建議我們改良現有架構的地方，也可以分析規劃"）：架構偵查產出 A1–A5，使用者選擇「全部併入現有 plan」（A1 + A3 + A5；A2 即 G1 落點、A4 即 G3 落點）。

## Requirement Revision History

- 2026-06-12: initial draft created via plan-init.ts
- 2026-06-12: scope 收斂為 P1（G1+G6）+ P2（G2+G3）兩個 phase
- 2026-06-12: 架構級偵查（07-architecture-improvements.md）後，使用者決定 A1/A3/A5 全部併入；A5 自 OUT（原 G4）移入 IN；新增 P3（A3+A5）、P4（A1）兩個 phase
- 2026-06-12: 使用者決定將獨立 plan `verification_reference-comparator`（arXiv 調研 P0-3 產物）併入本 plan 為 **P5（G7）**：comparator 消費 P2 的 `CrossCheckDiff` 與 P3 的 `ValidationEvidence` schema，不自定平行輸出格式；原獨立 plan 撤除。落點與邊界沿用該 plan 已確認決策：模組 = `packages/design-ir` 子模組、v1 = library API only（MCP tool 包裝另案）

## Effective Requirement Description

1. **G1 — RequirementContract schema**：在 workflow-core 的 plan 結構中定義 `RequirementContract`（`{id, statement, metric, threshold, measurement_method, oracle_tool, status}`）。規劃階段強制收斂每個品質目標到此 schema；無法量測者標記 `unverifiable` 並升級為使用者決策。每輪驗證輸出 per-requirement pass/fail 表。
2. **G6 — Debug 成本排序紀律**：驗證失敗（DRC/ERC/SI/比對不一致）時，工作流先產出 `simple-fix-candidates` 清單（規則參數、單一 net、footprint 錯誤等廉價假設），全部排除後才允許結構性重佈局提案。落點：skills/bodesign 紀律段落 + workflow blocker 分類。
3. **G2 — Design Review Gate**：workflow-core 的 reference-board / generated-design plan 在「propose subsystem/layout intent」與「deterministic validation」之間插入 `design-review` 節點：情境清單推演（電源時序、reset 鏈、位址衝突、電平相容、差分對拓撲…）+ CRITICAL/MAJOR/MINOR 分級 + APPROVE/REJECT 裁決，review 文檔作為 evidence 落盤。
4. **G3 — 結構化 diff + root-cause 報告**：對照已知良品時輸出結構化差異清單（net-by-net、pad-by-pad、rule-by-rule），按嚴重度排序並標出第一筆關鍵分歧；root-cause 報告標準化為四段式 schema（methodology / findings / evidence(anchored) / fix），寫入 events。落點：`reference_crosscheck.py` 的 `ReferenceCheck` 泛化為 `CrossCheckDiff`（= A4）。
5. **A3 — Evidence backflow**：`_orchestration/` 增加第三類 artifact `evidence_returns/`（schema `bodesign.c00.evidence_return.v1`）。驗證工具的量測結果（含 per-requirement pass/fail，引用 G1 合約）回流 C00；C00 據此更新 PRD answer_state 或開新 work packet。沿用 spine 既有的持久化、count-based ID、append-only log 模式。
6. **A5 — ValidationEvidence envelope**：定義統一驗證輸出格式 `{tool, inputs, findings[], severity, anchors, requirement_refs[]}`。新工具強制採用、既有工具（si_check / DRC gate / crosscheck）漸進包裝；`requirement_refs` 連到 G1 合約，使 pass/fail 表可機器生成。
7. **A1 — 編排表面統一**：`contracts.py` 的 `ReferenceBoardWorkflowPlan` stage status/blockers 改為**從 `_orchestration/` spine 狀態推導**（work packets + blockers + evidence returns 為輸入），靜態 plan 函式降級為模板。單一事實來源，消除 API 回報與 runtime 狀態的分裂。
8. **G7 — Reference Comparator**：確定性 IR-vs-IR 比對引擎，落點 `packages/design-ir` 子模組（如 `design_ir/compare/`），v1 為 library API only。輸入兩份 `BoardDesign IR`（candidate + golden reference），輸出三項子分數（`S = 0.4·S_comp(Dice) + 0.2·S_attr + 0.4·S_conn`，權重集中 config）+ 加權總分 + component/pin/net 級匹配明細。演算法骨架借鏡 pcbGPT：required/optional 兩段式元件匹配、pin 鄰域簽名、Hungarian 全域指派、對稱兩腳被動件 pin 正規化（`__sym__`）、FlexiblePin 等效集合展開。**輸出格式收斂**：mismatch 明細以 `CrossCheckDiffItem` 表達（dimension 擴充 `component` / `pin`）、整體結果可包裝為 `ValidationEvidence` envelope（`tool="crosscheck"`），不另立平行 schema。確定性保證：同輸入同輸出（tie-breaking 規則明確化）、無 LLM 參與。

## Scope

### IN
- workflow-core：RequirementContract schema（擴充 `ExtractedRequirement`，非平行 schema）、design-review 節點、blocker 分類（simple-fix-candidates）
- skills/bodesign：G6 debug 紀律 + G2 review 方法論的 skill 文字
- reverse-core / gerber-core / workflow-core：結構化 diff 輸出（`reference_crosscheck.py` 的 `ReferenceCheck` 泛化為 `CrossCheckDiff`，建立在現有 output comparison 雛形上）
- 報告 schema：root-cause 四段式 + per-requirement pass/fail 表
- **A3 Evidence backflow**：orchestration spine 增加 `evidence_returns/` artifact 類別（`bodesign.c00.evidence_return.v1`），驗證量測證據回流 C00
- **A5 ValidationEvidence envelope**：統一驗證輸出格式 `{tool, inputs, findings[], severity, anchors, requirement_refs[]}`，新工具強制、舊工具漸進包裝
- **A1 編排表面統一**：`ReferenceBoardWorkflowPlan` stage 狀態改由 `_orchestration/` spine 推導，靜態 plan 函式降級為模板
- MCP 工具面：必要時為 diff/review/contract/evidence 增加或擴充工具介面
- **G7 Reference Comparator**：`packages/design-ir` 子模組（comparator 核心演算法 + scoring config + IR 最小 schema 擴充：`optional` 元件標記、`flexible_pin_group`）；test vectors（良品自比對滿分、擾動退化曲線）
- 測試：fixture-driven，沿用現有測試基準

### OUT
- 多 variant 並行競賽式探索（依賴 G1 落地後再評估）
- golden reference 的取得與入庫管線（vault L6 reference-circuits，另案）
- comparator 的 MCP tool 包裝與 UI 呈現（v1 為 library API；佈局/幾何比對不在 G7 範圍）
- LLM 語意審查層（arXiv P1-9 validation agent，另案）
- 自主長程編排 / per-project memory（A3+A1 已涵蓋其 80% 效益：證據回流 + 單一編排事實來源）
- 移除或弱化 user approval gate
- 任何 fallback mechanism（天條）

## Non-Goals

- 不追求全自主不間斷執行模型：PCB 領域**不存在可執行的整板 golden model**（無 Spike 等價物）——參考板交叉檢核是結構比對而非行為驗證，EMC/熱/機構/bring-up 失效模式無法在軟體迴圈內閉環。bodesign 維持 client-orchestrated + approval gate。
- 不自建分散式 infra。

## Constraints

- 確定性驗證 gate 不得被繞過；新節點只能增加 gate，不能放鬆。
- 無法量測的需求必須 fail fast 升級使用者決策，不得 silent skip。
- diff/review 輸出必須 evidence-linked（沿用現有 EvidenceRef 約定）。
- 與現有 `/workflow/reference-board`、`/candidates/generated-design` API 向後相容。

## What Changes

- workflow plan 增加 requirement-contract 與 design-review 兩類節點與對應 schema。
- 驗證失敗的 blocker 回報增加 simple-fix-candidates 分類。
- 交叉檢核從 confidence overlay 升級為「結構化 diff + 第一分歧點 + root-cause 報告」。
- skills/bodesign 增補 debug 紀律與 review 方法論。
- orchestration spine 增加 `evidence_returns/` 第三類 artifact（量測證據回流 C00）。
- 驗證工具輸出統一為 `ValidationEvidence` envelope（新工具強制、舊工具漸進包裝）。
- `ReferenceBoardWorkflowPlan` stage 狀態改由 `_orchestration/` spine 推導，消除雙編排表面分裂。

## Phasing

- **P1**：G1 RequirementContract（A2 落點）+ G6 debug 紀律 — schema 擴充 + skill 文字
- **P2**：G2 Design Review Gate + G3/A4 結構化 diff 與 root-cause 報告
- **P3**：A3 Evidence backflow + A5 ValidationEvidence envelope（依賴 P1 的 requirement_refs）
- **P4**：A1 編排表面統一（依賴 P3：evidence/blocker 皆為 stage 狀態輸入）
- **P5**：G7 Reference Comparator（依賴 P2 的 `CrossCheckDiff` schema + P3 的 `ValidationEvidence` envelope：comparator 輸出消費這兩個契約而非自定格式）

## Capabilities

### New Capabilities
- `RequirementContract`：機器可查的需求合約 + per-requirement 驗證對表
- `design-review` workflow 節點：實作前情境推演審查與分級裁決
- 結構化 IR/golden diff（`CrossCheckDiff`）：net/pad/rule 級差異清單與第一分歧點
- root-cause 報告 schema：四段式標準化報告
- `evidence_returns/` spine artifact：驗證量測證據回流 C00（`bodesign.c00.evidence_return.v1`）
- `ValidationEvidence` envelope：跨工具統一驗證輸出格式
- `reference-compare`（G7）：兩份 BoardDesign IR 的確定性比對——`S_comp/S_attr/S_conn` 子分數、加權總分、component/pin/net 級 mismatch 明細（以 `CrossCheckDiffItem` 表達）

### Modified Capabilities
- workflow-core plan 回報：blockers 增加 simple-fix-candidates 分類
- gerber-core output comparison：輸出升級為結構化 diff
- `plan_reference_board_workflow`：stage 狀態由 spine 推導（單一事實來源），靜態函式降級為模板
- 既有驗證工具（si_check / DRC gate / crosscheck）：漸進包裝為 envelope 格式

## Impact

- `packages/design-ir`（G7：comparator 子模組 + IR 最小 schema 擴充：`optional`、`flexible_pin_group`）
- `packages/workflow-core`（schema + plan 節點 + orchestration spine 擴充 + contracts.py 重構）
- `packages/reverse-core` / `packages/gerber-core`（diff + envelope 包裝）
- `services/mcp`（工具面：diff/review/contract/evidence）
- `skills/bodesign`（紀律文字）
- `tests`（fixture 驗證；A1 需要 spine→stage 推導的整合測試）
- `specs/architecture.md`（AI design workflow 段落同步；A1/A3 動到模組邊界與資料流，必須全貌同步）
