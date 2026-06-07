# Toolchain Worker Architecture (Batch E — design)

Status: planned (design before code, per the user's "land it in the plan first")

## Why

C00–C07 will orchestrate **many** heavy professional toolchains (KiCad/ngspice/EMC,
build123d/OCP CAD, LibreOffice render, ML vision, …). A single image that bundles
them all becomes huge, forces every deployment to carry tools it never uses, and lets
one native library's crash take down the whole MCP. The fix is to keep ONE
externally-facing MCP server but run the heavy toolchains in **a few worker
containers grouped by function/responsibility** — the same C0x responsibility split
the `agent_registry` already encodes, now realized physically.

## Grouping principle: by responsibility, NOT by weight

Group toolchains by **professional discipline / C0x responsibility and co-usage**.
Weight-isolation is a *consequence*, not the driver. The rule: every heavy dependency
lives in exactly ONE container; tools that share it and form a pipeline co-locate
(stay in-process, fast); cross-container hops happen only at natural seams (a file
handed over a shared volume, infrequent).

This deliberately rejects "even by count/size": balancing by count would split tools
that share KiCad across containers and ship KiCad twice.

## Container map (workers)

| Container | Responsibility (C0x) | Owns (packages/toolchains) | Weight |
|---|---|---|---|
| **bodesign-core** | Product/spec/guide + orchestration — C00 PRD, C01 ID consult, C05 FW-spec, the spine | MCP server, agent_registry, orchestration loop, package_readiness, doc scaffold/emit, pm-skills, plan-builder, self-built C00/C01/C05 skills | light |
| **bodesign-ee** | Electronics engineering — C03 circuit · C04 layout · C06 verify | KiCad 9 (kicad-cli + pcbnew), ngspice, pygerber, emc, datasheets, bom/distributors | heavy (~GB) |
| **bodesign-me** | Mechanical engineering — C02 enclosure | build123d/OCP/vtk, OpenSCAD, (future FreeCAD/CadQuery) | heavy (~400MB+) |
| **bodesign-docs** *(optional; may fold into core)* | Deliverable rendering (cross-cutting) | LibreOffice/soffice, kidoc render, pdf | mid-heavy |

The grouping reads as real org boundaries: `ee` = the EE/PCB engineer's toolbox,
`me` = the mechanical engineer's toolbox, `core` = the PM/architect's desk. Heavy-dep
isolation (KiCad in ee, OCP in me) falls out for free.

**Already-MCP toolchains** (`docxmcp`, `drawmiat`) are NOT re-containerized — they are
mounted via the MCP-of-MCPs route (②) as upstream MCP servers.

## Worker contract

- **One external endpoint unchanged.** Only `bodesign-core` exposes UDS+TCP. Workers
  are internal to the compose project; clients still see a single MCP server (the
  README promise — "no host shell or gateway" — holds).
- **Workers reuse the bodesign image + transport.** Each worker runs the same
  `server.py` exposing only its tool subset (a `--tools <group>` selector) over MCP
  Streamable-HTTP on the compose network. No new protocol to invent.
- **Core routes by a tool→group table.** The tool registry gains a `group` per tool
  (core | ee | me | docs). For a tool owned by a worker, the core forwards the
  `tools/call` to that worker's endpoint instead of running a local handler; core-group
  tools run in-process as today.
- **Shared session volume = the file model.** The `bodesign-sessions` named volume
  (token doc_dir + cache) mounts into every worker, so all see the same project tree:
  constraints in, `Enclosure.step`/gerbers/reports out. Payloads over the wire stay
  small (args + token); bulk data is files on the shared volume.
- **Unavailable-gate generalizes, with a starting/unavailable distinction.** Two
  cases, surfaced as distinct retry semantics (never fabricate output for either):
  - **No worker configured** for the group (a deliberate slim deployment) → permanent
    `worker_unavailable` (status, `group`): this deployment cannot run it; do not retry.
  - **Worker configured but unreachable** (booting/warming/briefly down) → retryable
    `worker_starting` (`retry_after_seconds`, `group`): the caller should wait and retry.
  This keeps workers always-on (cheap idle) while giving an agent a clean "warming up,
  retry" signal during boot — instead of mistaking a starting worker for an absent one.
  Minimal deployment = just `bodesign-core`; add a worker to light up its capabilities.
- **In-process fallback for hybrids.** A tool that can run in-process (e.g. build123d
  imported locally) keeps that path when no worker is configured; the worker is an
  optional acceleration/isolation, not a hard requirement.

## Migration (incremental, non-breaking)

- **Phase 0 (now):** monolith image keeps working; nothing breaks.
- **Phase 1 — extract `bodesign-me` first** (reference worker): smallest blast radius,
  heaviest dep, and the build123d backend was just built. Add the `--tools me`
  selector, a `me` service in compose mounting the session volume, and core routing
  for `bodesign_c02_*`. Worker absent → `c02_export_*` report unavailable.
- **Phase 2 — extract `bodesign-ee`** (the big KiCad cluster): C03/C04/C06 tools.
- **Phase 3 — optional `bodesign-docs`**; mount `docxmcp`/`drawmiat` via MCP-of-MCPs.

## Non-goals

- Not changing the single external MCP endpoint or the token file model.
- Not Docker-out-of-docker (no docker socket in the server).
- Not splitting light skills/spec work out of core.
- Not per-tool containers — group by responsibility (3–4 workers), not 15+.

## Acceptance

- A deployment of `bodesign-core` alone answers every tool, returning `*_unavailable`
  for tools whose worker is not running (no fabrication, no crash).
- With `bodesign-me` running, `bodesign_c02_export_step` produces a real STEP on the
  shared volume; stopping it flips the same tool back to `step_export_unavailable`.
- Clients see one MCP endpoint throughout; the worker topology is invisible to them.
- A heavy dependency appears in exactly one worker image (no KiCad/OCP duplication).
