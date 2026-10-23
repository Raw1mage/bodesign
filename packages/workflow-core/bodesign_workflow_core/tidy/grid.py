"""
Grid snapping primitives for PCB components and routing vias.
"""

from __future__ import annotations

import math
from typing import Any


def snap_coord(val: float, step_mm: float = 0.1) -> float:
    """Snaps a single scalar coordinate to the nearest step_mm multiple."""
    if step_mm <= 0:
        return val
    return round(round(val / step_mm) * step_mm, 6)


def snap_point(x: float, y: float, step_mm: float = 0.1) -> tuple[float, float]:
    """Snaps a 2D coordinate pair (x, y) to the specified grid in mm."""
    return (snap_coord(x, step_mm), snap_coord(y, step_mm))


def snap_components(
    components: list[dict[str, Any]],
    grid_mm: float = 0.1,
) -> tuple[list[dict[str, Any]], int]:
    """
    Snaps component placement coordinates in-place or returns updated records.
    Returns (updated_components, count_of_modified_elements).
    """
    modified_count = 0
    updated_list: list[dict[str, Any]] = []

    for comp in components:
        c = dict(comp)
        x_val: float | None = None
        y_val: float | None = None
        is_nested = False

        if "placement" in c and isinstance(c["placement"], dict):
            placement = dict(c["placement"])
            x_val = float(placement.get("x", 0.0))
            y_val = float(placement.get("y", 0.0))
            is_nested = True
        elif "x" in c and "y" in c:
            x_val = float(c["x"])
            y_val = float(c["y"])
        else:
            updated_list.append(c)
            continue

        snapped_x, snapped_y = snap_point(x_val, y_val, grid_mm)
        changed = (abs(snapped_x - x_val) > 1e-5) or (abs(snapped_y - y_val) > 1e-5)

        if changed:
            modified_count += 1

        if is_nested:
            placement["x"] = snapped_x
            placement["y"] = snapped_y
            c["placement"] = placement
        else:
            c["x"] = snapped_x
            c["y"] = snapped_y

        updated_list.append(c)

    return updated_list, modified_count
