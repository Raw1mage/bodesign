# Spec: mcp_r13-landing-webdav-cache

## Purpose

Refactor bodesign per the fleet MCP integration standard: land the ~40
deterministic repo-local verbs as skill-attached scripts executed on the host
(R13 compute/landing split), keep only heavy compute + vault in the container,
and port docxmcp's per-deliverable WebDAV working cache so heavy workflows stop
paying the host-dir↔token-namespace packing/round-trip tax.

## Requirements

### Requirement: Landing verbs run on the host with zero token round-trip

Every Bucket-2 verb (C0x scaffold/readiness/answers/emit, orchestration spine,
read/gate, pure functions — ~40 verbs) MUST be executable as
`python3 skills/bodesign/scripts/gate.py <verb> --repo <abs> [--json {…}]`,
writing results directly into the caller's project folder under the agent's uid.

#### Scenario: C00 Q&A loop entirely on host

- **GIVEN** a caller project folder on the host
- **WHEN** the agent runs `gate.py c00_scaffold_prd`, then `c00_readiness`,
  then `c00_update_answers`, then `c00_emit_prd` against `--repo <abs>`
- **THEN** all files are created/updated directly in the folder, each call
  returns a single JSON envelope on stdout, and no tarball / token / blob GET
  is involved

#### Scenario: Heavy verb refused by the landing gate

- **GIVEN** the agent invokes `gate.py emit_fab --repo <abs>`
- **WHEN** gate.py consults its verb registry
- **THEN** it exits non-zero with typed `VERB_NOT_LANDING` and a hint naming
  the container tool to call instead — it never attempts the heavy work

#### Scenario: Missing packages fail fast, no container fallback

- **GIVEN** `BODESIGN_SRC` resolves to a directory without `packages/*`
- **WHEN** any landing verb is invoked
- **THEN** gate.py exits non-zero with typed `LANDING_PACKAGES_NOT_FOUND`
  before importing anything; it does not silently fall back to the MCP tool

### Requirement: Container surface converges to compute plane

The MCP tool registry MUST drop the landed Bucket-2 tools, keeping heavy
compute, vault, borderline (`c00_emit_prd_docx` assemble path,
`c02_voice_to_design`, `spice_model_card`, `stage_dir`, `mcp_call`) and the new
cache lifecycle tools. `mcp.json` bumps to 0.2.0 and its `instructions`
declare the three verb classes (R13.5).

#### Scenario: Legacy client calls a landed tool

- **GIVEN** a client still calls `bodesign_c00_readiness` on the 0.2.0 surface
- **WHEN** the server receives the call
- **THEN** it returns a typed `TOOL_LANDED` error carrying the equivalent
  gate.py command line — not an anonymous unknown-tool failure

### Requirement: Per-deliverable WebDAV working cache

An authenticated owner MUST be able to provision an idempotent-per-subject
deliverable cache, mount it via WebDAV class-2 (rclone/davfs2), have heavy
container tools read/write the same namespace, export it to a host target,
and close it behind a dirty-gate.

#### Scenario: Provision → mount → heavy relay → export → close

- **GIVEN** an owner provisions a cache for subject `boardX-fab`
- **WHEN** inputs are PUT over the mount, heavy tools (route → pour → DRC →
  emit_fab) run against the cache namespace, and the owner exports to
  `<project>/fab_out` then closes
- **THEN** artifacts land in the caller's authoritative folder, close succeeds
  only when the tree is clean since last export (409 `WORKSPACE_CLOSE_DIRTY`
  otherwise, unless `force`), and the namespace is reaped after close

#### Scenario: Cross-owner access rejected

- **GIVEN** user B holds valid credentials but token T belongs to user A
- **WHEN** B issues any DAV method or lifecycle call against T
- **THEN** the server returns typed 403 (typed 401 when unauthenticated);
  there is no fallback to a shared or first-available identity

#### Scenario: Deliverable cache survives idle, ephemeral tokens do not

- **GIVEN** a deliverable-cache token idle beyond the 1h ephemeral TTL
- **WHEN** the reaper runs
- **THEN** the deliverable cache is NOT reaped (only export-clean close or the
  long safety-net TTL reclaims it) while ephemeral tokens keep today's TTL/LRU

### Requirement: Two-layer verification with reproducible recipe

The full test suite MUST pass in both the host venv and the deployment image,
and the exact in-image invocation (mount points, workdir, optional specs bind)
MUST be written into tasks.md/handoff.md, not just the conclusion.

#### Scenario: Deployment-image regression

- **GIVEN** the rebuilt `bodesign:latest` image
- **WHEN** the suite runs in a disposable container per the recorded recipe
- **THEN** all tests pass, and a first-run failure is triaged as environment
  artifact vs regression before any fix

## Acceptance Checks

- AC-1: All ~40 Bucket-2 verbs invocable via gate.py with the JSON envelope;
  `--list` enumerates them; registry smoke test resolves every module path.
- AC-2: gate.py typed errors (`LANDING_PYTHON_TOO_OLD`,
  `LANDING_PACKAGES_NOT_FOUND`, `VERB_UNKNOWN`, `VERB_NOT_LANDING`) covered by
  tests; no container fallback path exists in the script.
- AC-3: C00 loop + orchestration dispatch→return→ingest cycle E2E green on a
  tmp repo via gate.py subprocess calls (host venv).
- AC-4: WebDAV PoC green in-process (provision → OPTIONS → PUT → PROPFIND →
  GET → MOVE → dirty-close 409 → export → close 200) + multi-user isolation
  (401/403 typed).
- AC-5: rclone E2E green against a real server (copyto/lsf/cat/mkdir/moveto/
  deletefile + wrong-password rejected).
- AC-6: Reaper class-aware tests green (deliverable-cache exempt, ephemeral
  unchanged, safety-net warn-first).
- AC-7: Removed-tool call returns `TOOL_LANDED` + landing command; `GET /tools`
  reflects the converged registry; UDS + TCP smoke pass after
  `mcpctl.sh restart`.
- AC-8: Host venv suite green AND deployment-image suite green via the
  documented recipe.
- AC-9: gate.py runs correctly from the XDG-projected skill dir with explicit
  `BODESIGN_SRC` (R13.6 self-containment).
- AC-10: `specs/architecture.md`, `skills/bodesign/SKILL.md`, README, and
  CHANGELOG synced; closing event recorded.
