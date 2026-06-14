# BR: Vault Diagnostics Access Gap

Status: fixed

## Summary

Host-side double-check of the server-side Component Vault cannot reliably inspect the real Docker-backed vault when the bodesign compose service is not running and the current user lacks permission to read the Docker volume mount directly.

## Evidence

- MCP tool registry is correct: `bodesign_vault_ingest`, `bodesign_vault_query`, `bodesign_vault_spec_check`, and `bodesign_vault_queue` are registered in the `core` group.
- Registry test passes with full local `PYTHONPATH`: `python3 -m unittest tests.test_vault_api.ToolRegistryTests -v`.
- No compose services are currently running, so there is no live MCP/HTTP process to query.
- Docker volume exists: `bodesign-pkcs12_bodesign-vault`.
- Host-side query with `BODESIGN_VAULT_DIR=/var/lib/docker/volumes/bodesign-pkcs12_bodesign-vault/_data` returns `VAULT-E002` because `/var/lib/docker/volumes` is not readable/writable by the current user.

## Impact

- Agents can confirm that vault CRUD-like tools are exposed, but cannot determine the actual production vault queue / missing external documents from the host session unless the service is running or a privileged volume access path exists.
- `bodesign_vault_queue` can only report missing-document work when pointed at an accessible vault directory.

## Expected

- Provide a supported diagnostic path that does not require direct host access to Docker volume internals.
- Examples: a documented compose-run diagnostic command, an MCP/HTTP health endpoint that reports vault queue/status through the running service, or a small safe admin command that executes inside the service container.

## Notes

- User has approved external automatic downloads, but current architecture still has a policy gate documented in `specs/architecture.md`; implementation should explicitly update policy/config rather than silently bypass it.
- Do not add silent fallback to a temp vault for diagnostics; it hides the real server-vault state.

## Resolution

- Added `bodesign_vault_diagnostics` MCP tool and `GET /vault/diagnostics` HTTP route.
- Diagnostics run through the normal `BODESIGN_VAULT_DIR` storage boundary, report queue preview and DB metadata, and return a safe compose-run command for inspecting named-volume state from inside the service container.
- Added tests covering registry exposure and non-fallback diagnostics behavior.
