# Spec: C06 analyzer engines runnable in the bodesign container

## Purpose

The three C06 verification tools (`bodesign_simulate`, `bodesign_analyze_emc`,
`bodesign_analyze_thermal`) must be able to **actually run** in the default
bodesign deployment and emit a real verdict. Today every default deployment
returns `skipped-no-skills` because the analyzer engine **scripts** are never
packaged into the image and no `BODESIGN_*_SKILL` env points at them — even though
the binary toolchain (kicad-cli, pcbnew, ngspice) is present. The honesty model
forbids fabricated verdicts, so a structurally-unrunnable C06 cannot be advanced
at all. `skipped-no-skills` (engine script absent) must be eliminated in the
default deployment, while `skipped-no-simulator` (binary genuinely absent) remains
a legitimate, distinct honest outcome.

## Requirements

### Requirement: C06 tools run in every EE-executing image

Every image that executes the EE tool group — the monolith `bodesign`
(`Dockerfile`, `--tools all`) and the `bodesign-ee` worker (`Dockerfile.ee`,
`--tools ee`) — ships the `kicad`, `spice`, and `emc` analyzer engine `scripts/`
at a fixed `$HOME`-independent path, with `BODESIGN_KICAD_SKILL` /
`BODESIGN_SPICE_SKILL` / `BODESIGN_EMC_SKILL` set to those paths.

#### Scenario: simulate against a real schematic in the default deployment
- **GIVEN** the default `docker-compose.yml` (monolith) deployment
- **WHEN** `bodesign_simulate` runs against a real `.kicad_sch` + `.kicad_pcb`
- **THEN** the result is a real verdict (pass/warn/fail) or an honest
  `skipped-no-simulator`, and is **never** `skipped-no-skills`

#### Scenario: analyze_emc / analyze_thermal in the EE worker
- **GIVEN** the workers overlay (`docker-compose.workers.yml`), where the core
  forwards the EE group to `bodesign-ee`
- **WHEN** `bodesign_analyze_emc` and `bodesign_analyze_thermal` run
- **THEN** each resolves its engine (`resolve_skill` non-None for kicad+emc /
  kicad) and is never `skipped-no-skills`

### Requirement: deterministic, host-independent engine resolution

Engine resolution must not depend on the runtime user's `$HOME`; the three
`BODESIGN_*_SKILL` env vars are authoritative (env wins in `resolve_skill` order),
each pointing at a directory that contains a `scripts/` subdir.

#### Scenario: env vars point at a scripts-bearing dir
- **GIVEN** a built EE image
- **WHEN** the image is inspected
- **THEN** each of `$BODESIGN_KICAD_SKILL`, `$BODESIGN_SPICE_SKILL`,
  `$BODESIGN_EMC_SKILL` is set and `"$VAR"/scripts` is a directory
- **AND** the image build fails loud if any of those `scripts/` dirs is absent

### Requirement: lean core stays engine-free

`Dockerfile.core` is not given the engines: the lean core forwards the EE group to
`bodesign-ee` and executes no EE tool locally.

#### Scenario: core forwards, does not run EE locally
- **GIVEN** the lean core image (`--tools core`)
- **WHEN** an EE tool is requested
- **THEN** it is forwarded to `bodesign-ee`, and the core image carries no analyzer
  engine (unchanged behaviour)

### Requirement: analyzer readiness is observable without docker exec

A deployment self-check reports, per engine, whether the engine is resolvable AND
its binary is present, so "can C06 run here" is answerable in one call.

#### Scenario: self-check on a correctly-built EE image
- **GIVEN** a correctly-built EE image
- **WHEN** the self-check runs
- **THEN** it reports kicad/spice/emc each as engine-resolvable=true and
  binary-present=true, distinguishing a missing engine (`skipped-no-skills`) from a
  missing binary (`skipped-no-simulator`)

### Requirement: docs match container reality

Docs that assert a default engine path must state the real in-container path or
that the image self-bundles the engines — never a host path absent in the container.

#### Scenario: MCP self-description default-path claim
- **GIVEN** the MCP server instructions / MANIFEST / skill
- **WHEN** they mention `BODESIGN_KICAD_SKILL` or a default engine path
- **THEN** the stated path resolves inside the container (or the text says the
  image bundles the engine), not `~/.claude/skills/...` which does not exist there

### Requirement: no runtime host-mount fallback

The fix bundles engines into the image; it must not introduce a runtime bind-mount
of the user's host skills as the correctness path.

#### Scenario: no `~/.claude` mount added to compose
- **GIVEN** the compose files
- **WHEN** the fix is applied
- **THEN** no `~/.claude/skills` bind-mount is added as the means of supplying
  engines (a mount may exist only as optional operator convenience, never the fix)

## Acceptance Checks

- [ ] `Dockerfile` and `Dockerfile.ee` extract `bodesign`/`spice`/`emc` engine
      scripts to a fixed path and set the three `BODESIGN_*_SKILL` env vars.
- [ ] Build-time assert: each `$BODESIGN_*_SKILL/scripts` exists; build fails loud otherwise.
- [ ] In a built monolith + ee image, `resolve_skill` returns non-None for kicad/spice/emc.
- [ ] `bodesign_simulate` / `analyze_emc` / `analyze_thermal` against the BR fixture
      never return `skipped-no-skills`.
- [ ] Self-check reports per-engine engine-resolvable + binary-present.
- [ ] `Dockerfile.core` unchanged; core still forwards EE and carries no engine.
- [ ] `server.py` instructions + `MANIFEST.md` + `SKILL.md` state the real container path.
- [ ] No `~/.claude/skills` runtime bind-mount added as the correctness path.
