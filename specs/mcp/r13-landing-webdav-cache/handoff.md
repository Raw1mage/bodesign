# Handoff: mcp_r13-landing-webdav-cache

## Executive summary

bodesign 依 fleet MCP integration standard 重構為 R13 compute/landing split +
WebDAV working-cache：~40 個純 Python 專案目錄 I/O verbs 落地為
`skills/bodesign/scripts/gate.py`（agent 在 host 以自身 uid 直跑，零 token 往返）；
容器只留 heavy compute（pcbnew/kicad-cli/ngspice/OpenSCAD/pyrender/…）+ vault +
cache lifecycle；heavy 流程的批量檔案交換由 docxmcp 精案移植的 WebDAV
per-deliverable working cache 承接（provision → mount → export → close）。

## Required Reads

1. `plans/mcp_r13-landing-webdav-cache/proposal.md` — why / scope / 使用者拍板
2. `plans/mcp_r13-landing-webdav-cache/spec.md` — 4 requirements + AC-1..AC-10
3. `plans/mcp_r13-landing-webdav-cache/design.md` — DD-1..DD-10 + 分桶清單 + Critical Files
4. `plans/mcp_r13-landing-webdav-cache/tasks.md` — 8 群 + 兩層驗證配方（頂部）
5. `specs/architecture.md` — core/worker 邊界、既有 token model
6. 移植源：`~/projects/docxmcp/bin/_webdav.py`、`bin/_auth_provider.py`、
   `bin/mcp_server.py::build_cache_dav_routes`（:2707 起）、
   `tests/test_webdav_poc.py`、`tests/test_webdav_cache_reaper.py`、
   `experiments/webdav_rclone_e2e.py`

## Execution contract

- 順序：群1-3（landing，獨立可驗證）→ 群4-5（store + WebDAV）→ 群6（收斂）→
  群7-8（驗證 + 文件）。
- 每完成一項立即勾 tasks.md checkbox。
- 天條：no silent fallback；landing script 缺件 typed error；WebDAV 認證失敗
  typed 401/403。
- 兩層驗證配方在 tasks.md 頂部（DD-9，不得只寫結論句）。

## Stop Gates In Force

- **群6 開始前**（breaking change：移除 ~40 tools + version 0.2.0）→ 需使用者批准。
- **`git push` / `plan_graduate`** → 使用者專屬，AI 不得自行觸發。
- **rclone E2E** 需真 rclone binary；缺 → 記 blocker（`[!]`）不硬造結果。
- **`mcpctl.sh rebuild`**（換映像）屬部署動作；dev loop 用
  `BODESIGN_DEV=1 ./mcpctl.sh restart` 即可，只有依賴變更才 rebuild。

## Execution-Ready Checklist

- [x] Scope 使用者三項拍板（R13 全 Bucket-2 / WebDAV 納入 / python3 gate + repo packages）
- [x] 分桶清單 line-verified（explore 偵查 2026-07-02）
- [x] 移植源已定位（docxmcp living spec `specs/mcp/webdav-working-cache` + bin/ 實作）
- [x] 兩層驗證配方明文化（tasks.md 頂部）
- [x] 風險 R1-R5 有對應緩解（design.md）
- [ ] 群6 使用者批准（實作到達時再取）

## Verification

- host venv 全套件綠 + 部署映像綠 + `mcpctl.sh restart` 雙 transport smoke +
  gate.py XDG 情境自足性（AC-9）+ rclone E2E（AC-5）。
