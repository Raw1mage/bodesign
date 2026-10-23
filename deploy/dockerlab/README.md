# bodesign MCP Server — DockerLab (CT105) Deployment Manifest

## 1. Metadata
- **Target Host**: Debian 12 LXC CT105 on asuspve PVE (`192.168.100.141`)
- **Assigned Ingress Port**: `TCP 8177` (allocated via central `port_registry`, project `bodesign-dockerlab`; LAN-plain HTTP, see §3)
- **Assigned Path**: `/opt/bodesign/`
- **Application Image**:
  - Registry URL: `registore.thesmart.cc/bodesign:6a7c286` (`:latest`, `98dba5e`, `f89db55`, `62095ba` unchanged)
  - Image Digest: `sha256:e6cb6d181ac9eabe92485e0060eb2e6ba51f0dc99e972626b8b71b25b8658bee`
  - Image Size: ~2.89 GB (monolith)
  - Rollback: `/opt/bodesign/docker-compose.yml.bak-20261023-62095ba` (previous: `.bak-20261023-f89db55`)
  - Architecture: `linux/amd64`
- **Component KB Snapshot**:
  - Source: `.specbase/ragbase.sqlite` (checkpointed with `PRAGMA wal_checkpoint(TRUNCATE)`)
  - Sha256: `6cd9d24fae697e39fcaa528b9687528c2d6b63391a91ef75c1d59c15206d4358`
  - Target Path: `/opt/bodesign/kb/ragbase.sqlite` (mounted `:ro`)

## 2. Directory Structure on CT105
```
/opt/bodesign/
├── docker-compose.yml
├── nginx.conf
├── fleet.env                 # root-owned 0600; never committed
├── fleet-outbox-adapter.py    # dynamic read-only mount
├── fleet-outbox-reconcile.py  # dynamic read-only mount
├── vault/
│   ├── vault.db
│   └── blobs/
└── kb/
    └── ragbase.sqlite
```

## 3. Exposure Boundary
- `nginx-sidecar` listens plain HTTP on `TCP 8177` — LAN only, no TLS, no auth.
- `POST /invoke` returns `403` at nginx (BR_20260730d).
- `/healthz` and `/mcp` are open on the LAN.
- Any exposure beyond the LAN MUST put an authenticating gateway in front of `8177` (AGENTS.md §3.1 rule 2, BR_20260730d).

## 4. Provisioning Steps on CT105
1. Create directories:
   ```bash
   mkdir -p /opt/bodesign/kb
   ```
2. Place `docker-compose.yml` and `nginx.conf`.
3. Copy checkpointed `ragbase.sqlite` to `/opt/bodesign/kb/ragbase.sqlite`:
   ```bash
   chmod 0644 /opt/bodesign/kb/ragbase.sqlite
   ```
4. Seed the writable server-owned component vault cache once from a dev snapshot;
   it is not a mirrored read-only artifact. Never checkpoint or change journal
   mode on the live `.run/vault/vault.db`; it has a live WAL/SHM pair. Copy the
   complete vault directory (including WAL/SHM and `blobs/`) to
   `~/.cache/scratch/vault-snapshot/` first, then run on the COPY:
   ```bash
   sqlite3 "$HOME/.cache/scratch/vault-snapshot/vault.db" \
     'PRAGMA wal_checkpoint(TRUNCATE); PRAGMA journal_mode=DELETE; PRAGMA integrity_check;'
   ```
   Require checkpoint success, `delete` journal mode and `ok` integrity before
   transferring only `vault.db` and `blobs/` to `/opt/bodesign/vault/` on CT105.
   Ensure the dropped service UID 1000 owns the cache and can traverse, read and
   write it. Mount the cache read-write at `/run/bodesign/vault` and configure
   `BODESIGN_VAULT_DIR` to that path; the storage contract requires writability.
   Keep the checkpoint-on-copy rule for cross-host snapshot consistency
   (AGENTS.md §3.1 rule 3). Do not overwrite the running server-owned cache
   with subsequent dev snapshots without a separate migration decision.
