# P2 Slice A (3.1–3.3) — Line Paused 2026-10-06

**Ruling**: user paused the line after the third consecutive independent NO on the same
electrical-illusion defects. Status: documented, not resolved. No commit of slice-A work.

## 1. What was attempted

Goal: five human-readable btdongle leaf pages (usbc, power_rail, battery, charge_enable,
mcu_swd) + root via `bodesign_emit_multisheet`, natively rendered by kicad-cli 9.0.9,
each passing one independent fresh-eyes reviewer (AC-14).

Handler: `ses_f8309c2e0ffehJGYyZvnQO7y5b` (agy-relay gemini-3.8-flash-high). Reviewers:
`task(general)`, one per leaf, new session each round, final sha256 verified by officer.

| Round | Leaves reviewed | Verdicts | Hashes (png) |
|---|---|---|---|
| CP1 (04:26) | usbc / power_rail / battery | NO / NO / NO | 6d953e14 / e4df67c1 / 152ed3da |
| CP2 (06:0x) | usbc / power_rail / battery | NO / NO / NO | 61fc8e60 / 6211f238 / af182be3 |
| CP3 (06:43) | usbc / power_rail / battery | NO / NO / NO | d9ac9bbd / 3aa46a31 / 05c982f5 |

charge_enable / mcu_swd: never independently reviewed (gated on first-leaf pass).

## 2. The contradiction that stopped the line

Worker's deterministic evidence (CP2 diagnosis, accepted):
- `kicad-cli sch export netlist` on each standalone leaf vs spec nets: **0 fused / 0 missing
  / 0 misrouted** on usbc, power_rail, battery. Electrical content is correct.
- All grey lines are `(wire`, not `(polyline`.
- CP3 added `test_leaf_geometric_readability_assertions`: wire-vs-body_box intersections = 0,
  cross-net collinear overlaps = 0 on all six leaves (worker-measured).

Six different reviewers across three rounds see the same things the assertion says are absent:
- **usbc**: VBUS_CON rail makes a junction at F1's *top* pin and continues to C1/D1; F1 bottom
  gets its own VBUS flag → F1 reads as bypassed. R1/R2 attached only by bare "CC1"/"CC2"
  text, no wire to J1. D1 diodes 2/3/4 with open cathodes.
- **power_rail**: L1 never wired by a drawn line to U1 SW or to C4/SYS (label-only, all three
  rounds). ISET2 vertical runs along all U1 left pin tips; VBUS/USB_DET cross it with no
  junction dot. R4/R6/SYS/U1.12 collinear on one horizontal.
- **battery**: CP3 is the closest to passing — BATT/GND/NTC separate, R5 NTC→GND, replica
  correctly reduced to a `→ U1.7 NTC — home: power_rail` label. Remaining: BAT_EXT wire
  through J2 body + glyph, Q1 pins 1/2 label-on-pin-end with no wire, BAT_EXT local text vs
  everything else global, 26% page use.

Diagnosis (officer): the assertion measures *segment vs symbol body box*; the reviewers
object to (a) **junction placement** (a dot on a pin tip that is electrically a T but reads
as a bypass), (b) **crossings without junctions** that read as shorts, (c) **label-only
attachment** where a drawn wire is expected, (d) **collinear runs of different nets**
that the collinearity check apparently does not catch at the pin-tip row. None of these
is "wire through body". The worker's consistency check is real but measures the wrong
population; three rounds of fixes targeted what it measures.

## 3. Landed in working tree (uncommitted, preserved)

- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` (+246/−47 vs 16ed192): `_page_pitch_floor`
  native pitch, pin-tip obstacle in text placement, outward escape vectors, `_guard_route`
  body/pin-tip rejection + outer corridor, `_corridor_clash` collinear exclusion.
- `packages/eda-bridge/bodesign_eda_bridge/hierarchical.py` (untracked, 1770 lines): root+N emit,
  replica → label when ≤2 pins, `_continuation_blocks` label-stack penalty, title_block, A4 floor.
- `partition.py` (793), `replica_fidelity.py` (458): untracked, unchanged this slice.
- `services/mcp/server.py` (+63): `_h_emit_multisheet` + schema incl. `subsystem_views` /
  `view_local_max_nodes` glue (officer-authorized).
- `tests/test_p2_leaf_delivery.py` (259): emit/render + geometric assertion. Worker-reported
  `test_p2_leaf_delivery test_mcp_emit_multisheet test_multisheet_emit` = Ran 49 OK.
- Receipt `p2-delivery-receipt.md` (120 lines) — contains the worker's self-assessment
  ("clearly routed", "clearly organized"); **not** officer-accepted, superseded by this note.
- Renders: `/home/pkcs12/.cache/scratch/p2-leaf-delivery/first/` (CP3 bytes); reviewer notes in
  `/home/pkcs12/.cache/scratch/task-ses_ef122*/`.
- Anchor: `refs/wip/officer-handover-20261006` (ea304d5) covers the pre-slice state of the three
  modules + 7 tests; slice-A edits to kicad_emit.py / hierarchical.py are NOT anchored.

## 4. What is settled and should not be redone

- Electrical correctness of the multi-sheet emitter on the real board (netlist diff = 0 on all
  three leaves; root arbitration 45/45 components, 27/27 nets, 31/31 NC).
- Replica-as-label ruling (≤2 pins) works and reviewers accept it (battery CP3).
- The problem is routing/presentation geometry, not partitioning, not identity, not netlist.
- P1 contracts (commits 7b0d8b5 / 6363c54 / d190480) are accepted and independent of this.

## 5. Open questions for the resume ruling

1. Who diagnoses the assertion-vs-render gap: architecture review (Astra, read router +
   reviewer notes + one leaf `.kicad_sch`), a fresh agy-relay worker, or the same handler?
2. Should the readability acceptance be re-specified as a measurable population the engine can
   target (junction-on-pin-tip = 0, crossing-without-junction = 0, pin-attached-by-label-only
   = 0 for local nets, page-use ≥ 50%) rather than "fresh-eyes YES"? The fresh-eyes gate stays
   as the final check, but the engine needs a target it can measure.
3. Whether to milestone-commit the three multi-sheet modules + tests now (pending since the
   previous shift) independent of slice-A outcome.

## 6. Officer process notes

- Two `[BRNS-DONE]` from the handler were not surfaced to the officer (CP1 at 04:26, CP2 at 06:43);
  both found by `read_subsession` tail. Officer now polls after each dispatch.
- Handler was rebound to codex after the 03:14 restart; corrected to agy-relay per user ruling.
