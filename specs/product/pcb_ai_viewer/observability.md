# Observability: bodesign

What an operator can see when bodesign runs as a standalone MCP service.

## Health

- **`GET /healthz`** — liveness; returns ok when the server + session manager are up.
- **Container healthcheck** — `docker-compose.yml` probes the UDS socket; `./mcpctl.sh status` reports container health + socket presence.
- **Readiness (domain-level)** — `package_readiness` is the *product's* compass (how complete a design package is), distinct from process health.

## Logs

- **Server** — request/transport logs from uvicorn (UDS + TCP binds); MCP tool dispatch logged per call.
- **Build** — `mcpctl.sh` streams `docker compose build --progress=plain` to `.run/build.log`.
- **Tool provenance** — generation tools embed an evidence string (`BodesignEvidence` property, `raw_pdf_text_committed=false`) so output traces back to its source without committing raw PDFs.
- **Verification verdicts** — each verify tool logs `passed|failed|skipped` + reason; skipped reasons (no-engine/no-skills/no-input) are first-class, not swallowed.

## Events

Domain + lifecycle events bodesign surfaces (logged per tool call):

- **upload** — token created (`POST /files` / `stage_dir`), reap sweep run.
- **generate** — symbol/schematic emitted + `kicad-cli` ERC verdict.
- **verify** — cross-check / SPICE / EMC / thermal verdict (`passed|failed|skipped` + reason).
- **emit** — layout/fab/doc artifact produced (`{token, rel}` + companion).
- **approve** — fab gate released (DD-8).
- **compass** — readiness recomputed → next step.

## Signals worth watching

| Signal | Meaning | Source |
|---|---|---|
| token store size / reap count | working-data growth; GC is functioning | `token_store.py` (`reap()` on access) |
| `skipped` verdict rate | how often verification degrades (missing engines/skills) | verify tools |
| cross-check coverage % | reliability basis per deliverable | `reference_crosscheck.py` |
| ERC/DRC failure rate | generation quality | `kicad-cli` via emit/layout |
| build.log tail | image build success/failure | `.run/build.log` |

## Privacy / data hygiene

- **TTL-GC** — `Token.doc_dir` entries older than `BODESIGN_TOKEN_TTL_SECONDS` (default 3600) are reaped on the next token operation; `resolve()` refreshes mtime (LRU keep-alive).
- **No working data in the repo or logs** — client trees live only under the token store or `data_root()`; logs reference files by `{token, rel}`, not by absolute host paths.
- **Secrets** — distributor/API keys are env-sourced; never logged. Skill token caches use `$XDG_RUNTIME_DIR` (0600), not predictable `/tmp`.

## Metrics

No metrics exporter ships in 1.0 (deferred). The signals above are log/health-derived; a Prometheus exporter for token-store size, verdict rates, and cross-check coverage is roadmap.
