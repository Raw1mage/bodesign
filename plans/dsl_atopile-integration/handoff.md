# Handoff: dsl_atopile-integration

## Execution Contract

- 交付 `ato_build` MCP 工具全鏈：Dockerfile.ee toolchain → ato_bridge（subprocess 包裝 + 錯誤解析 + 證據組裝）→ server.py 註冊/路由 → workflow-core 三處 constraint_solve 註冊 → test-vectors 全過。
- Done 定義 = tasks.md 全勾 + spec.md Acceptance Checks 全過 + `specs/architecture.md` 同步。
- 每完成一個 slice 立即勾對應 tasks.md checkbox（不批次補）。

## Required Reads

- `plans/dsl_atopile-integration/design.md`（七項 DD，特別是 DD-5 選料三態、DD-6 結構化錯誤）
- `plans/dsl_atopile-integration/data-schema.json`（request/result/deficiency/evidence 契約）
- `specs/architecture.md`（C03/C04 邊界、core/worker 分工）
- `services/mcp/server.py:83-110, 646-, 860-950`（handler 模式、TOOLS 註冊、worker 路由）
- `packages/workflow-core/bodesign_workflow_core/validation_evidence.py`（信封契約）

## Stop Gates In Force

- **No new fallback**：任何「pick 不到就用近似值」「registry 不通就跳過驗證」都是缺陷；fail fast + 缺項清單。
- **atopile 版本變更**（0.12.5 → 其他）需使用者批准（DD-1）。
- **send-to-fab 不在本 spec 範圍**；ato 產物仍須走既有 DRC gate + 使用者批准才可出廠。
- **graduate 僅使用者觸發**。

## Execution-Ready Checklist

- [x] design.md 七項 DD 定案，IDEF0/GRAFCET 經 drawmiat 驗證
- [x] 整合接點 code anchors 已查證（explore 調查 2026-07-03）
- [ ] atopile 0.12.5 在 ubuntu 24.04 / Python 3.12 可安裝（1.1 首步實測）
- [ ] `BODESIGN_DEV=1` dev loop 環境可用
