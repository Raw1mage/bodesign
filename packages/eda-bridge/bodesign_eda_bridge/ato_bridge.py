"""atopile build bridge (dsl_atopile-integration, tasks 2.1-2.4).

Wraps the pinned atopile compiler (`ato build`, DD-1: 0.12.x) as a
fail-fast subprocess adapter: compile + unit/tolerance check + assert
constraint solve → `.kicad_pcb` artifact + structured verification result.

Contracts (plans/dsl_atopile-integration/data-schema.json):
  - AtoBuildResult  → ato_build_result   (ok / pcb_path / evidence / deficiencies / build_log_path)
  - Deficiency      → deficiency          (kind / detail / source_anchor)
  - build_constraint_evidence → constraint_solve_evidence

Hard rules (errors.md):
  1. all deficiencies reported in one pass — no drip-feeding;
  2. raw build log goes to disk (`build_log_path`), never into the MCP
     response body (DD-6);
  3. ok=False with an empty deficiency list is a bridge defect — the
     parser always emits at least one entry;
  4. no retries, no downgrades, no silent fallback of any kind (天條).
"""

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BUILD_TIMEOUT_S = 150

COMPONENT_SOURCES = ("vault", "registry", "vault_then_registry")

DEFICIENCY_KINDS = (
    "compile_error",
    "unsat_constraint",
    "pick_failure",
    "component_wrapper_missing",
    "toolchain_missing",
    "worker_unavailable",
)

_ORACLE_NAME = "constraint_solve"

_SOLVER_VERDICTS = ("sat", "unsat", "trivially_true")

_PICK_SOURCES = ("vault", "registry")


class ComponentWrapperMissing(Exception):
    """Raised when a component class has no `.ato` vault wrapper (DD-5)."""

    def __init__(self, component_class: str):
        self.component_class = component_class
        super().__init__(
            f"no .ato vault wrapper for component class {component_class!r}; "
            "supported classes: " + ", ".join(sorted(_WRAPPER_EMITTERS))
        )


@dataclass(slots=True)
class Deficiency:
    kind: str
    detail: str
    source_anchor: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in DEFICIENCY_KINDS:
            raise ValueError(f"unknown deficiency kind {self.kind!r}; allowed: {DEFICIENCY_KINDS}")

    def to_dict(self) -> dict:
        out: dict = {"kind": self.kind, "detail": self.detail}
        if self.source_anchor is not None:
            out["source_anchor"] = self.source_anchor
        return out


@dataclass(slots=True)
class AtoBuildResult:
    ok: bool
    pcb_path: str | None = None
    evidence: dict | None = None
    deficiencies: list[Deficiency] = field(default_factory=list)
    build_log_path: str | None = None

    def __post_init__(self) -> None:
        if not self.ok and not self.deficiencies:
            # errors.md principle 3: this state is itself a bridge defect.
            raise ValueError("AtoBuildResult with ok=False requires at least one deficiency")

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "pcb_path": self.pcb_path,
            "evidence": self.evidence,
            "deficiencies": [d.to_dict() for d in self.deficiencies],
            "build_log_path": self.build_log_path,
        }


# ── error parsing (DD-6) ────────────────────────────────────────────────

# Calibrated against REAL atopile 0.12.5 output (TV-1..TV-4 in-container runs,
# 2026-07-03). Diagnostics are rich-formatted MULTI-LINE blocks:
#
#   [02:31:25] ERROR    Pick Error
#                       No matching component found for c
#                       - `package`: `[BackendPackage.C0402]` ...
#
#              ERROR    Incompatible Unit Error
#                       Given units (microfarad) are incompatible with ...
#                       Source: main.ato:7:4          <- anchor on its OWN line
#
# An always-false assert surfaces as a Pick Error block containing
# "Contradiction: Intersection of literals is empty" (the solver feeds the
# picker) — so unsat classification is checked BEFORE pick_failure.
# The trailer "Unfortunately errors ^^^ stopped the build" is noise, not an error.

