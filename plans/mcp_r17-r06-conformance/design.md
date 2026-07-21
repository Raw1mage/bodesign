# Design: mcp_r17-r06-conformance

## Context

bodesign 是獨立 MCP server（`services/mcp/server.py`，2526 行），對 fleet
`mcp-integration-standard`（living）在 R1–R16 已 fully conformant（gap matrix
2026-06-29）。標準之後追加兩條 fleet-wide 條款——R17（minimum operational toolset）
與 R0.6（companion-skill wall-nudge）——bodesign 尚未採用，且 repo 內無 spec 追蹤。
`issues/BR_20260721_mcp_r17_r0.6_conformance_gap.md` 已逐行盤點確認 7 個真正 gap。

本設計以 IDEF0（`idef0.json`，5 activity A1–A5）為系統骨架，每個 activity 對應一條
標準條款族；GRAFCET（`grafcet.json`，18 step）描述單次 MCP 請求在 server 內的
執行狀態機（分類 → 各分支 → 匯合回應 → 迴圈待下一請求）。design 由此骨架長出。

IDEF0 骨架 → design 對映（每個 DD 掛在對應 activity 上）：
- **A1** Advertise machine-readable capabilities → DD-1（`bodesign_init` capabilities）。
- **A2** Serve portable resource egress → DD-2（`resources/list` + `resources/read`）。
- **A3** Inspect workspace before transform → DD-3（`bodesign_workspace_inspect`）。
- **A4** Preflight + assert delivery → DD-4（`preflight.py` typed preflight + content-assertion）。
- **A5** Nudge skipped-contract walls → DD-5（`_skill_nudge.py` wall-fingerprint + remedy 投影）。
- 橫切：DD-6（R17.5 parity）、DD-7（R17.6 五情境隨 A1–A5 收斂）。

現況關鍵事實（逐行讀證）：
- `bodesign_init` in-process 回 `{ok,doctrine,source}` 純 prose（`server.py:1407-1410`）。
- error wrapper `server.py:1446-1447`（R0.6 remedy 投影等價點；docxmcp `_render_remedy_line` 為 reference）。
- `list_prompts`/`get_prompt` 已存在（`:1813-1838`）；**無** `list_resources`/`read_resource`。
- `TokenStore.stage_tarball/stage_raw/stage_files` 三者皆回完整 `{token, doc_dir, files}`
  （`token_store.py:214/221/234`）→ **R17.2.1 已合規**（BR 待驗證點消解，無需補）。
- `TokenStore.list_files(doc_dir)`（`:195-197`）、`safe_join(doc_dir, rel)`（`:189-193`）
  現成可複用做 R17.2.3 workspace inspection 與 R17.2.4 preflight 的 path 解析機構。
- `_h_fab`（`:190`）、`render_board_model`、`_h_doc`、`compose_schematic` 為 render/emit
  mutation entry，皆不在 render 前拒 unresolved/missing/host-only path，亦不 assert 成品非空。

## Goals / Non-Goals

**Goals**

- bodesign 對 R17（全部）+ R0.6（全 sub-point）達 fully conformant。
- 每條 requirement 有 pytest 涵蓋；R17.1.2/R17.6 的測試能對 init 結構化 payload /
  各情境分支斷言，非只驗 text 存在。
- 所有新閘 fail-fast + 顯式報錯 + 缺項清單（bodesign 天條 no-silent-fallback）。
- 新能力對 bare MCP client（僅 tools/call + resources/read + prompts/get）可用；
  remedy 落 portable `content` text（R0 floor）。

**Non-Goals**

- R17.3 host-file ingress mediation（Layer 2，host 側 `ingest_host_file`）——由 opencode
  host `harness_plugin-extension-points` 擁有，非本 repo。
- R11 gateway outward-routing（Layer 2，host 側）。
- 重寫既有已合規面（R17.1 init+prompts/get+/health、R17.2.1 stage_dir、R17.2.2 HTTP blob、
  R17.4 WebDAV lifecycle、R17.5 single-source doctrine load）。
- 不改 compute/landing split（R13）既有分界；不新增任何 fallback；不偽造交付物。

## Decisions

