# Handoff: quality_tool-generalization

## Execution Contract

- This is generality *hardening*, not feature work. Touch only the eda-bridge silent-failure overfits (H1 `route_net2pcb`, H2 `si_check`) plus the generality-check artifact. Do not modify workflow-core (C00–C07) — it is already general and is the reference bar.
- Preserve the project's hard rules verbatim: `pcbnew` tools stay EE-worker-routed (`_EE_GROUP_TOOLS`); no fabricated success; mutating board tools write a new output path and return it; results are structured JSON, not stdout.
- Backward compatibility is mandatory (DD-3): existing constants become documented defaults that are *echoed* in results, never removed. When a caller omits the new inputs, output must be numerically identical to today for the OpenMV board.
- Severity-first order (DD-2): H1 and H2 before any H3–H5 expose/document work.

## Required Reads

- `plans/quality_tool-generalization/proposal.md` — the hotspot table H1–H5 with line-verified locations.
- `plans/quality_tool-generalization/design.md` — remediation architecture + DD-1..3.
- `plans/quality_tool-generalization/spec.md` — requirements + acceptance scenarios.
- `packages/eda-bridge/bodesign_eda_bridge/routing.py` — `_USBC`/J1 gate (lines 37-38,113), `si_check` (lines 28,466-505).
- `services/mcp/server.py` — EE tool schemas/handlers (`_h_route_net2pcb`, `_h_si_check`) and `_EE_GROUP_TOOLS`.
- `plans/feature_eda-mcp-toolchain/` — the sibling plan these tools came from; reuse its socket-level smoke test pattern for T10.

## Stop Gates In Force

- STOP if a fix would require inventing a board/process default for a genuinely unknown value — fail fast instead.
- STOP if H1 board-mutation regression needs `pcbnew`/EE worker and neither is available — record an env blocker (like feature_eda-mcp-toolchain T10), do not fake a board.
- STOP and split a new plan if scope grows into a shared "process profile" object spanning all EE tools.

## Execution-Ready Checklist

- [ ] Read proposal.md hotspot table and design.md decisions.
- [ ] Confirmed the OpenMV-board default values for `_USBC`, `rdrv`, `cload`, `edge`, thresholds before changing anything (so defaults stay identical).
- [ ] EE worker / `pcbnew` availability checked for H1 board tests; env-blocker path understood if absent.
- [ ] ngspice available for H2 SI tests.
- [ ] Socket-level smoke test pattern from feature_eda-mcp-toolchain located for the T10 no-regression check.
