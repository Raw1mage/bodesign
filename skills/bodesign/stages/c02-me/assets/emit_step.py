#!/usr/bin/env python3
"""
C02-ME draft STEP emitter (build123d / OCP, OpenCASCADE kernel).

Reads Mechanical_Constraints.json and emits a REAL ISO-10303 STEP solid:
a parametric shell box sized to the (provisional) board outline + the tallest
component, with the lid clearance baked in. This is a DRAFT for soft-tooling
(EVT/DVT), NOT a production / DFM / tolerance-approved model.

HONESTY CONTRACT
  - This script REQUIRES build123d (pip install build123d). If it is not
    installed, it EXITS NON-ZERO and writes NOTHING. Do not hand-fabricate a
    .step or claim `step_exported: true` when this did not run — verify with:
        python3 -c "import build123d" && echo OK
  - The OpenSCAD model (Enclosure.scad) is independent SOURCE; rendering/
    exporting it to STL needs `openscad` (verify: `which openscad`). If neither
    toolchain is present, the .scad ships as un-rendered source and STEP/STL
    export stays `not-run` with that reason.

Usage:
    python3 emit_step.py Mechanical_Constraints.json Enclosure.step
"""
import json
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: emit_step.py <Mechanical_Constraints.json> <out.step>", file=sys.stderr)
        return 2
    cons_path, out_path = sys.argv[1], sys.argv[2]

    try:
        from build123d import Box, Location, Pos, Compound, export_step
    except ImportError:
        print(
            "build123d NOT installed — STEP export is not-run. "
            "Install build123d/OCP on an ME worker, or ship Enclosure.scad as "
            "un-rendered source. Did NOT write any artifact.",
            file=sys.stderr,
        )
        return 1

    with open(cons_path, encoding="utf-8") as fh:
        c = json.load(fh)

    bo = c.get("board_outline", {})
    bw = float(bo.get("width_mm") or 0)
    bh = float(bo.get("height_mm") or 0)
    heights = [float(h.get("height_mm") or 0) for h in c.get("component_heights", [])]
    max_h = max(heights) if heights else 0.0

    if bw <= 0 or bh <= 0:
        print(
            "board_outline width/height missing or zero — cannot size a solid. "
            "This is an engineering_pending input (owner: C04 layout/ME). "
            "Leaving STEP not-run rather than inventing dimensions.",
            file=sys.stderr,
        )
        return 1

    # Parametric draft envelope (all derived, no magic geometry).
    wall, clr, lid_clr = 2.5, 1.0, 1.5
    inner_w = bw + clr * 2
    inner_h = bh + clr * 2
    case_w = inner_w + wall * 2
    case_h = inner_h + wall * 2
    case_d = max_h + clr + lid_clr + wall * 2

    outer = Box(case_w, case_h, case_d)
    cavity = Box(inner_w, inner_h, case_d)
    # hollow from the top, leaving a floor of `wall`
    cavity = Pos(0, 0, wall) * cavity
    shell = outer - cavity

    export_step(shell, out_path)
    print(
        f"WROTE {out_path}  (draft_unapproved)  case {case_w:.1f}x{case_h:.1f}x{case_d:.1f} mm; "
        f"board {bw:.0f}x{bh:.0f}, tallest component {max_h:.1f} mm. "
        "DRAFT for soft-tooling only — not DFM/tolerance/strength/waterproof approved."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
