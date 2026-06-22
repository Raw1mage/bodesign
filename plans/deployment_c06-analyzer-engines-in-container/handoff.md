# Handoff: deployment_c06-analyzer-engines-in-container

## Execution Contract

This package is **plan-only** (state: planned). The fix is **not** implemented —
it requires Dockerfile edits + image rebuilds (GB-scale) + a live-container restart,
which is a separately-authorized pass. The root cause is fully diagnosed with code
evidence: the EE-executing images ship the binary toolchain (kicad-cli/pcbnew/ngspice)
but never the analyzer engine **scripts**, and set no `BODESIGN_*_SKILL` env, so
`resolve_skill` returns None → `skipped-no-skills`. The fix bundles the cleaned engine
tarballs into the image + sets the three env vars + adds a readiness self-check + aligns
docs.

## Required Reads

- `issues/issue_20260623_c06_analyzer_engines_not_mounted_in_container.md` — the BR.
- `spec.md` (this package) — invariants + behavioural contract.
- `design.md` (this package) — fix design + DD-1..DD-6 + code anchors + risks.
- `tasks.md` (this package) — execution checklist with per-task acceptance.
- Sibling `specs/quality_readiness-fail-loud-on-invisible-path/` — the other
  "container boundary" BR (distinct defect; cross-linked) + its
  `references/container-boundary.md`.

## Stop Gates In Force

- **Image rebuild** (task 6.1) restarts the live bodesign MCP container and ships
  new server INSTRUCTIONS — coordinate, don't surprise live sessions.
- **Cross-repo edit** (task 5.4, `prompts/enablement.json` lives in the opencode
  repo) — do NOT edit it from the bodesign repo; file as a follow-up for the user.
- **No runtime host-mount fallback** — the fix bundles engines into the image; a
  `~/.claude/skills` bind-mount must never become the correctness path (only
  optional operator convenience). Preserve this in any future change.
- **No send-to-fab implication** — this only restores C06 *analysis* verdicts; it
  does not relax the deterministic-validation + explicit-approval fab gate.

## Validation Plan

- Build-time: `test -d $BODESIGN_*_SKILL/scripts` fails the build if an engine is missing.
- In-image: `resolve_skill` non-None for kicad/spice/emc.
- Behavioural: the three C06 tools against the aiguard fixture never return
  `skipped-no-skills`.
- Self-check: per-engine engine-resolvable + binary-present on a built EE image.
- Negative: `Dockerfile.core` unchanged; core still forwards EE.

## Execution-Ready Checklist

- [x] Root cause identified with code evidence (skill_paths/pcb_verify/simulate anchors + Dockerfile/group analysis).
- [x] BR filed local-first in `issues/`.
- [x] Fix design with decisions (DD-1..DD-6) + risks + critical files.
- [x] Task breakdown with per-task acceptance.
- [x] IDEF0 + GRAFCET + sequence + data-schema authored and validated.
- [ ] Dockerfile + Dockerfile.ee engine bundling + env (tasks 1–2).
- [ ] Self-check implemented (task 4).
- [ ] Docs aligned (task 5; 5.4 cross-repo routed by user).
- [ ] Image rebuild + manual MCP round-trip (task 6).
