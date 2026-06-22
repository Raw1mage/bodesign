# Handoff: quality_readiness-fail-loud-on-invisible-path

## Execution Contract

The permanent fix is **implemented and tested** (2026-06-23). The readiness family fails loud and
distinguishable on an invisible root via the shared `root_guard`; ingest carries `root_exists`;
every readiness `to_dict()` carries `root_visible` + `warnings` (additive superset for visible
folders); docs sediment the container boundary. Remaining: cross-repo enablement note (4.4) and the
image rebuild + manual MCP round-trip (5.2).

## Required Reads

- `issues/issue_20260623_readiness_silent_missing_on_invisible_path.md` — the BR + full RCA.
- `spec.md` (this package) — invariants + behavioural contract.
- `design.md` (this package) — fix design + code anchors + DD-1..DD-6 (DD-4 resolved to structured form).
- `references/honesty-model.md` (skill) — why a false-clean 0% is the cardinal sin here.
- `skills/bodesign/references/container-boundary.md` — the sedimented boundary + file-model routing.

## Stop Gates In Force

- **Cross-repo edit** (task 4.4, `prompts/enablement.json` lives in the opencode repo) — do NOT edit
  it from the bodesign repo; it is filed as a follow-up note for the user to route.
- **Image rebuild** (task 5.2) restarts the bodesign MCP container and ships the new server
  INSTRUCTIONS — coordinate, don't surprise live sessions. The code fix is already live under
  `BODESIGN_DEV=1 ./mcpctl.sh restart`; only the self-description string needs the rebuild.
- **No new fallback** (global red line #11) — the fix only reports the boundary; never auto-mount,
  auto-retry, or guess an alternate path. Any future change must preserve this.

## Validation Plan

- `tests/test_readiness_invisible_path.py` (9 tests) — ingest root_exists, package + c00–c06
  root_visible, honesty invariant, backward-compat superset. All green.
- Unchanged `test_run_tool_c00_readiness_missing_state_is_data_error` — confirms the c00
  artifact-missing-in-visible-folder path still raises.
- Manual MCP round-trip (5.2) after `./mcpctl.sh rebuild`: unmounted host path → `root_visible:false`;
  uploaded tree via file model → real scoring.

## Execution-Ready Checklist

- [x] Root cause identified with code evidence (5 anchors + 2 container-boundary probes).
- [x] BR filed local-first in `issues/`.
- [x] Fix design with decisions + risks + critical files; DD-4 resolved.
- [x] Task breakdown with per-task acceptance.
- [x] Implementation across ingest + readiness family + docs.
- [x] Tests written and green; honesty-regression assertion included.
- [ ] Cross-repo enablement note (4.4) routed by the user.
- [ ] Image rebuild + manual MCP round-trip (5.2).
