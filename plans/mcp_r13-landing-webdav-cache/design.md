# Design: mcp_r13-landing-webdav-cache

## Context

偵查（2026-07-02，explore subagent）分桶結論：

- **Bucket 1（留容器，heavy）**：layout/routing 家族（pcbnew，
  `packages/eda-bridge/bodesign_eda_bridge/layout.py:20`、`routing.py:22`）、
  emit_symbol/compose_schematic/emit_fab/export_bom/export_netlist（kicad-cli）、
  simulate/si_check/analyze_emc/analyze_thermal（ngspice + `/opt/bodesign-engines`）、
  c02_export_stl/step/render 家族（OpenSCAD/build123d/pyrender/trimesh）、
  dxf_dwg（LibreDWG）、render_companion/emit_doc（LibreOffice）、
  render_gerber_preview（pygerber）、vault 家族（server-owned SQLite+FTS5 state，
  data-locality 留容器）。
- **Bucket 2（落地，~40 verbs）**：C00 PRD 家族、C01 全家族、C02 analysis-only、
  C03 emitters、C04/C05/C06 scaffold+readiness、orchestration spine（14 verbs，
  純 JSON under `<folder>/_orchestration/`）、read/gate（ingest_project、
  package_readiness、datasheet_lookup/spec_check/rca_spec_audit）、
  純函數（plan_design_intent、evidence_manifest、pin_allocation、
  reference_crosscheck、impedance_solve）。
- **Borderline**：`c00_emit_prd_docx`（render 可落地；assemble 需 docxmcp bridge
  留容器）、`c02_voice_to_design`（前半純、尾段 OpenSCAD 留容器）、
  `spice_model_card`（讀 server vault + 寫 client tree，留容器）、
  `stage_dir`/`mcp_call`（server 基礎設施，保留）。

## Architecture

```
┌──────────────── host (agent uid) ────────────────┐
│ python3 skills/bodesign/scripts/gate.py <verb>    │  landing plane
│   --repo <abs> [--json {…}]                       │  (~40 deterministic verbs)
│   └─ PYTHONPATH = bodesign repo packages/*        │
│   └─ writes directly into caller repo             │
└───────────────────────────────────────────────────┘
┌──────────────── container (bodesign-${USER}) ─────┐
│ MCP tools (heavy + vault + borderline, ~30)       │  compute plane
│ + cache lifecycle: POST /caches /export /close    │
│ + WebDAV class-2: /dav/{token}[/{rel}]            │  ← rclone/davfs2 mount
│   (identity: Basic per-owner credential)          │
└───────────────────────────────────────────────────┘
```

## Goals / Non-Goals

**Goals**

- ~40 個確定性 repo-local verbs 零 token 往返：agent 在 host 以自身 uid 直跑 gate.py。
- heavy 流程的批量檔案交換改走 per-deliverable WebDAV working cache（provision → mount → export → close）。
- caller 專案資料夾恢復 authoritative（修復權威目錄倒置）。
- 容器 tool surface 收斂至 heavy + vault + borderline + cache lifecycle（~30）。

**Non-Goals**

- 不追求 token model 退場（remote 場景保留 R2 契約）。
- 不動 heavy 工具內部演算法、vault 資料模型、workers 拓撲、gateway。
- 不做 R12 shared-tier / multi-host。

## Decisions

- **DD-1 Landing 執行器 = `gate.py` 單入口 + repo packages（使用者拍板）**：
  仿 specbase `gate.ts`。gate.py 以自身位置推導不出 repo —— bodesign 邏輯住在
  bodesign repo 的 `packages/*`，故 gate.py 需要 `BODESIGN_SRC`（預設：
  skill dir 的上上層，即 skill 隨 repo shipped 的 in-tree 情境；XDG 投影情境
  用 env 顯式指定）。找不到 packages → typed `LANDING_PACKAGES_NOT_FOUND`，
  絕不 fallback 到容器。**不 vendor**（單一事實來源）。
- **DD-2 Verb registry 是宣告式表**：`gate.py` 內單表
  `VERBS = {name: (module, callable, arg-schema)}`，1:1 對應 server.py 被移除的
  handlers；hard-guard：不在表內的 verb（heavy）→ typed `VERB_NOT_LANDING`。
- **DD-3 server.py 收斂 = 移除 Bucket-2 registry entries，核心函數不搬家**：
  純邏輯本來就在 `packages/*`（workflow-core / reverse-core），landing 與容器
  共用同一套件源；server.py 只是不再註冊那些 tools。避免 dual-source drift。
- **DD-4 WebDAV 層直接移植 docxmcp 已驗證件**：
  `bin/_webdav.py`（純協議 composer：multistatus/PROPFIND depth/LockTable/
  timeout parse，HTTP-agnostic）與 `bin/_auth_provider.py`（Basic per-owner
  credential store + AuthProvider 介面）近乎原樣移植為
  `services/mcp/_webdav.py` / `_auth_provider.py`；route factory 仿
  `build_cache_dav_routes`。改寫點僅：env 前綴 `BODESIGN_*`、token_store 介面
  對接（bodesign 的 `token_store.py` 需補 deliverable-cache 類別 +
  mkdir/move/copy helpers + owner 欄位）。
