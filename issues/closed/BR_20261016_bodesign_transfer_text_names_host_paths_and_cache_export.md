---
id: BR_20261016_bodesign_transfer_text_names_host_paths_and_cache_export
title: bodesign transfer text names plain host paths, curl UDS JSON-RPC, and cache_export as agent egress, and cache_provision returns relative mount_url
date: 2026-10-16
status: closed
closed_date: 2026-10-16
closed_by: ses_04db7a1c5ffelvbxyLP1p6xlRH
worker_session: ses_ebf0d5f91ffeE47ByMPV899tO7
severity: high
priority: P1
component: services/mcp/server.py, README.md, README.en.md, skills/bodesign/
reporter_session: ses_04db7a1c5ffelvbxyLP1p6xlRH
edges:
  - to: /home/pkcs12/projects/opencode/issues/BR_20261016_mcp_file_transfer_guidance_contradicts_across_layers.md
    type: dispatched-from
    section: §11-bodesign
---

# bodesign transfer text names host paths, curl UDS JSON-RPC, and cache_export; cache_provision returns relative mount_url

## §0 Background & Fleet-wide Transfer Rule

Dispatched by opencode ★main (`ses_f05594495ffed70mIx6CAPjb1H`) per cross-fleet user rulings:
- **§0.2 User ruling (2026-10-16)**: 「說到底還是webdav一條路萬用到底是最省事的」
- **§0.5 / §0.6 User ruling**: WebDAV is repo-level shared workspace. Agents move files through the opencode runtime verb `system-manager_webdav_mount(app)`, which returns `mount_path` and `token`.
- **Prohibited Agent Rails**:
  - Raw host paths (`plain host paths`)
  - Inline base64 / `<app>_stage` as agent transfer rail
  - `<app>_cache_export` as agent egress step
  - Agent-run `<app>_cache_provision` or agent-run `rclone mount`
  - Bare `curl --unix-socket` JSON-RPC to the MCP endpoint
- **Permitted**:
  - Moving files to/from `mount_path` using standard file tools (`cp`, `cat`, `sha256sum`).
  - curl directly on the HTTP file endpoints (`/files/...`, `/dav/...`) is allowed as an alternate view of the token tree.

## §1 Audit Rows (B1–B5 & O31)

From opencode `BR_20261016_mcp_file_transfer_guidance_contradicts_across_layers.md` §7.2:

| # | File / Location | Current Defect | Fix Direction |
|---|---|---|---|
| **B1** | `services/mcp/server.py:74-80` (`bodesign_init`) | States `cache_export` to host dir, `POST /files` tarball or `bodesign_stage_dir` | Remove `cache_export` and `POST /files` tarball agent advice; direct agents to `system-manager_webdav_mount` + WebDAV workspace `mount_path`. |
| **B2** | `services/mcp/server.py:1912-1924` (`folder`/`token` doc) | Mentions `stage_dir` or `POST /files` | Align description with WebDAV workspace token / folder usage. |
| **B3** | `services/mcp/server.py:2388`, `README.en.md:93-98`, `README.md:115-121` | "Tools also accept plain host paths" + `curl --unix-socket .run/bodesign.sock` JSON-RPC | Remove "plain host paths" claims and UDS curl JSON-RPC recipe entirely. |
| **B4** | `services/mcp/preflight.py:139-142` | "stage the asset inside the token; no host paths" | Verify consistent with WebDAV workspace. |
| **B5** | `skills/bodesign/references/container-boundary.md:42-48` | Under a mount → "pass the host path directly as folder" | Remove claim that plain host paths can be passed directly as folder; align to WebDAV workspace. |
| **O31** | `skills/bodesign/doctrine.md:170-181`, `skills/bodesign/SKILL.md:432-445` | Names `cache_export` as egress rail and inline `stage_dir` | Update to `system-manager_webdav_mount`, drop `cache_export` as required egress. |

## §2 Asks & Scope

1. **Remove "Tools also accept plain host paths"**:
   - `services/mcp/server.py` line 2388.
   - `README.en.md` line 93.
   - `README.md` line 115.
   - `skills/bodesign/references/container-boundary.md` line 42.
