# KiCad interactive-layout operating manual — the "what stays human" layer of C04

The C04 GUIDE hands several classes of work to **interactive KiCad** — fab-grade
controlled-impedance routing, coupled differential pairs, keepout areas, copper-to-edge
clearance, board-outline shaping, net-class-driven routing — but only *names* them. This
reference is the operator layer behind those names: the concrete KiCad 7/8 PCB-editor
operations an agent (or a human it is guiding) uses to close what the MCP finishing chain
and the autorouter deliberately leave open (GUIDE step 4, "What the autorouter + this chain
do NOT finish").

Provenance: distilled from *"10 Essential KiCad PCB Layout Design Tips"* (PCBWay-sponsored
KiCad tutorial, youtube `YDjp2NEFB2U`). It is a **usage manual for the KiCad UI**, not a
bodesign gate — every claim about a bodesign gate/threshold still lives in `../GUIDE.md`.
These operations feed the same deliverables the gate scores; none of them relax it.

> Honesty boundary (`../../../references/honesty-model.md`): interactive edits are still
> `draft` until `bodesign_layout_drc_gate` + `c04_readiness` pass. Nothing here is a
> "board is done" signal — it is how you *produce* copper that the gate can then judge.

---

## 1. Set the origin before you measure anything (drawing/placement datum)

KiCad's default page origin (top-left, Y-down) makes every coordinate you read off the
status bar meaningless for a board datum. Fix it once per board, before authoring the
outline or placing datum-critical parts:

- **Relative datum (quick):** press **Space** to zero the `dx/dy` readout at the cursor —
  a throwaway relative origin for measuring one distance.
- **Absolute datum (persistent):** *Preferences → PCB Editor → Origins & Axes* → set the
  drill/place origin to **grid origin** and set **Y axis increases upward**. Then *Place →
  Grid Origin* at the board's chosen corner. Now `x/y` reads engineering coordinates
  (corner = 0,0; right = +x; up = +y).

Why C04 cares: placement constraints in `Placement_Constraints.md` (connector edge
openings, keepout XY, mounting-hole positions from C02) are only unambiguous against a
declared datum. **Record which corner is (0,0)** in `Layout_Constraints.json` so the datum
is not an unstated assumption — same discipline as the honesty model's "state provenance".

## 2. Board outline with filleted (rounded) corners — on Edge.Cuts

Fab-grade outlines are rarely sharp rectangles (enclosure fit, stress relief, C02 handoff):

1. On **Edge.Cuts**, draw the outline rectangle to the C02-frozen dimension (e.g. 80×80 mm).
2. Select the outline → **Shape Modification → Fillet Lines** → enter a radius (e.g. 4 mm).
   Re-run with a different radius to iterate; corners round in place.
3. Verify in **3D viewer** (Alt+3) — the rounded corners and any keep-out around
   corner-adjacent pads are visible there before you trust them.

**Cutouts / internal openings:** draw the cut shape *also on Edge.Cuts* (e.g. a rectangle)
— KiCad treats a closed Edge.Cuts loop inside the outline as a milled cutout, confirmable in
3D. Use for connector windows, antenna clearance slots, mechanical reliefs.

> C04 does **not** own the *final* outline/mounting holes (GUIDE "What C04 does not own" —
> shared with C02). If C02's outline is not frozen, the filleted outline is an `assumption`
> in `Layout_Constraints.json`, not a decision.

## 3. Rule areas (keepout) — the interactive form of a copper-pour exclusion

The GUIDE's placement constraints (`antenna_keepouts`, heat zones, relay/HV clearance) become
real copper only through a **rule area**:

- *Place → Add Rule Area (Keepout)*, draw the polygon, open **Rule Area Properties**.
- Select the **layers** it applies to (top / inner1 / inner2 / bottom) and the **keep-out
  classes**: *keep out copper fill (zones)*, tracks, vias, pads, footprints — independently.
- Re-pour (`B`) after editing/moving the area; the excluded region shows no copper.

Canonical uses in C04: no-pour ring around a relay / HV node, antenna keepout (from C03's
`Mechanical_Constraint_Export.json`), thermal-relief exclusion, connector-shell clearance.
A rule area is a **local, layer-scoped** exception — distinct from the board-wide
copper-to-edge clearance in §6.

## 4. Schematic ⇄ PCB cross-probe — manual counterpart of `net2pcb` mapping (diagnostic, NOT equivalent)

With both editors open, selecting a symbol/pin in one **highlights the same object** in the
other — down to individual pads. This is the human-inspection counterpart of C04's
`net2pcb` pad-mapping sidecar and the unmapped-pad gate (the floating-PSRAM lesson):

- Use it to **eyeball** that a footprint's pads map to the intended symbol pins *before*
  trusting the automated `unmapped == 0` count — a fast sanity check when a footprint was
  swapped or a pin-name mismatch is suspected.
- Cross-probe is a *diagnostic*, **not** the gate. The gate is still
  `bodesign_layout_drc_gate` parsing `unmapped pads > 0` as HARD FAIL. Cross-probe helps you
  *find* the mismatch; it does not certify its absence.

## 5. Net classes — where impedance/clearance/width rules actually attach

`Routing_Rules.md` net classes (§ GUIDE step 2) are enforced in KiCad here:
*File → Board Setup → Design Rules → Net Classes*.

- Define a class per constrained bus (e.g. `diff_pair_USB`) with its **clearance**, **track
  width**, **via** sizes, and **diff-pair gap** — the widths you computed via
  `impedance_solve`, not guesses.
- **Assign nets to the class** (by net or netclass pattern); routing then auto-applies the
  class rule, and DRC checks against it. Change a class value → re-route/re-pour → the new
  clearance/width propagates to every member net at once.

This is the interactive execution of the *same* net-class table the Tier-3 handoff exports
(`SI_Net_Classes.csv`) — one source of truth, two consumers (KiCad DRC here; Allegro/
Xpedition/Altium there).

## 6. Copper-to-edge clearance — the board-wide constraint the gate assumes

*File → Board Setup → Design Rules → Constraints → Copper to edge clearance* (e.g. 0.3 →
1.0 mm). After changing it, **re-pour** so fills retreat from the Edge.Cuts outline by the
new margin; DRC then enforces it globally.

Why it is load-bearing for C04: this is a **global** clearance (every copper feature vs the
board edge), the board-wide peer of the §3 local rule area. Fab houses reject boards that
violate it; set it to the chosen fab's minimum (validate against `jlcpcb`/`pcbway` DFM
rules) before freezing. It is one of the DFM values the C04 gate/`fab_release_gate`
assumes is already satisfied.

