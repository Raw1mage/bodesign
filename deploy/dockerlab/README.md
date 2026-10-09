# bodesign MCP Server — DockerLab (CT105) Deployment Manifest

## 1. Metadata
- **Target Host**: Debian 12 LXC CT105 on asuspve PVE (`192.168.100.141`)
- **Assigned Ingress Port**: `TCP 8177` (allocated via central `port_registry`, project `bodesign-dockerlab`; LAN-plain HTTP, see §3)
- **Assigned Path**: `/opt/bodesign/`
- **Application Image**:
  - Registry URL: `registore.thesmart.cc/bodesign:eaf16cc` (`:latest` unchanged)
  - Image Digest: `sha256:37a8013e7adb8cbf76187e302eb0ec0886a6326e465f312397f850e04321b1d9`
  - Image Size: `2886717150` bytes (2.89 GB; monolith)
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
- Total footprint: 1.2 CPU, 1664 MiB RAM (leaves ample headroom within CT105's 2C/4GiB envelope).

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
