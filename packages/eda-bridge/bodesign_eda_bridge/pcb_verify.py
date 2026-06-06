"""EMC + thermal verification orchestration (N16) — board-level risk analysis.

Completes the SPICE counterpart (`simulate.py`): given a schematic + a
`.kicad_pcb` (from `emit_layout`), run the `kicad` analyzers (schematic + PCB)
then the `emc` skill (EMC pre-compliance risk) and the kicad `analyze_thermal`
script (hotspot estimate). Returns severity-bucketed findings.

Per DD-2 (orchestrate mature skills) and the verification model: this is the
EMC/thermal-risk layer — still pre-silicon, never a substitute for an accredited
EMC lab, but it flags layout-level risks before prototyping. Degrades gracefully
(reports skipped, never raises) when skills or inputs are absent.
"""
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import subprocess


def _skill(explicit, name: str, env: str) -> Path | None:
    p = explicit or os.environ.get(env) or str(Path.home() / ".claude" / "skills" / name)
    return Path(p) if (Path(p) / "scripts").is_dir() else None


@dataclass(slots=True)
class PcbVerifyResult:
    kind: str            # "emc" | "thermal"
    status: str          # "ok" | "skipped-no-skills" | "failed"
    by_severity: dict = field(default_factory=dict)
    finding_count: int = 0
    summary: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)   # top few {rule_id, severity, summary}
    report_path: str | None = None
    warnings: list[str] = field(default_factory=list)


def _prep_analysis(sch: Path, pcb: Path, out_dir: Path, kicad: Path) -> tuple[Path, Path] | None:
    sch_json, pcb_json = out_dir / "schematic.json", out_dir / "pcb.json"
    subprocess.run(["python3", str(kicad / "scripts" / "analyze_schematic.py"), str(sch), "--output", str(sch_json)],
                   capture_output=True, text=True)
    subprocess.run(["python3", str(kicad / "scripts" / "analyze_pcb.py"), str(pcb), "--full", "--output", str(pcb_json)],
                   capture_output=True, text=True)
    return (sch_json, pcb_json) if sch_json.exists() and pcb_json.exists() else None


def _bucket(findings: list[dict]) -> dict:
    out: dict[str, int] = {}
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        out[sev] = out.get(sev, 0) + 1
    return out


def analyze_emc(
    schematic_path: str | Path, pcb_path: str | Path, out_dir: str | Path,
    *, kicad_skill=None, emc_skill=None, standard: str = "fcc-class-b",
) -> PcbVerifyResult:
    out_root = Path(out_dir); out_root.mkdir(parents=True, exist_ok=True)
    kicad = _skill(kicad_skill, "kicad", "BODESIGN_KICAD_SKILL")
    emc = _skill(emc_skill, "emc", "BODESIGN_EMC_SKILL")
    if kicad is None or emc is None:
        return PcbVerifyResult("emc", "skipped-no-skills", warnings=["kicad/emc skill not found."])
    if not Path(schematic_path).exists() or not Path(pcb_path).exists():
        return PcbVerifyResult("emc", "failed", warnings=["schematic or pcb not found."])
    prep = _prep_analysis(Path(schematic_path), Path(pcb_path), out_root, kicad)
    if prep is None:
        return PcbVerifyResult("emc", "failed", warnings=["kicad analyzers did not produce schematic/pcb JSON."])
    sch_json, pcb_json = prep
    report = out_root / "emc.json"
    subprocess.run(["python3", str(emc / "scripts" / "analyze_emc.py"), "--schematic", str(sch_json),
                    "--pcb", str(pcb_json), "--output", str(report), "--standard", standard],
                   capture_output=True, text=True)
    if not report.exists():
        return PcbVerifyResult("emc", "failed", warnings=["analyze_emc produced no output."])
    data = json.loads(report.read_text(encoding="utf-8"))
    findings = data.get("findings", [])
    top = [{"rule_id": f.get("rule_id"), "severity": f.get("severity"), "summary": (f.get("summary") or "")[:100]}
           for f in findings[:8]]
    return PcbVerifyResult("emc", "ok", by_severity=_bucket(findings), finding_count=len(findings),
                           summary=data.get("summary", {}), findings=top, report_path=str(report))


def analyze_thermal(
    schematic_path: str | Path, pcb_path: str | Path, out_dir: str | Path,
    *, kicad_skill=None, ambient: float = 25.0,
) -> PcbVerifyResult:
    out_root = Path(out_dir); out_root.mkdir(parents=True, exist_ok=True)
    kicad = _skill(kicad_skill, "kicad", "BODESIGN_KICAD_SKILL")
    if kicad is None:
        return PcbVerifyResult("thermal", "skipped-no-skills", warnings=["kicad skill not found."])
    if not Path(schematic_path).exists() or not Path(pcb_path).exists():
        return PcbVerifyResult("thermal", "failed", warnings=["schematic or pcb not found."])
    prep = _prep_analysis(Path(schematic_path), Path(pcb_path), out_root, kicad)
    if prep is None:
        return PcbVerifyResult("thermal", "failed", warnings=["kicad analyzers did not produce schematic/pcb JSON."])
    sch_json, pcb_json = prep
    report = out_root / "thermal.json"
    subprocess.run(["python3", str(kicad / "scripts" / "analyze_thermal.py"), "--schematic", str(sch_json),
                    "--pcb", str(pcb_json), "--output", str(report), "--ambient", str(ambient)],
                   capture_output=True, text=True)
    if not report.exists():
        return PcbVerifyResult("thermal", "failed", warnings=["analyze_thermal produced no output."])
    data = json.loads(report.read_text(encoding="utf-8"))
    findings = data.get("findings", [])
    top = [{"rule_id": f.get("rule_id"), "severity": f.get("severity"), "summary": (f.get("summary") or "")[:100]}
           for f in findings[:8]]
    return PcbVerifyResult("thermal", "ok", by_severity=_bucket(findings), finding_count=len(findings),
                           summary=data.get("summary", {}), findings=top, report_path=str(report))
