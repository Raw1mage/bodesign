# Errors: mcp_r13-landing-webdav-cache

## Error Catalogue

### Landing plane (gate.py)

| Code | Condition | Behaviour |
| ---- | --------- | --------- |
| `LANDING_PYTHON_TOO_OLD` | host python3 < 3.10 | exit≠0 before any import; message names required version |
| `LANDING_PACKAGES_NOT_FOUND` | `BODESIGN_SRC` unresolvable or no `packages/*` under it | exit≠0 before import; message shows tried paths + how to set `BODESIGN_SRC`; NO container fallback |
| `VERB_UNKNOWN` | verb not in registry at all | exit≠0; message suggests `--list` |
| `VERB_NOT_LANDING` | verb is a known heavy/container verb | exit≠0; `hint` carries the container tool name to call instead |
| `VERB_ARGS_INVALID` | required args missing / `--json` unparseable / `--repo` not an absolute existing dir | exit≠0; message names the missing/invalid arg |
| `VERB_RUNTIME_ERROR` | verb callable raised | exit≠0; envelope carries exception class + message (traceback to stderr) |

### Container surface (0.2.0)

| Code | Condition | Behaviour |
| ---- | --------- | --------- |
| `TOOL_LANDED` | client calls a removed Bucket-2 tool | `{ok:false, error:TOOL_LANDED, landing_command}` — never an anonymous unknown-tool error |

### Cache lifecycle + WebDAV

| Code / status | Condition | Behaviour |
| ------------- | --------- | --------- |
| `AUTH_REQUIRED` 401 | no/invalid Basic credential (non-OPTIONS method) | typed 401 + `WWW-Authenticate: Basic realm="bodesign-webdav"`; no fallback identity |
| `AUTH_BASIC_REJECTED` 401 | credential present but wrong (constant-time compare) | typed 401 |
| `CACHE_FORBIDDEN` 403 | authenticated but not the token owner (incl. cross-token MOVE/COPY Destination) | typed 403; cross-owner isolation absolute |
| `CACHE_NOT_FOUND` 404 | token absent / already reaped | typed 404 |
| `WORKSPACE_CLOSE_DIRTY` 409 | close requested while tree modified since last export (no `force`) | 409 + unexported file list |
| `EXPORT_TARGET_UNREACHABLE` | export target dir missing/unwritable on host side | typed error; never auto-creates ancestor trees, never guesses an alternative target |
| `DAV_TRAVERSAL_REJECTED` 403 | rel path escapes token dir after resolution | typed 403 (same `_safe` defence as token CRUD) |
| `DAV_LOCKED` 423 | write method against another holder's LOCK | typed 423 |
| `PAYLOAD_TOO_LARGE` 413 | PUT exceeds size cap | typed 413 (existing cap reused) |

## Principles

- All errors are typed + logged; none is a silent fallback (repo 天條 2).
- Landing errors go to stdout envelope + exit code; DAV errors go to HTTP
  status + JSON/XML body; both carry enough context to self-serve the fix.
- Soft caps (per-owner usage) WARN, never block (docxmcp precedent).