_BLOCK_START_RE = re.compile(
    r"^\s*(?:\[[\d:\-_. ]+\]\s+)?(?:ERROR|error)(?::\s*|\s{2,})(?P<header>.*)$")
_ANCHOR_RE = re.compile(r"(?P<anchor>[\w./\-]+\.ato:\d+(?::\d+)?)")
_GUTTER_RE = re.compile(r"^\s*\u2771?\s*\d+\s*\u2502?")  # code-frame gutter lines
_FOOTER_RE = re.compile(r"errors \^\^\^ stopped the build", re.IGNORECASE)
_UNSAT_RE = re.compile(
    r"contradiction|unsatisfiable|cannot be satisfied|never true|no solution"
    r"|intersection of literals is empty"
    r"|assert(?:ion)?\b.*(?:fail|unsatisf)",
    re.IGNORECASE,
)
_PICK_RE = re.compile(
    r"pick error"
    r"|no (?:matching|suitable) (?:part|component|candidate)"
    r"|(?:could not|couldn't|failed to|unable to)\s+pick"
    r"|picker\b.*(?:fail|error)|pick_failure",
    re.IGNORECASE,
)
_UNCAUGHT_RE = re.compile(r"uncaught compiler exception|^exception$|traceback", re.IGNORECASE)
_SKIP_DETAIL_PREFIXES = ("Source:", "Code causing", "Origins:", "Literals:", "-")


def parse_ato_errors(log_text: str) -> list[Deficiency]:
    """Parse `ato build` output into structured deficiencies (DD-6).

    Block-aware: an ERROR header line opens a block; indented continuation
    lines (rich formatting) belong to it until the next header / footer.
    Classification looks at the WHOLE block (unsat > pick > compile), the
    anchor is the LAST `file.ato:line[:col]` in the block (the code-frame
    culprit, not the enclosing module).

    Guarantees at least one entry for a failed build (errors.md #3):
    unclassifiable failures yield a single `compile_error` /
    "unparsed build failure" entry.
    """
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for raw in log_text.splitlines():
        line = raw.rstrip()
        m = _BLOCK_START_RE.match(line)
        if m:
            current = [m.group("header").strip()]
            blocks.append(current)
            continue
        if _FOOTER_RE.search(line):
            current = None
            continue
        if current is not None:
            stripped = line.strip()
            if stripped:
                current.append(stripped)
    deficiencies: list[Deficiency] = []
    seen: set[tuple[str, str]] = set()
    for block in blocks:
        text = "\n".join(block)
        # Uncaught-exception / traceback blocks (e.g. registry unreachable when
        # offline) are infrastructure failures: classify by HEADER only — their
        # bodies are python tracebacks that can spuriously match solver regexes.
        if _UNCAUGHT_RE.search(block[0]):
            kind = "compile_error"
        elif _UNSAT_RE.search(text):
            kind = "unsat_constraint"
        elif _PICK_RE.search(text):
            kind = "pick_failure"
        else:
            kind = "compile_error"
        anchors = _ANCHOR_RE.findall(text)
        anchor = anchors[-1] if anchors else None
        header = block[0]
        detail_extra = next(
            (l for l in block[1:]
             if not l.startswith(_SKIP_DETAIL_PREFIXES) and not _GUTTER_RE.match(l)),
        "")
        if header and detail_extra:
            detail = f"{header}: {detail_extra}"
        else:
            detail = header or detail_extra or "unlabelled build error"
        detail = detail[:200]
        key = (kind, detail)
        if key in seen:
            continue
        seen.add(key)
        deficiencies.append(Deficiency(kind=kind, detail=detail, source_anchor=anchor))
    if not deficiencies:
        deficiencies.append(Deficiency(
            kind="compile_error",
            detail="unparsed build failure (see build log for raw output)",
        ))
    return deficiencies


# ── constraint_solve evidence (DD-4 payload side) ───────────────────────

