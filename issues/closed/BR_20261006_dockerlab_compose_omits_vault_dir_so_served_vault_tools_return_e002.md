# BR_20261006: DockerLab compose omits BODESIGN_VAULT_DIR, so every served vault tool returns VAULT-E002

- **Status**: CLOSED — fixed 2026-10-09 (worker ses_ee44bd358, officer-verified served diagnostics ok); §5.1 `:ro` withdrawn, vault is a writable server-owned cache; §5.3 page-anchor half out of scope (data gap, see §7)
- Priority: P2 (blocks the datasheet-grounded path that AGENTS.md §2.4 makes mandatory)
- Family: deploy / config parity
- Filed by: ★main (bodesign duty officer), 2026-10-06
- Surfaced by: S3 R6 Gate 1 (ses_ef06f84feffecMAhyjhMV7Mq6P), trying to verify PESD5V0L4UF pinning via the approved path

## 1. Observed

On the served instance (CT105 `192.168.100.141:8177`, image `registore.thesmart.cc/bodesign:v0.3.0-dockerlab`):

- `bodesign_vault_query`, `bodesign_vault_spec_check`, `bodesign_vault_diagnostics` (no args) → `VAULT-E002 "no directory configured (set BODESIGN_VAULT_DIR or pass an explicit path)"`.
- `bodesign_vault_query(vault_dir=/home/pkcs12/projects/bodesign/.run/vault)` → `VAULT-E002 "vault_dir override does not exist"` (host path, not visible in the container — expected).

The error is correct fail-fast behaviour. The defect is upstream: the deployment never configures the vault.

## 2. Root cause (config diff, read-only)

| file | `BODESIGN_VAULT_DIR` | vault volume |
| --- | --- | --- |
| `docker-compose.yml` (local dev) | `/run/bodesign/vault` (:57) | repo-local bind `./.run/vault` (comment :85-87) |
| `deploy/dockerlab/docker-compose.yml` (served) | **absent** (:11-18) | **absent** (:19-23 mounts sessions + KB only) |

The DockerLab compose was authored from the KB-only requirement (sessions + `ragbase.sqlite:ro`) and never carried the vault over. `AGENTS.md §2.4` requires datasheet-grounded electrical claims via `vault_spec_check`; on the only live deployment that path cannot return anything.

## 3. Secondary observation

The local `.run/vault/vault.db` (109 components, dated Jun 11) has zero rows for `%PESD%`. Even with the env fixed, this part's datasheet is not in the vault; ingestion is a separate step (see §5).

## 4. Not in scope

- Server-side architecture ruling (Round 483): server holds only ephemeral cache + internal KB/symbol library. A read-only vault snapshot mounted like the KB snapshot fits that ruling; an NAS/product mount does not.
- Vendor datasheet access control: Nexperia's asset host returns 403 to curl's default UA (Akamai bot gate); a browser UA succeeds. That is an acquisition detail, not this BR.

## 5. Proposed fix (needs deploy-owner dispatch; officer does not edit deploy/ here)

1. `deploy/dockerlab/docker-compose.yml`: add `BODESIGN_VAULT_DIR: "/run/bodesign/vault"` and a read-only bind `/opt/bodesign/vault:/run/bodesign/vault:ro` (mirror the KB snapshot pattern, incl. `PRAGMA wal_checkpoint(TRUNCATE); journal_mode=DELETE` before copying per AGENTS.md §3.1 rule 3).
2. Publish SOP: snapshot the populated vault from the dev host to `/opt/bodesign/vault` on CT105 alongside the KB snapshot; document in `deploy/dockerlab/README.md`.
3. Acceptance: `bodesign_vault_diagnostics` on `:8177` returns a configured directory + component count instead of E002; `vault_spec_check` for a known-ingested MPN returns a page-anchored value.
4. Ingest PESDXL4UF_G_W.pdf once acquired (S3 R6 worker holds the file under `$XDG_CACHE_HOME/scratch/s3-elk-spike/datasheets/`).

## 7. Closure (duty officer ses_04db7a1c5ffelvbxyLP1p6xlRH, 2026-10-09)

- Rulings: (a) `:ro` in §5.1 withdrawn — storage contract is writable-or-E002 by design
  (`packages/component-kb/bodesign_component_kb/storage.py:13,464-496`); vault mounted rw at
  `/opt/bodesign/vault:/run/bodesign/vault`, seeded once from a checkpointed COPY of the dev
  snapshot. (b) §5.3 "page-anchored value" is NOT achievable: all 16156 chunks have
  `page_number` NULL and `spec_values` carry no `evidence_chunk_id`; accepted as a measured data
  gap, out of this BR. (c) §5.4 PESD ingest not performed.
- Served BEFORE: `VAULT-E002 … no directory configured`. Intermediate (`:ro`): `VAULT-E002 Vault
  directory is not writable: /run/bodesign/vault`. AFTER (officer independent call from this
  session): `status: ok, vault_dir: /run/bodesign/vault, db_exists: true, db_size_bytes: 43044864`.
- `vault_spec_check W25Q128JVSIQ vin_min_v 2.7` → `verified`, source disclosed as
  `client-cache-import:Digi-Key spec table … Full datasheet PDF not yet acquired`; no page anchor
  claimed. component_count 109 measured in-container (diagnostics schema has no count field).
- CT105: `/opt/bodesign/vault` owned 1000:1000, runtime now owns WAL; `bodesign-app` healthy on
  the same image `eaf16cc`, config-only reload.
- Repo: `deploy/dockerlab/{docker-compose.yml,README.md}` +24/-1, committed S28.
- Raw SSE receipts: `~/.cache/scratch/vault-snapshot/{before,after,after-rw,spec-check,spec-check-rw}.sse`.

## 6. Evidence

- Worker report, R6 Gate 1 table (all fields MISSING), VAULT-E002 verbatim ×2.
- `grep -rn BODESIGN_VAULT_DIR docker-compose.yml deploy/` → only the local compose matches.
