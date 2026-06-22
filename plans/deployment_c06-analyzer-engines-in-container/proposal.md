# Proposal: deployment_c06-analyzer-engines-in-container

## Why

- bodesign's three C06 verification tools — `bodesign_simulate`,
  `bodesign_analyze_emc`, `bodesign_analyze_thermal` — resolve their analyzer
  engine at runtime via `resolve_skill(name, BODESIGN_*_SKILL, ...)`. The Docker
  images bundle the **binary toolchain** (kicad-cli, pcbnew, ngspice) but **never
  the analyzer engine scripts** and set **no `BODESIGN_*_SKILL` env**. So all three
  tools return `skipped-no-skills` in every default deployment, and C06
  SPICE/EMC/thermal is **structurally unable to run** — permanently stuck at
  `not-run`.
- The honesty model forbids fabricated verdicts, so the *only* way to advance C06
  is to let the tools actually run. With no engine in the container, "reliability
  is shown, not asserted" cannot be satisfied — there is no path to *show*.
- The failure signal (`skipped-no-skills`) is honest but **non-actionable from
  inside bodesign**: env + mounts are deployment-layer, not tool parameters, so an
  agent receiving the skip cannot self-recover.
- Source BR: `issues/issue_20260623_c06_analyzer_engines_not_mounted_in_container.md`.

## Original Requirement Wording (Baseline)

- "處理兩個新的BR … C06是新的BR要plan-builder處理" — handle the C06 analyzer-engines
  BR by opening a plan-builder package to design the root-cause fix.
- BR §5 fix directions: 容器內提供 analyzer engine + 設 `BODESIGN_*_SKILL` env +
  釐清執行歸屬（main vs ee/me worker）+ 部署自檢 + 文件對齊.

## Requirement Revision History

- 2026-06-23: initial draft created from BR `issue_20260623_c06_analyzer_engines_not_mounted_in_container`.

## Effective Requirement Description

1. The default bodesign deployment MUST be able to run `bodesign_simulate`,
   `bodesign_analyze_emc`, and `bodesign_analyze_thermal` against a real
   `.kicad_sch` + `.kicad_pcb` and produce a real verdict (pass/warn/fail or an
   honest `skipped-no-simulator` where a *binary* is genuinely absent) — **not**
   `skipped-no-skills`.
2. The analyzer engine scripts (`kicad`, `spice`, `emc`) MUST be present inside
   every image that executes the EE tool group, at a deterministic path the
   server resolves without host-dir guessing.
3. Whether the analyzer runs in the monolith or the `bodesign-ee` worker MUST be
   explicit and correct (the EE group owns these tools).
4. Analyzer-engine readiness MUST be observable without `docker exec` probing
   (a self-check surfaces engine + binary readiness).
5. Docs that assert a default engine path (`server.py` instructions, MANIFEST,
   skill, enablement) MUST match the real container reality.

## Scope

### IN
- `Dockerfile` (monolith, `--tools all`) and `Dockerfile.ee` (`--tools ee`):
  bundle engine scripts + set `BODESIGN_KICAD_SKILL` / `BODESIGN_SPICE_SKILL` /
  `BODESIGN_EMC_SKILL`.
- A deployment self-check that reports analyzer-engine readiness.
- Doc/instruction alignment for the real container path.

### OUT
- `Dockerfile.core` (lean core): it forwards the EE group to `bodesign-ee` and
  runs **no** EE tool locally, so it does not need the engines.
- The readiness path-visibility BR (`issue_20260623_readiness_silent_missing_on_invisible_path`)
  — separate defect, separate spec (`specs/quality_readiness-fail-loud-on-invisible-path/`).
  Only shared theme is "container mount boundary".
- Changing the honesty model or the `skipped-no-*` three-state contract itself.
- New analyzer capabilities — this is a packaging/deployment fix, not analyzer work.

## Non-Goals

- Mounting the user's host `~/.claude/skills` into the container at runtime
  (host-dependent, non-portable; the image must be self-contained).
- Refactoring `resolve_skill`'s resolution order (env-var win is sufficient and
  already supported).

## Constraints

- **Single source of truth for engine scripts**: the cleaned, secret-scrubbed
  distributables already exist at `services/mcp/assets/skills/*.tar.gz`
  (`bodesign.tar.gz` carries `engines/kicad`+`engines/kidoc`; `spice.tar.gz`,
  `emc.tar.gz` are standalone). Prefer extracting these over `COPY`-ing the raw
  repo `skills/` tree — the raw tree is incomplete (no `spice`, `emc` has no
  `scripts/`) and unscrubbed.
- `resolve_skill` qualifies a candidate **only if it contains a `scripts/`
  subdir**; the bundled path must satisfy that.
- Env var wins over host-dir default in `resolve_skill` order, so setting the
  three env vars makes resolution deterministic regardless of `$HOME`.
- Image is already intentionally heavy (~GB); engine scripts are markdown+python,
  negligible added weight.

## What Changes

- Both EE-capable images gain the analyzer engines at a fixed path + the three
  `BODESIGN_*_SKILL` env vars → the three C06 tools resolve their engine and run.
- A self-check makes engine readiness visible.
- Docs stop asserting a host path that does not exist in the container.

## Capabilities

### New Capabilities
- Deployment self-check: report whether each analyzer engine (kicad/spice/emc) is
  resolvable *and* its underlying binary (kicad-cli/ngspice) is present.

### Modified Capabilities
- `bodesign_simulate` / `analyze_emc` / `analyze_thermal`: in the default
  deployment, transition from always-`skipped-no-skills` to actually executing.

## Impact

- Build layer: `Dockerfile`, `Dockerfile.ee`.
- Code anchors (unchanged logic, now satisfied at runtime):
  `packages/eda-bridge/bodesign_eda_bridge/skill_paths.py`,
  `packages/eda-bridge/bodesign_eda_bridge/pcb_verify.py`,
  `packages/eda-bridge/bodesign_eda_bridge/simulate.py`.
- Docs: `services/mcp/server.py` instructions (default-path line),
  `services/mcp/assets/skills/MANIFEST.md`, `skills/bodesign/SKILL.md`,
  enablement.
- Operators: anyone running the default or workers compose topology for C06.