def build_constraint_evidence(
    constraints_checked: int,
    solver_verdict: str,
    picks: list[dict],
    atopile_version: str,
) -> dict:
    """Assemble a constraint_solve_evidence payload (data-schema.json)."""
    if solver_verdict not in _SOLVER_VERDICTS:
        raise ValueError(f"solver_verdict must be one of {_SOLVER_VERDICTS}, got {solver_verdict!r}")
    if constraints_checked < 0:
        raise ValueError("constraints_checked must be >= 0")
    norm_picks: list[dict] = []
    for p in picks:
        missing = {"designator", "source", "spec_interval", "rated_interval", "mpn"} - set(p)
        if missing:
            raise ValueError(f"pick_proof missing fields {sorted(missing)}: {p!r}")
        if p["source"] not in _PICK_SOURCES:
            raise ValueError(f"pick_proof source must be one of {_PICK_SOURCES}, got {p['source']!r}")
        norm_picks.append({
            "designator": p["designator"],
            "source": p["source"],
            "spec_interval": p["spec_interval"],
            "rated_interval": p["rated_interval"],
            "mpn": p["mpn"],
        })
    return {
        "constraints_checked": constraints_checked,
        "solver_verdict": solver_verdict,
        "picks": norm_picks,
        "atopile_version": atopile_version,
    }


def to_validation_evidence(evidence: dict) -> dict:
    """Shape the payload for the workflow-core validation_evidence.v1 wrapper.

    The actual envelope construction (and ORACLE_TOOLS enforcement) lives in
    bodesign_workflow_core.validation_evidence; this only fixes the oracle
    name and payload shape at the bridge boundary.
    """
    return {
        "oracle": _ORACLE_NAME,
        "verdict": "pass" if evidence.get("solver_verdict") in ("sat", "trivially_true") else "fail",
        "payload": evidence,
    }


# ── vault component wrappers (DD-5 minimal viable set: R/C/L) ───────────

def _wrap_resistor(name: str, entry: dict) -> str:
    return _wrap_passive(name, entry, kind="Resistor", prop="resistance")


def _wrap_capacitor(name: str, entry: dict) -> str:
    return _wrap_passive(name, entry, kind="Capacitor", prop="capacitance")


def _wrap_inductor(name: str, entry: dict) -> str:
    return _wrap_passive(name, entry, kind="Inductor", prop="inductance")


_WRAPPER_EMITTERS = {
    "Resistor": _wrap_resistor,
    "Capacitor": _wrap_capacitor,
    "Inductor": _wrap_inductor,
}

_REQUIRED_VAULT_FIELDS = ("value", "tolerance", "package", "mpn")


def _wrap_passive(name: str, entry: dict, kind: str, prop: str) -> str:
    missing = [f for f in _REQUIRED_VAULT_FIELDS if not entry.get(f)]
    if missing:
        raise ValueError(f"vault entry for {name!r} missing fields: {missing} (no guessing — fix the vault entry)")
    lines = [
        f"# generated by bodesign ato_bridge from Component Vault entry (mpn={entry['mpn']})",
        f"component {name} from {kind}:",
        f"    footprint = \"{entry['package']}\"",
        f"    mpn = \"{entry['mpn']}\"",
        f"    {prop} = {entry['value']} +/- {entry['tolerance']}",
    ]
    if entry.get("rating"):
        lines.append(f"    # rated: {entry['rating']}")
    return "\n".join(lines) + "\n"


def generate_component_wrapper(component_class: str, vault_entry: dict) -> str:
    """Generate `.ato` wrapper text for a vault component (DD-5).

    Minimal viable set: Resistor / Capacitor / Inductor. Anything else
    raises ComponentWrapperMissing — the caller reports the deficiency,
    never substitutes. No registry/network access here, ever.
    """
    emitter = _WRAPPER_EMITTERS.get(component_class)
    if emitter is None:
        raise ComponentWrapperMissing(component_class)
    name = vault_entry.get("name") or f"Vault{component_class}"
    return emitter(name, vault_entry)


# ── build execution (task 2.1) ──────────────────────────────────────────

