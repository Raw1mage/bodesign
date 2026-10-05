# Tasks: eda-bridge_human-ai-collaborative-system

## Phase 1: Engine Seams Unlocking & SSOT Convergence (Low Risk, Pure Refactor)

- [ ] 1.1 Promote 6 tightly-coupled nested closures in `kicad_emit.py` to top-level functions accepting explicit state arguments:
  - `_guard_route(net_name, waypoints, ledger, fusion_registry, ...)`
  - `_assert_no_cross_net_junction(junction_pt, net_name, junction_registry)`
  - `_route_clears_ledger(waypoints, endpoint_refs, net_name, ledger)`
  - `_route_clears_points(waypoints, avoid_points)`
  - `_record_run(x1, y1, x2, y2, net_name, ledger)`
  - `_place_local_label(net_name, mid_x, mid_y, waypoints, ledger)`
- [ ] 1.2 Write isolated unit tests for the 6 promoted functions in `tests/test_kicad_emit_seams.py`.
- [x] 1.3 Collapse duplicate cross-IC pairwise counting in `composer.py:2208-2231`:
  - Delete inline pairwise loop and `_is_ic` helper.
  - Call `capacity_plan.decide_route_policy` as the sole authority.
  - Verify zero divergence against existing route policy test vectors.
- [ ] 1.4 Baseline regression check: Run `./scripts/run_tests.sh` to ensure zero newly introduced test regressions.

## Phase 2: Subcircuit Motifs Engine & In-situ Power/GND Infrastructure

- [x] 2.1 Implement `packages/eda-bridge/bodesign_eda_bridge/motifs.py`:
  - Subcircuit motif detector: parses netlist and identifies `decoupling_shunt`, `voltage_divider`, `pull_resistor`, and `rc_filter` subgraphs.
  - Motif geometric templates: generates deterministic relative coordinates and pin orientations for each motif.
  - Supported geometry: left/right host pins with upright R/C symbols. Other host edges and reversed passive orientation fail explicitly; ambiguous multi-host rails are not assigned an invented owner.
- [x] 2.2 Implement In-situ Power and Ground Glyphs:
  - Shunt capacitors and divider bottom pins emit local `power:GND` symbols at point-of-use (2.54mm below pin).
  - Strip global `GND` from `_bus_chain_points` daisy-chain routing list.
- [x] 2.3 Wire `motifs.py` into `composer.py` pre-placement:
  - Identified motif passives are bound to their host IC pins before force-directed placement.
  - The force-directed solver treats host IC + attached motif passives as a single rigid macro-block.
- [x] 2.4 Unit test motif placement: Verify in `tests/test_motifs.py` that a basic 3-part divider (`U1 -> R1 -> R2 -> GND`) produces 1 junction, 2 drawn wires, 1 in-situ GND symbol, and 0 global labels.
  - Verification: `python3 -m unittest tests.test_motifs tests.test_composer tests.test_capacity_plan` — 34 tests, OK; real KiCad partition fidelity exercised for divider and decoupling fixtures. Full-board benchmark and visual QA not run.

## Phase 3: Anti-fusion Remediation & Typography-Aware Routing

- [ ] 3.1 Overhaul `anti-fusion guard` fallback behavior in `kicad_emit.py`:
  - Replace immediate label fallback after 3 small jogs with multi-channel detours (mid-channel Z-routes outside obstacle columns).
  - Record detailed fallback telemetry distinguishing between collinear overlap vs. ledger intrusion.
- [ ] 3.2 Typography-Aware Spatial Ledger in `occupancy.py` and `kicad_emit.py`:
  - Calculate bounding boxes for Reference (`R1`), Value (`10k`), Pin Names, and Net Labels.
  - Register text boxes into `OccupancyLedger` with 0.5mm clearance under layer `text_keepout`.
  - Enforce `_orthogonal_route` avoidance of `text_keepout`.
- [ ] 3.3 Verify text avoidance: Confirm zero wires intersecting component text strings in generated SVG/PDF views.

## Phase 4: Human-AI Collaborative Workflow & Bidirectional Sync

- [ ] 4.1 Implement `bodesign_kicad_sync` differential merge engine:
  - Detect human modifications in `.kicad_sch` and `.kicad_pcb` compared to git baseline.
  - [x] Detect schematic moves/rotations against an explicitly supplied baseline `.kicad_sch`.
  - [x] Extract human-adjusted schematic positions and tag them with `user_pinned: true`.
  - PCB sync and automatic git-baseline retrieval remain outside this implementation.
- [x] 4.2 Integrate `user_pinned` constraint into `composer.py`:
  - Pinned components are excluded from force-directed movement; remaining auto-placed parts flow around them.
  - Preserve exact pinned origins through sheet fitting and emitter snapping; nonzero pinned rotation fails explicitly.
  - Verified with `python3 -m unittest tests.test_kicad_sync` (8 tests) and `tests.test_composer` (5 tests).
- [ ] 4.3 Implement Interactive Decision Gate helpers via `ask_question`:
  - Emit structured trade-off options for major circuit decisions (LDO vs Buck, BOM alternates).
- [ ] 4.4 Implement Visual QA Companion report:
  - Generate diff render showing newly added wires (green), moved parts (yellow), and DRC warnings (red).

## Phase 5: End-to-End Benchmark & Verification on Real Board

- [ ] 5.1 Run full benchmark against real `04.btdongle` 45-component board (`sch_gen/design.py`):
  - Metric 1: Total drawn junctions > 20 (up from baseline 5).
  - Metric 2: Pin-to-label stubs <= 40% of total wires (down from baseline 74%).
  - Metric 3: Subcircuit drawn ratio >= 50% (up from baseline 3/11).
  - Metric 4: Electrical partition fidelity: PASS with `moved = 0` (zero collinear fusion shorts).
  - Metric 5: Native KiCad ERC: PASS with 0 fatal errors.
- [ ] 5.2 Architecture sync & KB distillation:
  - Update `specs/architecture.md` with the new Motif & In-situ Power subsystems.
  - Record closeout event and cross-repo lessons into `.specbase/events.sqlite`.
