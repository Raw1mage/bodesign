# Proposal: quality_readiness-fail-loud-on-invisible-path

## Why

- bodesign MCP runs inside a Docker container whose only mounts are `.run`, the sessions
  volume, and the vault volume. When a caller passes a **host path that is not mounted into the
  container** (e.g. a Google Drive FUSE mount, or simply a typo'd path), the readiness family
  does not fail — it returns a syntactically clean `readiness_pct: 0` with every deliverable
  `missing`, and silently drops the one warning that would have explained why.
- This is a direct violation of bodesign's honesty model ("never claim more than you can show")
  and the global fail-fast rule. A tool that *cannot see the folder* must not return a score that
  is indistinguishable from *the folder is genuinely empty*.
- Observed live: every `bodesign_*_readiness` call against
  `thesmart_products/01.openmv` returned 0%/missing while the files (e.g. a 2568-byte
  `Design_Direction.md`, a 29 KB `answer_state.json`) demonstrably exist on the host. An agent
  nearly concluded the entire portfolio was empty and needed full regeneration.

## Original Requirement Wording (Baseline)

- "我發現許多磨擦點。agent竟然不知道mcp是跑在docker裏，嘗試用非正規手段調用。這些都要寫RCA發BR建立治本修復plan"

## Requirement Revision History

- 2026-06-23: initial draft created via plan_create. Scope = RCA + BR + 治本修復 plan (NOT
  implementation), all filed in the bodesign repo, per user's two scoping answers.

## Effective Requirement Description

1. Produce a permanent fix design (this plan) that makes the readiness family **fail loud and
   distinguishable** when the target folder is not visible/does not exist, instead of returning a
   false 0%.
2. Surface ingest-layer warnings all the way to MCP tool output (no silent drop).
3. Unify the readiness family's error contract (c00 already raises; the rest swallow).
4. Sediment the container-boundary knowledge into the bodesign skill + `enablement.json`, and
   correct the MCP self-description's misleading "accepts plain host paths" line; add big-tree
   upload guidance for the file-model path.

## Scope

### IN
- `ingest_project_folder` (`packages/reverse-core/.../project_ingest.py`) fail-loud on non-existent
  root.
- `assess_package_readiness` + `PackageReadiness.to_dict()` (`package_readiness.py`) carrying a
  `warnings` / `root_visible` signal to output.
- Per-stage readiness functions (c01/c02/c04/c05/c06) gaining a consistent "root not visible"
  distinct status rather than blanket `missing`.
- MCP server instructions / self-description: clarify host-path-must-be-mounted; document
  file-model (tar → token → doc_dir) as the path for unmounted trees; add big-tree exclude/size
  guidance.
- bodesign skill + `enablement.json`: record the container mount boundary + routing.

### OUT
- **No implementation in this pass.** This package stops at `designed`/`planned` artifacts.
- Not changing the deliverable-scoring rubric (the POC_CHECKLIST keywords) — only the
  not-visible-vs-empty distinction.
- Not adding any new fallback that "guesses" a path or silently retries — fail-fast only.
- Not re-mounting the container or changing docker-compose volumes as the *primary* fix (a mount
  change is one option to evaluate in design, but the contract fix is mandatory regardless).

## Non-Goals

- Auto-detecting and auto-mounting arbitrary host paths into the container (security + scope).
- Changing how the original 01.openmv C00–C07 completion task proceeds (that task is paused,
  separate).

## Constraints

- Honesty model is non-negotiable: the fix must make false-clean impossible, not paper over it.
- No new fallback mechanisms without explicit approval (global red line #11).
- Deterministic + read-only contract of the readiness family must be preserved.
- Backward compatibility: existing callers that pass a *visible* folder must see byte-identical
  output (only the not-visible path changes behavior).

## What Changes

- `ingest_project_folder` returns a result whose "root missing" state is structurally explicit.
- Readiness outputs gain a `warnings` (and/or `root_visible: bool`) field.
- Readiness family error contract unified to fail-loud on invisible root.
- MCP self-description + skill + enablement updated for the container boundary.

## Capabilities

### New Capabilities
- Distinguishable "path not visible to the container" signal across the entire readiness family.

### Modified Capabilities
- `ingest_project_folder`: non-existent root → explicit, not silent-empty.
- `assess_package_readiness` / per-stage readiness: emit warnings + a not-visible status.

## Impact

- Code: `packages/reverse-core/bodesign_reverse_core/project_ingest.py`,
  `packages/workflow-core/bodesign_workflow_core/package_readiness.py`,
  `c01_id_package.py`, `c02_me_package.py`, `c04_layout_constraints.py`, `c05_fw_spec.py`,
  `c06_test_plan.py` (per-stage readiness).
- Docs: MCP server instructions, bodesign skill (`SKILL.md` + a boundary reference),
  `prompts/enablement.json`.
- Consumers: any agent/orchestrator that reads readiness output; behavior improves (no false
  clean), no schema break for visible-folder callers.
