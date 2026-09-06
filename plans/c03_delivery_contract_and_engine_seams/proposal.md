# Proposal: c03_delivery_contract_and_engine_seams

## Why

- C03 accumulated 39 BRs between 2026-06-18 and 2026-09-05 and the symptom never
  moved: the first BR's title
  (`issues/closed/issue_20260618_compose_schematic_draftsman_quality.md`) and the
  latest one (`issues/BR_20260905_draftsman_connection_strategy_degenerates_to_label_farm_on_non_label_friendly_topology.md`)
  describe the same failure. 38 of the 39 landed in the drawing/verification
  layer; 1 touched design completeness, and its fix landed on a pipeline the
  delivery path does not execute.
- Root cause G (`docs/research/rca_20260906_c03_schematic_total_root_cause.md`
  §10.6): `skills/bodesign/stages/c03-ee/GUIDE.md` defines the C03 deliverable as
  a consolidated `.docx`. Of the four `MANDATORY` markers in that file, two
  (`:399` document consolidation, `:437` file naming) govern document appearance;
  the netlist row (`:392`) carries no `MANDATORY`, no bold, and no version-control
  requirement, and `:447-450` explicitly places `02_build/` **out of scope**. A
  consumer that shipped a docx and left `.kicad_sch`/`.net` untracked followed the
  GUIDE exactly.
- Root cause D/§5: two schematic pipelines exist and share no code. PC-001 — the
  only machine backstop for the pinout-to-circuit obligation table — lives in
  `skills/bodesign/engines/kicad/scripts/validation_detectors.py` (measured: 3
  files in `skills/`, **zero** files in `packages/` + `services/`). From
  `bodesign_compose_schematic` it can never run.
- Root cause B: `packages/eda-bridge/bodesign_eda_bridge/design_suggest.py` (756
  lines, KB-anchored, `review_required=True`) is registered in **no** MCP verb
  (measured: `design_suggest` count 0 in `services/mcp/server.py`).
- Root cause C/§10.3: the fidelity gate is reachable only through
  `compose_schematic`, has no concept of NC (`nc_`/`no_connect` zero hits in
  `fidelity.py`; control: 8 hits in `kicad_emit.py`), and a parsed-zero read can
  return `ok=True`.
- Root cause F/§10.4: `bodesign_check_c03` is registered (measured: 1 hit) yet a
  consumer reading the published skill cannot run it, because the projection ships
  no executable body.

## Original Requirement Wording (Baseline)

- "六項全做，順序 1→4半步→F→Q5→2→3；MCP 管線（composer→kicad_emit→fidelity）為 C03
  交付路徑，skill 管線降內部工具；走 plan-builder，起草後由 dispatcher 驗、凍結、才派實作。"
  (user ruling, 2026-09-06, relayed in the dispatch order for this package)
- Upstream problem statement, same ruling: C03 as commissioned is "design the
  RC/RLC/LC/RL passive network from the datasheet, then draw it in an engineering
  standard format" — two segments, of which bodesign implements only the second.

## Requirement Revision History

- 2026-09-06: initial draft created via plan-init.ts
- 2026-09-06: scope fixed at six work packages in the user-ruled order
  1 → 4-half-step → F → Q5 → 2 → 3, mapped to WP1..WP6 below.

## Effective Requirement Description

1. Rewrite the C03 delivery contract so the deliverable is a **frozen,
   version-controlled, independently electrically verified netlist**; the docx is
   a projection of it (WP1).
2. Record and land the pipeline adjudication: the MCP pipeline (`composer.py` →
   `kicad_emit.py` → `fidelity.py`) is the C03 delivery path; the skill pipeline
   (`symbol_4edge.py`, `host_from_pinmap.py`, `netlist_to_kicad_sch.py`,
   `render_hybrid_sch.sh`) is demoted to an internal tool. Produce the migration
   list that follows from it (WP2).
3. Make the projected skill able to execute the verbs it advertises (WP3).
4. Expose the fidelity comparison as a standalone verb
   `bodesign_verify_netlist_fidelity` that consumes `.net` files, reports
   `nc_wired` separately, and never reports `ok` from an empty read (WP4).
5. Expose `design_suggest` as `bodesign_design_suggest` and widen its rule
   coverage toward the nine pin classes (WP5).
6. Only then project the drawing rules into a **form-axis** readability gate that
   is explicitly barred from authorizing electrical claims (WP6).

## Scope

### IN
- `skills/bodesign/stages/c03-ee/GUIDE.md` — deliverable table, MANDATORY
  placement, netlist freeze rules, docx demotion.
- `specs/architecture.md` — DD-01 pipeline adjudication + migration list.
- `services/mcp/server.py` — two new handler+schema pairs (WP4, WP5), plus the
  `spec` schema inner-field description (RCA §3-F).
- `packages/eda-bridge/bodesign_eda_bridge/fidelity.py` — `.net` adapter layer.
- `packages/eda-bridge/bodesign_eda_bridge/design_suggest.py` — rule coverage.
- `skills/bodesign/scripts/gate.py` — packages resolution under XDG install.
- A readability gate reading `route_stats`, thresholds anchored to
  BR_20260905 §8.5 real-board measurements.

