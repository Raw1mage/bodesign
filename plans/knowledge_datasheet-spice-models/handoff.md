# Handoff: knowledge_datasheet-spice-models

## Execution Contract

- **Goal**：把 vault L4 datasheet 參數變成可被第 3 層 SPICE 驗證消費的確定性 model 卡，並讓模擬結果誠實標注 model 來源。
- **執行單位**：tasks.md 五個 phase；每完成一個 task 立即勾選 + 記錄；phase 邊界寫 slice summary event。
- **測試方式**：`export PYTHONPATH="packages/shared:packages/design-ir:packages/component-kb:packages/doc-core:packages/eda-bridge:packages/workflow-core:services/mcp"` + `.venv/bin/python -m pytest tests/ -q`（沿用前一 plan 的執行慣例）。
- **Fixture MPN**：`D-TEST-1N4148`（diode）、`L-TEST-AMS1117`（ldo）、`P-TEST-CAP100N`（passive）——對應 test-vectors.json 的 TV-* 條目。

## Required Reads

1. `design.md`（DD-1..DD-9）+ `data-schema.json`（欄位與契約 SSOT）
2. `packages/component-kb/bodesign_component_kb/repository.py` — FIELD_PATH_ROOTS / `resolve_field_path()` / `upsert_spec_value` / `_audit()` 既有形狀
3. `packages/component-kb/bodesign_component_kb/storage.py` — spec_values 表 + verified-needs-evidence triggers
4. `packages/eda-bridge/bodesign_eda_bridge/simulate.py` — SimResult 與 skill 編排
5. `~/.config/opencode/skills/spice/scripts/spice_model_cache.py` — cascade tier 1 的 manifest 格式（**唯讀參考**，鎖 fixture，不改 skill）
6. `packages/workflow-core/bodesign_workflow_core/validation_evidence.py` — envelope 介面（沿用，不新增 schema）
7. `services/mcp/server.py` — run_tool 包裝層 + TOOLS registry 模式

## Hard Constraints（天條）

- **不改 spice skill**（host 側；OUT scope）
- **缺參數不得補預設值**；多值無 typ 不得平均（SPX_PARAMS_AMBIGUOUS）
- **無 evidence 不得寫入 L4**；not_found 不落 DB
- **model 卡 byte-identical**（無時間戳）
- **smoke fail 的卡不得進 manifest**
- 不放鬆既有 verified-needs-evidence trigger；只新增 field roots，不改 EAV 結構

## Stop Gates In Force

| Gate | 條件 | 動作 |
|---|---|---|
| manifest 格式失配 | fixture 跑 `simulate_subcircuits.py` 時 cascade tier 1 未命中物化卡（R-A 風險） | 停，回報實際 manifest 格式差異，與使用者確認對策（調整物化格式 vs 另闢消費路徑），不得猜格式硬寫 |
| scope 漂移 | 實作中發現需要動 spice skill 或新增 SPICE 參數類別 | 停，走 extend mode |
| 既有測試紅 | 任何既有 484 tests 因本 plan 變紅 | 停在該 phase，先修回歸再前進 |
| commit / graduate | 全部完成後 | 等使用者明確指示；AI 不自行 commit、不自行 plan_graduate |

## Execution-Ready Checklist

- [x] proposal.md（scope 決策定案）
- [x] spec.md（5 requirements × scenarios）
- [x] design.md（DD-1..DD-9 + risks + critical files）
- [x] data-schema.json（封閉欄位清單 + 契約 + SPX 碼）
- [x] idef0/grafcet/c4/sequence（drawmiat 驗證通過）
- [x] tasks.md（5 phases / 17 tasks）
- [x] test-vectors.json（19 vectors 對應全部 requirements）
- [x] errors.md / observability.md
- [ ] 驗證證據（implementing 完成後附）

## Validation Evidence

（implementing → verified 時填入：全 suite 測試結果、新增測試數、architecture sync 記錄）
