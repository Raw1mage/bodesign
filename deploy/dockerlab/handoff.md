# DockerLab deployment handoff

## k2 rotation 2026-10-10T08:19:57Z

- Mother ruling: k1 retired at 2026-10-10T08:14:48Z;
  acceptUntil 2026-10-10T10:14:48Z. Registry remained read-only.
- k2 active; key_id=k2, sha8=5159a711 using SHA256 of the hex string
  without a trailing newline. The earlier 275d3e03 used a newline and was
  withdrawn by Mother. No secret bytes are included in this receipt.
- Only FLEET_KEY_ID and FLEET_NODE_SECRET changed in the private CT105 env;
  stat raw: `600 root root`. Other env fields were preserved.
- Used `docker compose -f /opt/bodesign/docker-compose.yml up -d --force-recreate fleet-sidecar`;
  app and nginx were not restarted. Container key output: `k2`.
- Self-test raw: `bodyHashHex PASS`, `X-Fleet-Signature PASS`.
- One initialized served MCP smoke: draft
  `01a124e5-b794-7cf4-b4a6-6f0d83aff571`, event
  `01a124e5-b794-73c8-8b67-15e13df393a7`.
- Read-only SQLite outcome: status=delivered, attempts=1,
  receipt_id=rcpt_01a124e5-b6ab-7000-b9c3-27a425e8a0c8,
  last_error=null, updated_at=2026-10-10T08:19:57.138Z.
- Adapter wake raw: `wake: {'delivered': 1, 'dead_letter': 0}`.
- Existing README rotation SOP already specifies force-recreate; unchanged.
- Not measured: verbatim HTTP success status/body (adapter does not retain
  them), Mother triage/notification and final k1 expiry enforcement.
- Raw evidence: `/home/pkcs12/.cache/scratch/fleet-rollout/k2/`.
  No stage/commit or other repo edits.
