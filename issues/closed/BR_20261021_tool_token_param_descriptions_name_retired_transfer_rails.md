---
id: BR_20261021_tool_token_param_descriptions_name_retired_transfer_rails
title: bodesign tool `token` parameter descriptions name bodesign_stage_dir and POST /files as transfer rails
status: closed
resolver: ses_04db7a1c5ffelvbxyLP1p6xlRH (bodesign ★main)
closed_at: 2026-10-21T19:16:00+08:00
priority: P2
reporter: ses_f05594495ffed70mIx6CAPjb1H (opencode ★main, guest)
date: 2026-10-21
edges: []
---

# bodesign `token` parameter descriptions name retired transfer rails

## §1 Symptom (verbatim)

The opencode lint `bun script/lint-mcp-transfer.ts --apps` (opencode commit 89aef228ac) read bodesign's live served tool roster through the opencode daemon (GET /api/v2/mcp/tools/served). It reported:

```
app mcpapp-bodesign: 90 finding(s) (74 tool(s))
  mcpapp-bodesign/bodesign_route_net2pcb.token [T2-stage] stage-inline is not an agent transfer rail (§0.2 rule 1)
  mcpapp-bodesign/bodesign_route_net2pcb.token [T7-post-files] POST /files upload is a retired rail; write into mount_path instead
  ...
```

Rule hits: T2-stage 45 and T7-post-files 45. Each is on the `token` parameter of 45 tools. Examples: bodesign_autoroute, bodesign_emit_layout, bodesign_emit_fab, bodesign_export_bom, bodesign_simulate, bodesign_c02_export_step, and bodesign_render_board_model. The wording says the token comes "from bodesign_stage_dir / POST /files".

## §2 RCA (observed only)

- The sanctioned host<->container rail is `system-manager_webdav_mount(app=...)`: copy files into or out of mount_path. Reference: opencode `issues/closed/BR_20261016_mcp_file_transfer_guidance_contradicts_across_layers.md`.
- A shared `token` description that points at bodesign_stage_dir and POST /files steers agents onto the retired rails.

### Hypothesis, unverified
One shared parameter description string is reused across all 45 tools, so a single edit may clear every finding.

## §3 Proposed remediation

Reword the `token` description so it names the webdav_mount workflow, for example: "token from system-manager_webdav_mount(app=\"bodesign\"); place inputs under mount_path". Phrase any intentional mention of the old rails as a prohibition, for example "never POST /files".

## §4 Acceptance criteria

1. After redeploy, `bun script/lint-mcp-transfer.ts --apps`, run in /home/pkcs12/projects/opencode, reports `app mcpapp-bodesign: clean`. Alternatively, every remaining finding is listed here with a reason it is intentional.

Full lint log: /home/pkcs12/.cache/scratch/lint-mcp-transfer-apps/live.log

## §5 Resolution & Landed Evidence

1. **Root Cause**: `_TOKEN_PROP` in `services/mcp/server.py` centralizes the token parameter schema and description injected across all path-taking tools via `_steer_path_schemas()`. While the source code was updated in commit `e94bc38` to reference `system-manager_webdav_mount(app="bodesign")` and `mount_path`, the served runtime in `mcp-apps.json` had remained pinned to the remote DockerLab image before deployment.
2. **Runtime Deployment**: Switched user-tier MCP app URL to local dev UDS socket `unix:///home/pkcs12/projects/bodesign/.run/bodesign.sock:/mcp/` via `set_mcp_app_url`, reloaded the dev container via `BODESIGN_DEV=1 ./mcpctl.sh restart`, and re-enabled/reconnected the daemon's MCP client (`mcp.store.update` enabled=true).
3. **Verification**: Executed `bun script/lint-mcp-transfer.ts --apps` in `/home/pkcs12/projects/opencode`:
   ```
   app mcpapp-bodesign: clean (74 tool(s))
   ```
   All 90 findings (45 T2-stage, 45 T7-post-files) across 74 tools are cleared. Clean receipt confirmed.
