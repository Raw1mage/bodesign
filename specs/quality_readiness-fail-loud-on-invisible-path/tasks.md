# Tasks: quality_readiness-fail-loud-on-invisible-path

> Execution checklist for the permanent fix. **This package is plan-only** — tasks are authored
> for a future implementation pass, not executed now. Each task names its file + acceptance.

## 1. Ingest-layer fail-loud (root cause)

- [x] 1.1 Add `root_exists: bool` to `ProjectFolderIndex` (`project_ingest.py`), set from `base.exists()`.
- [x] 1.2 `ingest_project_folder`: keep the `warnings.append("Folder not found: …")` but ensure
  `root_exists=False` is set and surfaced via `to_dict()` (add `root_exists` + keep `warnings`).
- [x] 1.3 Unit test: `ingest_project_folder("/nonexistent")` → `root_exists is False`,
  `warnings` non-empty, `file_count == 0` (distinguishable from an existing-but-empty dir which
  is `root_exists True` + empty files).

## 2. package_readiness surfaces the signal

- [x] 2.1 `PackageReadiness` dataclass: add `warnings: list[str]` + `root_visible: bool` fields.
- [x] 2.2 `assess_package_readiness`: capture `index.root_exists` / `index.warnings`; when root not
  visible, set `root_visible=False`, propagate warnings, and override `next_step` to the
  boundary-specific instruction (see DD-3) instead of a deliverable next-step.
- [x] 2.3 `PackageReadiness.to_dict()` (`package_readiness.py:82-93`): emit `warnings` + `root_visible`.
- [x] 2.4 `render_readiness_markdown`: render a prominent "⚠ folder not visible to the bodesign
  container" banner when `root_visible is False`.
- [x] 2.5 Test: `assess_package_readiness("/nonexistent")` → `root_visible False`, warnings present,
  `next_step` mentions mount/file-model. Regression test: a **visible** folder → `root_visible True`,
  `warnings == []`, and output is a **superset** of the pre-change shape (R1 mitigation).

## 3. Unify per-stage readiness error contract

- [x] 3.1 Add a shared helper `_root_guard(folder) -> (root: Path, visible: bool, warning: str|None)`
  (location TBD: `package_readiness.py` or a small `readiness_common.py`).
- [x] 3.2 Wire `_root_guard` into `assess_c01_package_readiness` (`c01_id_package.py`),
  `c02_readiness` (`c02_me_package.py`), `c04_readiness` (`c04_layout_constraints.py`),
  `c05_readiness` (`c05_fw_spec.py`), `c06_readiness` (`c06_test_plan.py`): when not visible, return a
  result with a distinct `root_visible: False` + warning, NOT blanket `missing`.
- [x] 3.3 Confirm c00 (`c00_prd_template.py:351`) already fails loud; align its message style with the
  new family contract (it may keep raising `C00TemplateError`, or move to the structured form per
  DD-4 — pick one and document).
- [x] 3.4 Decide DD-4 (raise typed error vs structured `root_visible:false`) and apply family-wide.
  Record the decision in design.md Decisions.
- [x] 3.5 Per-stage tests: each readiness fn against `/nonexistent` → distinguishable not-visible
  signal, not `missing`.

## 4. Docs / boundary sedimentation (F3/F4/F5)

- [x] 4.1 MCP server self-description: replace the unqualified "accepts plain host paths" line with
  the mounted-namespace qualification + file-model pointer (DD-5).
- [x] 4.2 Add big-tree upload guidance to the file-model docs: readiness only needs text/json
  deliverables; exclude `.glb`/`*_viewer.html`/PNG/`generated/`; give a size hint (the live 46 MB
  tree timed out twice; the text/json subset is ~tens of KB).
- [x] 4.3 New `engines/`-adjacent or skill `references/container-boundary.md`: state that bodesign MCP
  runs in Docker, lists the only mounts, and the host-path-vs-file-model decision rule.
- [x] 4.4 Cross-repo opencode edit DONE (2026-06-23, user-authorized). Added a `bodesign` entry to
  `mcp_servers.runtime_observed` in opencode's enablement.json SSOT
  (`packages/opencode/src/session/prompt/enablement.json`) + template (`templates/prompts/enablement.json`),
  per opencode AGENTS.md §142/§147. The entry carries a `container_boundary_note`: confirm a host
  path is inside the container mount namespace before passing it to a `bodesign_*` tool; otherwise
  use the file model; and never read a 0%/all-missing readiness as deliverables-missing without
  checking `root_visible`. Skill projection (`~/.local/share/opencode/skills/bodesign`) re-syncs
  `container-boundary.md` + the SKILL.md pointer automatically on next probe (hashes working-tree
  files; `probeCachedUntil` already expired) — no hand-copy.

## 5. Validation (whole-package acceptance)

- [x] 5.1 `pytest` for the new tests in §1.3, §2.5, §3.5 — all green.
- [x] 5.2 Manual MCP round-trip (DONE 2026-06-23 via `BODESIGN_DEV=1 ./mcpctl.sh restart`):
  (a) unmounted host path `/nonexistent/...` → `root_visible: false` + warnings + boundary
  `next_step` + empty deliverables ✓; (b) file-model tree (`bodesign_stage_dir` → doc_dir under the
  sessions mount) → `root_visible: true`, `warnings: []`, real scoring (67%, PRD+BOM present) ✓.
  Pre-restart the live container reproduced the bug (false 0%, no `root_visible` key), confirming the
  fix is what changed the behavior.
- [x] 5.3 Honesty regression: assert there is **no** input that yields `readiness_pct: 0` /
  all-missing while the warning is suppressed. The 0% path must always carry `root_visible:false`
  + a warning when the cause is invisibility.
- [x] 5.4 No new fallback introduced (red line #11): the fix only *reports* the boundary; it never
  auto-mounts, auto-retries, or guesses an alternate path.

## Acceptance summary

The fix is done when: an invisible/nonexistent folder produces a **distinguishable, loud** signal
across the entire readiness family (package + c00–c06); ingest warnings reach MCP output; visible
folders are byte-compatible supersets of today's output; docs + skill + enablement record the
container boundary; and no fallback was added.
