"""
Geometric primitives and collision detection for PCB tidy operations.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(slots=True, frozen=True)
class Point2D:
    x: float
    y: float

    def distance(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def rotate(self, angle_deg: float, origin: Point2D | None = None) -> Point2D:
        """Rotates point around an origin counter-clockwise by angle_deg."""
        if angle_deg % 360 == 0:
            return self
        ox = origin.x if origin else 0.0
        oy = origin.y if origin else 0.0
        rad = math.radians(angle_deg)
        cos_val = math.cos(rad)
        sin_val = math.sin(rad)
        dx = self.x - ox
        dy = self.y - oy
        new_x = ox + dx * cos_val - dy * sin_val
        new_y = oy + dx * sin_val + dy * cos_val
        return Point2D(new_x, new_y)


@dataclass(slots=True, frozen=True)
class BoundingBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        return max(0.0, self.xmax - self.xmin)

    @property
    def height(self) -> float:
        return max(0.0, self.ymax - self.ymin)

    @property
    def center_x(self) -> float:
        return (self.xmin + self.xmax) / 2.0

    @property
    def center_y(self) -> float:
        return (self.ymin + self.ymax) / 2.0

    def intersects(self, other: BoundingBox, margin: float = 0.0) -> bool:
        """Returns True if this bounding box (optionally expanded by margin) intersects another."""
        return not (
            self.xmax + margin < other.xmin
            or self.xmin - margin > other.xmax
            or self.ymax + margin < other.ymin
            or self.ymin - margin > other.ymax
        )

    def contains(self, x: float, y: float) -> bool:
        return self.xmin <= x <= self.xmax and self.ymin <= y <= self.ymax

    def expand(self, margin: float) -> BoundingBox:
        return BoundingBox(
            self.xmin - margin,
            self.ymin - margin,
            self.xmax + margin,
            self.ymax + margin,
        )

    def union(self, other: BoundingBox) -> BoundingBox:
        return BoundingBox(
            min(self.xmin, other.xmin),
            min(self.ymin, other.ymin),
            max(self.xmax, other.xmax),
            max(self.ymax, other.ymax),
        )

    @classmethod
    def from_center(cls, cx: float, cy: float, w: float, h: float) -> BoundingBox:
        hw = w / 2.0
        hh = h / 2.0
        return cls(cx - hw, cy - hh, cx + hw, cy + hh)
