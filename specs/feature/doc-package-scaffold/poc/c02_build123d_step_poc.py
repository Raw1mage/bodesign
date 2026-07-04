"""C02 PoC: parametric enclosure -> real STEP via build123d/OCP.

Evaluates adopting `earthtojake/text-to-cad`'s backend (build123d on OpenCASCADE)
to fill C02's STEP-export gap: `bodesign_c02_export_step` currently returns
`step_export_unavailable` because no CAD kernel is configured. This PoC proves the
SAME constraint inputs C02 already holds (board outline, wall, clearance, internal
height, mounting standoffs) produce a valid ISO-10303-21 STEP file.

Run (after `pip install build123d` — pulls cadquery-ocp/vtk, ~heavy):
    python plans/feature_doc-package-scaffold/poc/c02_build123d_step_poc.py /tmp/out

Result observed 2026-06-07: build123d 0.10.0 / cadquery-ocp 7.8 — wrote a 61 KB
valid `ISO-10303-21` STEP in 0.09 s. Conclusion: build123d->STEP can back a real,
toolchain-gated `bodesign_c02_export_step` (and an `Enclosure.step` deliverable),
keeping the existing fail-fast `step_export_unavailable` when the kernel is absent.
"""

import sys
import time
from pathlib import Path


def build_enclosure_step(out_dir: Path, *, board_x=60.0, board_y=40.0, wall=2.0,
                         clearance=1.0, inner_h=15.0, standoff_h=4.0,
                         standoff_d=5.0, hole_d=2.5) -> Path:
    from build123d import (BuildPart, Box, Locations, Cylinder, Align, Mode,
                           export_step)

    inner_x, inner_y = board_x + 2 * clearance, board_y + 2 * clearance
    outer_x, outer_y, outer_h = inner_x + 2 * wall, inner_y + 2 * wall, inner_h + wall

    with BuildPart() as enclosure:
        Box(outer_x, outer_y, outer_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations((0, 0, wall)):
            Box(inner_x, inner_y, inner_h + 1, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        hx, hy = board_x / 2 - 4, board_y / 2 - 4
        posns = [(hx, hy, wall), (-hx, hy, wall), (hx, -hy, wall), (-hx, -hy, wall)]
        with Locations(*posns):
            Cylinder(standoff_d / 2, standoff_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations(*posns):
            Cylinder(hole_d / 2, standoff_h + 1, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

    out_dir.mkdir(parents=True, exist_ok=True)
    step_path = out_dir / "Enclosure.step"
    export_step(enclosure.part, str(step_path))
    return step_path


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    t0 = time.time()
    p = build_enclosure_step(out)
    head = p.read_text(encoding="utf-8", errors="replace")[:40]
    assert p.stat().st_size > 1000 and head.startswith("ISO-10303-21"), "not a valid STEP file"
    print(f"OK: {p} ({p.stat().st_size} bytes, {time.time() - t0:.2f}s) valid ISO-10303-21 STEP")
