# Errors: bodesign — failure catalog + handling

How bodesign behaves when things go wrong. The guiding rule (DD-8 + B4): **never report a
false success** — degrade to an explicit `skipped`/`failed` with a reason, or raise.

## Error Catalogue

The tables below enumerate the failure conditions, their handling, and the owning module.

## Generation errors

| Condition | Behaviour | Where |
|---|---|---|
| Pin table validation not passed / no rows | `ValueError` — refuse to emit a bogus symbol | `eda-bridge/kicad_symbol.py` |
| `kicad-cli` ERC reports errors | schematic is **not** reported ready; ERC errors surfaced | `eda-bridge/kicad_emit.py` |
| Symbol not resolvable (`lib_id` → no `.kicad_sym`) | clear "symbol not found" with the searched lib name | `eda-bridge/kicad_emit.py` (`load_symbol`) |
| Compose plan references an unknown part | composition fails with the missing ref, not a partial emit | `eda-bridge/composer.py` |

## Verification degradation (never a false pass)

| Condition | Behaviour | Where |
|---|---|---|
| No SPICE engine on PATH | `skipped-no-engine` (verdict carries the reason) | `eda-bridge/simulate.py` |
| Skill path given but invalid | `skipped-no-skills` (does not fall through to "failed") | `eda-bridge/simulate.py` |
| EMC/thermal inputs missing (no PCB JSON) | `skipped` with the missing input named | `eda-bridge/pcb_verify.py` |
| Cross-check reference has no coverage for a net | net reported as a **gap**, never silently passed | `workflow-core/reference_crosscheck.py` |
| Datasheet coverage absent (DS-001 class) | findings downgraded to "consistency only"; no "verified" claim | orchestrated `kicad`/`datasheets` skills |

## Document / companion errors

| Condition | Behaviour | Where |
|---|---|---|
| `soffice --convert-to docx` produces no file | explicit filter `docx:MS Word 2007 XML` + per-format LO profile dir (avoids profile lock); failure raised if still empty | `reverse-core/doc_emit.py` |
| Unsupported engineering file for companion | reports "unsupported" clearly rather than emitting nothing silently | `reverse-core/companion_render.py` |

## Server / transport errors

| Condition | Behaviour | Where |
|---|---|---|
| POST to `/mcp` (no trailing slash) | 307 redirect to `/mcp/`; clients must POST to `/mcp/` | `services/mcp/server.py` |
| Token not found / expired (reaped) | resolve fails with a not-found; client re-uploads | `services/mcp/token_store.py` |
| Path arg escapes the token `doc_dir` | rejected (no traversal outside the namespace) | `services/mcp/server.py` |
| Tool raises | error returned as the MCP tool result content; server stays up | `services/mcp/server.py` (`run_tool`) |

## Safety invariants

- **No fab output without validation + explicit approval** (DD-8) — the fab path is approval-gated.
- **No working data written into the repo** — only `Token.doc_dir` (runtime) or `data_root()` (external).
- **No silent truncation** — if coverage is bounded (top-N, sampling), it is logged, not hidden.
