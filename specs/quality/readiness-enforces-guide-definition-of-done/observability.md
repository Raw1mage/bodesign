# Observability: quality_readiness-enforces-guide-definition-of-done

Read-only and deterministic; observability lives in the readiness payload.

## Events

- **dod-not-met** — a readiness result with `dod_ok: false`. The cause is in
  `guide_compliance.missing_blocking`, `fake_complete_fields`, and `warnings`.
- **fake-complete** — a field appears in `fake_complete_fields` (answered but hollow).
- **rf-violation** — a warning naming a radio part with `include_rf=false`.
- **honest-deferral** — a deliverable reported `honest-status` (deferred via dod_status.json).

## Metrics

Carried in the readiness payload, per call:

- `dod_ok` (bool) — the primary done-bit. The real gate; read it instead of `readiness_pct`.
- `missing_blocking` (count) — required deliverables silently absent.
- `fake_complete_fields` (count, c00) — hollow `answered` fields.
- `dod_missing` (list of stages, package) — stages whose GUIDE DoD is not met.

## Logs (structured)

- `result.warnings` — fake-complete field list + RF-violation message (stable wording).
- `result.guide_compliance.deliverables[].evidence` — per-deliverable reason (matched
  path, honest status, or which files are missing) with the GUIDE row.

## Invariants observed

- No readiness result reports `dod_ok: true` while a required deliverable is missing
  without an honest status, or while an `answered` field is fake-complete.
- A fully-compliant stage reads `dod_ok: true`, `missing_blocking: []`, and is a strict
  superset of the pre-change output (existing keys unchanged).

## Alerts (manual gate, not automated)

- An agent seeing `dod_ok: false` must STOP and fix what `missing_blocking` /
  `fake_complete_fields` name (or record an honest status) before reporting the stage
  done — never announce done on a fake green. This is the human/agent judgment gate
  the whole change exists to enforce.
