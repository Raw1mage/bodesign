# Errors: quality_readiness-enforces-guide-definition-of-done

The point of this change is to make a previously-silent failure (fake green) loud.
The "errors" are structured non-raising signals on the readiness payload.

## Error Catalogue

## E-DOD-001 MISSING_REQUIRED_DELIVERABLE (signal, non-raising)
- **Trigger**: a GUIDE Required-deliverable has no matching file and no honest
  `dod_status.json` entry.
- **Surface**: `guide_compliance.deliverables[i] = {status: missing, blocking: true,
  guide_row}` and the id in `missing_blocking`; `dod_ok: false`.
- **Caller action**: produce the file, or record an honest status in
  `<base>/dod_status.json` ({status, reason, owner}). Never relax the gate.

## E-DOD-002 FAKE_COMPLETE_FIELD (signal, non-raising)
- **Trigger**: an answer_state field has `state: answered` but its value is a
  placeholder (`TBC`/`TBD`/`待補`/empty/…).
- **Surface**: the field becomes blocking; its key is in `fake_complete_fields`; a
  warning names it; `dod_ok: false`.
- **Caller action**: fill the real value, or set the field's state to `drafted`/
  `accepted-risk` honestly. `accepted-risk` is exempt (it documents the gap).

## E-DOD-003 CONDITIONAL_REQUIRED_VIOLATION (signal, non-raising)
- **Trigger**: a deliverable required-on-condition is dodged by a flag — currently
  RF: a radio part detected in the PRD while `include_rf=false`.
- **Surface**: a warning ("RF appendix required: radio part detected … include_rf=false")
  and `dod_ok: false`.
- **Caller action**: set `include_rf=true` and produce the RF appendix, or correct the
  PRD if there is genuinely no radio.

## Non-error: HONEST_DEFERRAL (n-a / honest-status)
- A conditional deliverable whose condition is not met is `n-a` (non-blocking). A
  missing deliverable with a valid `dod_status.json` entry is `honest-status`
  (non-blocking, surfaced). Neither flips `dod_ok` — honest deferral is allowed; only
  silent absence is not.

## Non-fallback invariants
- A high `readiness_pct` never overrides `dod_ok` — `dod_ok: false` with
  `readiness_pct: 100` is the exact false-green the BR cites, now caught.
- The placeholder detector is conservative by contract; a legitimate value
  (`STM32 … Neural-ART`, `待機電流`) must never be flagged (asserted by negative tests).
