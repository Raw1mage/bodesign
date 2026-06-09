# Errors: quality_tool-generalization

## Error Catalogue

| Code | Condition | Tool behaviour | Caller action |
|---|---|---|---|
| `E-GEN-MISSING-INPUT` | A genuinely required input is absent (e.g. board path, nets). | `{ok: false, error: "<Type>: <msg>"}` — fail-fast, no fabricated default. | Supply the input. Never expect the tool to guess. |
| `W-GEN-UNMAPPED-CONNECTOR` | H1: a connector refdes matched no built-in or supplied pinmap. | Tool succeeds but lists the refdes in `unmapped_connectors` (warning, not failure). | Pass an explicit `connectors` pinmap for that refdes, or confirm the connector needs no special mapping. |
| `W-GEN-DEFAULT-ASSUMPTION` | H2: caller omitted SI driver/load/edge/thresholds. | Tool uses documented STM32-class defaults and reports them in `result.effective`. | If the device is not STM32-class CMOS, pass `rdrv`/`cload`/`edge_ns`/thresholds. |
| `E-GEN-EE-WORKER-DOWN` | A `pcbnew` board-mutation tool cannot reach the EE worker. | `{ok: false, status: worker_unavailable}` — never falls back to core, never fakes a routed board. | Bring up the EE worker; do not retry against core. |
| `E-GEN-FABRICATION-BLOCKED` | A fix path would require inventing a board/process value to proceed. | STOP: record an env/scope blocker, do not synthesize the value. | Provide the real value or accept the explicit limitation. |
| `W-GEN-LINT-FLAG` | Generality lint found a board/process constant in shipped tool logic not exposed as input (and not on the physics allow-list). | Warn-only initially; hard gate after H1/H2 land. | Expose the constant as a caller input or echo it in the result. |