5. Start containers:
   ```bash
   docker compose up -d
   ```

## 5. Resource Allocation
- `bodesign`: 1.0 CPU, 1536 MiB RAM limit
- `nginx-sidecar`: 0.2 CPU, 128 MiB RAM limit
- `fleet-sidecar`: 0.2 CPU, 128 MiB RAM limit
- Total configured limits: 1.4 CPU, 1792 MiB RAM within CT105's 2C/4GiB envelope.

## 6. Client MCP Configuration
Workstation `~/.config/opencode/mcp_config.json` or project `mcp.json`:
```json
{
  "mcpServers": {
    "bodesign": {
      "transport": "streamable-http",
      "url": "http://192.168.100.141:8177/mcp/"
    }
  }
}
```

## 7. Fleet telemetry

The application persists drafts without network or secret access; a separate
UID-1000 sidecar signs and sends them over verified HTTPS. The deployment-owned
adapter and reconcile CLI are read-only bind mounts from
`/opt/bodesign/fleet-outbox-adapter.py` and `fleet-outbox-reconcile.py`.
Copy them from the released Git archive, not a dirty working tree.

The root-owned `/opt/bodesign/fleet.env` must be mode `0600`, is never committed,
and is loaded only by the sidecar through `env_file`. Required fields:
`FLEET_CALLBACK_URL` (HTTPS only), `FLEET_NODE_ID`, `FLEET_DEPLOYMENT_ID`,
`FLEET_KEY_ID`, `FLEET_NODE_SECRET` (64 lowercase hex), `FLEET_DRAFTS_DB`,
`FLEET_SIDECAR_SOCKET`, and `FLEET_OUTBOX_DIR`. The callback is operator-injected,
not stored in the node registry. Never print secrets or expanded Compose config.

Both containers share `fleet-runtime` at `/run/fleet` and `fleet-drafts` at
`/var/lib/fleet/drafts`; the application's DB and socket paths match the sidecar:
`/var/lib/fleet/drafts/feedback_drafts.db` and `/run/fleet/sidecar.sock`.
The sidecar initializes the schema, owns these directories as UID/GID 1000 with
mode `0700`, and blocks on the mode-0600 UNIX datagram socket. `fleet-outbox` is
a persistent named volume at `/var/lib/fleet/outbox`, never a temporary path.
Do not use `docker compose down -v` unless explicit data destruction is intended.
Vault remains a writable server-owned cache; Ingress still forbids `/invoke`.

For rotation, first register a new active key with Mother, securely replace
`FLEET_KEY_ID` and `FLEET_NODE_SECRET` in the private env file, retain `0600`
root ownership, then `docker compose up -d --force-recreate fleet-sidecar`.
Verify acceptance before Mother retires the old key. Do not change signing or
fall back to HTTP. Only report the key id and secret SHA256 prefix.

Operator reconciliation uses the same container env and persistent volumes:
```bash
docker exec --user 1000 bodesign-fleet-sidecar python3 /opt/fleet/fleet-outbox-adapter.py --self-test
docker exec --user 1000 bodesign-fleet-sidecar python3 /opt/fleet/fleet-outbox-reconcile.py --list
docker exec --user 1000 bodesign-fleet-sidecar python3 /opt/fleet/fleet-outbox-reconcile.py --show <eventId>
docker exec --user 1000 bodesign-fleet-sidecar python3 /opt/fleet/fleet-outbox-reconcile.py --requeue <eventId>
docker compose restart fleet-sidecar
```
Requeue preserves event/draft IDs and frozen body bytes; the restart catch-up
scan retries with a fresh timestamp/signature. HTTP 401 is a deterministic
refusal: the adapter dead-letters after one attempt, not five. Live acceptance
(`202 mother_accepted`) is pending Mother 3R; rerun smoke and requeue the
deployment smoke only after Mother confirms readiness.