- **DD-5 Cache 定性 = per-deliverable ephemeral working cache（承 docxmcp DD-1/4/6）**：
  truth store（caller 專案資料夾，authoritative）/ WebDAV cache（working tree，
  ephemeral）/ vault（server 品牌/模型資產，正交）。export 是一等 landing verb；
  close 走 dirty-gate（`WORKSPACE_CLOSE_DIRTY` 409 unless clean/force）。
  這同時修復偵查發現的「權威目錄倒置」問題。
- **DD-6 identity = Basic-auth-only 首發**（承 docxmcp 2026-07-01 部署拍板）：
  per-owner credential 存 named volume `bodesign-sessions` 的 dotfile sibling
  （`.webdav-creds.json`，reaper 只 glob token 目錄不掃 dotfile）；
  不掛 gateway JWT secret（不新增 host bind）。認證失敗 → typed 401，無 fallback。
- **DD-7 deliverable-cache 不受 idle reap**：token_store 現行 TTL 1h mtime-LRU
  只適用 ephemeral token；新增 kind 欄位（`ephemeral` | `deliverable-cache`），
  後者僅 export-clean + close 或 safety-net 長 TTL 回收（承 docxmcp reaper 語意）。
- **DD-8 mcp.json instructions 依 R13.5 三類宣告**：compute（容器 tools）/
  landing（gate.py verbs）/ cache lifecycle（provision→mount→export→close 流程）。
  version 0.1.0 → 0.2.0（breaking：~40 tools 從 MCP surface 移除）。
- **DD-9 兩層驗證配方明文化**（吸收 docxmcp BR_20260702 教訓）：in-image pytest
  的 mount 點 / workdir / 依賴以可複製指令寫進 tasks.md 與 handoff.md，
  不讓執行配方只存在結論句。
- **DD-10 workers 模式不動**：cache namespace 本來就在 shared named volume
  `bodesign-sessions`（me/ee workers 已掛同 volume），WebDAV routes 只落 core
  server；worker forwarding 邏輯零改動。

## Risks / Trade-offs

- **R1 host python3 版本 / stdlib 差異**：landing verbs 過去在容器 python 3.x 跑；
  host 的 python3 可能較舊。緩解：gate.py 開頭 fail-fast 檢查
  `sys.version_info >= (3, 10)`（typed `LANDING_PYTHON_TOO_OLD`）+ 兩層驗證涵蓋
  host venv。
- **R2 Bucket-2 verbs 隱性 heavy 依賴**：個別 emitter 可能 lazy-import cairosvg
  等 host 沒有的套件。緩解：現行程式已是 gated-optional 模式（cairosvg 缺 →
  honestly omit PNG）；落地時逐 verb 驗證 import 圖，測試矩陣涵蓋。
- **R3 移除 ~40 tools 是 breaking change**：既有 IDE 設定 / 腳本呼叫舊 tool 會
  404。緩解：version bump + instructions 指路；被呼叫的已移除 tool 回 typed
  `TOOL_LANDED`（含 gate.py 等效指令），不是無聲消失。
- **R4 WebDAV 移植的 store 介面落差**：docxmcp `_token_store` 與 bodesign
  `token_store.py` 結構不同（後者精簡）。緩解：先補齊 store helpers（kind/
  owner/mkdir/move/copy/export 標記）再接 DAV routes；PoC 測通再全量。
- **R5 憑證儲存跨 rebuild**：named volume 持久，但 `mcpctl.sh rebuild` 若清
  volume 會洗掉憑證。緩解：確認 rebuild 不 `down -v`；文件明示。

## Critical Files

| File | Role |
| ---- | ---- |
| `skills/bodesign/scripts/gate.py` | 新增：landing-plane 單入口 verb runner |
| `services/mcp/server.py` | registry 收斂 + cache lifecycle/DAV routes 掛載 |
| `services/mcp/token_store.py` | kind/owner 欄位 + mkdir/move/copy + class-aware reaper |
| `services/mcp/_webdav.py` | 新增：DAV class-2 協議 composer（docxmcp 移植） |
| `services/mcp/_auth_provider.py` | 新增：Basic per-owner credential store（docxmcp 移植） |
| `mcp.json` | instructions R13.5 三類宣告 + version 0.2.0 |
| `skills/bodesign/SKILL.md` | landing/compute 路由契約段 |
| `specs/architecture.md` | 全貌同步 |

## Code anchors

- `services/mcp/server.py:1212` — `PATH_ARG_KEYS` token 重寫（landing 後仍服務
  heavy tools）
- `services/mcp/server.py:1256-1273` — snapshot-diff produced-files 偵測
- `services/mcp/token_store.py:26-31` — TTL/LRU（DD-7 改造點）
- `docker-compose.yml:22` — `bodesign-sessions` named volume（cache 家）
- docxmcp 移植源：`~/projects/docxmcp/bin/_webdav.py`、`bin/_auth_provider.py`、
  `bin/mcp_server.py::build_cache_dav_routes`（:2707 起）

## Submodule refs

- 無（單 repo 交付；docxmcp 是移植來源不是依賴）
