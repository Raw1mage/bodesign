<!--
  bodesign CANONICAL USAGE DOCTRINE  (R15 self-describing organism, one-source)

  This file is the SINGLE SOURCE projected by BOTH the `bodesign_init` MCP tool
  (tools/call) AND the `bodesign_init` prompts/get entry. Edit it here; both MCP
  faces serve this text byte-for-byte (R15.5 no-drift).

  It is the PORTABLE, in-band condensate of skills/bodesign/SKILL.md — it carries
  the cross-tool tradeoffs, pre-call disciplines, organ coordination, and
  counter-intuitive gotchas that a per-tool `description` cannot structurally hold
  (R15.2). It is NOT the full C00–C07 lifecycle methodology; load the `bodesign`
  skill for that. Keep this file in step with SKILL.md §"How to use this skill" +
  §"Landing / compute routing contract" + §"The one rule that overrides
  convenience" when they change.
-->

# bodesign — usage doctrine (read before first use)

bodesign is an **AI PCB design copilot**: it walks a hardware product through the
**C00–C07 lifecycle** (PRD → ID → ME → EE → Layout → FW → Verify → MFG) and emits
a documented, honestly-gated design package. Its defining discipline is that it
**shows reliability rather than claiming it** — every "it works" is backed by
deterministic evidence (KiCad ERC/DRC, cross-check against a known-good reference,
SPICE, EMC/thermal), never by an LLM assertion. The LLM does upstream
extraction/adjudication only; validation and comparison never involve it.

## 0. First use — the concrete baseline tools (R17.5)

Before anything else, call these NAMED tools (not "load the skill" hand-waving):

- **`bodesign_init`** — this doctrine + a machine-readable `capabilities` summary
  (transport / file ingress-egress / webdav state / companion skill / conditional
  tool families). Its `capabilities.transport.service_endpoints[]` flag container
  endpoints `host_executable:false` — do NOT paste a container UDS socket path as a
  host shell command.
- **`bodesign_stage_dir`** — stage an inline file tree into a token namespace
  (`{token, doc_dir, files}`); the portable ingress rail.
- **`bodesign_workspace_inspect`** — enumerate a token's tree and PROVE your staged
  assets are present BEFORE any render/emit; this is also the recon step that keeps
  a first large operation from being flagged as a skipped-contract wall (R0.6).
- **portable egress** — read any produced blob as `bodesign://files/<token>/<rel>`
  via MCP `resources/read` (a bare stdio client needs no HTTP/WebDAV).

Conditional (file-producing) tools — **`bodesign_emit_fab`**, **`bodesign_emit_doc`**,
**`bodesign_render_board_model`**, **`bodesign_compose_schematic`** — run a typed
asset preflight before they touch anything (unresolved / missing-media / out-of-
namespace / host-only paths are refused with a remedy) and accept an opt-in `assert`
(expected files/media/text, `non_empty`) so a transport-valid but EMPTY artifact is
never reported delivery-ready. The one companion skill is **`bodesign`** (this file's
source); `mcp.json.skillPaths`, `GET /skills` and `bodesign_init` all name it.

## 1. Cross-tool tradeoffs — pick the right plane, honour the honesty contract

- **The surface has TWO planes; route by plane, not by habit (R13.5).**
  - **Landing verbs — run LOCALLY on the host via `gate.py`, zero token
    round-trip.** The ~52 deterministic project-folder verbs (C00 PRD family,
    C01 ID family, C02 analysis, C03 emitters, C04–C06 scaffold/readiness, the
    orchestration spine, `ingest_project` / `package_readiness` / `datasheet_lookup`
    / `spec_check` / `rca_spec_audit`, and pure functions `impedance_solve` /
    `pin_allocation` / `reference_crosscheck` / `plan_design_intent` /
    `evidence_manifest`) are **NOT MCP tools**. Run them against the project repo:
    `python3 <bodesign-skill>/scripts/gate.py <verb> --repo /abs/project [--json '{…}' | --arg k=v]`
    (`gate.py --list` enumerates every landing verb). They write straight into the
    project tree — no upload, no container round-trip.
  - **Compute tools — this MCP server, prefix `bodesign_`.** The heavy toolchain a
    host cannot run: KiCad schematic/layout/fab, verification (simulate / si_check
    / analyze_emc / analyze_thermal), CAD/render (c02 STL/STEP/SKP + enclosure/board
    render + project_svg), the component vault (`vault_*`), spice_model_card, DXF↔DWG,
    export_bom/netlist, emit_doc/render_companion, mcp_call, stage_dir, and the
    cache lifecycle. `GET /tools` (and `/tools/{name}`) on the running service is the
    authoritative, current schema — do NOT hardcode tool schemas from memory.