- **DD-1 (A1): `bodesign_init` 加 `capabilities` 為 additive 第四鍵，既有三鍵 byte-preserve。**
  回 `{ok, doctrine, source, capabilities}`。`capabilities` 是結構化 dict：
  `transport`（含 `service_endpoints[]` / `host_endpoints[]` 兩桶，各項帶
  `host_executable: bool` 旗標——container UDS socket path 標 `host_executable=false`）、
  `file_ingress` / `file_egress` / `webdav_state` / `companion_skill` /
  `conditional_tool_families`。conformance test 對 `capabilities.transport.service_endpoints`
  的 `host_executable` 旗標分支斷言（R17.1.2 «execute at least one decision»）。
  拒絕方案：另開 `bodesign_capabilities` 工具——會讓 bare client 需知道第二個工具名，
  違反 R17.1 «init 是單一入口» 精神。

- **DD-2 (A2): portable egress 用 MCP `resources/list` + `resources/read`，URI scheme
  `bodesign://files/<token>/<rel>`。** `read_resource` 以 `TokenStore.resolve(token)`
  + `safe_join(doc_dir, rel)` 解析（既有 traversal guard 複用），回 blob bytes。
  `list_resources` 列舉 live token 的所有檔（`list_files`）。這使 bare client 不靠
  HTTP blob route / WebDAV / UDS curl 即可取回成品（R0.1 floor）。URI 由現有
  `/files/{token}/blob/{rel}` HTTP route 的 `{token}/{rel}` 對映，single-source。
  拒絕方案：只保留 HTTP blob——bare stdio client 無 HTTP 面，違反 R0 portability。

- **DD-3 (A3): workspace inspection 為新 in-process 工具 `bodesign_workspace_inspect`。**
  入參 `token`（+ optional `subpath`）；回 `{token, doc_dir, files[], count}`。
  純讀（`list_files` + 可選 subpath 過濾），無 mutation。放在 `run_tool` in-process
  分支（比照 `bodesign_init`），不進 worker——純 python 無重依賴。滿足 R17.2.3
  «prove expected assets exist before a transform»。

- **DD-4 (A4): typed asset preflight + content-assertion 抽成純函式模組 `services/mcp/preflight.py`。**
  兩組純函式（無 I/O 副作用，只吃 path 列表 / 成品清單 + 斷言 spec，回 verdict）：
  - `preflight_assets(doc_dir, asset_paths) -> PreflightVerdict`：對每個 declared path
    分類 `resolved` / `unresolved`（safe_join raise / 不存在）/ `out_of_namespace`
    （逃逸 token dir）/ `host_only_absolute`（絕對路徑且非 doc_dir 內）。任一失敗 →
    typed `PREFLIGHT_*` code + 缺項清單 + R0.5 remedy dict。
  - `assert_content(produced, assertions) -> AssertionVerdict`：驗
    `expected_files` / `expected_media` / `required_text` / `non_empty`（每檔 size>0）。
    transport-valid 但空成品 → `ASSERTION_EMPTY` NOT-delivery-ready。
  接入點：`run_tool` 在 render/emit/assemble 工具（`emit_fab`/`render_board_model`/
  `emit_doc`/`compose_schematic`）dispatch **前**跑 preflight、**後**跑 assertion（當
  caller 傳 `assert` 參數）。純函式便於 pytest 直接斷言分支（不需起 server）。
  拒絕方案：把閘寫進各 handler——重複 5 份、無法單元測試、易漂移。

- **DD-5 (A5): R0.6 wall-nudge 抽成 single-source 模組 `services/mcp/_skill_nudge.py`，
  docxmcp reference 對齊。** 一個 generator（`skill_nudge_note` / `skill_nudge_remedy` /
  `skill_nudge_advisory`），一個 wall-fingerprint detector（`detect_wall(name, args, doc_dir)`
  → `None` | `("hard"|"advisory", why, correct_primitive)`）。fingerprint 純函式，只吃
  當前 toolcall + workspace state，**不查 caller skill-state**（R0.6.1 定海神針）：
  - bad-shape id：token/path 參數形狀屬 recon 步驟從不 emit 的命名空間 → hard。
  - grain-mismatch zero-element edit：edit 目標在 workspace 匹配 0 檔 → 原本 silent
    `ok=true` no-op 轉 loud failure（R0.6.3 hard）。
  - 首次無 recon 的 unbounded sweep：大 workspace 首個 unbounded 操作、無先前
    inspect → advisory（非阻塞 hint，不把 success 轉 failure）。
  remedy 經 `run_tool` error wrapper 投影到 portable `content` text（新增
  `_render_remedy_line` 等價：把 `error.remedy` dict 投成 `remedy:` 行；無 remedy 時
  byte-identical，天條 11）。structured mirror additionally 留在 result dict。

