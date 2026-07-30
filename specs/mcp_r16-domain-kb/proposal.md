# Proposal: mcp_r16-domain-kb

## Why

- bodesign 的知識基礎（ragbase KB，`.specbase/ragbase.sqlite`，52+ 筆 evidence-graded PCB 設計知識：IPC 間距/載流表、EMC 去耦準則、DFM 閘、derating gate、failure modes）目前只存在 host-side，唯一讀取路徑是 specbase `gate.ts ragbase_query`（需要 host 檔案系統 + bun）。
- **bodesign 的用戶——透過 MCP 驅動 `bodesign_*` 工具的 agent（含經 gateway 連入的遠端 client）——完全查不到這個 KB**。服務要求領域判斷（layout、EMC、derating），卻不供給支撐判斷的領域記憶。
- 上游標準已就位：mcp-integration-standard **R16 Domain-KB self-shipping**（DD-21，2026-07-11 extend）規定 expert-domain MCP MUST 自帶 in-band queryable domain KB。bodesign 被指定為 R16 reference impl。

## Original Requirement Wording (Baseline)

- "bodesign的知識基礎非常弱，而且不會主動調用KB. 先從github蒸餾知識進入KB，讓設計者可以在需要的時候補充知識。"（蒸餾已完成：52 筆，6 repos，2026-07-11）
- "重點是bodesign的用戶，也就是agent，能不能在工作中查到bodesign的ragbase"
- "這個工具應該是mcp integration standard spec中要強制規定的，所有專家型 mcp 除了帶skill也應應該帶rag"

## Requirement Revision History

- 2026-07-11: initial draft created via plan-init.ts
- 2026-07-11: scoped to R16 reference impl（標準條文已在 opencode spec 落地；本 plan 只做 bodesign 端實作）

## Effective Requirement Description

1. bodesign MCP server 新增 `bodesign_kb_query(q, type?, limit?)` 與 `bodesign_kb_get(id)` 兩個 read-only 工具，對 repo 的 ragbase KB 做確定性檢索（FTS/BM25 + 短 token LIKE fallback，比照 specbase 查詢語義），任何 MCP client（UDS 或 TCP）皆可呼叫。
2. KB store 掛載進 core 容器；serving 端 application-level 唯讀（R16.4：無 KB-write MCP 工具；寫入唯一路徑仍是 host-side specbase producer）。
3. Recall-first signpost（R16.5）：`mcp.json` instructions 加一句 KB 宣告；判斷密集工具（layout/EMC/SI/derating 類）description 加 `consider: bodesign_kb_query`。
4. 查詢降級自述（R16.6）：payload 揭露 matchMode（fts / like-scan / hybrid）；KB 檔缺失 → typed `KB_UNAVAILABLE` fail-fast，不回靜默空結果。

## Scope

### IN
- `services/mcp/server.py`：兩個 handler + schema（core group，pure-python）
- `docker-compose*.yml`：`.specbase/` 掛載進 core 容器
- `mcp.json` instructions signpost + 版本 bump
- 判斷密集工具 description 的 `consider:` affordance
- unittest（查詢語義 + fail-fast + read-only 驗證）

### OUT
- KB 內容擴充（另有蒸餾工作流）
- KB 寫入工具（R16.4 明確禁止）
- R15 `bodesign_init` guide（另案 `mcp_r15-self-describing-guide`；本 plan 只在既有 instructions 加 signpost）
- specbase 端任何變更

## Non-Goals

- 不做 LLM re-ranking / semantic embedding（R16.2 deterministic serving）
- 不做 KB 同步/複製（R16.7 one-KB-two-doors：同一個 sqlite 檔，兩個門）

## Constraints

- Core-side pure-python（不得引入 worker-only 依賴）；sqlite3 stdlib 即可
- 天條 1：KB 不可用 → fail fast 顯式報錯，不靜默續跑
- WAL store：host 端 producer 用 WAL 寫入；容器讀取需能建 `-shm`/`-wal` side files → 掛載目錄 rw、application 層 `mode=ro` + `PRAGMA query_only` 強制唯讀（見 design DD-3）

## What Changes

- bodesign MCP tool 數 53 → 55（`bodesign_kb_query`, `bodesign_kb_get`）
- core 容器新增 `.specbase/` bind mount + `BODESIGN_KB_DB` env
- `mcp.json` instructions 增 KB signpost 段

## Capabilities

### New Capabilities
- `bodesign_kb_query`: 對 ragbase KB 做確定性全文檢索，回傳 evidence-graded 知識物件（id/type/title/score/confidence/matchMode）
- `bodesign_kb_get`: 取單一知識物件全文（body_md + provenance）

### Modified Capabilities
- 判斷密集工具 description：加 `consider: bodesign_kb_query` recall-first affordance

## Impact

- `services/mcp/server.py`（handler + schema 註冊）
- `docker-compose.yml` / `docker-compose.dev.yml` / `docker-compose.workers.yml`（掛載）
- `mcp.json`（instructions + version）
- `tests/`（新測試模組）
- 上游 spec：`opencode/specs/mcp-integration-standard` R16 reference-impl 地位
