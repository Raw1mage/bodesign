# Errors: feature_eda-mcp-toolchain

## Error Catalogue

| Code | Condition | Tool behaviour | Caller action |
|---|---|---|---|
| `E-EDA-WORKER-DOWN` | A `pcbnew` board-mutation tool cannot reach the EE worker. | `{ok:false, status:worker_unavailable}` — never falls back to core, never fakes a routed board. | Bring up the EE worker; do not retry against core. |
| `E-EDA-MISSING-INPUT` | Required input absent (board path, nets, stackup, `ps_per_mm`). | `{ok:false, error:"<Type>: <msg>"}` — fail-fast, no fabricated default. | Supply the input. |
| `E-EDA-BAD-STACKUP` | `impedance_solve` stackup missing `dielectric_height_mm`/`er` or non-positive. | `{ok:false}` ValueError surfaced as data. | Provide a valid stackup; no defaults invented. |
| `W-EDA-RENDER-UNAVAILABLE` | Gerber preview asked for composite/front/stack with no safe multilayer renderer. | Returns `status:render-unavailable` (warning, not crash). | Use single-layer mode or install/supply a compositing renderer. |
| `E-EDA-DEP-MISSING` | pygerber / ngspice / Freerouting / `kicad-cli` absent for a tool that needs it. | Explicit unavailable/error state, not a decorative or partial success. | Install the dependency or accept the explicit limitation. |
| `E-EDA-SOCKET-UNPROVABLE` | Socket-level MCP path cannot be exercised (no MCP SDK). | Smoke test skips (gated on `import mcp`); not a fake pass. | Run in an MCP-SDK environment to prove the callable path. |