- **`TOOL_LANDED` is not "unknown tool".** Calling a landed verb as an MCP tool
  returns a typed `TOOL_LANDED` error carrying the equivalent `gate.py` command.
  Follow the command; do not retry the tool. (Model memory / old docs may still
  advertise `bodesign_c00_readiness` etc. as tools — they were landed in R13.)
- **Generation is NOT validation.** Whatever a compute tool emits is `draft` /
  `pending` until you run the local analyzers + gates over it (exactly as the stage
  guides require). No send-to-fab output without deterministic validation + explicit
  user approval.
- **Never fabricate a deliverable or a native file.** `.ai` / `.skp` / STEP / STL
  are produced only when a real toolchain is present; otherwise the tool honestly
  reports `*_unavailable` (or emits an intermediate like `figma_import_spec.json`) —
  it never draws a decorative fake. `files` lists only bytes that exist on disk;
  pending outputs are surfaced as a status, not a phantom placeholder.
- **Datasheet-grounded electrical claims.** Before stating any part's electrical
  spec, gate it: `bodesign_vault_spec_check` (or `datasheet_lookup`); publish an RCA
  only after `rca_spec_audit`. A spec value with no datasheet source is BLOCKING,
  never guessed.

## 2. Pre-call disciplines

- **`refs_ingest` is step 0 of every stage.** Scan the stage's `01_refs/` SSOT into
  a ranked source manifest first — the refs-gated emitters hard-fail
  `REFS_SSOT_MISSING` without it. An absent refs root reports `root_visible:false`
  loudly; never a clean empty.
- **Read the honesty model before writing any deliverable.** Unproven things are
  marked `draft` / `pending` / `not-run` with a reason + owner; external gates
  (EVT/DVT, FCC/CE, EMC lab, safety) are NEVER marked passed. An honest blocked
  artifact is allowed; silent absence is forbidden.
- **Produce the whole stage set in one pass (Definition of Done).** When you enter a
  stage, author/generate its entire required-deliverable set, then self-verify with
  the stage readiness check and report `dod_ok` + `guide_compliance` — NOT the bare
  `readiness_pct`. `readiness_pct: 100` with `dod_ok: false` means the deliverables
  do not yet meet the guide. "I can produce X if you'd like" is the anti-pattern:
  produce X, or mark it honestly blocked.
- **Self-verify against the guide's DoD manifest, not chat memory.** Run the stage's
  readiness verb (`c00_readiness` … `c06_readiness` via `gate.py`; C04 =
  `bodesign_layout_drc_gate` + `c04_readiness`; C03 = the schematic analyzer gate +
  `bodesign_prd_bom_crosscheck` PASS) and state which required items are
  present/partial/missing in your completion report.
- **Cheap hypotheses before structural changes (G6).** When a gate fails (DRC / ERC
  / SI / crosscheck mismatch), enumerate `simple_fix_candidates` and rule each out
  WITH evidence before any structural proposal. `structural_proposal_allowed` stays
  false while any candidate is unresolved — a structural change made while a cheap
  explanation is alive destroys evidence and multiplies blast radius.

## 3. Organ coordination (how the pieces fit)

- **Two halves, one workflow.** The **`bodesign` companion skill** is the workflow
  brain + the KiCad/kidoc analysis+doc engines; **this MCP server** is the
  generation half. skill → MCP for *generation* (emit KiCad artifacts instead of
  hand-authoring); MCP → skill for *analysis* (`bodesign_simulate` /
  `analyze_emc` / `analyze_thermal` call the skill's engines back via
  `BODESIGN_KICAD_SKILL` / `BODESIGN_SPICE_SKILL` / `BODESIGN_EMC_SKILL`, self-bundled
  in the container image under `/opt/bodesign-engines`). Load the `bodesign` skill
  FIRST for any multi-step hardware job — it is where the C00–C07 SOPs and the
  honesty contract live. This is advisory, not a gate: a bare MCP client with no
  skill mechanism is still correct to drive the tools using this doctrine alone.
