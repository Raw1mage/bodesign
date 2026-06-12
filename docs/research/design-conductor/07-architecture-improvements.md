# 07 — 架構級改良分析（基於原始碼偵查）

> 對照層級：不是工作流紀律（那是 06 的 G1–G7），而是 **bodesign 現有架構本體**的結構性改良。
> 證據來源：`packages/workflow-core/bodesign_workflow_core/` 原始碼實讀（2026-06-12）。
>
> **定位修正（2026-06-12）**：本文件每一項發現（A1–A5）都獨立站在 bodesign 程式碼的行號證據上——DC 論文僅是觸發偵查的透鏡，不是依據。晶片設計的領域專業與 PCB 零轉移；下表的「DC 概念」欄只是命名對照，刪掉整欄論證依然成立。

## 0. 先說好消息：編排骨幹已經存在

偵查發現 bodesign 其實**已有**完整的編排骨幹，而且比 architecture.md 描述的「client-orchestrated 報告器」更進一步：

| 能力 | bodesign 現有實作 | 證據 |
|---|---|---|
| 編排 spine | **C00 orchestration spine**：work packet dispatch + blocker backflow + append-only log | `orchestration.py:1-25`（`bodesign.c00.work_packet.v1` / `blocker_return.v1`，`_orchestration/` 資料夾狀態模型，deterministic count-based IDs） |
| 需求合約所有權 | C00 是 requirement-contract owner；下游只能 diagnose/draft/run_tool/return_blocker | `agent_registry.py:58-71`（`_DOWNSTREAM_ALLOWED` / `_DOWNSTREAM_FORBIDDEN` 含 `silently_fill_missing` 禁令） |
| 反問釐清 | keyword-based 需求抽取 + open_questions + `needs-clarification` 狀態 | `requirement_planning.py:128-160`（`plan_design_intent`） |
| 參考板對照 | net-level matched/missing/extra + coverage% + provenance | `reference_crosscheck.py:45-58`（`crosscheck_nets`） |
| 人類審批 gate | 每層有明確 `_HUMAN_GATE`（user / ID designer / EE reviewer / layout engineer…） | `agent_registry.py:48-56` |

所以架構改良不是「從零建編排層」，而是**把已存在的骨幹接起來、補齊缺的回路**。

## 1. 架構級發現與改良建議

### A1 — 雙編排表面分裂（最重要的結構問題）

**現況**：存在兩套互不相通的編排機制：

1. `contracts.py:46-120` `plan_reference_board_workflow()` — **靜態寫死的 6-stage 清單**（ingest → resolve-knowledge → reconstruct-IR → propose-intent → validation → approval），blockers 是 hard-coded 字串，給 `/workflow/reference-board` API 回報用。
2. `orchestration.py` — **真正的 runtime spine**（C00 work packets、blocker returns、`_orchestration/log.jsonl` 持久化、agent registry 授權）。

兩者沒有資料流連接：API 回報的 stage 狀態不是從 work packet/blocker 狀態推導的，是函式參數（`artifact_count`、`net_count`…）算出來的快照。

**改良**：讓 `ReferenceBoardWorkflowPlan` 的 stage status/blockers **從 `_orchestration/` 狀態推導**——單一事實來源。靜態 plan 函式降級為「模板」，runtime 狀態由 spine 擁有。這同時解決「DC 式 living 編排」與「API 回報失真」兩個問題。

### A2 — RequirementContract 的落點已經明確（G1 的架構面）

**現況**：`requirement_planning.py:83-89` 的 `ExtractedRequirement` 只有 `{key, label, state, evidence}`——state 是 `stated|answered|missing`，**沒有 metric / threshold / oracle**。這是 G1 缺口的程式級證據：需求被「抽取」但從未變成「可驗證合約」。

**改良**：不新建平行 schema，直接擴充 `ExtractedRequirement` → `RequirementContract`：加 `metric`、`threshold`、`measurement_method`、`oracle_tool`、`verification_status` 欄位。`C00_REQUIREMENT_FIELD_BINDINGS`（`requirement_planning.py:31-41`）已綁定 C00 PRD template 欄位，合約自然落進 C00 文件架構，且 `validate_requirement_bindings` 的 fail-fast 模式可沿用。

### A3 — Blocker backflow 應升級為 Evidence backflow（DC 的「下游證據反寫上游」）

**現況**：下游 → C00 的回流通道只有 **blocker**（問題、決策需求）。DC 的關鍵能力是 P&R timing 這種**量測證據**也回流並反寫 design proposal（living document）。bodesign 的驗證結果（ERC/DRC/SI/crosscheck）目前是終端報告，不進 spine。

**改良**：在 `_orchestration/` 增加第三類 artifact：`evidence_returns/`（`bodesign.c00.evidence_return.v1`）。驗證工具產出的量測結果（含 per-requirement pass/fail，接 A2 的合約）作為 evidence return 回流 C00，C00 據此更新 PRD answer_state 或開新 work packet。這就是 DC living proposal 的 bodesign 版本——且完全沿用既有 spine 的持久化與 log 模式。

### A4 — 交叉檢核從 net-level 擴展為多層 diff（G3 的架構面）

**現況**：`reference_crosscheck.py` 的 matched/missing/extra 結構**已經是 G3 要的 diff 形狀**，但只有 net 名稱集合一個維度，且 verdict 是 prose 字串。

**改良**：把 `ReferenceCheck` 泛化為 `CrossCheckDiff`，維度擴展：nets → pins/pads → 關鍵元件值 → 規則（layout rules from component-kb L6）。每筆 diff item 帶 `severity` 與 `first_divergence` 標記，verdict 從 prose 改為結構化 + prose 雙軌。現有 markdown 渲染器保留。

### A5 — 工具驗證輸出缺統一 envelope（G4，架構債）

**現況**：各工具回傳結構各異（`si_check` 回 effective values、DRC gate 另一格式、crosscheck 又一格式）。agent 要跨工具彙整證據時得逐一適配——正是 DC「VCD→CSV 資料化」要避免的狀況。

**改良**：定義 `ValidationEvidence` envelope（`{tool, inputs, findings[], severity, anchors, requirement_refs[]}`），新工具強制、舊工具漸進包裝。`requirement_refs` 連到 A2 合約，使 per-requirement pass/fail 表可機器生成。

## 2. 依賴關係與建議順序

```
A2 RequirementContract（schema 擴充，獨立可做）
 │
 ├─→ A3 Evidence backflow（evidence 要能引用 requirement）
 │     │
 │     └─→ A1 編排表面統一（stage 狀態從 spine 推導，evidence/blocker 都是輸入）
 │
 └─→ A5 ValidationEvidence envelope（requirement_refs 依賴 A2）
       │
       └─→ A4 多層 diff（diff 輸出採 envelope 格式）
```

A2 是一切的錨點——這與 06 的結論一致（G1 先行）。A1 是最大的結構手術，放最後。

## 3. 與既有 plan 的關係

`plans/workflow_verification-discipline/`（proposed）目前 scope 是 G1+G6+G2+G3。本分析的對應：

- **A2 = G1 的具體落點**（已在 plan IN scope，本分析補上「擴充 ExtractedRequirement 而非平行 schema」的設計決策）
- **A4 = G3 的具體落點**（已在 plan IN scope，落點確認為 `reference_crosscheck.py` 泛化）
- **A3、A5、A1 = 新增架構項**，原 plan 未涵蓋（A5 原列 G4/OUT）

選項：(a) 把 A3 納入現有 plan、A5/A1 留後續；(b) 現有 plan 不動，另開架構 plan 收 A1/A3/A5；(c) 全部併入現有 plan 變大 scope。
