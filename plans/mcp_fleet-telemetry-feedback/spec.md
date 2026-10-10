# Specification: mcp_fleet-telemetry-feedback

## 1. Functional Requirements

1. **Retrospective Tool Interface (REQ-TOOL-01)**:
   - Tool `submit_retrospective` and alias `bodesign_submit_retrospective` must accept:
     - `intent` (string, max 4096 chars, required)
     - `trajectory` (string, max 16384 chars, optional)
     - `friction` (string, max 8192 chars, required)
     - `suggestion` (string, max 4096 chars, optional)
   - Exceeding any field length or overall 1 MiB payload limit must return `{ "ok": false, "error_code": "FIELD_TOO_LARGE" }` or `{ "ok": false, "error_code": "PAYLOAD_TOO_LARGE" }`.
   - Tool must generate UUIDv7 `draft_id` and `event_id`, ensuring the prefix of `event_id` matches the UTC millisecond timestamp of `event_created_at`.
   - Tool must persist an immutable draft to SQLite and return `{ "ok": true, "draftId": "<UUIDv7>" }`.

2. **Non-blocking IPC Wake (REQ-WAKE-02)**:
   - Upon SQLite commit, tool must attempt a non-blocking UNIX datagram write (`socket.SOCK_DGRAM`) of `b"1"` to `$FLEET_SIDECAR_SOCKET` (or `$XDG_RUNTIME_DIR/fleet-telemetry/sidecar.sock`).
   - If socket is absent, unopened, or buffer full, the call must silently ignore the error without failing the tool execution.
   - Use of `/tmp` or `/var/tmp` for the wake socket is strictly forbidden.

3. **Outbox Adapter Lifecycle (REQ-OUTBOX-03)**:
   - `fleet-outbox-adapter.py` must block on the wake datagram socket, waking immediately upon incoming datagram.
   - On startup, adapter must perform a catch-up scan for any drafts with status `pending`.
   - Adapter must mark draft as `in_flight`, write an atomic outbox record (`~/.cache/fleet-outbox/<eventId>.json`), and calculate canonical string:
     `${timestamp}.${nodeId}.${deploymentId}.${eventId}.${sha256(rawBodyBytes)}`.
   - Adapter must sign the canonical string using HMAC-SHA256 with the 32-byte secret decoded from hex.
   - Adapter must execute up to 5 total attempts (initial + 4 retries with delays 1s, 2s, 4s, 8s).
   - On receiving `HTTP 202 Accepted` or `HTTP 200 OK` (with `duplicate: true`), adapter marks draft `delivered`.
   - On deterministic rejection (400, 403, 404, 409, 413) or retry exhaustion, adapter moves the outbox file to `dead-letter/` and updates draft status to `dead_letter`.

4. **Reconciliation Tooling (REQ-RECON-04)**:
   - `scripts/fleet-outbox-reconcile.py` must support `--list`, `--show <eventId>`, and `--requeue <eventId>`.

5. **Mother System Dispatch Alignment (REQ-MOTHER-05)**:
   - The node registry entry in `~/.config/opencode/fleet-nodes.json` must declare `serviceName: "bodesign"`, `ownerUser: "pkcs12"`, and `owningRepo: "/home/pkcs12/projects/bodesign"`.
   - Telemetry events must be recorded in `/home/pkcs12/projects/bodesign/.specbase/fleet-events.sqlite` and trigger notifications to bodesign's Duty Officer (`★main`).

---

## 2. Non-Functional & Security Requirements

1. **Zero Secret Leakage (SEC-01)**: The application runtime (`services/mcp/`) must never read or require `FLEET_NODE_SECRET`. Secrets belong exclusively to the deployment harness sidecar.
2. **Strict Time Skew & Replay Horizon (SEC-02)**: Ingress enforces ±300s window on request timestamps and rejects events older than 90 days.
3. **Pre-auth Flooding Defense (SEC-03)**: Global rate limit of 120 requests/minute and 1 MiB body size cap.
4. **Side-effect Free Reading (SEC-04)**: Mother `fleet_read_event` tool is read-only and requires matching `ownerUser` and `owningRepo`.

---

## 3. Scenarios

### Scenario 1: Agent Reports Autorouting Collision
- **Given**: An agent invokes `bodesign_autoroute` and encounters unexpected track overlap.
- **When**: The agent calls `submit_retrospective(intent="Auto-route power rail", friction="Track overlap on layer 2")`.
- **Then**: Tool returns `{ ok: true, draftId: "019..." }`. SQLite records draft as `pending`.
- **And**: Sidecar wakes up, signs event, posts to Mother Ingress, and receives 202.
- **And**: Mother bodesign Duty Officer (`★main`) receives `[FLEET-EVENT]` notification, reads evidence, and files a bug report in `bodesign/issues/`.

### Scenario 2: Offline Network Resilience
- **Given**: The Mother Gateway is temporarily unreachable (network timeout or maintenance).
- **When**: A retrospective is submitted.
- **Then**: Adapter retries with backoff (1s, 2s, 4s, 8s). Once network restores within 5 attempts, event is accepted without draft loss.
