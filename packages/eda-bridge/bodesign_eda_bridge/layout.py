"""Layout emit (G8 / N14): place footprints on a board via pcbnew + DRC + render.

Wraps KiCad's `pcbnew` Python API to turn a component+footprint list into a
starting `.kicad_pcb` — footprints loaded from the KiCad footprint libraries,
auto-placed on a grid, inside a rectangular Edge.Cuts outline — then runs
`kicad-cli pcb drc` and renders a readable SVG/PDF companion. This is a starting
layout for the engineer to route (auto-routing is freerouting/manual, bounded);
bodesign does not claim a finished, routed board.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os
import shutil
import subprocess

DEFAULT_FOOTPRINT_DIR = os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")

try:
    import pcbnew  # type: ignore
    PCBNEW_AVAILABLE = True
except ImportError:  # pragma: no cover - pcbnew only present where KiCad is installed
    pcbnew = None
    PCBNEW_AVAILABLE = False


@dataclass(slots=True)
class LayoutResult:
    status: str  # "ok" | "no-pcbnew" | "failed"
    board_path: str | None = None
    placed: int = 0
    unresolved_footprints: list[str] = field(default_factory=list)
    drc_report: str | None = None
    drc_violations: int | None = None
    companion: str | None = None
    warnings: list[str] = field(default_factory=list)


def _add_outline(board, width_mm: float, height_mm: float, margin_mm: float = 10.0) -> None:
    x0, y0 = margin_mm, margin_mm
    x1, y1 = margin_mm + width_mm, margin_mm + height_mm
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    for (ax, ay), (bx, by) in zip(corners, corners[1:]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(ax), pcbnew.FromMM(ay)))
        seg.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(bx), pcbnew.FromMM(by)))
        seg.SetLayer(pcbnew.Edge_Cuts)
        board.Add(seg)


def emit_layout(
    out_dir: str | Path,
    project_name: str,
    components: list[dict],
    board_mm: tuple[float, float] = (60.0, 40.0),
    footprint_dir: str | Path = DEFAULT_FOOTPRINT_DIR,
    columns: int = 4,
    render: bool = True,
) -> LayoutResult:
    if not PCBNEW_AVAILABLE:
        return LayoutResult(status="no-pcbnew", warnings=["pcbnew not importable (KiCad not installed here)."])

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    board = pcbnew.BOARD()
    result = LayoutResult(status="ok")

    for index, comp in enumerate(components):
        ref = str(comp.get("ref", "")).strip()
        fp_id = str(comp.get("footprint", "")).strip()
        lib, _, name = fp_id.partition(":")
        if not ref or not name:
            result.unresolved_footprints.append(ref or f"#{index}")
            continue
        lib_dir = str(Path(footprint_dir) / f"{lib}.pretty")
        try:
            fp = pcbnew.FootprintLoad(lib_dir, name)
        except Exception:  # pragma: no cover - upstream load errors vary
            fp = None
        if fp is None:
            result.unresolved_footprints.append(f"{ref} ({fp_id})")
            continue
        fp.SetReference(ref)
        x = 15.0 + (index % columns) * 12.0
        y = 15.0 + (index // columns) * 12.0
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        board.Add(fp)
        result.placed += 1

    _add_outline(board, board_mm[0], board_mm[1])
    board_path = out_root / f"{project_name}.kicad_pcb"
    pcbnew.SaveBoard(str(board_path), board)
    result.board_path = str(board_path)

    cli = shutil.which("kicad-cli")
    if cli is not None:
        drc_path = out_root / f"{project_name}.drc.rpt"
        proc = subprocess.run([cli, "pcb", "drc", str(board_path), "-o", str(drc_path)], capture_output=True, text=True)
        if drc_path.exists():
            result.drc_report = str(drc_path)
            import re
            m = re.search(r"Found (\d+) unconnected", proc.stdout or "")
            result.drc_violations = int(m.group(1)) if m else None
        if render:
            svg = out_root / f"{project_name}.pcb.svg"
            subprocess.run([cli, "pcb", "export", "svg", str(board_path), "-o", str(svg),
                            "--layers", "F.Cu,B.Cu,F.SilkS,Edge.Cuts"], capture_output=True, text=True)
            if svg.exists():
                result.companion = str(svg)
    else:
        result.warnings.append("kicad-cli not found; board saved but DRC/render skipped.")
    return result