- **DD-6: R17.5 companion-skill parity 用單一 source constant assert。** `skillPaths`
  （`mcp.json`）、`GET /skills`（`assets/skills/*.tar.gz`）、`bodesign_init`
  （`skills/bodesign/doctrine.md`）三面的 companion 身分由一個 `COMPANION_SKILL="bodesign"`
  常數 single-source；新增 parity 測試斷言三面一致（drift test）。doctrine.md 的
  first-use section 具名 baseline（`bodesign_init`/`bodesign_stage_dir`/
  `bodesign_workspace_inspect`）與 conditional（`bodesign_emit_fab` 等）工具（R17.5
  «name the concrete tools, not merely load the skill»）。

- **DD-7: R17.6 (a)-(e) 五情境不獨立實作，隨 gap 1–5 收斂並各有測試。**
  (a) host-readable FUSE 當未驗證 container path → preflight `host_only_absolute` 拒（DD-4）；
  (b) init 只含 container socket path → `host_executable=false` 旗標（DD-1）；
  (c) assemble/render 帶 unresolved media → preflight `unresolved`/`missing_media`（DD-4）；
  (d) 空 template 回 `ready=true` → content-assertion `ASSERTION_EMPTY`（DD-4）；
  (e) skill/guide/manifest 宣告不同 transfer rail → parity assert（DD-6）。

## Risks / Trade-offs

- **R1: preflight 誤拒合法 same-host 絕對路徑。** bodesign 工具接受本機路徑（同機 UDS
  case，見 landing HTML `file_stage`）。緩解：preflight 只在 caller 帶 `token`
  （portable case）時強制 namespace 檢查；無 token 的 same-host 絕對路徑保留現行語意，
  但 host-only-absolute 分類仍 emit advisory（不硬阻），避免破壞既有同機呼叫。
- **R2: wall-fingerprint false hard-block。** 誤判合法操作為 hard wall 比漏判更糟
  （定海神針）。緩解：fingerprint ambiguous 時一律降級 advisory；hard 只用於「工具本來
  就會 fail」或「本來 silent no-op」兩種確定情形（enrich 既有 failure，不新造 block）。
- **R3: resources/read 暴露 token 內全部檔。** 緩解：URI 仍需 caller 持有 token
  （token 是 capability），safe_join 防逃逸，與既有 HTTP blob route 同權限模型，無新增暴露面。
- **R4: SVG render 落 host 路徑受容器 UID 權限限制。** drawmiat 容器無法寫 `/home/pkcs12`。
  緩解：`idef0.json`/`grafcet.json` 已通過 `specbase_diagram_validate`（designed gate 只
  要求 JSON 存在，SVG 為 rendered companion）；SVG 若需要改用 token namespace 落地後取回。

## Critical Files

- `services/mcp/server.py` — MCP 工具註冊 + `run_tool` dispatch；init/error-wrapper/
  resources/workspace-inspect/preflight 接入的唯一總線（`:1387` run_tool、`:1407` init、
  `:1446` error wrapper、`:1800` call_tool、`:1813` prompts）。
- `services/mcp/token_store.py` — `list_files`/`safe_join`/`resolve` 複用機構（R17.2.3/.2.4）。
- `services/mcp/preflight.py`（新增）— typed asset preflight + content-assertion 純函式。
- `services/mcp/_skill_nudge.py`（新增）— single-source wall-nudge generator + fingerprint。
- `skills/bodesign/doctrine.md` — R17.5 first-use section 具名工具 + parity source。
- `tests/test_mcp_r17_r06_conformance.py`（新增）— R17.1/.2.x/.5/.6/R0.6 test vectors。
