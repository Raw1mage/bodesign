# Handoff: quality_prd-bom-crosscheck

## Execution Contract

- 交付 L1（pure function + tests + MCP 註冊）與 L2（GUIDE 協議 + readiness 接線 + architecture sync）；L3 在使用者裁決拓撲後執行。
- Done 定義：tasks.md 1.x/2.x 全勾、目標測試綠、E2E 迴歸案（現有純電阻 netlist → BLOCKING FAIL）證據落盤。

## Required Reads

- `plans/quality_prd-bom-crosscheck/design.md`（DD-1..DD-5）與 `data-schema.json`（manifest/report schema 為契約）
- `issues/BR_20260703_prd_bom_crosscheck_gap_cc_regulator_missing.md`（RCA 三層失效鏈）
- `packages/workflow-core/bodesign_workflow_core/c00_prd_template.py:226`（readiness 慣例）
- `services/mcp/server.py`（handler/schema 註冊慣例 + tool count 測試）

## Stop Gates In Force

- L3 拓撲裁決（AL5809 datasheet ingest / NPN sink）— user-only。
- approvals[] 寫入 — user-only；工具與 agent 不得自行寫批准。
- commit / push — 使用者明確指示才做。

## Execution-Ready Checklist

- [x] BR 已立案並投影 issue 物件
- [x] E2E 迴歸素材存在（`experiments/e2e-led-driver/C00-PRD/answer_state.json` + `C03-EE/e2e-led-driver.net`）
- [ ] 使用者裁決 L3 拓撲（僅 gate L3；L1/L2 不受阻）
