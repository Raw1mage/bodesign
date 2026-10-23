"""
Silkscreen tidy primitives for detecting and repairing Silk-Over-Pad collisions.

Enforces DFM manufacturing hygiene:
1. Standardizes reference text rotation to 0° or 90°.
2. Detects collisions between silkscreen text and exposed copper pads.
3. Automatically repositions text outside pad bounding boxes with safety margins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

from .geometry import BoundingBox, Point2D


@dataclass(slots=True)
class PadGeometry:
    name: str
    rel_x: float
    rel_y: float
    width: float
    height: float
    shape: str = "rect"

    @property
    def bbox(self) -> BoundingBox:
        return BoundingBox.from_center(self.rel_x, self.rel_y, self.width, self.height)


@dataclass(slots=True)
class FootprintSilkRecord:
    refdes: str
    origin_x: float
    origin_y: float
    rotation: float = 0.0
    pads: list[PadGeometry] = field(default_factory=list)
    silk_ref_text: str = ""
    silk_pos_x: float = 0.0  # relative to footprint origin
    silk_pos_y: float = 0.0  # relative to footprint origin
    silk_rotation: float = 0.0
    font_size_x: float = 1.0
    font_size_y: float = 1.0

    def compute_pad_bounds(self) -> BoundingBox | None:
        if not self.pads:
            return None
        box = self.pads[0].bbox
        for p in self.pads[1:]:
            box = box.union(p.bbox)
        return box

    def compute_silk_bbox(
        self,
        pos_x: float | None = None,
        pos_y: float | None = None,
        rot: float | None = None,
    ) -> BoundingBox:
        px = self.silk_pos_x if pos_x is None else pos_x
        py = self.silk_pos_y if pos_y is None else pos_y
        r = self.silk_rotation if rot is None else rot

        text = self.silk_ref_text or self.refdes
        raw_w = max(0.5, len(text) * self.font_size_x * 0.75)
        raw_h = max(0.5, self.font_size_y)

        # If text is rotated 90 or 270 deg, swap dimensions
        norm_r = abs(r) % 180
        if 45 < norm_r < 135:
            box_w, box_h = raw_h, raw_w
        else:
            box_w, box_h = raw_w, raw_h

        return BoundingBox.from_center(px, py, box_w, box_h)

    def to_dict(self) -> dict[str, Any]:
        return {
            "refdes": self.refdes,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "rotation": self.rotation,
            "silk_ref_text": self.silk_ref_text or self.refdes,
            "silk_pos_x": self.silk_pos_x,
            "silk_pos_y": self.silk_pos_y,
            "silk_rotation": self.silk_rotation,
            "font_size_x": self.font_size_x,
            "font_size_y": self.font_size_y,
            "pads": [
                {"name": p.name, "x": p.rel_x, "y": p.rel_y, "w": p.width, "h": p.height}
                for p in self.pads
            ],
        }


def has_silk_pad_overlap(
    record: FootprintSilkRecord,
    pos_x: float | None = None,
    pos_y: float | None = None,
    rot: float | None = None,
    clearance_mm: float = 0.2,
) -> bool:
    """Returns True if the silkscreen text overlaps any component pad."""
    silk_box = record.compute_silk_bbox(pos_x, pos_y, rot)
    for pad in record.pads:
        if silk_box.intersects(pad.bbox, margin=clearance_mm):
            return True
    return False


def normalize_silk_rotation(rot: float) -> float:
    """Standardizes text angle to 0° or 90° for human readability and DFM consistency."""
    ang = rot % 360
    if ang < 0:
        ang += 360
    # Map into readable buckets
    if 45 <= ang < 135:
        return 90.0
    elif 135 <= ang < 225:
        return 0.0  # invert upside down to 0
    elif 225 <= ang < 315:
        return 90.0  # invert 270 to 90
    else:
        return 0.0


def tidy_footprint_silk(
    record: FootprintSilkRecord,
    clearance_mm: float = 0.25,
) -> tuple[FootprintSilkRecord, bool]:
    """
    Adjusts silkscreen rotation to standard (0°/90°) and relocates text
    outside component pad boundaries if any overlap occurs.

    Returns (updated_record, modified_flag).
    """
    pad_bounds = record.compute_pad_bounds()
    if not pad_bounds:
        # No pads to collide with
        return record, False

    orig_x = record.silk_pos_x
    orig_y = record.silk_pos_y
    orig_rot = record.silk_rotation

    norm_rot = normalize_silk_rotation(orig_rot)
    changed = False

    # Check if current position has overlap
    is_overlapping = has_silk_pad_overlap(record, orig_x, orig_y, norm_rot, clearance_mm)

    if not is_overlapping and abs(norm_rot - orig_rot) < 1e-4:
        return record, False

    # Text box dimensions at normalized rotation
    temp_box = record.compute_silk_bbox(0.0, 0.0, norm_rot)
    tw_half = temp_box.width / 2.0
    th_half = temp_box.height / 2.0

    candidates = [
        # 1. Top of pads
        (pad_bounds.center_x, pad_bounds.ymin - th_half - clearance_mm),
        # 2. Bottom of pads
        (pad_bounds.center_x, pad_bounds.ymax + th_half + clearance_mm),
        # 3. Right of pads
        (pad_bounds.xmax + tw_half + clearance_mm, pad_bounds.center_y),
        # 4. Left of pads
        (pad_bounds.xmin - tw_half - clearance_mm, pad_bounds.center_y),
    ]

    best_x = orig_x
    best_y = orig_y
    found_clean = False

    for cx, cy in candidates:
        if not has_silk_pad_overlap(record, cx, cy, norm_rot, clearance_mm):
            best_x = round(cx, 4)
            best_y = round(cy, 4)
            found_clean = True
            break

    if not found_clean:
        # Fall back to top with double clearance
        best_x = round(pad_bounds.center_x, 4)
        best_y = round(pad_bounds.ymin - th_half - clearance_mm * 2.0, 4)

    record.silk_pos_x = best_x
    record.silk_pos_y = best_y
    record.silk_rotation = norm_rot

    changed = (
        abs(best_x - orig_x) > 1e-4
        or abs(best_y - orig_y) > 1e-4
        or abs(norm_rot - orig_rot) > 1e-4
    )

    return record, changed


def tidy_all_footprints(
    records: list[FootprintSilkRecord],
    clearance_mm: float = 0.25,
) -> tuple[list[FootprintSilkRecord], int, int]:
    """
    Runs silk_tidy on a collection of footprints.
    Returns (updated_records, overlaps_before_count, overlaps_resolved_count).
    """
    overlaps_before = 0
    overlaps_after = 0
    updated_records = []

    for r in records:
        if has_silk_pad_overlap(r, clearance_mm=clearance_mm):
            overlaps_before += 1

        tidied, _ = tidy_footprint_silk(r, clearance_mm=clearance_mm)
        updated_records.append(tidied)

        if has_silk_pad_overlap(tidied, clearance_mm=clearance_mm):
            overlaps_after += 1

    resolved = overlaps_before - overlaps_after
    return updated_records, overlaps_before, resolved
