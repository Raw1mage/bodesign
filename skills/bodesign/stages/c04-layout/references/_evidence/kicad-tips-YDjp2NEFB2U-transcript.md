# Source transcript — "10 Essential KiCad PCB Layout Design Tips"

- Source: YouTube `YDjp2NEFB2U` (PCBWay-sponsored KiCad tutorial)
- Captured: 2026-07-03 via youtube-transcript-api (en)
- Purpose: raw evidence for the C04 interactive-layout knowledge distill.
  Distilled into `skills/bodesign/stages/c04-layout/references/kicad-interactive-layout.md`
  and ragbase objects (workflow.c04-kicad-interactive-ops + concepts).

## Tips (normalized from the auto-transcript; ASR spellings corrected)

1. **Origins & axis** — default page origin is top-left, Y-down. Space bar sets a
   relative zero (dx/dy). Preferences → PCB Editor → Origins & Axes → switch page-origin to
   grid-origin and set Y-axis increasing upward; Place → Grid Origin at the board corner so
   x/y read engineering coordinates (corner=0,0, right=+x, up=+y).

2. **Rounded corners** — draw board outline rectangle on Edge.Cuts (e.g. 80×80 mm), select
   net → Shape Modification → Fillet Lines → radius (10 mm, then 4 mm). Verify in 3D viewer.
   Pro tip: a rectangle drawn on Edge.Cuts *inside* the outline becomes a milled cutout
   (visible in 3D).

3. **Draw rule area (keepout)** — Place → Add Rule Areas. Rule Area Properties: pick layers
   (top/inner1/inner2/bottom) and keep-out classes (e.g. keep out fill zones). Used to keep
   copper pour away from a relay. Move + Update re-applies.

4. **Schematic editor integration (cross-probe)** — with schematic + PCB open, selecting a
   part (USB connector / fuse / an IC) highlights it in the other editor, down to individual
   pads.

5. **Constraints** — File → Board Setup → Design Rules → Constraints. Copper-to-edge
   clearance (0.5 → 1 mm), Update board → fills retreat from the edge.

5A. **[AD — excluded]** PCBWay ordering plugin (Tools → External Plugins → PCBWay): uploads
   Gerbers/BOM, detects board size + layer count. Sponsor segment; not distilled.

6. **Align text** — selection filter: disable all except Text, select labels, right-click →
   Align/Distribute (align horizontal center; distribute vertical by centers).

7. **Interactive router** — right-click → Interactive Router Settings. Modes: walk-around
   (detour around existing tracks at DRC clearance), shove (push existing tracks aside),
   highlight-collisions (no auto-avoid; violations highlighted).

8. **3D models** — View → 3D Viewer; Footprint Properties → 3D models tab to attach/enable a
   STEP. Sourcing: SnapEDA (by part number), DigiKey (EDA/CAD models → STEP), Würth
   (part downloads → STEP file).

9. **Net classes** — File → Board Setup → Design Rules → Net Classes. Default class + a
   custom class (e.g. diff_pair_USB) with larger clearance / track width; assign nets to the
   class so routing auto-applies the rule. Change value → redraw → clearance propagates.

10. **KiCad cheat sheet** — hotkey reference (linked in the video description); force hotkey
    use. Full docs at docs.kicad.org → PCB Editor → Reference Manual.

## Relevance to bodesign C04

Tips 1–4, 6–9 are the operator layer behind C04 GUIDE's "What the autorouter + this chain do
NOT finish" (fab-grade impedance routing, diff pairs, keepout, copper-to-edge clearance,
outline shaping). Tip 5A is a sponsor advertisement, excluded. All operations produce
copper/geometry the C04 gate (`bodesign_layout_drc_gate` + `c04_readiness`) grades — none
relaxes a gate.
