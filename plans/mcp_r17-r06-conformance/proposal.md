# Proposal: mcp_r17-r06-conformance

## Why

bodesign 的 fleet MCP 對照 `mcp-integration-standard`（living）在 R1–R16 已 fully
conformant（gap matrix 2026-06-29 記錄），但標準之後又追加兩條 fleet-wide 條款：

- **R17 — Minimum operational toolset + host mediation**：把 MCP 的 common lifecycle
  收斂成一個小而可預測的工具家族，並要求 delivery-oriented 操作能對成品做
  machine-checkable 斷言。R15 能交付正確 doctrine，卻仍會在 action boundary 失手——
  正確操作只是 prose recipe 而錯誤操作是 first-class tool。
- **R0.6 — Companion-skill wall-nudge**：R0.5 的特例，綁定 R9。修正的是「skipped-contract
  reflex」——沒載 companion skill 的 agent 一頭撞牆後傾向繞過工具（手改底層格式），
  而非回頭讀契約。服務端要從 toolcall 本身偵測牆，在既有 error 上附「正確 primitive +
  該載的 skill」remedy。

bodesign 對 R17/R0.6 逐條盤點（`issues/BR_20260721_mcp_r17_r0.6_conformance_gap.md`，
基於 `services/mcp/server.py` 2526 行逐條讀 + docxmcp `bin/_skill_nudge.py` reference
校準）後確認：R17 部分缺漏、R0.6 完全缺，且本 repo 無任何 spec 追蹤。使用者拍板範圍為
**R17 全部 + R0.6 完整補齊（fully conformant）**。

## Original Requirement Wording (Baseline)

- "讓 bodesign MCP 完整採用 fleet mcp-integration-standard 的最新兩條 R17（minimum
  operational toolset）+ R0.6（companion-skill wall-nudge），達到 fully conformant。"
- "範圍 = R17 全部 + R0.6 完整補齊（fully conformant，非最小子集）。"

## Requirement Revision History

- 2026-07-21: initial draft created via plan-init.ts
- 2026-07-21: 填入 BR 盤點 + 使用者拍板範圍；合併 R17 與 R0.6 為單一 spec。

## Effective Requirement Description

1. **R17.1.1/.1.2** — `bodesign_init` 除 prose doctrine 外，additionally 回結構化、
   machine-readable `capabilities` summary：`transport` / `file_ingress` / `file_egress` /
   `webdav_state` / `companion_skill` / `conditional_tool_families`，且以機器可辨旗標區分
   service/container endpoint vs host-visible endpoint（container socket path 不得看起來
   host-executable）。conformance test 必須能對此結構化 payload 分支斷言（非只驗 text 存在）。
2. **R17.2.2** — 補 portable MCP `resources/read` egress（`@server.list_resources()` +
   `@server.read_resource()`），把每個 token 產物暴露成 MCP resource（`bodesign://files/<token>/<rel>`），
   使 bare client 不靠 HTTP blob / WebDAV / UDS curl 即可取回成品。
3. **R17.2.3** — token workspace list/status/probe 工具：transform 前列 token namespace tree、
   證明預期資產存在。
4. **R17.2.4** — render/assemble/emit 前 typed asset preflight：拒 unresolved paths /
   missing media / token 命名空間外路徑 / host-only 絕對路徑，附 R0.5 remedy 行。
5. **R17.2.5** — content-assertion 契約：delivery-oriented 操作 accept/emit machine-checkable
   斷言（expected file/media/page/slide counts、required text、non-empty）；transport-valid
   but EMPTY 成品不得回報 delivery-ready。
6. **R17.6 (a)-(e)** — 五 conformance 情境不再 silent-pass，且有測試涵蓋。
7. **R0.6 全 sub-point** — `_skill_nudge` 等價物（single-source generator note/remedy/advisory）
   + wall-fingerprint detector（bad-shape id / grain-mismatch zero-element edit / 首次無 recon
   的 unbounded sweep）+ hard（enrich 既有 failure；silent `ok=true` no-op 轉 loud failure）
   / advisory（非阻塞 hint，不把 success 轉 failure）兩級 + single-source remedy generator +
   把結構化 remedy 投影到 MCP `content` text（docxmcp `_render_remedy_line` 等價）。
8. **R17.5 補強** — companion-skill 身分 parity：`skillPaths` / `GET /skills` / `bodesign_init`
   doctrine source 三面 single-source assert，有 drift/parity 測試。

## Scope

### IN

