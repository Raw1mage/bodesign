# Observability: mcp_r17-r06-conformance

## Events

- `bodesign_init_hit` (existing, `server.py:1408`) — unchanged; capabilities added additively.
- `preflight_reject` (new) — emitted when typed asset preflight rejects a call:
  `preflight_reject tool=<name> reason=<unresolved|out_of_namespace|host_only_absolute|missing_media> path=<rel>`.
- `assertion_not_delivery_ready` (new) — emitted when content-assertion refuses an
  empty/short artifact: `assertion_not_delivery_ready tool=<name> code=<ASSERTION_*>`.
- `wall_nudge_attached` (new) — emitted when R0.6 attaches a nudge:
  `wall_nudge_attached tool=<name> force=<hard|advisory> why=<fingerprint>`.
- `resource_read` (new) — emitted when a bare client reads a portable resource:
  `resource_read token=<tok> rel=<rel> bytes=<n>`.

## Metrics

- preflight rejection rate per tool (counts by reason) — surfaces which mutation
  entries most often receive unresolved assets (indicates missing recon upstream).
- assertion-empty count — how often transport-valid-but-empty artifacts are refused
  (a non-zero rate proves the gate is load-bearing, not decorative).
- wall_nudge hard vs advisory ratio — a healthy ratio skews advisory (定海神針:
  false hard-blocks are worse than harmless advisories).
