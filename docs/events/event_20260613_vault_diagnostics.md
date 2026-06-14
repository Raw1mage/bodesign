# Event: Vault Diagnostics BR Fix

Date: 2026-06-13
Scope: bodesign vault diagnostics
Status: fixed

## Scope

- Fixed `issues/issue_20260613_vault_diagnostics_access.md`.
- Added a supported inspection path for the live server-side Component Vault without direct host access to Docker volume internals.

## Key Decisions

- Added `bodesign_vault_diagnostics` as a core MCP tool.
- Added `GET /vault/diagnostics` as the matching HTTP route.
- Diagnostics use the normal `BODESIGN_VAULT_DIR` storage boundary and do not fall back to temporary vaults.
- User approval for external automatic downloads is recorded as policy context, but diagnostics do not perform downloads or bypass the existing external-fetch policy gate.

## Issues Found

- Host-side direct access to `/var/lib/docker/volumes/...` can fail with `VAULT-E002` due to permissions.
- Existing `bodesign_vault_queue` only works when pointed at an accessible vault dir or when called from the running service boundary.

## Verification

- `PYTHONPATH=/home/pkcs12/projects/bodesign/packages/shared:/home/pkcs12/projects/bodesign/packages/component-kb:/home/pkcs12/projects/bodesign/services/mcp:/home/pkcs12/projects/bodesign python3 -m unittest tests.test_vault_api -v` → 13 tests OK.
- `python3 -m compileall -f services/mcp/vault_api.py services/mcp/server.py tests/test_vault_api.py` → OK.
- Smoke-tested `bodesign_vault_diagnostics` with `BODESIGN_VAULT_DIR=/tmp/bodesign-vault-diagnostics-smoke` → `ok`, DB metadata returned, empty queue reported explicitly.
- Architecture Sync: updated `specs/architecture.md` with vault diagnostics boundary.

## Remaining

- External automatic download policy remains a separate implementation/configuration task; this fix only exposes diagnostics.
