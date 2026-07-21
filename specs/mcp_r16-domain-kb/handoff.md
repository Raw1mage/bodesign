# Handoff: mcp_r16-domain-kb

## Execution Contract

- 交付 `bodesign_kb_query` + `bodesign_kb_get` 兩個 read-only MCP 工具（core group，pure-python stdlib sqlite3），三份 compose 的 KB 掛載 + `BODESIGN_KB_DB` env，mcp.json signpost + version bump，判斷密集工具 `consider:` affordance，及 `tests/test_kb_tools.py`。
- Done = tasks.md 全勾 + 新測試全綠 + 既有套件無回歸 + live MCP smoke（kb_query 由 rail 命中既有蒸餾物件）+ 兩門一致性通過。

## Required Reads

- `plans/mcp_r16-domain-kb/design.md`（DD-1..DD-6，尤其 DD-3 WAL 唯讀策略）
- `specs/architecture.md`（C00-C07 邊界、core vs worker）
- `services/mcp/server.py` 既有 handler 模式（`_h_*` + TOOLS schema 雙處註冊）
- 實作 SQL 前：`sqlite3 .specbase/ragbase.sqlite ".schema"`（DD-2，不憑記憶寫欄位名）
- `~/projects/opencode/specs/mcp-integration-standard/standard.md` §R16（上游契約）

## Stop Gates In Force

- 不得新增任何 KB 寫入工具（R16.4）
- 不得引入 fallback（KB 缺 → KB_UNAVAILABLE，不猜路徑、不回空 hits）
- compose 變更後用 `BODESIGN_DEV=1 ./mcpctl.sh restart` 驗證，不得手工 docker run

## Execution-Ready Checklist

- [x] KB 實體存在且非空（52+ objects，2026-07-11 蒸餾）
- [x] 上游 R16 條文已 living（opencode spec）
- [x] design DD 完整、test vectors 定義
- [ ] 實作者已讀 required reads
