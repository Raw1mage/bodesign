# Tasks: workflow_verification-discipline

> 對應 spec.md 八項 requirement、design.md DD-1~DD-13。每完成一項立即勾選並跑 plan-sync。

## 1. RequirementContract + Debug 紀律（P1 — G1 + G6）

- [x] 1.1 擴充 `ExtractedRequirement`：新增 `metric` / `threshold` / `measurement_method` / `oracle_tool` / `verification_status` 可選欄位（預設 `verification_status="unverified"`），既有呼叫端不破（DD-1）
- [x] 1.2 定義 `OracleTool` 封閉枚舉（`drc_gate | erc | crosscheck | si_check | gerber_compare | spice | user_judgment | none`）+ fail-fast 校驗：`none` 強制標記 `unverifiable` 並進 open_questions（DD-2）
- [x] 1.3 合約收斂邏輯接入 `plan_design_intent` 流程：可量測項綁 metric/threshold/oracle，沿用 `C00_REQUIREMENT_FIELD_BINDINGS`，`validate_requirement_bindings` 模式不變
- [x] 1.4 per-requirement pass/fail 對表輸出：缺 oracle 執行記錄的項目維持 `unverified`，禁止推定 pass（DD-9）
- [x] 1.5 擴充 `BlockerReturn`：新增可選 `simple_fix_candidates[]`（`{hypothesis, check_method, ruled_out, evidence_ref}`）（DD-3）
- [x] 1.6 skills/bodesign 增補 G6 debug 成本排序紀律段落：結構性提案前必須 all `ruled_out`
- [x] 1.7 P1 fixture-driven 測試：合約收斂、unverifiable fail-fast、pass/fail 表、simple_fix_candidates 序列化

## 2. Design Review Gate + 結構化 Diff（P2 — G2 + G3/A4，depends 1）

- [x] 2.1 stage 序列插入 `design-review` 節點（propose-layout-intent 與 deterministic-validation 之間），gate 檢查裁決欄位 + 情境清單非空（DD-4）
- [x] 2.2 DesignReviewRecord evidence 落盤格式（client 專案資料夾）+ stage 狀態依文檔存在性與裁決推導；`REJECT` → validation blocked；無 review 記錄 → fail-fast blocker
- [x] 2.3 skills/bodesign 增補 G2 review 方法論：最低情境集（電源時序、reset 鏈、I2C 位址、電平相容、差分對拓撲）
- [x] 2.4 新增 `crosscheck_diff()`：回傳 `CrossCheckDiff`（`items[]` 帶 dimension/key/status/severity/evidence_refs + `first_divergence`）；保留 `crosscheck_nets` 與 markdown 渲染雙軌（DD-5）
- [x] 2.5 缺 evidence 維度顯式回報 `dimension-unavailable`，禁止輸出假 matched
- [x] 2.6 四段式 root-cause 報告 schema（methodology/findings/evidence[]/fix）+ 寫入 events
- [x] 2.7 P2 fixture-driven 測試：review gate blocked 路徑、CrossCheckDiff、first_divergence、dimension-unavailable

## 3. Evidence Backflow + ValidationEvidence（P3 — A3 + A5，depends 1）

- [x] 3.1 新檔 `validation_evidence.py`：`ValidationEvidence` dataclass（`{tool, inputs, findings[], severity, anchors[], requirement_refs[]}`）+ `wrap_validation_evidence()` adapters（si_check / DRC gate / crosscheck），原生回傳保留（DD-6）
- [x] 3.2 spine 新增 `evidence_returns/`：schema `bodesign.c00.evidence_return.v1`、count-based ID（`<LAYER>-EV-0001`）、JSON 落盤、append `log.jsonl`、malformed → `OrchestrationError`（DD-7）
- [x] 3.3 C00 ingest：evidence return 更新 requirement `verification_status`；fail 項可開新 work packet（沿用既有 dispatch），不自動執行修改
- [x] 3.4 MCP 工具層接線：驗證工具輸出包裝 envelope；agent_registry 授權沿用
- [x] 3.5 P3 fixture-driven 測試：envelope 包裝逐工具鎖定、evidence return 持久化、malformed fail-fast、C00 ingest 更新狀態

## 4. 編排表面統一（P4 — A1，depends 3）

- [x] 4.1 新函式 `derive_workflow_plan(folder)`：由 spine 狀態（packets + blockers + evidence returns）計算 stage status/blockers；`plan_reference_board_workflow()` 降級為模板產生器（DD-8）
- [x] 4.2 無 `_orchestration/` 時回報 `spine-not-initialized` blocker，不 fallback 回參數快照（天條）
- [x] 4.3 `/workflow/reference-board` 切換至推導路徑；回傳 shape 不變（API 向後相容）
- [x] 4.4 P4 測試：spine 推導正確性、未初始化 fail-fast、既有呼叫端相容性（既有測試全綠）

## 5. Reference Comparator（P5 — G7，depends 2, 3）

- [x] 5.1 IR 最小 schema 擴充：`optional` 元件標記 + `flexible_pin_group`（可選欄位，既有 IR 不破）+ comparator 輸入校驗（缺必要欄位 → `CMP_IR_INVALID` fail fast）（DD-13）
- [x] 5.2 `design_ir/compare/` 子模組骨架：scoring config（權重 0.4/0.2/0.4 預設、閾值集中）+ 對稱被動件 pin 正規化（`__sym__`）+ FlexiblePin 展開（DD-10/DD-12）
- [x] 5.3 元件匹配：pin 鄰域簽名 → 相似度矩陣 → Hungarian 全域指派；required 先行、optional 缺席不扣分；tie-breaking 規則明確化（DD-12）
- [x] 5.4 三項子分數計算：`S_comp`（Dice）/ `S_attr` / `S_conn` + 加權總分
- [x] 5.5 mismatch 明細輸出：`CrossCheckDiffItem`（dimension 擴充 `component`/`pin`）+ `first_divergence`；整體結果包裝 `ValidationEvidence` envelope（`tool="crosscheck"`）（DD-11）
- [x] 5.6 P5 test vectors + fixture 測試：良品自比對滿分、缺件/值差/net 調換的分級退化曲線、確定性（重複執行 byte-equal）、`CMP_IR_INVALID` fail-fast、板級規模 benchmark（數百元件 Hungarian 可行性）

## 6. 收尾

- [x] 6.1 全 scenario 測試於乾淨 clone 通過（pytest）
- [x] 6.2 `specs/architecture.md` 同步（A1/A3 模組邊界與資料流變更；G7 新增 design-ir compare 子模組）
- [x] 6.3 event log 收尾記錄 + 驗證證據附 handoff.md