- **Transport is MCP Streamable HTTP over a Unix domain socket** (local
  `.run/bodesign.sock`). The process also binds TCP `:8077` inside the container,
  but that port is **NOT published to the host** (BR_20260730d): reach the service
  over the UDS, which is what `mcp.json`'s `url` declares. External HTTP, if ever
  wanted, belongs behind a gateway in front of the socket -- a published port put
  an unauthenticated `POST /invoke` on every interface.
  The container runs in Docker and only sees `.run` / sessions /
  vault — a host path OUTSIDE those mounts is invisible, and readiness tools report
  `root_visible:false` for it. Never read a `readiness_pct: 0` as "deliverables
  missing" without checking `root_visible` first.
- **Cache 三層 mental model — where files live and how they move:**
  - **truth store** = the client-owned project tree (durable inputs + deliverables);
    landing verbs read/write it directly on the host; the container ingests it
    read-only.
  - **working cache** = a per-deliverable WebDAV workspace on the server;
    `bodesign_cache_provision` (idempotent per owner+subject; returns cache token +
    `/dav/{token}/` mount URL + optional Basic credential) → mount with rclone/davfs2
    or let heavy tools emit into it → `bodesign_cache_export` back to a host target →
    `bodesign_cache_close` (dirty-gated: `WORKSPACE_CLOSE_DIRTY` unless exported or
    `force=true`).
  - **vault** = cross-project component knowledge (server SQLite); `vault_*` tools
    only.
- **Small one-shot trees use the token file model:** `POST /files` (tarball) or
  `bodesign_stage_dir` → pass the returned `token` to any tool (path args resolve
  inside its doc_dir) → `GET /files/{token}/blob/{rel}` to read back.
- **Runtime is managed ONLY via `./mcpctl.sh`** (docker-compose; per-user project).
  A new tool / prompt / instruction takes effect after a container restart
  (`BODESIGN_DEV=1 ./mcpctl.sh restart` in dev; `rebuild` only when dependencies
  change). Never hand-roll `docker run` / `docker cp`.

## 4. Cache & file transfer (the single most-reflexed-wrong area)

Fleet SSOT: `opencode/specs/mcp-integration-standard` R2.0 (transfer modes) + R14
(WebDAV working-cache). Get the axis right BEFORE moving bytes.

- **Two orthogonal axes — never conflate them:**
  - **Location** — which filesystem your inputs/deliverables sit on (gdrive / `/tmp`
    / host path). This does NOT decide transport. A file being on gdrive has ZERO
    bearing on whether WebDAV works.
  - **Transfer** — how bytes cross the host↔container boundary. Route by this only.
- **Transfer is one of two modes:**
  - **pass-by-value** (DEFAULT, works on every deployment): `bodesign_stage_dir`
    (inline) AND a WebDAV mount are both this — bytes go over the UDS / WebDAV wire;
    the container needs to see NO host path.
  - **pass-by-reference** (special case, saves base64): only
    `cache_export(target)` and container-namespace paths. The container reads/writes
    that path itself, so it MUST be inside the container namespace. The deciding
    question is "is the path in the container namespace", NOT "is the workspace on
    gdrive".
- **The anti-reflex rule:** a file being on gdrive is NEVER the reason WebDAV is
  unusable. If WebDAV isn't working the real cause is credential / mount provision
  not ready — unrelated to gdrive/FUSE. When in doubt, pass-by-value
  (`bodesign_stage_dir`) always works.

## 5. Counter-intuitive gotchas

- **A tool gap is a tool gap — STOP, do not fall back (天條: no silent fallback).**
  Missing field / geometry / datasheet evidence → fail fast + explicit error + the
  missing-items list; never continue on a default value, the first-available value,
  or a generic model. If a compute tool errors or its output fails a gate: report,
  file a local `issues/` BR with the exact missing primitive, and wait for a fix or
  scope change. Never "finish the job" by hand-assembling OOXML / Gerber / a fake
  native file.
