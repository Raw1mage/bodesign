# Errors: quality_readiness-fail-loud-on-invisible-path

The whole point of this change is to make one previously-silent failure mode loud. The "errors"
here are mostly structured non-raising signals (the readiness family stays `ok: true` at the MCP
layer and carries the meaning in the payload — DD-4), plus the one genuine raise that is preserved.

## Error Catalogue

## E-RDY-001 ROOT_NOT_VISIBLE (signal, non-raising)
- **Trigger**: `root_guard(folder)` finds `Path(folder).exists() == False` — the path is outside the
  container mount namespace (unmounted FUSE mount, or a typo), or genuinely absent.
- **Surface**: readiness result with `root_visible: false`, `warnings: ["Folder not found / not
  visible to the bodesign container: <root>"]`, `next_step`/`next_question` = boundary instruction,
  `readiness_pct: 0`, and `status: "path-not-visible"` where a status field exists.
- **Caller action**: pass a path under a container mount, or upload via the file model
  (tar → token → doc_dir) and call with the token. Never interpret as "deliverables missing".
- **Non-fallback**: the tool does not auto-mount, retry, or guess an alternate path.

## E-RDY-002 INGEST_ROOT_ABSENT (signal, non-raising)
- **Trigger**: `ingest_project_folder` on a non-existent root.
- **Surface**: `ProjectFolderIndex.root_exists = false` + a warning; `files == []`. Distinct from a
  scanned-but-empty directory (`root_exists == true`, `warnings == []`).
- **Caller action**: check `root_exists` before treating an empty `files` list as "empty folder".

## E-C00-ARTIFACT-MISSING C00TemplateError (raise, preserved)
- **Trigger**: a **visible** folder whose `C00-PRD/answer_state.json` is absent (or has an
  unsupported schema). This is artifact-missing inside a visible folder — distinct from root-invisible.
- **Surface**: `assess_c00_prd_readiness` raises `C00TemplateError("C00 artifact not found: …")`;
  the MCP handler returns `ok: false` (a data error). Unchanged by this work; covered by
  `test_run_tool_c00_readiness_missing_state_is_data_error`.
- **Caller action**: scaffold the C00 PRD (`bodesign_c00_scaffold_prd`) before assessing.

## Non-fallback invariants

- An invisibility-caused `readiness_pct: 0` ALWAYS carries `root_visible: false` + a warning. There
  is no input that produces a bare 0% / all-missing while suppressing the signal (INV-1).
- Root-invisibility (E-RDY-001) and artifact-missing-in-visible-folder (E-C00-ARTIFACT-MISSING) are
  two distinct loud signals; neither masks the other (INV-6).
