# Spec: readiness fail-loud on invisible path

## Purpose

The readiness family (`bodesign_package_readiness`, `bodesign_c00_readiness` … `bodesign_c06_readiness`)
must distinguish **"the root folder is not visible / does not exist"** from **"the folder is visible
but its deliverables are missing/incomplete"**. bodesign MCP runs containerized and only mounts
`.run`/sessions/vault; a host path outside those mounts (an unmounted FUSE mount, or a typo) is
invisible. The first case must fail loud and distinguishable; the second is the existing readiness
scoring. A `readiness_pct: 0` caused by invisibility must never look identical to a genuinely-empty
folder — that false-clean reading nearly drove an agent to regenerate real, hand-written deliverables.

## Requirements

### Requirement: Distinguishable not-visible signal across the readiness family

Every readiness entrypoint guards root visibility first (shared `root_guard`) and, when the root is
not visible, returns a result carrying `root_visible: false` + a non-empty `warnings` list + a
boundary `next_step`, with `status: "path-not-visible"` where the result has a status field.

#### Scenario: readiness call against an unmounted / nonexistent host path
- **GIVEN** a folder path the container cannot see (unmounted FUSE mount, or a path that does not exist)
- **WHEN** any `bodesign_*_readiness` tool is called with it
- **THEN** the result has `root_visible == false`, `warnings` non-empty, and `next_step` instructs to
  pass a mounted path or use the file model (tar → token → doc_dir)
- **AND** `readiness_pct == 0` is accompanied by that signal — never a bare 0% with all-missing deliverables

#### Scenario: ingest distinguishes invisible root from an empty folder
- **GIVEN** `ingest_project_folder` is called on a nonexistent root vs an existing-but-empty directory
- **WHEN** each returns a `ProjectFolderIndex`
- **THEN** the nonexistent root has `root_exists == false` + a warning; the empty directory has
  `root_exists == true` + `warnings == []` — both surfaced via `to_dict()`

### Requirement: Backward compatibility for visible folders

A visible folder produces output that is a strict superset of the pre-change shape, so existing
callers keep working.

#### Scenario: readiness call against a mounted, visible folder
- **GIVEN** a folder visible to the container
- **WHEN** a readiness tool is called
- **THEN** `root_visible == true`, `warnings == []`, and every prior `to_dict()` key is present and unchanged

### Requirement: Artifact-missing stays a separate loud signal

Root-invisibility and in-folder-artifact-missing are two distinct loud signals; folding in the new
guard must not weaken the existing artifact-missing behaviour.

#### Scenario: c00 with a visible folder but missing answer_state.json
- **GIVEN** a visible folder whose `C00-PRD/answer_state.json` is absent
- **WHEN** `assess_c00_prd_readiness` runs
- **THEN** it raises `C00TemplateError` (existing behaviour), NOT the structured `path-not-visible` form

### Requirement: No new fallback

The fix only reports the boundary; it never papers over invisibility.

#### Scenario: invisible path is never auto-resolved
- **GIVEN** an invisible root
- **WHEN** any readiness tool runs
- **THEN** it does not auto-mount, auto-retry, or guess an alternate path (global red line #11; AGENTS §2.1)

## Acceptance Checks

- [x] Invisible/nonexistent folder → `root_visible: false` + warnings + boundary `next_step` across package + c00–c06.
- [x] `ingest_project_folder`: `root_exists` distinguishes invisible root from scanned-but-empty.
- [x] Where a status field exists, invisible root yields `status == "path-not-visible"` (c04/c05/c06; c00 structured form).
- [x] Visible folder → `root_visible: true`, `warnings: []`, output is a superset of the prior shape.
- [x] c00 still raises `C00TemplateError` for a missing `answer_state.json` in a visible folder.
- [x] No fallback / auto-mount / silent retry introduced.
- [x] MCP self-description + skill `container-boundary.md` document the boundary + file-model routing.
- [x] Covered by `tests/test_readiness_invisible_path.py` (9 tests) + unchanged `test_run_tool_c00_readiness_missing_state_is_data_error`.
