# Design: mcp_r16-domain-kb

## Context

bodesign 是 expert-domain MCP（PCB 設計），mcp-integration-standard R16（DD-21）規定此類服務 MUST 自帶 in-band queryable domain KB，且 bodesign 被指定為 reference impl。KB 實體已存在：`.specbase/ragbase.sqlite`（specbase ragbase schema：`objects` 表 + FTS5 trigram 索引 + lineage 邊），2026-07-11 已蒸餾 52+ 筆 evidence-graded PCB 知識。缺的只是「容器內的門」：server 端查詢工具 + 掛載 + signpost。

## Goals / Non-Goals

**Goals**

- 任何 MCP client 可查 ragbase KB（R16.2）
- 唯讀 serving、fail-fast、降級自述（R16.4/16.6、天條 1）
- 與 host-side gate.ts 同 store 無 fork（R16.7）
- recall-first signpost 全就位（R16.5）

**Non-Goals**

- KB 寫入工具、KB 內容擴充、LLM 排序、R15 guide 本體

## IDEF0-first skeleton

架構掛在 `idef0.json` A0 分解上：**A1 Serve KB Query**（FTS/LIKE/hybrid 查詢規劃 + matchMode 揭露）→ DD-2；**A2 Serve KB Get**（單物件全文 + provenance）→ DD-2；**A3 Guard Read-Only Access**（ro 連線 + fail-fast）→ DD-3/DD-4/DD-6；**A4 Signpost Recall-First**（instructions + consider: affordance）→ DD-5。A1/A2 的 mechanism 來自 A3 的唯讀連線；A4 是部署面前置（grafcet step 6）。

## Decisions

- **DD-1（core-side pure-python）**：kb_query/kb_get 落 core group（`services/mcp/server.py` `_h_*` handler），只用 stdlib `sqlite3`。不進 worker——KB 檢索無重依賴，走 worker 反而引入不必要 forward hop。
- **DD-2（查詢語義比照 specbase，不重造）**：trigram tokenizer 的 ≥3 碼點限制照抄 specbase gate.ts 的 plan 邏輯：全 token ≥3 → FTS `AND`；全 <3 → LIKE scan over title/body（score=0、按 recency）；混合 → hybrid。payload 必帶 `matchMode`。這是 R16.6 的自述義務，也避免 CJK 短查詢靜默 0-hit 假象。SQL 對象是 ragbase schema 的既有表（實作前先 `sqlite3 .schema` 對齊實際欄位，不憑記憶寫 SQL）。
- **DD-3（WAL 唯讀策略：目錄 rw 掛載 + 連線層強制唯讀）**：host producer 以 WAL 寫入；sqlite 讀 WAL DB 需要能建 `-shm`/`-wal` side files，純 ro bind mount 會 `SQLITE_CANTOPEN`。`immutable=1` 在有並行寫入者時會讀到 stale/torn 資料——不合格。故：**目錄以 rw 掛載，唯讀在 application 層強制**（URI `mode=ro` + `PRAGMA query_only=ON`），MCP surface 零寫入工具。R16.4 的「read-only serving」語義由連線層 + 工具面共同保證，不由 mount flag 保證。拒絕方案：ro mount（WAL 讀不了）、immutable（資料完整性）、複本同步（R16.7 fork 禁令）。
- **DD-4（fail-fast typed error）**：KB 檔缺失/不可開 → `KB_UNAVAILABLE: <reason>\nremedy: KB lives host-side at <repo>/.specbase/ragbase.sqlite; distill via specbase producer.ts (ragbase_distill), then restart is NOT needed — mount is live.`（R0.5 error-text affordance 慣例）。絕不回空 hits 假裝無知識。
- **DD-5（signpost 三軌）**：(a) mcp.json instructions 加一句 KB 宣告（R16.5a）；(b) 判斷密集工具 description 尾加 `consider: bodesign_kb_query`（R16.5c）；(c) R15 guide 的 doctrine 納入 recall-first——但 guide 本體是另案，本 plan 只留 hook 註記。
- **DD-6（env 定位，不 hardcode）**：`BODESIGN_KB_DB` env 指 KB 路徑（compose 設 `/var/lib/bodesign/kb/ragbase.sqlite`）；未設時工具回 `KB_UNAVAILABLE`（顯式），不猜路徑。

## Risks / Trade-offs

- **rw mount 理論上允許容器寫 KB** — mitigation：server 程式無任何寫路徑 + query_only pragma + code review；R12.5 turnstile 不需要（工具面唯讀）。
- **host WAL 寫入與容器讀並行** — sqlite WAL 本就支援多讀者單寫者跨進程；容器讀者透過同一檔案系統（bind mount 同 inode）鎖協調，安全。
- **FTS schema 與 specbase lib 演進脫鉤** — mitigation：測試含兩門一致性 check，schema 變更會被測試抓到。

## Critical Files

- `services/mcp/server.py` — handler `_h_kb_query`/`_h_kb_get` + TOOLS schema 註冊（53→55）
- `docker-compose.yml` / `docker-compose.dev.yml` / `docker-compose.workers.yml` — `./.specbase:/var/lib/bodesign/kb` 掛載 + `BODESIGN_KB_DB` env
- `mcp.json` — instructions signpost + version bump
- `tests/test_kb_tools.py` — 查詢語義 / fail-fast / 唯讀 / 兩門一致性
- `~/projects/opencode/specs/mcp-integration-standard/standard.md` — R16 條文（上游契約，唯讀參照）