def get_atopile_version() -> str | None:
    """Return the installed atopile version string, or None if unavailable."""
    ato = shutil.which("ato")
    if ato is None:
        return None
    try:
        proc = subprocess.run([ato, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or proc.stderr).strip() or None


def _write_build_log(project: Path, text: str) -> str | None:
    try:
        log_dir = project / ".bodesign"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "ato_build.log"
        log_path.write_text(text, encoding="utf-8")
        return str(log_path)
    except OSError:
        # Log persistence must never mask the build outcome itself.
        return None


def _find_pcb_artifact(project: Path) -> str | None:
    candidates = sorted(
        (p for p in project.rglob("*.kicad_pcb") if ".bodesign" not in p.parts),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(candidates[0]) if candidates else None


def _count_asserts(project: Path) -> int:
    total = 0
    for src in project.rglob("*.ato"):
        try:
            text = src.read_text(encoding="utf-8")
        except OSError:
            continue
        total += sum(1 for line in text.splitlines() if line.strip().startswith("assert "))
    return total


def run_ato_build(
    project_path: str,
    component_source: str = "vault",
    target: str | None = None,
    workspace_root: str | None = None,
    timeout_s: int = DEFAULT_BUILD_TIMEOUT_S,
) -> AtoBuildResult:
    """Run `ato build` on an .ato project and return the structured result.

    component_source semantics (DD-5): recorded fail-fast policy. `vault`
    (default) resolves parts exclusively through vault-generated wrappers —
    the picks in the evidence must all be source=vault. `registry` /
    `vault_then_registry` are explicit opt-ins at the caller's (user's)
    request; this bridge never switches sources on its own.
    """
    if component_source not in COMPONENT_SOURCES:
        raise ValueError(f"component_source must be one of {COMPONENT_SOURCES}, got {component_source!r}")

    project = Path(project_path).resolve()
    if workspace_root is not None:
        ws = Path(workspace_root).resolve()
        if not project.is_relative_to(ws):
            return AtoBuildResult(ok=False, deficiencies=[Deficiency(
                kind="compile_error",
                detail=f"project_path {project} escapes workspace root {ws}",
            )])
    if not project.is_dir() or not (project / "ato.yaml").is_file():
        return AtoBuildResult(ok=False, deficiencies=[Deficiency(
            kind="compile_error",
            detail=f"not an atopile project (missing ato.yaml): {project}",
        )])

    ato = shutil.which("ato")
    if ato is None:
        return AtoBuildResult(ok=False, deficiencies=[Deficiency(
            kind="toolchain_missing",
            detail="atopile compiler not found on PATH (`ato`); install the pinned toolchain in the ee worker image",
        )])

    cmd = [ato, "build"]
    if target:
        cmd += ["--target", target]

    try:
        proc = subprocess.run(cmd, cwd=str(project), capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        log_path = _write_build_log(project, (exc.stdout or "") + "\n" + (exc.stderr or ""))
        return AtoBuildResult(ok=False, build_log_path=log_path, deficiencies=[Deficiency(
            kind="compile_error",
            detail=f"ato build timed out after {timeout_s}s (no retry — see errors.md #4)",
        )])

    log_text = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    log_path = _write_build_log(project, log_text)

    if proc.returncode != 0:
        return AtoBuildResult(
            ok=False,
            build_log_path=log_path,
            deficiencies=parse_ato_errors(log_text),
        )

    pcb_path = _find_pcb_artifact(project)
    if pcb_path is None:
        return AtoBuildResult(ok=False, build_log_path=log_path, deficiencies=[Deficiency(
            kind="compile_error",
            detail="ato build exited 0 but produced no .kicad_pcb artifact",
        )])

    constraints = _count_asserts(project)
    evidence = build_constraint_evidence(
        constraints_checked=constraints,
        solver_verdict="sat" if constraints else "trivially_true",
        picks=[],  # pick extraction from build output lands with vault adapter integration
        atopile_version=get_atopile_version() or "unknown",
    )
    return AtoBuildResult(ok=True, pcb_path=pcb_path, evidence=evidence, build_log_path=log_path)
