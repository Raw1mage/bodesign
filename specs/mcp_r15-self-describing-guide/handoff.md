# Handoff: mcp_r15-self-describing-guide

## Execution Contract

- Deliver R15 conformance for bodesign: a `bodesign_init` MCP tool + a new
  `prompts/get bodesign_init` handler + `instructions` signposts, all projecting a
  single-source `BODESIGN_GUIDE_DOCTRINE` loaded fail-fast at startup.
- **Done** = live UDS smoke passes: tool returns doctrine; prompts/get returns
  byte-identical doctrine; `initialize.instructions` carries the signpost; missing
  doctrine.md refuses boot; and the R15.1–R15.5 §13 checklist is ticked.
- Status: **all tasks complete + live-verified** (tasks.md §1–§5 all `[x]`).

## Required Reads

- `design.md` (this package) — DD-1..DD-7, especially DD-7 (doctrine source =
  condensed `skills/bodesign/doctrine.md`, NOT raw SKILL.md; Dockerfile omits raw skills/).
- `/home/pkcs12/projects/opencode/specs/mcp-integration-standard/standard.md` — R15
  clauses + §13 checklist (acceptance reference).
- `services/mcp/server.py` — tool registration + prompts handler + INSTRUCTIONS.
- `Dockerfile` (+ `docker-compose.dev.yml`) — targeted COPY / bind-mount of doctrine.md.

## Stop Gates In Force

- **Graduation gate** (`verified → living`): user-only. AI may report readiness but
  MUST NOT call `plan_graduate` (AGENTS.md zone contract).
- **No send-to-fab analogue here**; no destructive ops. Container rebuild is via
  `mcpctl.sh` only (no manual docker run).

## Execution-Ready Checklist

- [x] doctrine source form decided (DD-7: condensed doctrine.md)
- [x] Dockerfile / dev overlay carry doctrine.md into image
- [x] server.py registers tool + prompts handler + signpost
- [x] live UDS smoke green across 3 services
- [x] §13 checklist R15.1–R15.5 verified
