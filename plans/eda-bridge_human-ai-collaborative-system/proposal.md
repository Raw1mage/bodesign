# Proposal: eda-bridge_human-ai-collaborative-system

## Why

In commercial circuit board development, black-box fully automated generative tools fail to gain engineer trust because they lack deterministic validation, visual readability, and fine-grained control. Simultaneously, the current `bodesign` schematic drawing pipeline suffers from severe architectural defects:
1. **Inability to draw real schematics ("畫不出來")**: Under `draftsman` mode with real multi-component circuits (e.g. `04.btdongle`), 74% of wires degenerate into 5.08mm pin-to-label stubs, zero junctions are formed, and passive components (R/C/L) hang with single unconnected pins attached to labels.
2. **Collinear fusion & Hard crashes**: For basic series dividers (`U1 -> R1 -> R2 -> GND`), vertical stacking in force-directed placement creates collinear wire overlaps that fuse `VOUT` into `GND`, triggering `FidelityError` exceptions that abort schematic composition entirely.
3. **Surrender anti-fusion guard**: When Manhattan orthogonal routes cannot clear obstacles after 3 small jogs, the engine's default policy is to abandon wire routing entirely and downgrade the entire net to per-pin label stubs.
4. **Lack of subcircuit motif primitives**: The placement engine treats every component (from a 64-pin MCU to an 0402 100nF capacitor) as an undifferentiated graph node in Fruchterman-Reingold force-directed placement. Passives are scattered radially, decoupling capacitors fly away from power pins, and voltage dividers fail to align.
5. **Global bus routing of power/ground nets**: Global power rails (especially `GND` with 50+ nodes) are daisy-chained across the entire sheet in 1200mm snake routes sorted by (x, y) ascending coordinates, causing massive route blockages and wire collisions.
6. **Lack of human-in-the-loop collaborative primitives**: Engineers cannot easily tweak intermediate AI-generated designs in KiCad GUI without having their changes overwritten upon the next AI iteration.

This plan establishes a comprehensive overhaul: transitioning `bodesign` into a **Mixed-Initiative Human-AI Collaborative PCB Co-Design System**, anchoring on **Subcircuit Motifs**, **In-situ Power/GND Glyphs**, **Bidirectional KiCad Sync with User-Pinning**, and **Deterministic Multi-Tier Verification**.

## Owning Specs & Predecessors

- **Direct Owning Spec**: `specs/eda_schematic-draftsman-quality/` (Graduated specification for draftsman quality and schematic emission).
- **Architecture SSOT**: `specs/architecture.md` (C00–C07 lifecycle, eda-bridge seams, DockerLab deployment).
- **Predecessor Plans**:
  - `plans/eda-bridge_draftsman-series-divider-wireable/` (Phase 1-2 delivered `declare_circuit`; Phase 3 stopped before wire-ledger integration).
  - `plans/eda-bridge_multi-sheet-subsystem-schematics/` (Delivered hierarchical leaf emission, confirmed multi-sheet alone does not eliminate wire crossings).
  - `docs/research/report_20261004_c03_lint_qa_structural_review.md` (Identified closure blockers, dead pipeline code, and dual-implementation in `composer.py:2208-2231`).

## Original Requirement Wording (Baseline)

- "現有足夠算力可對bodesign做一次code review，檢討一下為什麼沒辦法把電路畫靜"
- "靜是錯字，我要表達是畫不出來"
- "好。請找出owning spec開始改版計畫。把你抓到的缺點都改良"

## Effective Requirement Description

1. **Schematic Drawing Engine Remediation (C03)**:
   - Establish `Subcircuit Motif` primitives (Decoupling, Voltage Divider, Pull-Up/Down, RC/LC Filter) with template-first geometric placement.
   - Decoupling capacitors must attach directly outside their host IC power pins (2.54–5.08mm) with in-situ local GND glyphs, bypassing global trunk routing entirely.
   - Voltage dividers and pull resistors must align vertically along functional axes.
   - Eliminate blanket label downgrades in `anti-fusion guard`: channel detours and spatial spreading must precede label fallback.
   - Add component text boxes (Reference, Value, Pin Names, Labels) into `OccupancyLedger` as spatial obstacles to prevent wire-through-text collisions.
   - Promote 6 tightly-coupled closures in `kicad_emit.py` to top-level testable functions with explicit state parameters.
   - Collapse duplicate cross-IC route policy in `composer.py:2208-2231` onto `capacity_plan.decide_route_policy`.
