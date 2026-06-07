"""C03 circuit-to-mechanical constraint export.

This module turns explicit circuit/spec data into mechanical-relevant constraints
for C02/C04. It does not infer board outline, placement coordinates, or final
mechanical dimensions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


C03_OUTPUT = Path("C03-EE") / "Mechanical_Constraint_Export.json"


@dataclass(slots=True)
class C03MechanicalConstraintResult:
    folder: str
    export_path: str
    status: str
    constraints: dict[str, Any]
    pending: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "folder": self.folder,
            "export_path": self.export_path,
            "status": self.status,
            "constraints": self.constraints,
            "pending": self.pending,
            "c02_ready_keys": sorted(key for key, value in self.constraints.items() if _has_value(value)),
            "mechanical_approval": False,
        }


def export_c03_mechanical_constraints(
    out_dir: str | Path,
    circuit: dict[str, Any] | None = None,
) -> C03MechanicalConstraintResult:
    """Export explicit C03 mechanical constraints for C02/C04 consumers."""
    root = Path(out_dir)
    data = circuit or {}
    components = _list(data.get("components"))
    constraints = {
        "component_heights": _component_heights(components),
        "connector_openings": _connector_openings(data, components),
        "heat_sources": _heat_sources(data, components),
        "antenna_keepouts": _antenna_keepouts(data, components),
        "battery_envelope": data.get("battery_envelope") or data.get("battery"),
        "esd_emc_notes": _notes(data, "esd_emc_notes", "emc_notes", "esd_notes"),
        "source": {
            "layer": "C03",
            "tool": "bodesign_c03_export_mechanical_constraints",
            "notes": "Only explicit C03 circuit/spec values are exported. Board outline, mounting holes, placement coordinates, and final dimensions remain C04/C02 responsibilities.",
        },
    }
    pending = _pending_items(constraints, components)
    payload = {
        "status": "mechanical_constraints_exported",
        "constraints": constraints,
        "pending": pending,
        "approval": {
            "mechanical_approval": False,
            "layout_approval": False,
            "notes": "This export is a C03 handoff, not ME/Layout approval.",
        },
    }
    path = root / C03_OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return C03MechanicalConstraintResult(
        folder=str(root),
        export_path=str(C03_OUTPUT),
        status="mechanical_constraints_exported",
        constraints=constraints,
        pending=pending,
    )


def _component_heights(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for component in components:
        height = _number(component, "height_mm", "max_height_mm")
        if height is None:
            continue
        out.append({
            "ref": str(component.get("ref", "")).strip() or "unknown",
            "height_mm": height,
            "source": "C03 component spec",
            "status": "explicit",
        })
    return out


def _connector_openings(data: dict[str, Any], components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    connectors = _list(data.get("connectors"))
    for component in components:
        role = str(component.get("role") or component.get("category") or component.get("type") or "").lower()
        if component.get("external") or "connector" in role or "usb" in role or "jack" in role:
            connectors.append(component)
    out: list[dict[str, Any]] = []
    for item in connectors:
        name = str(item.get("name") or item.get("value") or item.get("ref") or "connector").strip()
        entry = {
            "name": name,
            "ref": item.get("ref"),
            "type": item.get("type") or item.get("connector_type") or item.get("value"),
            "preferred_edge": item.get("edge") or item.get("preferred_edge"),
            "opening": item.get("opening") or item.get("opening_requirement"),
            "status": "explicit_without_final_coordinates",
            "owner": "C03 EE / C04 layout / C02 ME",
        }
        out.append({key: value for key, value in entry.items() if _has_value(value)})
    return out


def _heat_sources(data: dict[str, Any], components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    heat = _list(data.get("heat_sources"))
    for component in components:
        watts = _number(component, "thermal_watts", "watts", "power_w")
        if watts is not None:
            heat.append({"ref": component.get("ref"), "watts": watts, "source": "C03 component power"})
    return [item for item in heat if isinstance(item, dict)]


def _antenna_keepouts(data: dict[str, Any], components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keepouts = _list(data.get("antenna_keepouts") or data.get("rf_keepouts"))
    for component in components:
        role = str(component.get("role") or component.get("category") or component.get("type") or "").lower()
        if "antenna" in role or "rf" in role:
            keepouts.append({
                "ref": component.get("ref"),
                "area": component.get("keepout") or component.get("area") or component.get("preferred_area"),
                "notes": component.get("notes") or "RF/antenna component requires C04 placement and C02 enclosure material review.",
            })
    return [item for item in keepouts if isinstance(item, dict)]


def _pending_items(constraints: dict[str, Any], components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    if not _has_value(constraints.get("component_heights")):
        pending.append({"key": "component_heights", "owner": "C03 EE", "reason": "No explicit component height envelope was provided."})
    missing_heights = [component.get("ref") for component in components if component.get("ref") and _number(component, "height_mm", "max_height_mm") is None]
    if missing_heights:
        pending.append({"key": "component_height_refs", "owner": "C03 EE", "reason": "Some components lack height_mm.", "refs": missing_heights})
    if not _has_value(constraints.get("connector_openings")):
        pending.append({"key": "connector_openings", "owner": "C03 EE / C04 layout", "reason": "No external connector/opening requirements were provided."})
    if not _has_value(constraints.get("heat_sources")):
        pending.append({"key": "heat_sources", "owner": "C03 EE", "reason": "No thermal source map or component power data was provided."})
    if not _has_value(constraints.get("antenna_keepouts")):
        pending.append({"key": "antenna_keepouts", "owner": "C03 EE/RF", "reason": "No antenna/RF keepout data was provided."})
    if not _has_value(constraints.get("battery_envelope")):
        pending.append({"key": "battery_envelope", "owner": "C03 EE / user", "reason": "No battery envelope was provided."})
    return pending


def _list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _notes(data: dict[str, Any], *keys: str) -> list[Any]:
    notes: list[Any] = []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            notes.extend(value)
        elif _has_value(value):
            notes.append(value)
    return notes


def _number(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True
