# Tasks: mcp_r17-r06-conformance

## 1. Preflight + content-assertion pure module (A4 / DD-4)

- [x] 1.1 新增 `services/mcp/preflight.py`：`preflight_assets(doc_dir, asset_paths)` 純函式，分類 resolved/unresolved/out_of_namespace/host_only_absolute/missing_media，回 typed `PREFLIGHT_*` + remedy dict
- [x] 1.2 `assert_content(produced, assertions)` 純函式：驗 expected_files/expected_media/required_text/non_empty，空成品回 `ASSERTION_EMPTY` NOT-delivery-ready
- [x] 1.3 接入 `run_tool`：render/emit/assemble 工具（emit_fab/render_board_model/emit_doc/compose_schematic）dispatch 前跑 preflight、後跑 assertion（caller 傳 assert 參數時）

## 2. R0.6 wall-nudge single-source module (A5 / DD-5)

- [x] 2.1 新增 `services/mcp/_skill_nudge.py`：`skill_nudge_note/remedy/advisory` generator（docxmcp reference 對齊，`COMPANION="bodesign"`）
- [x] 2.2 `detect_wall(name, args, doc_dir)` 純 fingerprint：bad-shape id / grain-mismatch zero-element / 首次無 recon unbounded sweep → None|('hard'|'advisory', why, correct_primitive)；不查 caller skill-state（定海神針）
- [x] 2.3 `run_tool` error wrapper 新增 `_render_remedy_line` 等價：把 error.remedy dict 投影到 portable content text；hard→enrich 既有 failure（silent no-op 轉 loud）；advisory→非阻塞 hint

## 3. init capabilities summary (A1 / DD-1)

- [x] 3.1 `bodesign_init` 加 additive `capabilities` 第四鍵：transport（service_endpoints[]/host_endpoints[] 各帶 host_executable 旗標）/file_ingress/file_egress/webdav_state/companion_skill/conditional_tool_families；既有三鍵 byte-preserve

## 4. portable resource egress (A2 / DD-2)

- [x] 4.1 `@server.list_resources()`：列舉 live token 的 `bodesign://files/<token>/<rel>`
- [x] 4.2 `@server.read_resource()`：URI → TokenStore.resolve + safe_join → blob bytes（traversal guard 複用）

## 5. workspace inspection tool (A3 / DD-3)

- [x] 5.1 新增 in-process 工具 `bodesign_workspace_inspect(token, subpath?)`：list_files → `{token,doc_dir,files[],count}` 純讀無 mutation；註冊 handler + schema 兩處

## 6. R17.5 parity + R17.6 scenario wiring (DD-6 / DD-7)

- [x] 6.1 single-source `COMPANION_SKILL="bodesign"` 常數；skillPaths/GET /skills/bodesign_init 三面對齊
- [x] 6.2 doctrine.md first-use section 具名 baseline（init/stage_dir/workspace_inspect）+ conditional（emit_fab 等）工具
- [x] 6.3 確認 R17.6 (a)-(e) 五情境各由 gap 1–5 收斂（無獨立實作，靠測試證明）

## 7. Tests (結構化斷言)

- [x] 7.1 新增 `tests/test_mcp_r17_r06_conformance.py`：R17.1.2 對 init 結構化 payload 分支斷言（host_executable 旗標）
- [x] 7.2 R17.2.2/.2.3 resources/read + workspace_inspect 測試
- [x] 7.3 R17.2.4/.2.5 preflight + content-assertion 純函式各分支測試
- [x] 7.4 R0.6 hard/advisory + remedy 投影測試；R17.5 parity/drift 測試
- [x] 7.5 R17.6 (a)-(e) 五情境各一測試證明不再 silent-pass

## 8. Validation + closeout

- [x] 8.1 全 pytest 綠（PYTHONPATH 含所有 packages/* 子目錄）
- [x] 8.2 live UDS/MCP smoke（DEV-mode restart；stage_dir→workspace_inspect round-trip 已驗證）
- [x] 8.3 event_record 收尾 + `specs/architecture.md` 同步 + plan_advance → verified

## Validation Evidence

- **pytest: 31 pass / 0 fail** — `tests/test_mcp_r17_r06_conformance.py`（20 test-vector 結構化分支斷言，非 smoke），PYTHONPATH 含全 `packages/*` 子目錄。
- **回歸: 0 新增 fail** — 既有 suite pre-existing 失敗經確認為環境性（缺重 CAD/EDA 依賴），新接入零回歸。
- **live smoke: PASS** — `BODESIGN_DEV=1 ./mcpctl.sh restart` 後，`bodesign_stage_dir → bodesign_workspace_inspect` round-trip 經 harness MCP client 回 `ok=true` / `count=2`（raw wire 走 FORBIDDEN_MCP_BYPASS 擋，確認只走 sanctioned client）。
- **DNA 圖**: `idef0.json` + `grafcet.json` 均過 `specbase_diagram_validate`。
