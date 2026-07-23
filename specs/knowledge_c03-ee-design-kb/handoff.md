# Handoff: knowledge_c03-ee-design-kb

## Execution Contract

執行者交付兩張 BR 的修復，依賴序 A1→A2→A3，done 定義 = tasks.md 全勾 + BR_A/BR_B validation 全過：
- **A1**：`_h_kb_query` 多詞 OR-ranked；`test_kb_tools.py` 綠；`crystal oscillator load capacitor` 命中在庫物件。
- **A2**：regulator 拓撲/SI 數值/pull-up sizing 三主題 ingest 成 graded control 且可查。
- **A3**：passive-completeness gate 攔 pinout-only 板、放行 honest-subset+waiver；判準引 KB threshold。

## Required Reads

- `plans/knowledge_c03-ee-design-kb/{proposal,design,spec,tasks}.md` + `idef0.json` / `grafcet.json`
- `issues/BR_20260723_kb_query_fts_and_false_negative_and_c03_content_gaps.md`（BR_A）
- `issues/BR_20260723_c03_composer_accepts_pinout_only_no_passive_completeness_gate.md`（BR_B）
- `research/c03-capability-diagnosis.md`（設計能力邊界）
- `services/mcp/server.py`（`_h_kb_query` L908-953）、`skills/bodesign/stages/c03-ee/references/pinout-to-circuit-method.md`（9-class obligation SSOT）
- `specs/architecture.md`（動手前，C03/KB 段）

## Stop Gates In Force

- **A3-T1（gate policy）**：哪些 pin class 算 mandatory obligation + waiver 語義 → **升使用者**，agent 不拍板（DD-3）。
- **A1 動 core**：`server.py` 改後需 `mcpctl.sh restart`（禁繞過 denylist；用 restart_self）。
- 送廠/破壞性動作：本 plan 無，但 A3 gate 一旦上線影響 C04 入口，行為變更需可觀測 + 使用者知悉。

## Execution-Ready Checklist

- [ ] BR_A / BR_B 已讀，依賴序 A1→A2→A3 理解
- [ ] `pinout-to-circuit-method.md` 9-class 表已讀（A3 gate 的 SSOT）
- [ ] 確認 A1 先於 A2（ingest 後要撈得到）、A2 先於 A3（gate 引 threshold）
- [ ] gate policy stop gate 已排入 A3.1（先問使用者再實作）
