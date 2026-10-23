"""
Linear component distribution and alignment primitives for arrays of passives.
"""

from __future__ import annotations

from typing import Any

from .grid import snap_coord


def distribute_passives(
    components: list[dict[str, Any]],
    axis: str = "x",
    pitch_mm: float | None = 1.2,
    align_cross_axis: bool = True,
    cross_axis_coord: float | None = None,
    grid_mm: float = 0.1,
) -> tuple[list[dict[str, Any]], int]:
    """
    Distributes an array of passive components uniformly along `axis` ('x' or 'y')
    and aligns their secondary axis to ensure tidy, aesthetic routing channels.

    Returns (updated_components, count_moved).
    """
    if len(components) <= 1:
        return [dict(c) for c in components], 0

    primary_axis = axis.lower()
    if primary_axis not in ("x", "y"):
        raise ValueError(f"Distribution axis must be 'x' or 'y', got '{axis}'")
    sec_axis = "y" if primary_axis == "x" else "x"

    # Helper to get/set coordinates
    def get_coords(c: dict[str, Any]) -> tuple[float, float, bool]:
        if "placement" in c and isinstance(c["placement"], dict):
            return float(c["placement"].get("x", 0.0)), float(c["placement"].get("y", 0.0)), True
        return float(c.get("x", 0.0)), float(c.get("y", 0.0)), False

    parsed = []
    for comp in components:
        c_copy = dict(comp)
        x_val, y_val, is_nested = get_coords(c_copy)
        parsed.append((comp, c_copy, x_val, y_val, is_nested))

    # Sort components along primary axis
    key_idx = 2 if primary_axis == "x" else 3
    parsed.sort(key=lambda item: item[key_idx])

    # Determine cross-axis target
    if cross_axis_coord is not None:
        target_sec = cross_axis_coord
    else:
        # Average of secondary axis
        sec_idx = 3 if primary_axis == "x" else 2
        target_sec = sum(item[sec_idx] for item in parsed) / len(parsed)
    target_sec = snap_coord(target_sec, grid_mm)

    # Determine primary axis spacing
    start_prim = parsed[0][key_idx]
    if pitch_mm is not None:
        effective_pitch = pitch_mm
    else:
        end_prim = parsed[-1][key_idx]
        span = end_prim - start_prim
        effective_pitch = span / (len(parsed) - 1) if len(parsed) > 1 else 1.0

    count_moved = 0
    result_components = []

    for i, (orig, c_copy, orig_x, orig_y, is_nested) in enumerate(parsed):
        new_prim = snap_coord(start_prim + i * effective_pitch, grid_mm)
        new_sec = target_sec if align_cross_axis else (orig_y if primary_axis == "x" else orig_x)

        new_x = new_prim if primary_axis == "x" else new_sec
        new_y = new_sec if primary_axis == "x" else new_prim

        changed = (abs(new_x - orig_x) > 1e-5) or (abs(new_y - orig_y) > 1e-5)
        if changed:
            count_moved += 1

        if is_nested:
            placement = dict(c_copy["placement"])
            placement["x"] = new_x
            placement["y"] = new_y
            c_copy["placement"] = placement
        else:
            c_copy["x"] = new_x
            c_copy["y"] = new_y

        result_components.append(c_copy)

    return result_components, count_moved
