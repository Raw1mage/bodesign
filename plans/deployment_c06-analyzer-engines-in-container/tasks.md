# Tasks: deployment_c06-analyzer-engines-in-container

> Execution checklist for the permanent fix. **This package is plan-only** — tasks
> are authored for a future, separately-authorized implementation + image-rebuild
> pass, not executed now. Each task names its file(s) + acceptance.

## 1. Bundle engine scripts into the EE-executing images (root cause)

- [ ] 1.1 In `Dockerfile` (monolith, `--tools all`): add a build step that extracts
  the cleaned `services/mcp/assets/skills/bodesign.tar.gz`, `spice.tar.gz`,
  `emc.tar.gz` into a fixed path `/opt/bodesign-engines/` (yielding
  `bodesign/engines/kicad/scripts`, `spice/scripts`, `emc/scripts`). Source =
  tarballs, NOT the raw repo `skills/` tree (DD-2).
- [ ] 1.2 In `Dockerfile.ee` (`--tools ee`): same extraction step. Factor into a
  shared snippet/stage if practical to avoid monolith↔ee drift (R3).
- [ ] 1.3 Confirm `Dockerfile.core` is **not** modified (it forwards EE; no local
  engine need — DD-4). Add a one-line comment recording why, so a future reader
  doesn't "fix" it by adding engines.
- **Acceptance**: built monolith + ee images contain
  `/opt/bodesign-engines/{bodesign/engines/kicad,spice,emc}/scripts`.

## 2. Wire the env vars (deterministic resolution)

- [ ] 2.1 In `Dockerfile` + `Dockerfile.ee`: `ENV BODESIGN_KICAD_SKILL=/opt/bodesign-engines/bodesign/engines/kicad`,
  `BODESIGN_SPICE_SKILL=/opt/bodesign-engines/spice`,
  `BODESIGN_EMC_SKILL=/opt/bodesign-engines/emc` (DD-3; env wins in `resolve_skill`).
- [ ] 2.2 Build-time assert (RUN `test -d "$BODESIGN_KICAD_SKILL/scripts" && test -d
  "$BODESIGN_SPICE_SKILL/scripts" && test -d "$BODESIGN_EMC_SKILL/scripts"`): build
  fails loud if any `scripts/` is missing (R2 mitigation).
- **Acceptance**: in the image, all three env vars set and each `$VAR/scripts` is a dir.

## 3. Verify resolution + tool execution

- [ ] 3.1 In a built image, run a tiny harness importing
  `bodesign_eda_bridge.skill_paths.resolve_skill` and assert non-None for
  `("kicad", "BODESIGN_KICAD_SKILL")`, `("spice", "BODESIGN_SPICE_SKILL")`,
  `("emc", "BODESIGN_EMC_SKILL")`.
- [ ] 3.2 Run `bodesign_simulate` / `analyze_emc` / `analyze_thermal` against the BR
  fixture (`aiguard_power.kicad_sch` + `aiguard_power_routed.kicad_pcb`); assert no
  result is `skipped-no-skills` (a real verdict or honest `skipped-no-simulator`).
- **Acceptance**: spec.md "C06 tools run in every EE-executing image" scenarios pass.

## 4. Deployment self-check (observability — DD-5)

- [ ] 4.1 Decide the host: extend an existing diagnostics/health path (e.g.
  `bodesign_vault_diagnostics`-style, or `/healthz` detail) rather than a new
  heavyweight tool. Record the choice in design.md Decisions.
- [ ] 4.2 Implement: for each of kicad/spice/emc report `{engine_resolvable,
  binary_present, resolved_path, can_run}` per the `AnalyzerEngineReadiness` schema
  (`data-schema.json`); kicad-cli for kicad/emc/thermal, ngspice for spice.
- [ ] 4.3 Surface `image_role` (monolith/ee/core) so a core report of "engines
  absent" reads as by-design, not broken.
- **Acceptance**: self-check on a built EE image reports all three
  engine-resolvable=true + binary-present=true.

## 5. Doc alignment (DD-6)

- [ ] 5.1 `services/mcp/server.py:39`: correct the `BODESIGN_KICAD_SKILL (default
  ~/.claude/skills/bodesign/engines/kicad)` instruction to the real in-container
  path / "image self-bundles the engine".
- [ ] 5.2 `services/mcp/assets/skills/MANIFEST.md`: same correction to its default-path note.
- [ ] 5.3 `skills/bodesign/SKILL.md` + cross-link the existing
  `references/container-boundary.md` (added by the readiness sibling) with the
  engine-bundling fact.
- [ ] 5.4 Enablement note (`prompts/enablement.json` — **cross-repo, opencode**):
  file as a follow-up for the user to route; do NOT edit from the bodesign repo.
- **Acceptance**: no doc asserts a host path absent in the container.

## 6. Build + manual round-trip (separately authorized)

- [ ] 6.1 `./mcpctl.sh rebuild` (and the workers overlay build) — restarts the live
  MCP container; coordinate, don't surprise live sessions (stop gate).
- [ ] 6.2 Manual MCP round-trip: upload the aiguard EE sources via the file model,
  run the three C06 tools, confirm real verdicts; run the self-check.
- **Acceptance**: aiguard C06 SPICE/EMC/thermal advance from `not-run` to a real
  tool verdict; the BR's reproduction no longer yields `skipped-no-skills`.
