"""Pure-python impedance estimates for C04 layout constraints.

Closed-form microstrip estimates are planning guidance only; fab stackup solver
confirmation remains required before release.
"""
from __future__ import annotations

import math
from typing import Any


LIGHT_SPEED_MM_PER_PS = 0.299792458


def _positive_number(mapping: dict, key: str) -> float:
    if key not in mapping:
        raise ValueError(f"missing required '{key}'")
    value = float(mapping[key])
    if value <= 0:
        raise ValueError(f"'{key}' must be > 0")
    return value


def _stackup_values(stackup: dict) -> tuple[float, float, float]:
    height_mm = _positive_number(stackup, "dielectric_height_mm")
    er = _positive_number(stackup, "er")
    copper_mm = float(stackup.get("copper_thickness_mm", 0.0) or 0.0)
    if copper_mm < 0:
        raise ValueError("'copper_thickness_mm' must be >= 0")
    return height_mm, er, copper_mm


def _effective_er(width_mm: float, height_mm: float, er: float) -> float:
    ratio = width_mm / height_mm
    base = (er + 1.0) / 2.0 + (er - 1.0) / 2.0 / math.sqrt(1.0 + 12.0 / ratio)
    if ratio < 1.0:
        base += 0.04 * (1.0 - ratio) ** 2
    return base


def _microstrip_ohms(width_mm: float, height_mm: float, er: float, copper_mm: float) -> float:
    effective_width = width_mm + copper_mm / math.pi if copper_mm else width_mm
    ratio = effective_width / height_mm
    effective_er = _effective_er(effective_width, height_mm, er)
    if ratio <= 1.0:
        return 60.0 / math.sqrt(effective_er) * math.log(8.0 / ratio + 0.25 * ratio)
    return 120.0 * math.pi / (math.sqrt(effective_er) * (ratio + 1.393 + 0.667 * math.log(ratio + 1.444)))


def _delay_ps_per_mm(width_mm: float, height_mm: float, er: float) -> float:
    return math.sqrt(_effective_er(width_mm, height_mm, er)) / LIGHT_SPEED_MM_PER_PS


def _solve_width(target_ohm: float, height_mm: float, er: float, copper_mm: float) -> float:
    low = 0.001
    high = max(height_mm * 20.0, 1.0)
    while _microstrip_ohms(high, height_mm, er, copper_mm) > target_ohm:
        high *= 2.0
        if high > height_mm * 1000.0:
            raise ValueError("unable to bracket microstrip width for target impedance")
    for _ in range(80):
        mid = (low + high) / 2.0
        if _microstrip_ohms(mid, height_mm, er, copper_mm) > target_ohm:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def _diff_ohms(single_ohm: float, gap_mm: float, height_mm: float) -> float:
    coupling = 1.0 - 0.48 * math.exp(-0.96 * gap_mm / height_mm)
    return 2.0 * single_ohm * coupling


def _target_items(targets: Any) -> list[tuple[str, dict]]:
    if isinstance(targets, dict):
        return [(str(name), spec if isinstance(spec, dict) else {"impedance_ohm": spec}) for name, spec in targets.items()]
    if isinstance(targets, list):
        items = []
        for spec in targets:
            if not isinstance(spec, dict) or "name" not in spec:
                raise ValueError("target list items must be objects with 'name'")
            items.append((str(spec["name"]), spec))
        return items
    raise ValueError("'targets' must be an object or list")


def solve_impedance(stackup: dict, targets: Any) -> dict:
    """Solve single-ended or differential microstrip planning dimensions.

    Required stackup keys: dielectric_height_mm, er. Targets may be a dict keyed by
    class name or a list of objects with name. Differential targets must provide
    either gap_mm (solve width) or width_mm (solve gap); no geometry defaults are
    invented.
    """
    if not isinstance(stackup, dict) or not stackup:
        raise ValueError("missing required 'stackup'")
    if targets is None or targets == {} or targets == []:
        raise ValueError("missing required 'targets'")
    height_mm, er, copper_mm = _stackup_values(stackup)
    classes: dict[str, dict] = {}
    warnings = ["closed-form microstrip estimate; confirm final geometry with the PCB fabricator's field solver"]
    for name, spec in _target_items(targets):
        target_ohm = _positive_number(spec, "impedance_ohm")
        kind = str(spec.get("kind") or spec.get("type") or "single").lower()
        if kind in {"single", "single-ended", "microstrip"}:
            width_mm = _solve_width(target_ohm, height_mm, er, copper_mm)
            actual_ohm = _microstrip_ohms(width_mm, height_mm, er, copper_mm)
            classes[name] = {
                "kind": "single-ended",
                "width_mm": round(width_mm, 4),
                "actual_ohm": round(actual_ohm, 2),
                "ps_per_mm": round(_delay_ps_per_mm(width_mm, height_mm, er), 3),
            }
        elif kind in {"diff", "differential", "edge-coupled"}:
            if "gap_mm" in spec:
                gap_mm = _positive_number(spec, "gap_mm")
                single_target = target_ohm / (2.0 * (1.0 - 0.48 * math.exp(-0.96 * gap_mm / height_mm)))
                width_mm = _solve_width(single_target, height_mm, er, copper_mm)
            elif "width_mm" in spec:
                width_mm = _positive_number(spec, "width_mm")
                single_ohm = _microstrip_ohms(width_mm, height_mm, er, copper_mm)
                ratio = (1.0 - target_ohm / (2.0 * single_ohm)) / 0.48
                if ratio <= 0.0 or ratio >= 1.0:
                    raise ValueError(f"target '{name}' cannot be reached with width_mm={width_mm}")
                gap_mm = -height_mm / 0.96 * math.log(ratio)
            else:
                raise ValueError(f"differential target '{name}' requires 'gap_mm' or 'width_mm'")
            actual_ohm = _diff_ohms(_microstrip_ohms(width_mm, height_mm, er, copper_mm), gap_mm, height_mm)
            classes[name] = {
                "kind": "differential",
                "width_mm": round(width_mm, 4),
                "gap_mm": round(gap_mm, 4),
                "actual_ohm": round(actual_ohm, 2),
                "ps_per_mm": round(_delay_ps_per_mm(width_mm, height_mm, er), 3),
            }
        else:
            raise ValueError(f"unsupported impedance target kind: {kind}")
    return {"classes": classes, "warnings": warnings, "limitations": warnings[:]}
