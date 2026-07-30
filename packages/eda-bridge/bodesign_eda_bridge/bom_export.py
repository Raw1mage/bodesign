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
    component_count: int = 0
    warnings: list[str] = field(default_factory=list)
    # BR_20260730c: a BOM is the (schematic, filter-rules) pair, not a property of
    # the schematic alone. line_count counts what SURVIVED the filters, so without
    # the rules and the casualty list beside it a caller cannot tell "this board has
    # 42 parts" from "47 parts, 5 filtered out" — and the downstream reader is
    # purchasing. Echo the rules actually applied, and name every part they removed.
    exclude_dnp: bool | None = None
    include_excluded_from_bom: bool | None = None
    excluded_dnp: list[str] = field(default_factory=list)
    excluded_from_bom: list[str] = field(default_factory=list)
    # "run" | "not_run:<reason>" | "failed:<reason>". An empty casualty list means
    # NOTHING WAS EXCLUDED only when this says "run"; otherwise it means nobody
    # looked. Collapsing those two into an empty list is the defect this fixes.
    exclusion_audit: str = "not_run"


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


def _audit_exclusions(cli: str, sch: Path, out_root: Path) -> tuple[list[str], list[str], str]:
    """Per-ref truth about which symbols the BOM filters would remove.

    Returns (dnp_refs, excluded_from_bom_refs, audit_status).

    Deliberately a SECOND kicad-cli pass that is UNGROUPED and excludes nothing.
    Grouping cannot be used for this: measured on kicad-cli 9.0.9, a normal 10k
    R1 and a DNP 10k R3 collapse into ONE row `"R1,R3","10k","2","DNP"` — the
    whole group inherits the flag, so a post-hoc filter over the grouped export
    would report R1 as excluded when it was shipped. The extra pass costs ~260ms;
    naming the casualties correctly is worth more than that to a purchasing reader.

    On failure the caller must surface `audit_status`, never an empty list: an
    empty casualty list has to mean "nothing was excluded", not "nobody looked".
    """
    audit_csv = out_root / f"{sch.stem}-bom-exclusion-audit.csv"
    proc = subprocess.run(
        [cli, "sch", "export", "bom", str(sch), "-o", str(audit_csv),
         "--fields", "Reference,${DNP},${EXCLUDE_FROM_BOM}",
         "--labels", "Refs,DNP,XBOM",
         "--group-by", "", "--include-excluded-from-bom"],
        capture_output=True, text=True)
    if not audit_csv.exists():
        detail = (proc.stderr or proc.stdout or "no output").strip()[:160]
        return [], [], f"failed:{detail}"

    import csv as _csv
    dnp: list[str] = []
    xbom: list[str] = []
    try:
        with audit_csv.open(encoding="utf-8", errors="ignore", newline="") as fh:
            for row in _csv.DictReader(fh):
                ref = (row.get("Refs") or "").strip()
                if not ref:
                    continue
                if (row.get("DNP") or "").strip():
                    dnp.append(ref)
                if (row.get("XBOM") or "").strip():
                    xbom.append(ref)
    except (OSError, _csv.Error) as exc:
        return [], [], f"failed:audit csv unreadable: {exc}"
    finally:
        audit_csv.unlink(missing_ok=True)
    return sorted(dnp), sorted(xbom), "run"


def export_bom(
    schematic_path: str | Path,
    out_dir: str | Path,
    *,
    group_by: str = "Value",
    exclude_dnp: bool = True,
    include_excluded_from_bom: bool = False,
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
    if include_excluded_from_bom:
        cmd.append("--include-excluded-from-bom")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not csv_path.exists():
        return BomResult(status="failed", warnings=[f"bom: {(proc.stderr or proc.stdout or 'no output').strip()[:200]}"])
    result.csv_path = str(csv_path)
    result.line_count = max(0, len(csv_path.read_text(encoding="utf-8", errors="ignore").splitlines()) - 1)

    # BR_20260730c: echo the filter rules and name what they removed. TWO rules
    # drop symbols here, and only one of them was ever mentioned anywhere:
    # --exclude-dnp (opt-out) and the fact that symbols marked 'Exclude from BOM'
    # are dropped unless --include-excluded-from-bom is passed (opt-IN, so the
    # default silently omits them).
    result.exclude_dnp = exclude_dnp
    result.include_excluded_from_bom = include_excluded_from_bom
    dnp_refs, xbom_refs, audit = _audit_exclusions(cli, sch, out_root)
    result.exclusion_audit = audit
    if audit == "run":
        # Report only what THIS call's rules actually removed: with
        # exclude_dnp=False the DNP parts are in the CSV, so listing them as
        # excluded would be a false claim.
        result.excluded_dnp = dnp_refs if exclude_dnp else []
        result.excluded_from_bom = [] if include_excluded_from_bom else xbom_refs
        dropped = len(result.excluded_dnp) + len(result.excluded_from_bom)
        if dropped:
            result.warnings.append(
                f"{dropped} symbol(s) omitted from this BOM by filter rules "
                f"(dnp={result.excluded_dnp or 'none'}, "
                f"excluded_from_bom={result.excluded_from_bom or 'none'}) — "
                f"line_count={result.line_count} counts only what survived.")
    else:
        # Fail loud rather than shipping empty lists that read as "nothing was
        # excluded". A purchasing reader must not mistake an unrun audit for a
        # clean one.
        result.warnings.append(
            f"exclusion audit did not run ({audit}) — excluded_dnp/excluded_from_bom "
            f"are UNKNOWN, not empty; line_count may omit filtered parts.")

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
    # BR_20260703: report line_count + component_count (was left at the dataclass
    # default 0, misreporting a real netlist as empty). Line count is the raw
    # file lines; component_count counts (comp (ref ...)) entries via the same
    # regex the emitter uses, so a populated netlist never reads as zero.
    import re
    net_text = net_path.read_text(encoding="utf-8", errors="ignore")
    component_count = len(re.findall(r"\(comp\s+\(ref\b", net_text))
    return BomResult(status="ok", netlist_path=str(net_path),
                     line_count=len(net_text.splitlines()),
                     component_count=component_count)
