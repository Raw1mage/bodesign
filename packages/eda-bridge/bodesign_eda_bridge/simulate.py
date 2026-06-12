"""SPICE simulation orchestration (N16) — verify analog behaviour of a schematic.

Thin orchestration over the `kicad` analyzer + the `spice` skill (per DD-2:
bodesign generates, mature skills verify). Given a schematic it runs
`analyze_schematic.py` then `simulate_subcircuits.py` (ngspice) and returns the
quantitative pass/warn/fail report for detected subcircuits (dividers, RC/LC
filters, opamp gains, crystal load). This is the analog-behaviour layer of the
trust model — distinct from structural ERC and reference cross-check.

Requires the `kicad` + `spice` skills present (path via args or the
BODESIGN_KICAD_SKILL / BODESIGN_SPICE_SKILL env vars, else ~/.claude/skills/*)
and a SPICE simulator (ngspice). Degrades gracefully — reports skipped, never
raises — when a dependency is absent.
"""
from dataclasses import dataclass, field
from pathlib import Path
import json
import shutil
import subprocess

from .skill_paths import resolve_skill


@dataclass(slots=True)
class SimResult:
    status: str  # "ok" | "skipped-no-skills" | "skipped-no-simulator" | "failed"
    passed: int = 0
    warned: int = 0
    failed: int = 0
    results: list[dict] = field(default_factory=list)   # per-subcircuit {type, components, expected, simulated, status}
    report_path: str | None = None
    warnings: list[str] = field(default_factory=list)


def simulate_schematic(
    schematic_path: str | Path,
    out_dir: str | Path,
    *,
    kicad_skill: str | Path | None = None,
    spice_skill: str | Path | None = None,
    simulator: str = "ngspice",
    types: str | None = None,
) -> SimResult:
    sch = Path(schematic_path)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    kicad = resolve_skill("kicad", "BODESIGN_KICAD_SKILL", kicad_skill)
    spice = resolve_skill("spice", "BODESIGN_SPICE_SKILL", spice_skill)
    if kicad is None or spice is None:
        return SimResult(status="skipped-no-skills",
                         warnings=["kicad/spice skill not found (set BODESIGN_KICAD_SKILL / BODESIGN_SPICE_SKILL)."])
    kicad, spice = Path(kicad), Path(spice)
    if simulator == "ngspice" and shutil.which("ngspice") is None:
        return SimResult(status="skipped-no-simulator", warnings=["ngspice not installed."])
    if not sch.exists():
        return SimResult(status="failed", warnings=[f"schematic not found: {sch}"])

    analysis = out_root / "analysis.json"
    proc = subprocess.run(["python3", str(kicad / "scripts" / "analyze_schematic.py"), str(sch), "--output", str(analysis)],
                          capture_output=True, text=True)
    if not analysis.exists():
        return SimResult(status="failed", warnings=[f"analyze: {(proc.stderr or proc.stdout or 'no output').strip()[:200]}"])

    report = out_root / "spice.json"
    cmd = ["python3", str(spice / "scripts" / "simulate_subcircuits.py"), str(analysis),
           "--output", str(report), "--simulator", simulator]
    if types:
        cmd += ["--types", types]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not report.exists():
        return SimResult(status="failed", warnings=[f"simulate: {(proc.stderr or proc.stdout or 'no output').strip()[:200]}"])

    data = json.loads(report.read_text(encoding="utf-8"))
    summ = data.get("summary", {})
    grounded = _vault_grounded_components(sch, analysis)
    results = [{
        "type": r.get("subcircuit_type"), "components": r.get("components"),
        "expected": r.get("expected"), "simulated": r.get("simulated"), "status": r.get("status"),
        "model_source": _model_source_for(r, grounded),
    } for r in data.get("simulation_results", [])]
    return SimResult(
        status="ok", passed=summ.get("pass", 0), warned=summ.get("warn", 0), failed=summ.get("fail", 0),
        results=results, report_path=str(report),
    )


def _vault_grounded_components(schematic_path: Path, analysis_path: Path) -> set[str]:
    """Return the set of component refs whose model is vault-grounded (DD-8).

    Deterministic: reads <project>/spice/models/manifest.json (the cascade
    tier-1 cache populated by component-kb's materialize step), collects the
    MPNs flagged source=vault-grounded, then maps them to schematic refs via
    the analyzer JSON's ref->value mapping. No fallback: a ref is grounded iff
    its value (MPN) is present in the manifest with source=vault-grounded.
    """
    project_dir = Path(schematic_path).parent
    manifest_path = project_dir / "spice" / "models" / "manifest.json"
    if not manifest_path.exists():
        return set()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    grounded_mpns = {
        str(entry.get("mpn", "")).strip()
        for entry in manifest.values()
        if isinstance(entry, dict) and entry.get("source") == "vault-grounded"
    }
    grounded_mpns.discard("")
    if not grounded_mpns:
        return set()

    try:
        adata = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()

    grounded_refs: set[str] = set()
    for comp in adata.get("components", []) or []:
        if not isinstance(comp, dict):
            continue
        ref = str(comp.get("reference") or comp.get("ref") or "").strip()
        value = str(comp.get("value") or comp.get("mpn") or "").strip()
        if ref and value in grounded_mpns:
            grounded_refs.add(ref)
    return grounded_refs


def _model_source_for(result: dict, grounded_refs: set[str]) -> str:
    """Annotate one simulation result with its model provenance (DD-8).

    vault-grounded iff any component ref in this subcircuit hits a grounded
    ref; otherwise generic-default. Deterministic table lookup, no inference.
    """
    comps = result.get("components") or []
    refs = {str(c).strip() for c in comps if c}
    if refs & grounded_refs:
        return "vault-grounded"
    return "generic-default"