2. **Remove README `curl --unix-socket .run/bodesign.sock` JSON-RPC recipe**:
   - `README.en.md` lines 95–99.
   - `README.md` lines 117–121.
3. **Drop `cache_export` as an agent egress step**:
   - `services/mcp/server.py` doctrine in `bodesign_init`.
   - `README.en.md` and `README.md`.
   - `skills/bodesign/doctrine.md` and `skills/bodesign/SKILL.md`.
   - Direct agents to access files directly in the mounted WebDAV directory provided by `system-manager_webdav_mount(bodesign)`.
4. **Make `bodesign_cache_provision` return an absolute `mount_url`**:
   - In `services/mcp/server.py` (`_h_cache_provision`):
     - Currently returns `"mount_url": f"{_base()}/dav/{meta.token}/"`. When `BODESIGN_HTTP_BASE` is unset, this is a relative path `/dav/{token}/`.
     - In opencode `webdav-mount.ts`, HTTP app mounts check `/^https?:\/\//.test(prov.mountUrl)`. If not absolute, it fails loud with `dav_url_unknown`.
     - `bodesign` is registered as a TCP/HTTP endpoint (`http://192.168.100.141:8177/mcp/`).
     - Resolve `mount_url` to an absolute URL: read `BODESIGN_PUBLIC_URL`, `BODESIGN_WEBDAV_BASE`, or `BODESIGN_HTTP_BASE`; if unset, fall back to the standard endpoint URL (`http://192.168.100.141:8177`) ensuring an absolute `http://...` URL is always returned.

## §3 Acceptance Criteria

1. Grep verification:
   - Zero occurrences of "plain host path" or "plain host paths" in `server.py`, `README.md`, `README.en.md`, `skills/`.
   - Zero occurrences of `curl --unix-socket .run/bodesign.sock` in `README.md` and `README.en.md`.
   - No documentation directing agents to use `cache_export` as mandatory egress.
2. `bodesign_cache_provision` unit test:
   - Verified that `mount_url` returns an absolute URL starting with `http://` or `https://`.
3. Repo test suite:
   - `./scripts/run_tests.sh test_mcp_server` passes without regressions.
4. Capability projection:
   - `opencode skill status bodesign` / `opencode skill resync bodesign --accept-source` executed.

## §4 Resolution & Verification Evidence

Landed by worker `ses_ebf0d5f91ffeE47ByMPV899tO7`, verified by duty officer `ses_04db7a1c5ffelvbxyLP1p6xlRH`:
1. **Host path removal**:
   - `server.py`: removed "Tools also accept plain host paths..." and Chinese counterpart.
   - `README.md` / `README.en.md`: removed plain host path claims.
   - `skills/bodesign/references/container-boundary.md`: rule 1 rewritten to state host paths are never passed as folder.
   - Zero matches on `grep -rni "plain host path" services/mcp/server.py README.md README.en.md skills/`.
2. **README UDS curl recipe removal**:
   - Removed `curl --unix-socket .run/bodesign.sock` JSON-RPC block from both `README.md` and `README.en.md`.
   - Zero matches on `grep -n "unix-socket" README.md README.en.md`.
3. **Drop cache_export as agent egress step**:
   - `server.py` instructions, folder/token descriptions, READMEs, `doctrine.md`, `SKILL.md` updated to direct agents to `system-manager_webdav_mount(app="bodesign")` -> `mount_path` + `token`.
   - Working files are accessed directly via standard file tools in `mount_path`; no export step required.
4. **Absolute mount_url in cache_provision**:
   - Added `_public_base_url()` in `server.py`, returning first absolute URL from `BODESIGN_PUBLIC_URL`, `BODESIGN_WEBDAV_BASE`, or `BODESIGN_HTTP_BASE`; falls back to `http://192.168.100.141:8177`.
   - Added `mount_url_base_source` to `_h_cache_provision` payload.
   - `tests/test_webdav_poc.py`: `test_mcp_tool_handlers_provision_export_close` passed with regex assertion `^https?://`.
5. **Skill projection synced**:
   - `opencode skill status bodesign`: both `bodesign` and `bodesign-kb` report `current`.