- server.py：`bodesign_init` capabilities summary、`list_resources`/`read_resource`、
  workspace inspection tool、typed asset preflight primitive、content-assertion 契約、
  R0.6 wall-nudge（`_skill_nudge` module + intercept points + remedy 投影）、R17.5 parity assert。
- 每條 requirement 的 pytest 涵蓋（含 R17.1.2/R17.6 對結構化 payload / 情境分支的斷言）。
- `specs/architecture.md` 同步、event log、live UDS/MCP smoke。

### OUT

- **R17.3 host-file ingress mediation**（Layer 2，host-side `ingest_host_file`）——非本 repo，
  由 opencode host 側 `harness_plugin-extension-points` 擁有。
- **R11 gateway outward-routing**（Layer 2，host-side）。
- 重寫既有已合規面（R17.1 init+prompts/get+/health、R17.2.1 stage_dir、R17.2.2 HTTP blob、
  R17.4 WebDAV lifecycle、R17.5 single-source doctrine load）。

## Non-Goals

- 不改 compute/landing split（R13）既有分界。
- 不新增任何 fallback mechanism（天條 11 / 使用者天條）——所有新閘一律 fail-fast + 顯式報錯 + 缺項清單。
- 不偽造交付物（天條 2）——content-assertion 只驗真實磁碟成品。

## Constraints

- bodesign 天條：no silent fallback、no fabrication、datasheet-grounded、no send-to-fab without
  deterministic validation + explicit approval。
- R0 portability floor：所有新能力必須讓 bare MCP client（僅 tools/call + resources/read +
  prompts/get）可用；remedy 必須落在 portable `content` text，不得只在 private field。
- R0.6.1 定海神針：服務端不得查詢 caller skill-state（跨行程 handshake 被拒）；只在真牆上附 nudge。
- Runtime 只透過 `mcpctl.sh`（dev loop `BODESIGN_DEV=1`）；daemon 換版需使用者當下許可。
- 測試 PYTHONPATH 需含所有 `packages/*` 子目錄；`python3`（無 `python`）。

## What Changes

- `services/mcp/server.py`：`bodesign_init` handler 加 `capabilities`；新增 `list_resources`/
  `read_resource`；新增 workspace-inspection in-process tool；新增 preflight primitive 並接入
  `_h_fab`/`_h_render_board_model`/`_h_doc`/`compose_schematic` 等 mutation entry；error wrapper
  接入 R0.6 remedy 投影。
- 新增 `services/mcp/_skill_nudge.py`（single-source nudge generator，docxmcp reference 對齊）。
- 新增 `services/mcp/preflight.py`（typed asset preflight + content-assertion 純函式）。
- `skills/bodesign/doctrine.md`：R17.5 first-use section 具名 baseline/conditional 工具。
- `tests/`：R17.1/R17.2.x/R17.5/R17.6/R0.6 test vectors。

## Capabilities

### New Capabilities

- `bodesign_init.capabilities`: 結構化 machine-readable capability summary（含 endpoint 旗標）。
- `resources/read` egress: `bodesign://files/<token>/<rel>` MCP resource（portable floor）。
- workspace inspection tool: transform 前列 token tree + 資產存在性。
- typed asset preflight: mutation/render/emit 前拒 unresolved/missing/host-only path。
- content-assertion: expected counts / required text / non-empty 斷言，空成品拒回 delivery-ready。
- R0.6 wall-nudge: toolcall wall-fingerprint → hard/advisory nudge，remedy 投影到 content text。

### Modified Capabilities

- `bodesign_init`: 由純 prose → prose + structured capabilities（既有欄位保留，additive）。
- `_h_fab` / `_h_render_board_model` / `_h_doc` / `compose_schematic`: render/emit 前多一道
  typed asset preflight + content-assertion 閘（fail-fast，不改成功路徑行為）。
- run_tool error wrapper: 既有 error 附 R0.6 remedy 行（byte-identical 當無牆可附，天條 11）。

## Impact

- 受影響碼：`services/mcp/server.py`、新增 `services/mcp/_skill_nudge.py` +
  `services/mcp/preflight.py`、`skills/bodesign/doctrine.md`、`tests/test_mcp_*`。
- 受影響對象：任何 MCP client（bare 與 opencode host）——新增 portable egress + 更嚴的成品閘；
  既有呼叫路徑成功語意不變（additive + fail-fast-on-defect）。
- 文件：`specs/architecture.md`（services/mcp 段）需同步新 surface。
