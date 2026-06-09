"""Fab outputs (G9 / N15): export manufacturing files from a .kicad_pcb.

Thin orchestration over `kicad-cli pcb export` — gerbers, drill, position/CPL,
STEP, IPC-2581 — plus a readable PDF companion, so a finalized board produces
the factory/assembly handoff set with a viewable version alongside. Validated
downstream by the `kicad` gerber analyzer; unlocks the full `kidoc`
Manufacturing-Transfer package.
"""

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess

# format -> (kicad-cli subcommand, output is a directory?, output filename if a file)
_EXPORTS = {
    "gerbers": ("gerbers", True, None),
    "drill": ("drill", True, None),
    "pos": ("pos", False, "{stem}-pos.csv"),
    "step": ("step", False, "{stem}.step"),
    "ipc2581": ("ipc2581", False, "{stem}.xml"),
    "pdf": ("pdf", False, "{stem}.pcb.pdf"),
}
_PDF_LAYERS = "F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts"


@dataclass(slots=True)
class FabResult:
    status: str  # "ok" | "partial" | "failed" | "skipped-no-kicad-cli"
    outputs: dict[str, str] = field(default_factory=dict)   # format -> path (dir or file)
    warnings: list[str] = field(default_factory=list)


def emit_fab_outputs(
    board_path: str | Path,
    out_dir: str | Path,
    formats: tuple[str, ...] = ("gerbers", "drill", "pos", "step", "pdf"),
    pdf_layers: str | None = None,
) -> FabResult:
    # H4: the PDF layer set is caller-overridable. The default suits 2/4-layer boards;
    # pass pdf_layers (e.g. add In1.Cu..In4.Cu) so 6+ layer inner copper is not omitted.
    pdf_layers = pdf_layers or _PDF_LAYERS
    board = Path(board_path)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    result = FabResult(status="ok")

    cli = shutil.which("kicad-cli")
    if cli is None:
        return FabResult(status="skipped-no-kicad-cli", warnings=["kicad-cli not found."])
    if not board.exists():
        return FabResult(status="failed", warnings=[f"board not found: {board}"])

    for fmt in formats:
        spec = _EXPORTS.get(fmt)
        if spec is None:
            result.warnings.append(f"unknown fab format: {fmt}")
            continue
        sub, is_dir, name_tpl = spec
        if is_dir:
            target = out_root / fmt
            target.mkdir(parents=True, exist_ok=True)
            out_arg = str(target)
        else:
            target = out_root / name_tpl.format(stem=board.stem)
            out_arg = str(target)
        cmd = [cli, "pcb", "export", sub, str(board), "-o", out_arg]
        if fmt == "pdf":
            cmd += ["--layers", pdf_layers]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        produced = (is_dir and target.is_dir() and any(target.iterdir())) or (not is_dir and target.exists())
        if produced:
            result.outputs[fmt] = str(target)
        else:
            result.warnings.append(f"{fmt}: {(proc.stderr or proc.stdout or 'no output').strip()[:160]}")

    got = len(result.outputs)
    result.status = "ok" if got == len(formats) else ("partial" if got else "failed")
    return result