- **Read `expected` vs `actual` BEFORE you read `ok`.** A tool that processed a
  collection reports what it ACTUALLY did, not what you asked for: check the count
  pair (`expected_components` vs `placed`), the `dropped_*` / `unresolved_*` /
  `*_applied` lists, and any `basis` field — THEN the `ok` flag. Reading only `ok`
  misses partial failure: `route_net2pcb` once returned `ok:true unmapped:0` on a
  board that had silently lost 8 of its 92 parts — every active IC (BR_20260729 §B).
  The review question that catches this class: *if the caller reads only `ok` or a
  single count, can they reach a wrong conclusion?* If yes, the API is at fault, not
  the caller. Enforced by `checkers/no_silent_degradation.py` (L2/L6/L8, T-A).
- **Never hand-merge or hand-edit an Office/OOXML deliverable.** `.docx` / `.pptx` /
  `.xlsx` go through `bodesign_emit_doc` (markdown → docx+pdf) or `bodesign_mcp_call`
  driving docxmcp — not a caller-side `zip`/`ElementTree`/`python-docx` script. A
  single Word/PowerPoint repair warning is a delivery failure, not a nuisance.
- **`readiness_pct: 0` ≠ "deliverables missing".** On the container it usually means
  the project root is outside the mount (`root_visible:false`). Check `root_visible`
  before concluding anything is absent.
- **The C02 2D vector is DERIVED from the 3D model, not a second LLM-drawn path.**
  `c02_project_svg` projects the generated STL (single source, no drift) — exact
  geometric paths, not a raster trace. The C01 ID skeleton SVG is a *different*
  deliverable class (description → ID hand-off scaffold), not the same drawing.
- **Two C01 display paths coexist and are NOT interchangeable:**
  `C01-ID/Display UIUX/` (no underscore, companion source-of-truth markdown) vs
  `C01-ID/Display UI_UX/` (underscore, the optional ID-native bucket). Don't collapse
  them.
- **`has_3d:false` / `*_export_unavailable` is a truthful source-data gap to
  surface, not a bug to paper over** by substituting a scaled generic body. The
  honest gap IS the signal — a downstream stage decides how to close it.
- **A JSON schema `description` is the only documentation an MCP caller has.**
  Python docstrings do not exist for the thing calling these tools. Any knowledge
  a caller needs in order to read a return value correctly — a parameter that is
  an upper limit rather than an amount, a field whose meaning depends on another
  input — belongs in the schema, not only in the docstring. A caller once threw a
  router at 25% of its default search budget for four rounds and read the result
  as "this board cannot be routed"; the docstring said otherwise and the caller
  could not see it (BR_20260729 §J).

## 6. Operating on shared workers

The ee/me workers are shared. A route on a real BGA board runs 30–165 minutes,
so the lifecycle commands are not private to whoever types them.

- **`mcpctl.sh restart` / `rebuild` / `stop` refuse to run while a worker is
  busy** (BR_20260729 §L). They print what they would have killed and exit 3.
  Before this gate they recreated the containers and reported
  `bodesign MCP restarted` — the same line whether the workers were idle or
  whether someone's multi-hour route had just been destroyed. **A command that
  reports its own intent rather than its effect is the ops-layer form of the
  silent-degradation anti-pattern this repo lints for in Python.**
- **`./mcpctl.sh busy` answers "is it safe to restart?" with no side effects**
  (exit 0 idle, 3 busy). Use it instead of asking a peer session; an agreement to
  "check with each other first" delegates the guard to memory, which evaporates
  exactly when both sides are busiest.
- **`BODESIGN_FORCE=1` overrides, and still names the casualty.** Overriding is
  allowed; doing it quietly is not.
- **When a probe fails, block — do not read it as idle.** "I could not look" is
  not "there is nothing there". The costs are asymmetric: a false block costs a
  short wait, a false pass costs someone's multi-hour computation, so the default
  under uncertainty is conservative. This is the general rule behind the
  `UNKNOWN` state in the busy gate, and it applies to any readiness probe here —
  a failed check never counts as a passed one.
- **A restart is not a debugging step for a busy worker.** If a tool call misbehaves
  while a long job is running, diagnose it in place (`docker exec`, logs, the
  tool's own return fields). Recreating the container destroys the evidence AND
  the job.