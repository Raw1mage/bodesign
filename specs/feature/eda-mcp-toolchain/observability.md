# Observability: feature_eda-mcp-toolchain

## Events

- `tool_registered` — a C04 tool added to the MCP registry with its group (core/ee); payload: name, group.
- `impedance_solved` — `bodesign_impedance_solve` returned class geometry; payload: class count, whether differential targets present.
- `board_mutated` — widen/length-match wrote a new board path; payload: tool, nets touched, output path.
- `gerber_preview_rendered` — single-layer render produced OR `render-unavailable` returned; payload: mode, rendered_layers, skipped.
- `ee_worker_unavailable` — an EE board tool fell into fail-fast because no worker was configured; payload: tool, group.
- `socket_smoke_run` — the socket-level MCP roundtrip executed; payload: tools listed, impedance_ok, ee_failfast_ok, skipped-on-host flag.

## Metrics

- **new_c04_tools_registered** — target 4 (impedance_solve, widen_bus_tracks, length_match_bus, render_gerber_preview). Achieved.
- **unit_tests_passing** — target green; achieved 19 ok / 1 skipped.
- **socket_smoke_passing** — target pass in MCP-SDK env, graceful skip on bare host. Achieved.
- **head_import_integrity** — fresh-checkout `import bodesign_eda_bridge` / `render_gerber_preview` succeeds. Achieved after repair `6dd6d3a`.
- **env_gated_remaining** — real-board EE widen/length-match + KiCad/pcbnew execution still require an EE worker with pcbnew; tracked, not a verification gap for the protocol-callable claim.
