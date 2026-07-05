# Handoff: quality_deterministic-preplacement

## Execution Contract

- 交付 `preplace.py` + `placement_rules.py` 純核心、`routing.py` strategy 接線、`server.py` schema、`tests/test_preplace.py`。
- Done = tasks.md 全勾 + spec.md Acceptance Checks 全過 + 基線對比量化數據記入 tasks.md 3.3 附註。

## Required Reads

- `plans/quality_deterministic-preplacement/design.md`（DD-1~DD-8）
- `specs/validation/prd-to-gerber-e2e/research/patent-placement-rules.md`（R1-R18 錨點）
- `packages/eda-bridge/bodesign_eda_bridge/routing.py:79-177`（net2pcb_board 現況）

## Stop Gates In Force

- graduate 到 /specs/ 僅使用者明確指示（zone contract）。
- 不新增任何 fallback：deterministic 缺幾何必 fail fast。

## Execution-Ready Checklist

- [x] 研究錨點文件存在且已讀（arxiv/patent research md）
- [x] 現有 placement 路徑已勘查（grid 段 routing.py:130）
- [x] 測試跑法確認（PYTHONPATH 全 packages、python3）
