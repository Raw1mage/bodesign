# Handoff: mcp_fleet-telemetry-feedback

<!-- plan-builder:scaffold — replace every <placeholder>, then delete this line -->

## Execution Contract

- <placeholder: what the executing agent must deliver, and how done is defined>

## Required Reads

- <placeholder: files/specs the executor MUST read before starting>

## Stop Gates In Force

- <placeholder: approval / decision points where execution must pause>

## Execution-Ready Checklist

- [ ] <placeholder: precondition that must hold before execution starts>

## DockerLab rollout 2026-10-10

- Release: isolated `git archive 98dba5e`, tree
  `0b66b268e15c44d875ba8c0a3f75fd135a8a9c39`.
- Registry image: `registore.thesmart.cc/bodesign:98dba5e`, digest
  `sha256:5687001f8537fc1e9cb3961fc99a3880c70e2da07c2e6f2f111001ae82abfe96`,
  size 2886613597 bytes. Previous `eaf16cc` and `latest` tags unchanged.
- Discarded: working-tree context contaminated by peer uncommitted edits
  (`mcp.json`, `elk_layout.py`, `kicad_emit.py`, `paths.py`, `skills/`).
  The candidate was not pushed; the clean archive build replaced its tag.
- Compose adds UID-1000 fleet sidecar, dynamic read-only adapter/reconcile
  mounts, shared socket/drafts volumes and persistent outbox. Vault remains rw;
  no host 8077 publish or nginx.conf change. Private env is root-owned 0600.
  Key id `k1`; secret SHA256 prefix `15e1eac2` (no secret in this receipt).
- HTTPS callback reachability from CT105: GET HTTP 401.
- Runtime: app healthy on inspected release image id matching the digest;
  sidecar Up; mode-0600 socket present in both containers. Offline self-test:
  `bodyHashHex PASS`, `X-Fleet-Signature PASS`.
- Ingress stale upstream evidence: current app IP `172.25.0.4` versus nginx
  upstream `172.25.0.2`. Approved nginx-sidecar restart restored LAN health 200
  (`tools:73`, `served_groups:[all]`), initialize 200 and `/invoke` 403.
  Initial immediate readiness check returned connection refused; one retry passed.
- Observation: health has no buildId; version `0.3.0` is unchanged across
  eaf16cc to 98dba5e and cannot distinguish releases. Identity proof uses
  `docker inspect` image id, not the version string.
- Served smoke draft: `01a12474-a602-7d96-aa99-58a431e1e6b6`; event:
  `01a12474-a602-74ae-b8ea-8081ef8b0446`. Raw SSE reports `ok:true`.
  Read-only draft query reports `dead_letter`, attempts 1, receipt null,
  `last_error:401:unauthorized`. Logs show dead-letter and wake counts;
  reconcile listing reports count 1 and the same IDs/error.
- Dead-letter file:
  `/var/lib/fleet/outbox/dead-letter/01a12474-a602-74ae-b8ea-8081ef8b0446.json`
  (0600, UID/GID 1000); attempt record contains HTTP 401 `unauthorized`.
  The unchanged adapter treats 401 as deterministic and does not retry it.
- Live acceptance (`202 mother_accepted`) pending Mother 3R; re-run smoke +
  `fleet-outbox-reconcile.py` requeue after Mother confirms.
- Not measured: Mother signature acceptance/dedup/dispatcher notification,
  202 receipt, recovery after 3R or key rotation. Existing adapter emits no
  standalone sign/POST log lines; signing self-test and persisted HTTP attempt
  are the measured evidence, not a claim of Mother HMAC acceptance.
- Raw outputs: `/home/pkcs12/.cache/scratch/fleet-rollout/` (runtime.txt,
  health-after.json, smoke.sse, draft-and-dead-letter.txt, smoke-evidence.txt,
  push.txt, rollout.txt, nginx-restart.txt). No stage/commit or peer edits.

### Post-3R requeue 2026-10-10T08:08:05Z

- post-3R requeue 2026-10-10T08:08:05Z: status=UNMEASURED
  body=UNMEASURED receipt_id=rcpt_01a124da-9ad2-7000-939c-8afa3dc7e6e1.
  The deployed adapter does not log or retain the successful HTTP status or
  response body and deletes the successful outbox record. No verbatim wire
  response was captured; do not label this as an observed HTTP 202.
- Requeued only event `01a12474-a602-74ae-b8ea-8081ef8b0446`, draft
  `01a12474-a602-7d96-aa99-58a431e1e6b6`. CLI raw:
  `requeued 01a12474-a602-74ae-b8ea-8081ef8b0446` and
  `next sidecar wake (or restart catch-up scan) will retry the requeued events`.
- Trigger: one documented `docker compose restart fleet-sidecar`; no second
  delivery trigger, signing/header/transport changes or key rotation.
- Read-only SQLite before: status=`dead_letter`, attempts=1, receipt_id=null,
  last_error=`401:unauthorized`. After: status=`delivered`, attempts=1,
  receipt_id=`rcpt_01a124da-9ad2-7000-939c-8afa3dc7e6e1`, last_error=null,
  updated_at=`2026-10-10T08:07:49.383Z`.
- Raw adapter log: `catch-up scan: {'delivered': 1, 'dead_letter': 0}`.
  Reconcile listing: `{"deadLetter": [], "count": 0}`.
- Measured: successful adapter acceptance branch, receipt persisted, one
  delivery attempt, dead-letter cleared. That branch accepts either HTTP 202
  with `mother_accepted` or HTTP 200 with `duplicate:true`; wire status/body
  cannot be distinguished from the retained evidence. Mother triage and
  notification were not measured. No extra POST was made to obtain evidence.
- Raw evidence: `/home/pkcs12/.cache/scratch/fleet-rollout/requeue/`
  (`before.json`, `cli.txt`, `restart.txt`, `after.txt`). No stage/commit.
