# Errors: mcp_r17-r06-conformance

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `PREFLIGHT_UNRESOLVED` | a declared asset path does not exist / safe_join raises inside the token dir | `{ok:false, error, remedy:{note}}` in result; remedy line in content text | stage the missing asset (bodesign_stage_dir) then retry |
| `PREFLIGHT_OUT_OF_NAMESPACE` | asset path escapes the token namespace (`../`) | typed error + remedy | pass a rel path inside the token; do not reference outside |
| `PREFLIGHT_HOST_ONLY_ABSOLUTE` | absolute host path passed in a token (portable) call | advisory (token case) / error (strict) + remedy | upload via token, not a raw host path |
| `PREFLIGHT_MISSING_MEDIA` | a referenced media/image file is absent from the workspace | typed error + remedy | stage the media then retry |
| `ASSERTION_EMPTY` | produced artifact is transport-valid but empty when non_empty/expected_* requested | `{ok:false, error, delivery_ready:false}` | fix input so the tool produces real content; empty ≠ delivery-ready |
| `ASSERTION_MISSING_FILE` | expected_files not all produced | typed error | check inputs; the expected deliverable was not emitted |
| `ASSERTION_MISSING_TEXT` | required_text not found in produced artifact | typed error | verify the content actually contains the required marker |
| `WALL_NUDGE_HARD` (enrichment, not a standalone code) | bad-shape id / grain-mismatch zero-element edit | existing failure `content` gains the single-source nudge + `skill(bodesign)` | load skill(bodesign); use the named correct primitive |
| `RESOURCE_NOT_FOUND` | resources/read URI names a token/rel that does not resolve | MCP read_resource error | inspect the token first (bodesign_workspace_inspect) |

Notes:
- Every remedy travels on MCP's portable `content` text surface (R0.5); a structured
  mirror additionally rides in the result dict. When there is no wall to nudge, the
  error is byte-identical to before (天條 11 — no fabricated affordance).
- Preflight `host_only_absolute` is advisory (not hard-block) in the same-host
  token-less case to avoid breaking legitimate local UDS calls (design R1).
