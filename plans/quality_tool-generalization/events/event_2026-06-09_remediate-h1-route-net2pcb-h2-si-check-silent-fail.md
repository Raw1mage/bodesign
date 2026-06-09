---
date: 2026-06-09
summary: "remediate H1 route_net2pcb + H2 si_check silent-failure overfits"
---

# remediate H1 route_net2pcb + H2 si_check silent-failure overfits

## Scope

Implemented the two severity-first silent-failure remediations (DD-2) from the generality inventory.

## H1 — route_net2pcb connector mapping (was silently refdes-gated)

- Removed the `ref == "J1"` gate on USB-C pin expansion. Added an optional `connectors = {refdes: {net: [pads]}}` caller map; when omitted, the built-in USB-C table now applies to ANY USB-C footprint (detected by FPID) on ANY refdes.
- Result now reports `applied_pinmaps` + `unmapped_connectors`, so a USB-C/declared connector that matched no net name is surfaced instead of being a silent no-op.
- Extracted the decision to a pure, pcbnew-free `resolve_connector_pads(ref, net, pin, connectors, usb_refs) -> (pads, expanded)` so the fix is unit-testable on a bare host.
- MCP schema/handler (`bodesign_route_net2pcb`) gained the `connectors` input + report fields in the description.

## H2 — si_check SI assumptions (were hardcoded / no-hidden-defaults violation)

- Promoted `rdrv` (17.0), `cload` (3e-12), `edge_ns` (0.3), `overshoot_pass_pct` (10.0), `overshoot_warn_pct` (20.0) to optional inputs — defaults documented as STM32-class CMOS reference, not hidden.
- Result echoes `effective` {z0, rs, vdd, ps_per_mm, rdrv, cload, edge_ns, thresholds} so the verdict is interpretable on any device.
- Extracted the pure `si_status(over, under, pass_pct, warn_pct)` classifier.
- MCP schema/handler (`bodesign_si_check`) gained the five new inputs.

## Backward compatibility (DD-3)

OpenMV board output unchanged: J1 USB-C still expands identically (usb_refs includes J1); omitted SI inputs fall back to the same numeric defaults — only now they are reported.

## Validation

- `tests/test_eda_bridge.py`: H1 helper tests (non-J1 expansion, J1 backward-compat, explicit-map-wins, no-match-keeps-single-pin) + H2 `si_status` tests (default + overridden thresholds change the verdict). 
- `tests/test_mcp_server.py`: schema tests assert `connectors` (H1) and rdrv/cload/edge_ns/thresholds (H2) are reachable inputs; group=ee preserved.
- Socket-level smoke re-run on the modified server (initialize→list_tools→call_tool) passes — no regression.
- 18 targeted tests OK; socket smoke OK in MCP-SDK venv.

## Remaining

- T1/T2 standalone generality-check artifact (checklist doc) + lint pass not yet built.
- T11 (H3–H5 visible overfits) deferred — lower priority.
- Full board-level H1 mutation regression env-gated on a pcbnew EE worker (same posture as feature_eda-mcp-toolchain T10).
- specs/architecture.md updated with the EDA-bridge generality contract.
