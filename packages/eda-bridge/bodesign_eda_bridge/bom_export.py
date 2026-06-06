"""BOM + netlist export (G12 / N12) — first-class deliverables from a schematic.

Wraps `kicad-cli sch export bom` (grouped by value, with quantity + an MPN field,
DNP excluded) into a readable BOM CSV, and `kicad-cli sch export netlist` into a
netlist. Optionally renders an xlsx companion of the BOM via LibreOffice (the
CSV stays the readable source). These were previously left to orchestration;
G12 makes them deterministic bodesign tools.
"""
from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess

# Default BOM columns. ${QUANTITY} is a kicad-cli substitution; MPN is a common
# user field (blank when unset — still a valid column for sourcing).
_BOM_FIELDS = "Reference,Value,Footprint,${QUANTITY},MPN"
_BOM_LABELS = "Refs,Value,Footprint,Qty,MPN"


@dataclass(slots=True)
class BomResult:
    status: str  # "ok" | "failed" | "skipped-no-kicad-cli"
    csv_path: str | None = None
    xlsx_path: str | None = None
    netlist_path: str | None = None
    line_count: int = 0
    warnings: list[str] = field(default_factory=list)


def _xlsx_from_csv(csv_path: Path, out_dir: Path) -> str | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        return None
    import tempfile
    with tempfile.TemporaryDirectory(prefix="bodesign-lo-") as profile:
        subprocess.run([soffice, "--headless", f"-env:UserInstallation=file://{profile}",
                        "--convert-to", "xlsx", "--outdir", str(out_dir), str(csv_path)],
                       capture_output=True, text=True)
    produced = out_dir / f"{csv_path.stem}.xlsx"
    return str(produced) if produced.exists() else None


def export_bom(
    schematic_path: str | Path,
    out_dir: str | Path,
    *,
    group_by: str = "Value",
    exclude_dnp: bool = True,
    xlsx: bool = False,
    fields: str = _BOM_FIELDS,
    labels: str = _BOM_LABELS,
) -> BomResult:
    sch = Path(schematic_path)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    result = BomResult(status="ok")

    cli = shutil.which("kicad-cli")
    if cli is None:
        return BomResult(status="skipped-no-kicad-cli", warnings=["kicad-cli not found."])
    if not sch.exists():
        return BomResult(status="failed", warnings=[f"schematic not found: {sch}"])

    csv_path = out_root / f"{sch.stem}-bom.csv"
    cmd = [cli, "sch", "export", "bom", str(sch), "-o", str(csv_path),
           "--fields", fields, "--labels", labels, "--group-by", group_by]
    if exclude_dnp:
        cmd.append("--exclude-dnp")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not csv_path.exists():
        return BomResult(status="failed", warnings=[f"bom: {(proc.stderr or proc.stdout or 'no output').strip()[:200]}"])
    result.csv_path = str(csv_path)
    result.line_count = max(0, len(csv_path.read_text(encoding="utf-8", errors="ignore").splitlines()) - 1)
    if xlsx:
        result.xlsx_path = _xlsx_from_csv(csv_path, out_root)
        if result.xlsx_path is None:
            result.warnings.append("xlsx companion skipped (LibreOffice not available).")
    return result


def export_netlist(schematic_path: str | Path, out_dir: str | Path, fmt: str = "kicadsexpr") -> BomResult:
    sch = Path(schematic_path)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    cli = shutil.which("kicad-cli")
    if cli is None:
        return BomResult(status="skipped-no-kicad-cli", warnings=["kicad-cli not found."])
    if not sch.exists():
        return BomResult(status="failed", warnings=[f"schematic not found: {sch}"])
    net_path = out_root / f"{sch.stem}.net"
    proc = subprocess.run([cli, "sch", "export", "netlist", str(sch), "-o", str(net_path), "--format", fmt],
                          capture_output=True, text=True)
    if not net_path.exists():
        return BomResult(status="failed", warnings=[f"netlist: {(proc.stderr or proc.stdout or 'no output').strip()[:200]}"])
    return BomResult(status="ok", netlist_path=str(net_path))
