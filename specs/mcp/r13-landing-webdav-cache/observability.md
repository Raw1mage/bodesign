# Observability: mcp_r13-landing-webdav-cache

## Events

### Landing plane (gate.py, stderr; stdout reserved for the envelope)

| Event | Fields | When |
| ----- | ------ | ---- |
| `landing_verb_start` | verb, repo, argv-hash | every invocation |
| `landing_verb_ok` | verb, duration_ms, files_written | success |
| `landing_verb_error` | verb, code, message | any typed error |

### Container (existing audit machinery reused)

| Event | Fields | When |
| ----- | ------ | ---- |
| `cache_provisioned` | owner, subject, token, soft_cap | POST /caches |
| `cache_exported` | owner, token, target, files, bytes | POST /caches/{t}/export |
| `cache_close` / `cache_close_dirty` | owner, token, unexported_count | POST /caches/{t}/close |
| `dav_<method>` | owner, token, rel, status | every DAV method (audit log) |
| `webdav_cred_issued` / `webdav_cred_revoked` | owner | credential lifecycle |
| `tool_landed_hit` | tool, caller-transport | legacy client calls removed tool (R3 migration signal) |
| `reaper_skip_deliverable` / `reaper_safety_net_warn` | token, idle_s | class-aware reap decisions |

## Metrics

- `tool_landed_hit` count trending to zero = migration complete signal.
- Landing verb duration vs former token round-trip (before/after comparison
  for the closing event's Verification section).
- Per-owner soft-cap usage (count/bytes) — warn-first, surfaced in provision
  response.
- Reaper decisions per class (ephemeral reaped vs deliverable retained).

## Debug checkpoints (code-thinker contract)

- **CP-1 landing entry**: gate.py resolved BODESIGN_SRC + PYTHONPATH (log the
  actual paths) — first thing to check when a verb misbehaves on host.
- **CP-2 verb boundary**: args in / envelope out at the registry dispatch —
  distinguishes arg-plumbing bugs from core-logic bugs.
- **CP-3 DAV identity**: resolve_identity outcome (owner vs typed 401/403)
  before any store touch — auth bugs never masquerade as file bugs.
- **CP-4 store mutation**: token_store helper in/out (rel, resolved path,
  bytes) — traversal + accounting evidence.
- **CP-5 export boundary**: cache tree hash/file-list vs landed target —
  proves export fidelity byte-for-byte.

## Retention

- Landing gate has no persistent log (stderr per-invocation; agent session
  captures it). Container audit log retention unchanged.
