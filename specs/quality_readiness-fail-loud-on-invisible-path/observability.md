# Observability: quality_readiness-fail-loud-on-invisible-path

This change is read-only and deterministic; observability is carried entirely in the tool result
payload (no separate telemetry sink). The signal lives in fields a caller/agent can inspect directly.

## Events

- **root-not-visible** — emitted (as a payload, not a side-channel) whenever a readiness tool is
  called against an invisible root. Identified by `root_visible == false`. The human-readable cause
  is in `warnings[0]`.
- **ingest-root-absent** — `ProjectFolderIndex.root_exists == false`; the upstream form of the above.
- **c00-artifact-missing** — `C00TemplateError` raised → MCP `ok: false`; a visible-folder
  artifact-missing, distinct from root-invisibility.

## Metrics

- `root_visible` (bool, per readiness call) — the primary health bit. A spike in `false` across a
  session means an agent is repeatedly passing unmounted paths → it should switch to the file model.
- `warnings_count` (per readiness call) — 0 for a healthy visible folder; ≥1 only on the not-visible path.
- `readiness_pct` — must be read together with `root_visible`; a 0% with `root_visible: false` is a
  boundary problem, not a deliverable gap.

## Logs (structured, in result.warnings)

The only structured log surface is `result["warnings"]` (and `ProjectFolderIndex.to_dict()["warnings"]`).
The message format is stable: `"Folder not found / not visible to the bodesign container: <root>"`.
`render_readiness_markdown` additionally renders a `⚠ folder not visible` banner for human display.

## Invariants observed

- INV-1: no readiness result has `readiness_pct == 0` with `root_visible == true` AND an empty
  `warnings` while the true cause is invisibility. (Asserted by the test suite.)
- INV-4: a visible folder always shows `root_visible == true`, `warnings == []`.

## Alerts (manual gate, not automated)

- An agent/orchestrator seeing `root_visible: false` should STOP and re-route (mount or file model),
  not proceed to regenerate deliverables. This is a human/agent judgment gate, not an automated alert.