## 7. Interactive router modes — the three collision behaviours

For the fab-grade / diff-pair routing the autorouter does not finish, drive the **interactive
router** (`Route → Route Single Track`, right-click → *Interactive Router Settings*):

| Mode | Behaviour | When |
|---|---|---|
| **Walk around** (default) | new track detours around existing copper at the DRC clearance | dense areas, preserve existing routing |
| **Shove** | new track pushes existing tracks aside (keeping DRC) | high-density boards, let the router re-pack |
| **Highlight collisions** | no auto-avoid; violating segments are highlighted | deliberate manual routing, see exactly where you conflict |

This is the human step behind GUIDE's "coupled/symmetric differential pairs" and
"fab-grade controlled-impedance routing" — the modes let you route to a net-class rule (§5)
without silently creating violations. **Re-gate after routing** (`layout_drc_gate`); the
DRC-guarded discipline (GUIDE step 4) applies to hand-routing exactly as to the finishing
chain: never keep a segment that adds a copper/unconnected violation.

## 8. 3D models — sourcing STEP for real parts (feeds C02 + fab view)

The 3D viewer (View → 3D Viewer) is only as honest as its models. Attach a real STEP per
footprint (*Footprint Properties → 3D models*) sourced from, in order of preference:

1. **Manufacturer** (Würth/Molex/TE… "downloads → STEP") — authoritative, matches the exact
   part. Prefer this.
2. **Distributor CAD** — DigiKey "EDA/CAD models", Mouser — the part's own STEP.
3. **SnapEDA / Ultra Librarian** — by MPN; good coverage but verify it matches the ordered
   variant.

Why C04 cares: the STEP models drive **enclosure-fit checks with C02** (component heights in
`Mechanical_Constraint_Export.json`) and the fab/assembly 3D view. A wrong/placeholder model
is a silent height/footprint lie — treat a missing STEP as an honest `pending`, never as a
generic stand-in that looks complete. (Same rule as the honesty model: no fabricated
deliverable dressed as real.)

## 9. Text alignment & the selection filter — assembly-drawing legibility

Assembly-drawing and silk legibility (a scored C04 deliverable — silk overlaps are a gate
*warn*) is faster with the **selection filter** (bottom-right): disable everything except
**Text**, rubber-band select, then right-click → **Align/Distribute** (align horizontal
centre; distribute by centres). Use it to tidy reference designators and connector labels so
the assembly drawing reads cleanly. Cosmetic — never a gate pass/fail, but it is the cheap
way to clear silk warns without touching copper.

## 10. Hotkeys & the reference manual — operator throughput

- The **KiCad cheat-sheet** (linked from the source video's description; also
  `docs.kicad.org` → PCB Editor → Reference Manual) is the authoritative hotkey list. Force
  hotkey use — it is the difference between a 20-minute and a 2-hour interactive pass.
- High-value defaults: `B` re-pour zones · `E` edit properties · `M` move · `R` rotate ·
  `X` route track · `V` place via / switch layer while routing · `Alt+3` 3D viewer ·
  `Space` zero relative origin (§1) · `` ` `` cycle active layer.

---

## Mapping back to the C04 gate (so this never drifts into a false "done")

| Interactive operation | C04 deliverable it feeds | The gate that judges it |
|---|---|---|
| §5 net classes, §6 edge clearance, §7 routing | routed `<board>.kicad_pcb` + DRC report | `bodesign_layout_drc_gate` (copper/unconnected = HARD FAIL) |
| §4 cross-probe (diagnostic) | pad-mapping sanity | unmapped-pad gate (`net2pcb` sidecar) |
| §2 outline/cutout, §3 rule areas | `Layout_Constraints.json` (outline = assumption until C02-frozen) | `c04_readiness` DoD manifest |
| §8 STEP models | fab 3D view + C02 height check | honesty: `pending`, never a fake model |
| §9 text align | silk legibility | gate **warn** only (cosmetic) |

Every operation here produces copper/geometry the deterministic gate then grades. **None of
them is a substitute for the gate, and none may be used to argue a board is done.** Fix the
board, then let `layout_drc_gate` + `c04_readiness` pass — never move a line to make it green
(the floating-PSRAM lesson, `../GUIDE.md` and `../../../references/honesty-model.md` rule 5).
