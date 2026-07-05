# BR_20260705 — Component vault split: server serves empty named-volume while populated 43 MB vault sits orphaned at `.run/vault`

- **Scope**: bodesign MCP server (component-kb vault) + docker-compose config
- **Severity**: BLOCKING for any `vault_*` reuse flow (e.g. plan `aiguard_refs-ssot-build` DD-3)
- **Discovered during**: `aiguard/refs-ssot-build` Phase 2 (vault reuse + datasheet expansion)

## 現象（硬證據）

1. `bodesign_vault_query mpn=BQ24075` → `{status: "absent", advice: "Component not in the server vault; ingest it via /vault/ingest."}`.
2. `bodesign_vault_diagnostics` → `configured_vault_dir: /var/lib/bodesign/vault`, `db_size_bytes: 176128`, `queue_count: 0`.
3. Container direct sqlite on the **served** db (`/var/lib/bodesign/vault/vault.db`, named volume `bodesign-pkcs12_bodesign-vault`): **0 rows** in `components`.
4. Container direct sqlite on the **host** vault mounted at `/run/bodesign/vault/vault.db` (host `.run/vault/vault.db`, 43,044,864 bytes): **109 components** incl. `BQ24075` (`canonical_key=component:bq24075`), `TPS62824`, `TCR2LE33`, `TLV75733PDRVR`, `TLV74018PDQNR`, `W25Q128JVSIQ`, `MX25UM25645G`, `LM66200` … + `documents=26`, `chunks=16156`. Schema identical (both `user_version=5`).
5. **`vault_dir` override is a no-op**: `bodesign_vault_query mpn=BQ24075 vault_dir=/run/bodesign/vault` → still `absent`; `vault_dir=/nonexistent/path/xyz` → **same clean `absent`** (not a bad-path error). A honored override would error on a nonexistent path. ⇒ the tool ignores `vault_dir` and always reads `configured_vault_dir`.

## RCA

Two independent defects compound:

- **(D1) Config/data drift**: the 43 MB populated vault was written to host `.run/vault` (mtime 2026-06-10). Compose later switched the served store to a **named volume** `bodesign-vault:/var/lib/bodesign/vault` with `BODESIGN_VAULT_DIR=/var/lib/bodesign/vault` (empty db created 2026-06-13). The populated vault is mounted into the container (`./.run:/run/bodesign` → visible at `/run/bodesign/vault`) but the server never points at it. Result: all 109 components + 26 datasheets are orphaned; the server serves an empty store.
- **(D2) `vault_dir` param is a no-op** on the query/spec-check path: the documented per-call override does not actually re-root the vault reader, so a caller cannot even work around D1 by passing `vault_dir=/run/bodesign/vault`. This also silently violates the no-silent-fallback 天条 — a bad `vault_dir` should fail fast, not resolve to the configured store.

## 建議修復

- **D1 (choose one, both need `mcpctl.sh restart`)**:
  - **A (re-point, preferred if `.run/vault` is canonical)**: set compose `BODESIGN_VAULT_DIR=/run/bodesign/vault` (drop/keep the named-volume mount); server reads the populated 43 MB vault, writes persist to host `.run/vault`. Matches container-boundary.md ("bodesign only sees `.run`/sessions/vault").
  - **B (re-seed, keeps compose)**: copy host `.run/vault/{vault.db,blobs}` into the `bodesign-pkcs12_bodesign-vault` named volume `_data`, restart.
- **D2**: make `vault_dir` actually re-root the reader (VaultRepository open path); a nonexistent `vault_dir` must return a typed error, never fall through to `configured_vault_dir`.

## 影響範圍

- Any `vault_*` reuse (`aiguard_refs-ssot-build` DD-3; every future "reuse ingested datasheet" flow).
- `spec_check`/`rca_spec_audit` server-vault tier silently degrades to `absent`/client-cache, masking 26 real datasheets → risks 天条4 (datasheet-grounded) false-BLOCKING.

## 驗證手段

- After D1 fix: `bodesign_vault_diagnostics` → `db_size_bytes ≈ 43 MB`; `bodesign_vault_query mpn=BQ24075` → `status: ok` with document chain.
- After D2 fix: `vault_query mpn=BQ24075 vault_dir=/nonexistent` → typed error (not `absent`).
