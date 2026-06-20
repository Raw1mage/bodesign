# Handoff: c01_design-vector (extended for BR C01 ID deliverable buckets)

## Execution Contract

實作三個 C01 ID-native bucket emitter + readiness 雙軌，全部落在既有 deterministic、script-first 的 C01 模組內。LLM 僅在 Ai file bucket 的 S2 受控組裝（選圖元 + 座標 + 色值）出現，輸出須過 schema 驗證。其餘 bucket 為純確定性推導。

## Required Reads

- `packages/workflow-core/bodesign_workflow_core/c01_id_package.py` — 既有 `C01_OUTPUTS`（五件 core companion）、`C01_INTERACTION_FIELDS`、`EXPOSED_COMPONENT_KEYWORDS`、`_constraints()`、`assess_c01_package_readiness()`、answer_state 機制。新 emitter 沿用這些，不另立平行狀態。
- `services/mcp/server.py` — c01 handler/schema 註冊區塊（~line 136 handler、~line 793 schema）。
- `plans/c01_design-vector/design.md` DD-1..DD-8、`data-schema.json`、`spec.md` 五個 Requirement。
- BR：`issues/issue_20260617_c01_rockbox_style_id_deliverables.md`。

## Key Constraints（天條）

- **No silent fallback**：各 bucket 缺關鍵欄位 → fail-fast 回 `missing`/`external-needed` + 缺欄清單，不以預設值續跑。
- **不偽造原生檔**：無 Illustrator path 不產 `.ai`；無 Figma 產 `figma_import_spec.json`。
- **PDF 走 pipeline**：經 `bodesign_emit_doc`（markdown→docx+pdf）或 `bodesign_mcp_call` 驅動 docxmcp，不手工拼 PDF bytes。
- **draft-marking 必有**：每個視覺/文件帶可見標記（`not final industrial design` / `not CMF approval` / `not UI sign-off`），`draft_markings` 不得為空。
- **readiness 向後相容**：既有 `readiness_pct`/`usable`/`artifacts` 對 core companion 語意不變；ID-native 產出不升 approved。
- **路徑並存**：BR bucket 用 `C01-ID/Display UI_UX/`（底線），與既有 companion `C01-ID/Display UIUX/`（無底線）並存不衝突。

## Stop Gates In Force

- 任何需要把 `human_approved` 改非 False 的設計 → 停（人工 gate）。
- PDF pipeline 不可用（docxmcp 無法呼叫）→ 回報 blocker，不手工拼 PDF。

## Validation Plan

- 三 bucket emitter 各自：正常輸出（檔案齊全 + draft_markings 非空）、fail-fast（缺欄不產檔）。
- Ai file：SVG schema（圖層齊全、元件 group、placeholder 告知）、不偽造（ai_emitted=false / 無 .ai）。
- readiness：companion 與 id_native 分軌、向後相容、不升 approved。
- 全測試套件綠燈；`specs/architecture.md` 同步；event log 收尾。

## Execution-Ready Checklist

- [x] spec.md 五 Requirement（含 v2 ADDED 四項）
- [x] design.md DD-1..DD-8
- [x] data-schema.json（BucketResult / CmfTokens / DualTrackReadinessExtension）
- [x] idef0.json / grafcet.json（drawmiat-validated）
- [x] tasks.md（7 phases）
- [ ] 進入 implementing
