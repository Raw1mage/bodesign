"""Render readable companions for non-readable engineering files (G1 / N3).

Completes the ingest→readable surface + the format policy: given an engineering
file the ingest flagged as non-readable, produce a readable companion beside it
— `.kicad_sch`/`.kicad_pcb` → PDF via `kicad-cli`, Gerber → PNG via pygerber.
Files needing the originating tool (OrCAD `.DSN`, `.step`, `.ai`) are reported
as unsupported (use the supplied export or an existing sibling).

Orchestration, not reinvention: KiCad's own `kicad-cli` and the gerber-core
pygerber path do the rendering.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

GERBER_EXTS = {".art", ".gbr", ".gtl", ".gbl", ".gto", ".gbo", ".gts", ".gbs", ".gko", ".gm1"}
DEFAULT_PCB_LAYERS = "F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts"


@dataclass(slots=True)
class CompanionResult:
    source: str
    status: str  # "rendered" | "render-failed" | "unsupported" | "skipped-no-kicad-cli"
    output: str | None = None
    renderer: str = ""
    note: str = ""


def _kicad_cli() -> str | None:
    return shutil.which("kicad-cli")


def render_companion(path: str | Path, out_dir: str | Path) -> CompanionResult:
    source = Path(path)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    ext = source.suffix.lower()

    if ext in {".kicad_sch", ".kicad_pcb"}:
        cli = _kicad_cli()
        if cli is None:
            return CompanionResult(str(source), "skipped-no-kicad-cli", renderer="kicad-cli")
        out_pdf = out_root / f"{source.stem}{'.sch' if ext == '.kicad_sch' else '.pcb'}.pdf"
        if ext == ".kicad_sch":
            cmd = [cli, "sch", "export", "pdf", str(source), "-o", str(out_pdf)]
        else:
            cmd = [cli, "pcb", "export", "pdf", str(source), "-o", str(out_pdf), "--layers", DEFAULT_PCB_LAYERS]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if out_pdf.exists():
            return CompanionResult(str(source), "rendered", str(out_pdf), "kicad-cli")
        return CompanionResult(str(source), "render-failed", None, "kicad-cli",
                               (proc.stderr or proc.stdout or "kicad-cli render failed").strip()[:200])

    if ext in GERBER_EXTS:
        try:
            from bodesign_gerber_core import render_gerber_raster_with_pygerber
        except ImportError:
            return CompanionResult(str(source), "render-failed", None, "pygerber-raster", "gerber-core unavailable")
        result = render_gerber_raster_with_pygerber(source, out_root)
        return CompanionResult(str(source), result.status, result.output_path, "pygerber-raster",
                               "; ".join(result.warnings)[:200])

    return CompanionResult(str(source), "unsupported", None, "",
                           "needs the originating tool (OrCAD/CAD/3D/vector) or a supplied export")


def render_all_companions(index, out_dir: str | Path) -> list[CompanionResult]:
    """Render companions for every non-readable file in a ProjectFolderIndex
    that lacks an existing readable sibling. `index.root` anchors relative paths.
    """
    root = Path(index.root)
    results: list[CompanionResult] = []
    for item in index.needs_companion:
        results.append(render_companion(root / item.rel_path, out_dir))
    return results
