# Handoff: feature_component_vault

## Execution Contract

- 本案在 `implementing` 階段由 build agent 依 `tasks.md` phase 順序執行（Phase 1 → 6），每完成一個 task 立即勾選並跑 plan-sync。
- **單一真相來源**：schema 一律以 `data-schema.json` 為準；任何 DDL 偏離必須先回寫 data-schema.json 再實作（amend mode）。
- field_path 命名空間沿用 `packages/component-kb/bodesign_component_kb/vault.py` 的 `FIELD_ALIASES`；不得另創平行命名。
- canonical key 正規化沿用 `contracts.py` 的 `component_knowledge_key()`；不得重新實作第二份正規化邏輯。
- 測試 fixture-driven（репо慣例）；test-vectors.json 是測試種子的單一來源。

## Required Reads

> 開工前必讀。

1. `plans/feature_component_vault/data-schema.json` — schema SSOT
2. `plans/feature_component_vault/spec.md` — R1–R10 行為需求
3. `plans/feature_component_vault/design.md` — DD-1~DD-9 決策與風險
4. `packages/component-kb/bodesign_component_kb/contracts.py` — 既有 dataclass 與 key 正規化
5. `packages/component-kb/bodesign_component_kb/vault.py` — spec_check 四態語意與 FIELD_ALIASES
6. `specs/architecture.md` — Knowledge base 段落與 External datasheet policy

## Hard Constraints（紅線）

- **禁止新增 fallback mechanism**：DB 損毀 fail-fast 不重建空庫；查無資料回顯式 absent 不回空殼；未知 field_path 回 error 不回空結果。
- **外部自動下載 datasheet 維持關閉**：`/knowledge/external-fetch` policy gate 不在本案解鎖。
- **verified 必須帶 evidence**：由 DB trigger 強制，不靠應用層自律；測試必須覆蓋 trigger ABORT 路徑。
- **audit_log append-only**：schema trigger 強制，無 UPDATE/DELETE 路徑。
- **client cache 匯入不靜默覆蓋**：衝突保留兩者並標示。
- **blob 先寫、DB 後 commit**：ingest 交易順序不可顛倒。

## Stop Gates In Force

| Gate | 條件 | 動作 |
|---|---|---|
| schema 偏離 | 實作中發現 data-schema.json 欄位不合用 | 停下，amend data-schema.json + design.md 後再繼續 |
| 既有合約破壞 | `ComponentKnowledge`/`spec_check` 簽名變更影響既有呼叫端 | 停下，列出受影響呼叫端，請使用者確認 |
| 新增依賴 | 需要引入新第三方套件（SQLite 以外） | 停下，請使用者批准 |
| scope 膨脹 | 發現需要 embedding / live distributor query / external fetch | 停下，走 extend mode |
| docker 佈局變更 | docker-compose 掛載點影響其他 service | 停下，請使用者確認 volume 路徑 |

## Validation Plan

- 每 phase 結束：`pytest` 對應 fixture 測試全綠（tests/ 慣例路徑）
- Phase 1 完成：docker volume 重啟資料保留驗證（R10）
- Phase 3 完成：trigger 行為驗證（verified-needs-evidence ABORT、audit append-only ABORT）
- Phase 4 完成：MCP tool + HTTP 端點整合測試（happy + absent/error path）
- 全案完成（→verified 前）：test-vectors.json 全向量通過、`specs/architecture.md` Knowledge base 段落已同步、CHANGELOG 已更新

## Execution-Ready Checklist

- [x] data-schema.json 完成且通過 designed 驗證
- [x] spec.md R1–R10 + Acceptance Checks 完成
- [x] tasks.md phase 切分完成（6 phases）
- [x] test-vectors.json / errors.md / observability.md 完成
- [ ] 使用者批准進入 implementing
