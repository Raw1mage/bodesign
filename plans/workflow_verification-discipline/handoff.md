# Handoff: workflow_verification-discipline

## Execution Contract

- **目標**：把 `tasks.md` 五 phase（+ 收尾）全部落地，讓 bodesign 的需求→設計→驗證迴圈具備機器可查合約與證據鏈，並補上交叉檢核層的確定性 comparator 引擎。
- **執行表面**：bodesign repo 主線（`packages/workflow-core/`、`packages/design-ir/`、`services/mcp/`、`skills/bodesign/`、`tests/`）。
- **Phase 順序**：1 → 2 與 3 可並行（都只依賴 1）→ 4（依賴 3）→ 5（依賴 2+3：消費 `CrossCheckDiffItem` 與 `ValidationEvidence` 契約）→ 6 收尾。單一 agent 執行時依 1→2→3→4→5→6 直序。
- **每完成一個 task**：立即勾選 `tasks.md` checkbox + 跑 `plan-sync.ts`；phase 邊界寫 phase summary（plan-builder §16.4）。

## Required Reads

1. `plans/workflow_verification-discipline/spec.md` — 八項 requirement 的 GIVEN/WHEN/THEN（驗收基準）
2. `plans/workflow_verification-discipline/design.md` — DD-1~DD-13 決策與理由（實作邊界）
3. `plans/workflow_verification-discipline/data-schema.json` — 全部資料契約（欄位即法律）
4. `plans/workflow_verification-discipline/errors.md` — 錯誤碼目錄（fail-fast 路徑）
5. `specs/architecture.md` — 現有模組邊界與 spine 模式
6. Code anchors（design.md 末段）— 動刀前親讀每個錨點的現況實作

## Stop Gates In Force

| Gate | 條件 | 動作 |
|---|---|---|
| **架構偏離** | 實作中發現 DD-N 決策不可行（如 `ExtractedRequirement` 擴充破壞既有序列化） | 停，回報證據，走 `amend`/`revise` mode，不得自行改設計 |
| **API 相容性破壞** | 既有測試紅燈且修法需要改回傳 shape | 停，這違反 DD-8 / spec「API 向後相容」requirement，需使用者決策 |
| **新 fallback 誘惑** | 任何「先讓它能跑」的 fallback 路徑 | 禁止（天條）。fail fast + 顯式錯誤碼（errors.md） |
| **scope 膨脹** | 發現 G4/G5 等 plan 外項目「順手可做」（含 comparator 的 MCP tool 包裝、golden reference 入庫管線、LLM 語意審查——皆為 OUT） | 不做。記 event log，留待 `extend` mode |
| **oracle 枚舉不足** | 真實需求需要枚舉外的 oracle | 停，枚舉擴充走 `amend` mode（design.md Risks 已預告） |

## Validation Plan

- 每 phase 的 fixture-driven pytest（tasks.md 1.7 / 2.7 / 3.5 / 4.4）對應 `test-vectors.json` 的 TV-* 條目
- 收尾：乾淨 clone 全測試綠 + 既有測試全綠（相容性 gate）
- `specs/architecture.md` 同步（A1/A3 改動模組邊界）後才可宣告完成

## Execution-Ready Checklist

- [x] spec.md / design.md / data-schema.json 完成（designed 已過）
- [x] tasks.md 五 phase 拆解完成（P5 comparator 併入後）
- [x] test-vectors.json 19 條 TV 對應全部 scenario（含 TV-G7-01~05）
- [x] errors.md 19 個錯誤碼 + 處理原則（含 CMP_IR_INVALID / CMP_CONFIG_INVALID）
- [x] observability.md 事件/指標/checkpoints 定義
- [x] 使用者批准進入 implementing（2026-06-12 "go"）

## Validation Evidence（implementing 收尾，2026-06-12）

- **全測試**：`python -m unittest discover -s tests` → **484 tests OK（skipped=6）**，含既有回歸全綠（API 向後相容 gate 通過）
- **新測試檔**：
  - `tests/test_requirement_contract.py` — 19 tests（P1：TV-G1-01/02/03、TV-G6-01）
  - `tests/test_verification_discipline_p2.py` — 20 tests（P2：TV-G2-01/02、TV-G3-01/02）
  - `tests/test_verification_discipline_p3.py` — 19 tests（P3：TV-A5-01、TV-A3-01/02/03 + MCP e2e）
  - `tests/test_verification_discipline_p4.py` — 13 tests（P4：TV-A1-01/02/03）
  - `tests/test_verification_discipline_p5.py` — 21 tests（P5：TV-G7-01~05，含 200 件 board-scale benchmark）
- **Architecture Sync**：`specs/architecture.md` 已全貌同步（design-ir compare 子模組、AI design workflow 段落改寫：spine 推導、design-review gate、evidence backflow、envelope、root-cause）
- **Drift**：全程無 sync warning；無新增 fallback（天條合規：SPINE_NOT_INITIALIZED / CMP_IR_INVALID / EV_SCHEMA_INVALID 等皆 fail-fast）
- **Phase summaries**：P1–P5 各一筆 event（scope `workflow/verification-discipline`）
