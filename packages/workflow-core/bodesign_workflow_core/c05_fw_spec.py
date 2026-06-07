"""C05 firmware software-development spec sub-package (spec, NOT code).

C05 is an extension of the PRD's functional description, realized as a
plan-builder-like software-development architecture spec. bodesign stands up and
maintains the *spec* (functional spec → module/interface decomposition →
state-machine → task breakdown, bridged to the C03 pin map); the FW team owns the
*firmware code*. This module writes deterministic draft scaffolds with explicit
FW-team-owned markers and never emits firmware source.

Inputs (all optional; absent data stays pending, never fabricated):
- `software`: PRD §7-derived software intent — functions / modes / interactions /
  interfaces / logging / update / security.
- `pin_map`: the C03 pin allocation (rows of {ref, pin, net, is_mcu}, or the alloc
  dict) — bridged into firmware signal responsibilities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

C05_FOLDER = Path("C05-FW")
C05_FUNCTIONAL = C05_FOLDER / "Functional_Spec.md"
C05_MODULES = C05_FOLDER / "Module_Architecture.md"
C05_STATE_MACHINE = C05_FOLDER / "State_Machine.md"
C05_TASKS = C05_FOLDER / "Task_Breakdown.md"
C05_PIN_BRIDGE = C05_FOLDER / "Pin_Map_Bridge.json"

_SOFTWARE_KEYS = ["functions", "modes", "interactions", "interfaces", "logging", "update", "security"]


@dataclass(slots=True)
class C05FwReadiness:
    folder: str
    present_sections: list[str]
    pending: list[str]
    functional_present: bool
    pin_bridge_present: bool
    status: str
    next_step: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "present_sections": list(self.present_sections),
            "pending": list(self.pending),
            "functional_present": self.functional_present,
            "pin_bridge_present": self.pin_bridge_present,
            "status": self.status,
            "next_step": self.next_step,
            "firmware_code": False,
            "fw_team_owned": True,
        }


@dataclass(slots=True)
class C05FwResult:
    folder: str
    files: list[str]
    pin_bridge: dict[str, Any]
    readiness: C05FwReadiness

    def to_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "files": list(self.files),
            "pin_bridge": self.pin_bridge,
            "readiness": self.readiness.to_dict(),
            "firmware_code": False,
        }


def _norm_software(software: dict[str, Any] | None) -> dict[str, list[Any]]:
    result = {k: [] for k in _SOFTWARE_KEYS}
    if not software:
        return result
    for key in _SOFTWARE_KEYS:
        value = software.get(key)
        if isinstance(value, list):
            result[key] = list(value)
        elif value:
            result[key] = [value]
    return result


def _pin_rows(pin_map: Any) -> list[dict[str, Any]]:
    if pin_map is None:
        return []
    rows = pin_map.get("rows", pin_map) if isinstance(pin_map, dict) else pin_map
    out: list[dict[str, Any]] = []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("ref") and row.get("pin"):
                out.append(row)
    return out


def _build_pin_bridge(pin_map: Any) -> dict[str, Any]:
    rows = _pin_rows(pin_map)
    mcu_rows = [r for r in rows if r.get("is_mcu")] or rows
    signals = [
        {
            "ref": r["ref"],
            "pin": r["pin"],
            "net": r.get("net", ""),
            "firmware_signal": r.get("net", "") or f"{r['ref']}_{r['pin']}",
            "responsibility": "TBD by FW team (init/direction/driver/ISR).",
        }
        for r in mcu_rows
    ]
    return {
        "schema": "bodesign.c05.pin_map_bridge.v1",
        "state": "drafted",
        "source": {"layer": "C05", "from_c03_pin_map": bool(rows)},
        "signals": signals,
        "note": "Bridges the C03 pin map to firmware signal responsibilities. Driver/ISR/init code is FW-team owned.",
    }


def _bullets(items: list[Any], empty: str) -> str:
    if not items:
        return f"- _{empty}_"
    return "\n".join(f"- {item}" for item in items)


def _render_functional(sw: dict[str, list[Any]]) -> str:
    return "\n".join([
        "# C05 FW — Functional Spec (DRAFT, extends PRD §7)",
        "",
        "> bodesign owns this spec; the FW team owns the firmware code. No code is generated here.",
        "",
        "## Functions",
        _bullets(sw["functions"], "no functions provided from PRD §7 yet"),
        "",
        "## Operating modes",
        _bullets(sw["modes"], "modes to be derived from PRD §7 / C01 UI state model"),
        "",
        "## User interactions",
        _bullets(sw["interactions"], "interactions to be aligned with C01 Display UI/UX"),
        "",
        "## External interfaces",
        _bullets(sw["interfaces"], "interfaces to be derived from C03 + PRD §6"),
        "",
        "## Logging / Update / Security",
        _bullets(sw["logging"] + sw["update"] + sw["security"], "logging/update/security expectations pending PRD confirmation"),
    ]) + "\n"


def _render_modules(sw: dict[str, list[Any]]) -> str:
    modules = [f"`{f}` module (interface + responsibilities — FW team)" for f in sw["functions"]]
    return "\n".join([
        "# C05 FW — Module / Interface Architecture (DRAFT)",
        "",
        "> Decomposition stubs derived from the functional spec. Concrete module APIs,",
        "> RTOS/bare-metal choice, and inter-module contracts are FW-team decisions.",
        "",
        "## Candidate modules",
        _bullets(modules, "modules to be decomposed once PRD §7 functions are provided"),
        "",
        "## Open architecture decisions",
        "- scheduler model (bare-metal loop vs RTOS) — FW team",
        "- inter-module messaging / shared state — FW team",
        "- HAL boundary vs C03 pin map — see Pin_Map_Bridge.json",
    ]) + "\n"


def _render_state_machine(sw: dict[str, list[Any]]) -> str:
    return "\n".join([
        "# C05 FW — State Machine (DRAFT)",
        "",
        "> Top-level firmware state model. States/transitions below are placeholders to be",
        "> confirmed against PRD §7 modes and the C01 UI/status model (GRAFCET-style refinement).",
        "",
        "## States",
        _bullets(sw["modes"], "states to be derived from operating modes"),
        "",
        "## Transitions",
        "- _transitions and guards to be specified with the FW team_",
    ]) + "\n"


def _render_tasks(sw: dict[str, list[Any]]) -> str:
    tasks = [f"Implement `{f}` (spec → driver → test)" for f in sw["functions"]]
    return "\n".join([
        "# C05 FW — Task Breakdown (DRAFT)",
        "",
        "> Spec-level task list for FW planning. Effort/ownership/scheduling are FW-team owned.",
        "",
        _bullets(tasks, "tasks to be generated once functions are provided"),
        "",
        "- Bring up C03 pin map (see Pin_Map_Bridge.json)",
        "- Define build/flash/log SOP (FW team)",
    ]) + "\n"


def scaffold_c05_fw_spec(
    out_dir: str | Path,
    software: dict[str, Any] | None = None,
    pin_map: Any = None,
) -> C05FwResult:
    """Scaffold the C05 FW software-development spec sub-package (spec, not code)."""
    root = Path(out_dir)
    sw = _norm_software(software)
    pin_bridge = _build_pin_bridge(pin_map)
    files: list[str] = []
    for rel, content in (
        (C05_FUNCTIONAL, _render_functional(sw)),
        (C05_MODULES, _render_modules(sw)),
        (C05_STATE_MACHINE, _render_state_machine(sw)),
        (C05_TASKS, _render_tasks(sw)),
        (C05_PIN_BRIDGE, json.dumps(pin_bridge, ensure_ascii=False, indent=2) + "\n"),
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        files.append(str(rel))
    return C05FwResult(str(root), files, pin_bridge, assess_c05_fw_readiness(root))


def assess_c05_fw_readiness(folder: str | Path) -> C05FwReadiness:
    root = Path(folder)
    sections = {
        "Functional_Spec": root / C05_FUNCTIONAL,
        "Module_Architecture": root / C05_MODULES,
        "State_Machine": root / C05_STATE_MACHINE,
        "Task_Breakdown": root / C05_TASKS,
        "Pin_Map_Bridge": root / C05_PIN_BRIDGE,
    }
    present = [name for name, path in sections.items() if path.exists() and path.stat().st_size > 0]
    pending: list[str] = []

    functional_present = False
    fpath = root / C05_FUNCTIONAL
    if fpath.exists():
        text = fpath.read_text(encoding="utf-8")
        functional_present = "_no functions provided" not in text
    if not functional_present:
        pending.append("PRD §7 functions/modes not yet supplied — functional spec is a skeleton.")

    pin_bridge_present = False
    bpath = root / C05_PIN_BRIDGE
    if bpath.exists():
        try:
            data = json.loads(bpath.read_text(encoding="utf-8"))
            pin_bridge_present = bool(data.get("signals"))
        except json.JSONDecodeError:
            pin_bridge_present = False
    if not pin_bridge_present:
        pending.append("C03 pin map not bridged — provide pin allocation for firmware signal responsibilities.")

    if not present:
        status = "missing"
        next_step = "Run bodesign_c05_scaffold_fw_spec with PRD §7 software intent and the C03 pin map."
    elif not functional_present and not pin_bridge_present:
        status = "blocked"
        next_step = "Supply PRD §7 functions/modes and the C03 pin map; the spec is an empty skeleton."
    else:
        status = "fw_spec_drafted"
        next_step = "Hand the SW-dev spec to the FW team; bodesign maintains the spec, the FW team writes the code."

    return C05FwReadiness(
        folder=str(root),
        present_sections=present,
        pending=pending,
        functional_present=functional_present,
        pin_bridge_present=pin_bridge_present,
        status=status,
        next_step=next_step,
    )