### OUT
- Any change to routing/anti-fusion geometry (`kicad_emit.py` `_bus_route`,
  `_guard_route`). BR_20260905 §8.5.2 measured that a geometry-only improvement
  raised `moved` from 10 to 67 — an open circuit — while every geometric criterion
  improved. That work needs its own package.
- Making the real board's fidelity gate turn green. BR_20260905 §8.5.4: HEAD
  already fails on the real board with `moved=10`, and that signature belongs to
  two other BRs (`multi_unit_symbol_support`, `BR_20260723e`).
- Migrating the skill pipeline's own scripts, deleting them, or changing their
  behaviour. Demotion is a contract statement, not a deletion.
- The C03a/C03b stage split (RCA §7 option 1's stronger form). WP1 rewrites the
  deliverable definition inside the existing stage boundary.

## Non-Goals

- Implementing subsystem→pin-level netlist synthesis. KB
  `concept.bodesign.netlist-synthesis-gap` records that omission as deliberate;
  WP5 delivers *suggestions with evidence*, never committed nets.
- Raising `design_suggest` above `suggested` status, or letting any verb set
  `review_required=false`.
- Connecting the vault to C03 (RCA §10.1). Named as a follow-on, not scoped here.
- Consuming ERC report files (RCA §10.7). Named as a follow-on.
- **Completing PC-001's coverage, and porting the DD-3 waiver sidecar.** Carved out
  2026-09-06 into `plans/c03_pc001_coverage_and_waiver_sidecar/` (tasks 2.7 / 2.8,
  moved verbatim and still `- [ ]`). **This package reaching `verified` does not lift
  their seal:** PC-001's measured coverage on the aiguard board is **9/16, NOT 16/16**
  (`experiments/aiguard_c03_verify/ccm.net`, `rails_checked=12`; `U9`, `U10`, `U11`,
  `U12`, `U_EE`, `U_IMU`, `U_S` reported in `ics_without_identifiable_rail`), and no
  statement to the contrary may be made. The waiver sidecar is likewise **not ported** —
  the delivery path reports `passive_completeness.waivers.status == "not_run"`, so a
  legitimately-waived gap still blocks C04 entry.

## Constraints

- AGENTS.md 天條 1 (no silent fallback) and 天條 2 (no fabrication) bind every new
  verb: a missing input is a typed error plus a missing-item list, never a default.
- AGENTS.md §6.3: any mutate→test→restore verification loop must clear
  `__pycache__` first; `python3 -B` does not treat an existing stale `.pyc`.
- AGENTS.md §6.1: this is a shared worktree. No `git reset --hard`,
  `git clean -fd`, or pathspec-less `git stash` during implementation.
- `code-thinker` §12: every module in this package declares its outcome codomain
  (`ok` / `failed` / `not-run` / `empty` / `indeterminate`) before implementation.
- Two upstream deployment paths never trigger each other (AGENTS.md §3.1/§3.2):
  `mcpctl.sh rebuild` for `services/`+`packages/`, `opencode skill resync` for
  `skills/`. WP1/WP3/WP6 touch both sides and must state which path applies.

## What Changes

- The C03 definition of done stops being "one merged Word document" and becomes
  "a frozen netlist that passed independent electrical verification, plus its
  document projection".
- `bodesign_verify_netlist_fidelity` and `bodesign_design_suggest` become callable
  from any MCP client; the two capabilities that already existed as pure functions
  stop being reachable only from their own unit tests.
- `gate.py` under an XDG install either finds `packages/` or reports
  `packages_resolved=false` and returns `not-run` per verb — never `ok`.
- A readability gate exists, reports on the `form` axis only, and carries
  `does_not_authorize:["electrical_correctness"]` in every report.

## Capabilities

### New Capabilities
- `bodesign_verify_netlist_fidelity`: standalone partition-fidelity comparison over
  `.net` files with independent `fused` / `split` / `node_diff` / `nc_wired`
  outputs and a `nets_parsed` count that makes an empty read `indeterminate`.
- `bodesign_design_suggest`: evidence-backed passive-network suggestion over a pin
  class, returning `suggested` / `no-rule` / `indeterminate`.
- Readability gate (`gate_axis="form"`): projects `route_stats` into thresholds and
  reports without authorizing any electrical claim.

### Modified Capabilities
- C03 delivery contract (`GUIDE.md`): netlist promoted to MANDATORY and to version
  control; docx demoted from the sole bolded deliverable to a projection.
- `gate.py --list` / verb dispatch: packages resolution under XDG install becomes a
  resolvable state instead of a hard `LANDING_PACKAGES_NOT_FOUND` per call.
- `compose_schematic` MCP schema: `spec` gains inner-field descriptions so
  `all_label` and `l6_avoidance` stop being invisible to schema readers.

## Impact

- Consumers of the C03 stage guide: their definition of done changes; a delivery
  that shipped only a docx becomes incomplete. `02_build/` gains a tracked subset.
- `thesmart_products` (btdongle, aiguard): the acceptance corpus for WP4/WP6
  thresholds is the real btdongle spec; synthetic corpora produce false verdicts
  (BR_20260905 §8.5.5).
- MCP tool count rises by two; `services/mcp/server.py` gains two handler+schema
  pairs, and any client caching the tool list must refresh.
- `specs/architecture.md` gains the pipeline adjudication — the first place the
  two-pipeline split is written down as a decision rather than an observation.