2. **Physical Placement & Routing Remediation (C04)**:
   - Ingest 3D mechanical keepout, board outline, mounting holes, and connector edge constraints from C02.
   - Implement functional cluster placement (Power, Core MCU, RF, I/O) with pin-facing orientation before routing.
   - Wire with BGA escape planning, differential pair handling, and ground plane pouring.
3. **Human-AI Collaborative Co-Design Infrastructure**:
   - Establish bidirectional sync between KiCad GUI / file modifications and AI Design IR, preserving engineer edits as `User-Pinned` constraints.
   - Implement interactive decision gates (`ask_question`) for architectural trade-offs (e.g. buck vs LDO, package choices, BOM alternates).
   - Provide Visual QA companion reporting with before/after diff overlays and redline annotations.
4. **Deterministic Verification & Remote Component KB**:
   - Integrate remote Component KB (`ragbase.sqlite` on DockerLab CT105 `:8177`) for datasheet-grounded electrical parameters.
   - Chain SPICE simulation (ngspice), KiCad DRC/ERC gates, and graph-theoretic partition fidelity gates.

## Scope

### IN
- `packages/eda-bridge/`:
  - `composer.py`: Refactor placement, remove duplicate route policy, wire motif templates.
  - `kicad_emit.py`: Closure promotion, in-situ power/GND glyph emission, anti-fusion jog overhaul, text obstacle registration.
  - `declare.py`: Connect declared circuit motifs directly to schematic emission.
  - `motifs.py` (New): Subcircuit motif detection, templates, and geometry synthesizer.
  - `occupancy.py`: Support text bounding box obstacles.
- `services/mcp/server.py`:
  - Expose collaborative tools: `bodesign_kicad_sync`, `bodesign_motif_apply`, `bodesign_hil_review`.
- Test suite:
  - Benchmark against real `04.btdongle` spec: `junction > 20`, `stub share < 40%`, zero collinear fusion shorts, fidelity gate PASS.

### OUT
- Writing ad-hoc scrapers or raw OOXML/PDF generators outside approved MCP pipelines.
- Replacing KiCad with an unverified third-party proprietary router.
- Modifying client code inside consumer repositories (`thesmart_products`).

## Non-Goals
- Attempting 100% full-board single-sheet drawn wires without any net labels: Cross-IC and cross-sheet high-speed buses legitimately use net labels (`M6-8d` policy).
- Manual schematic drafting without automated placement: The system remains automated-first with human-in-the-loop steering.

## Constraints
- **Zero-Trigger Directives**: No `sudo`, fail fast with evidence, display reliability over claims.
- **Electrical Fidelity Invariant**: Never disable or soften `verify_partition_fidelity` to mask geometric errors.
- **Byte Equivalence Rail**: Legacy `style=netlist` behavior must remain available and regression-safe.
- **Decoupled Architecture**: Development in WSL repo (SSOT), runtime EDA/KiCad services on DockerLab CT105.

## What Changes
- `kicad_emit.py`: 6 nested closures promoted to top-level; in-situ power glyphs emitted at point of use.
- `composer.py`: Inline cross-IC counting replaced by `capacity_plan.decide_route_policy`.
- New `motifs.py` module in `packages/eda-bridge/` owning subcircuit motif definitions and spatial rules.
- `OccupancyLedger`: Text boxes for reference and value labels registered as obstacles.
- Automated tests verifying junction count, stub ratio, and fidelity on the real `btdongle` design.

## Capabilities

### New Capabilities
- `subcircuit_motifs`: Deterministic synthesis and placement of standard analog/passive functional blocks (decoupling, dividers, filters).
- `in_situ_power_symbols`: Point-of-use power and ground glyphs eliminating global serpentine ground nets.
- `bidirectional_user_pinning`: Preservation of human engineer manual adjustments during iterative AI schematic/layout updates.
- `text_aware_routing`: Routing engine actively avoids Reference/Value/Pin text boxes.

### Modified Capabilities
- `bodesign_compose_schematic`: Generates fully connected, human-readable schematics with real junctions and drawn passive networks, eliminating the label farm degradation.
- `bodesign_declare_circuit`: Directly drives schematic motif layout and in-situ wiring.

## Impact
- **End-user experience**: The delivered `.kicad_sch` files become genuine, professional schematics adhering to industry visual standards instead of netlist pin-out connection tables.
- **Engine robustness**: `FidelityError` crashes on simple series circuits are structurally eliminated.
- **Maintainability**: `kicad_emit.py` becomes modular and testable without massive closure captures.
