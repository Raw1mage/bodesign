---
date: 2026-06-09
summary: "expose H3-H5 visible overfits + build generality check artifact and lint guard"
---

# expose H3-H5 visible overfits + build generality check artifact and lint guard

## Scope

Completed the rest of the plan after the H1/H2 silent-failure fixes: exposed the visible overfits (H3-H5) and built the repeatable generality check (T1) + automated regression guard (T2).

## H3 — emit_layout (small-board grid)

Exposed `place_start_mm` (15.0), `place_pitch_mm` (12.0), `margin_mm` (10.0) as inputs (alongside existing board_mm/columns); outline margin threaded through. MCP schema + handler updated. Defaults documented as a ~60x40mm prototype reference.

## H4 — emit_fab (PDF layer set)

Exposed `pdf_layers` input; default kept as the 2/4-layer set (F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts) but now overridable for 6+ layer stacks. MCP schema + handler updated.

## H5 — via_in_pad / pour_planes (process defaults)

`via_in_pad` drill/pad/keep_rings were already inputs — documented as JLCPCB-advanced POFV defaults. `pour_planes` stitch geometry was BAKED (14mm pitch, 0.3/0.6mm via, GND hardcoded) — promoted to `stitch_net`/`stitch_pitch_mm`/`stitch_drill_mm`/`stitch_pad_mm` inputs. MCP schemas + handler updated.

## T1 — generality check artifact

`docs/generality-check.md`: the bar (no silent overfit), scope (shipped tool layer only), 5-axis checklist (input-driven/hidden-defaults/toolchain-coupling/domain-breadth/silent-vs-reported), severity classes, current audit table, and the automated arm.

## T2 — automated regression guard

`tests/test_tool_generality.py`: encodes the contract as data — GENERALITY_CONTRACT (tool -> required override inputs) and REPORTED_CONTRACT (tool -> required report fields) asserted against live MCP schemas. Schema-level, no pcbnew/ngspice, runs on bare host. Fails if any de-overfit override is later dropped.

## Coverage re-check

ME group (c02_generate_openscad/export_stl/skp/step, render_board_model) re-audited this session: caller-driven (wall/clearance/lid passed in; render width/height cosmetic) — general, no action. workflow-core C00-C07 already de-productized.

## Validation

- tests/test_tool_generality.py (3 tests) + tests/test_eda_bridge.py + MCP schema tests: 19 OK on bare host.
- Socket-level smoke re-run on the modified server: OK, no regression.

## Result

All audited board/process assumptions are now caller-overridable OR reported; the bar is regression-guarded. specs/architecture.md updated. No remaining silent or hidden-default overfit; only full board-level mutation regression stays env-gated on a pcbnew EE worker.
