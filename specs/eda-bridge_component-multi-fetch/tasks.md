# Tasks: eda-bridge_component-multi-fetch

## 1. eda-bridge 多筆迭代

- [x] 1.1 `component_fetch.py` 新增 `fetch_components(lcsc_ids, output_lib, *, overwrite=True)`：順序迭代呼叫 `fetch_component`，continue-on-error，回傳 `{ok, output_lib, fetched, failed, results[]}`（DD-1/DD-2/DD-4）。空輸入 fail-fast。

## 2. MCP handler + schema

- [x] 2.1 `services/mcp/server.py` `_h_component_fetch`：lcsc_id XOR lcsc_ids 分派，皆無/皆有 → 顯式報錯（DD-3）。XOR 檢查前置於重 import（bad-args fail-fast）。
- [x] 2.2 `bodesign_component_fetch` schema 加 `lcsc_ids: {type:array, items:string}`；`required` 改為僅 `output_lib`（XOR 由 handler 把關）；description 補多筆用法。

## 3. 驗證

- [x] 3.1 `tests/test_component_fetch_multi.py`：mock `fetch_component`，驗 (a) 全成功 results/fetched (b) 部分失敗 continue-on-error + failed 計數 (c) 空 lcsc_ids fail-fast。
- [x] 3.2 handler XOR 分派單元測試（皆無/皆有報錯、單筆走舊路徑）。
- [x] 3.3 跑既有 component_fetch 相關 test 確認無回歸；architecture sync check；收尾 event。

## Validation

- `python3 -m unittest tests.test_component_fetch_multi`: **6 pass / 0 fail** (2 skipped — `test_*_routes_*` skip when kiutils worker-only dep absent, by design per AGENTS.md §4).
- `python3 -m unittest tests.test_component_kb`: **4 pass / 0 fail** (no regression).
- `python3 -m py_compile services/mcp/server.py packages/eda-bridge/bodesign_eda_bridge/component_fetch.py`: OK (both compile).
- Architecture Sync: Verified (No doc changes) — capability extension of existing `component_fetch` tool (array input + iteration wrapper); no module-boundary / data-flow / state-machine / observability change. `specs/architecture.md` carries no named `component_fetch` description, so nothing to sync.
