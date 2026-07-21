# Handoff: mcp_r17-r06-conformance

## Execution Contract

實作 bodesign MCP server 對 R17（全部）+ R0.6（全 sub-point）的 fully conformance。
Done 定義：tasks.md 全 `[x]`、全 pytest 綠、live UDS/MCP smoke 通過、R17.6 (a)-(e)
五情境各有測試證明不再 silent-pass、`specs/architecture.md` 同步、event log 收尾。

所有新閘一律 **fail-fast + 顯式報錯 + 缺項清單**（bodesign no-silent-fallback 天條）；
新能力對 bare MCP client（tools/call + resources/read + prompts/get）可用；remedy 落
portable `content` text（R0 floor）。**additive**：既有呼叫路徑成功語意不變。

## Required Reads

- `plans/mcp_r17-r06-conformance/design.md` — DD-1..DD-7、IDEF0 activity 對映、Critical Files。
- `plans/mcp_r17-r06-conformance/spec.md` — 每條 requirement + scenario + acceptance checks。
- `plans/mcp_r17-r06-conformance/data-schema.json` — InitCapabilities/PreflightVerdict/AssertionVerdict/WallNudge 形狀。
- `issues/BR_20260721_mcp_r17_r0.6_conformance_gap.md` — 逐行 code 盤點（file:line 起點）。
- `/home/pkcs12/projects/opencode/specs/mcp-integration-standard/standard.md` — R17（:1090+）、R0.6（:119+）標準原文。
- `/home/pkcs12/projects/docxmcp/bin/_skill_nudge.py` + `bin/mcp_server.py:360` `_render_remedy_line` — R0.6 reference。
- `services/mcp/server.py`（run_tool :1387 / init :1407 / error wrapper :1446 / prompts :1813）、`services/mcp/token_store.py`（list_files :195 / safe_join :189）。

## Stop Gates In Force

- **daemon 換版需使用者當下許可**：live smoke 前若需 `BODESIGN_DEV=1 ./mcpctl.sh restart`
  讓 running daemon 換版，必須先停下來問使用者（禁止自行 spawn/kill daemon）。
- **送廠無關**：本 spec 不觸及 send-to-fab 路徑，但 content-assertion 只驗真實磁碟成品（天條 2）。

## Execution-Ready Checklist

- [x] designed gate 通過（8 artifact valid，2 份 DNA 圖 drawmiat-validated）
- [x] IDEF0/GRAFCET 骨架完成且 design 由其長出
- [ ] planned gate 通過（tasks.md + handoff.md 就緒）
- [ ] 測試 PYTHONPATH：`PP=$(ls -d packages/*/ | tr '\n' ':')` 前綴（`python3`，無 `python`）
