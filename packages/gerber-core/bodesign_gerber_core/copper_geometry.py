"""Copper-geometry parser: gerber copper layer -> computable, net-attributed
primitives + deterministic geometry queries with provenance.

Pure-python, ZERO pcbnew. Mirrors the board_outline.py template: consumes
already-parsed draw/flash/region input (not raw gerber s-expr), reduces it to
straight segments for exact point-to-segment distance math, honestly SKIPS
arc/circle/curve primitives (never chord-approximates -> no fabricated clearance),
and FAILS FAST (never empty/0/inf silent pass) on missing or uncomputable geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Literal


PrimitiveType = Literal["track", "pad", "polygon", "plane", "curve"]
QueryType = Literal["edge_to_edge", "point_to_copper", "plane_coverage"]
MissingReason = Literal["layer_absent", "zero_geometry", "empty_primitive_set"]

# Epsilon for connected-copper-island merging (same source evidence frame as coords).
_ISLAND_EPSILON = 1e-6


@dataclass(slots=True)
class CopperPrimitive:
    """A computable copper feature. `coords` are polyline/polygon vertices in the
    source evidence frame; a `track` is a 2-point polyline, a `pad`/`polygon`/`plane`
    is a closed vertex ring. A `curve` keeps its raw params and is EXCLUDED from
    linear distance math (curve_params populated, coords empty)."""

    id: str
    primitive_type: PrimitiveType
    coords: list[tuple[float, float]] = field(default_factory=list)
    width: float | None = None
    net_island: str = ""
    source_layer: str = ""
    curve_params: dict[str, float] | None = None


@dataclass(slots=True)
class GeometryProvenance:
    source_layers: list[str] = field(default_factory=list)
    primitive_refs: list[str] = field(default_factory=list)
    skipped_curves: list[str] = field(default_factory=list)
    algorithm: str = ""


@dataclass(slots=True)
class MissingGeometryError(Exception):
    """Fail-fast marker: geometry absent / uncomputable. Raised by build; carried
    (not raised) inside a GeometryQueryResult for an empty query set."""

    reason: MissingReason
    missing_items: list[str] = field(default_factory=list)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.reason}: missing_items={self.missing_items}"


@dataclass(slots=True)
class GeometryQueryResult:
    query_type: QueryType
    distance_mm: float | None = None
    covered: bool | None = None
    provenance: GeometryProvenance = field(default_factory=GeometryProvenance)
    error: MissingGeometryError | None = None


@dataclass(slots=True)
class CopperGeometry:
    """Materialized copper primitives for one or more source layers."""

    primitives: list[CopperPrimitive] = field(default_factory=list)
    source_layers: list[str] = field(default_factory=list)

    def curves(self) -> list[CopperPrimitive]:
        return [p for p in self.primitives if p.primitive_type == "curve"]

    def linear(self) -> list[CopperPrimitive]:
        return [p for p in self.primitives if p.primitive_type != "curve"]

    def island(self, net_island: str) -> list[CopperPrimitive]:
        return [p for p in self.linear() if p.net_island == net_island]


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build_copper_geometry(
    tracks: list[dict] | None = None,
    pads: list[dict] | None = None,
    polygons: list[dict] | None = None,
    curves: list[dict] | None = None,
    *,
    source_layer: str = "copper",
) -> CopperGeometry:
    """Materialize already-parsed copper draw input into computable primitives.

    Input shapes (already parsed upstream; this layer does NOT parse gerber s-expr):
      tracks:   {"x1","y1","x2","y2","width"?}
      pads:     {"x","y","w"?,"h"?}  -> rectangular ring around the flash center
      polygons: {"points": [[x,y],...], "plane"?: bool}
      curves:   {"cx","cy","r", ...}  -> flagged, excluded from distance math (DD-3)

    Fail-fast (DD-4): if no track/pad/polygon primitive would be produced, raise
    MissingGeometryError(zero_geometry) — never return an empty CopperGeometry.
    """
    tracks = tracks or []
    pads = pads or []
    polygons = polygons or []
    curves = curves or []

    prims: list[CopperPrimitive] = []
    idx = 0

    for t in tracks:
        prims.append(
            CopperPrimitive(
                id=f"trk{idx}",
                primitive_type="track",
                coords=[(float(t["x1"]), float(t["y1"])), (float(t["x2"]), float(t["y2"]))],
                width=float(t["width"]) if t.get("width") is not None else None,
                source_layer=source_layer,
            )
        )
        idx += 1

    for p in pads:
        cx, cy = float(p["x"]), float(p["y"])
        hw = float(p.get("w", 0.0)) / 2.0
        hh = float(p.get("h", 0.0)) / 2.0
        ring = [
            (cx - hw, cy - hh),
            (cx + hw, cy - hh),
            (cx + hw, cy + hh),
            (cx - hw, cy + hh),
        ]
        prims.append(
            CopperPrimitive(
                id=f"pad{idx}",
                primitive_type="pad",
                coords=ring,
                source_layer=source_layer,
            )
        )
        idx += 1

    for poly in polygons:
        pts = [(float(x), float(y)) for x, y in poly["points"]]
        prims.append(
            CopperPrimitive(
                id=f"poly{idx}",
                primitive_type="plane" if poly.get("plane") else "polygon",
                coords=pts,
                source_layer=source_layer,
            )
        )
        idx += 1

    # Curves: flagged, excluded from distance math (DD-3 — no chord approximation).
    for c in curves:
        prims.append(
            CopperPrimitive(
                id=f"crv{idx}",
                primitive_type="curve",
                coords=[],
                curve_params={k: float(v) for k, v in c.items() if isinstance(v, (int, float))},
                source_layer=source_layer,
            )
        )
        idx += 1

    linear_count = sum(1 for p in prims if p.primitive_type != "curve")
    if linear_count == 0:
        raise MissingGeometryError(
            reason="zero_geometry",
            missing_items=["no track/pad/polygon copper primitives in input"],
        )

    geom = CopperGeometry(primitives=prims, source_layers=[source_layer])
    _assign_net_islands(geom)
    return geom


def from_gerber_summary(summary, *, source_layer: str | None = None) -> CopperGeometry:
    """Adapter: build copper geometry from a GerberGeometrySummary's sample draws/flashes.

    Note: GerberGeometrySummary keeps only SAMPLE draws/flashes (sample_limit); full
    geometry completeness is an upstream concern. This adapter is a convenience over the
    already-parsed summary, not a re-parse.
    """
    layer = source_layer or getattr(summary, "source_path", "copper")
    tracks = [
        {"x1": s.x1, "y1": s.y1, "x2": s.x2, "y2": s.y2}
        for s in getattr(summary, "sample_draws", [])
    ]
    pads = [{"x": f.x, "y": f.y} for f in getattr(summary, "sample_flashes", [])]
    return build_copper_geometry(tracks=tracks, pads=pads, source_layer=layer)


# ---------------------------------------------------------------------------
# Net-island attribution (connected-copper grouping, union-find)
# ---------------------------------------------------------------------------


def _assign_net_islands(geom: CopperGeometry) -> None:
    linear = geom.linear()
    n = len(linear)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i in range(n):
        for j in range(i + 1, n):
            if _primitives_touch(linear[i], linear[j]):
                union(i, j)

    # Stable island ids by first-appearance order of each root.
    root_to_island: dict[int, str] = {}
    next_id = 0
    for i in range(n):
        r = find(i)
        if r not in root_to_island:
            root_to_island[r] = f"island{next_id}"
            next_id += 1
        linear[i].net_island = root_to_island[r]


def _primitives_touch(a: CopperPrimitive, b: CopperPrimitive) -> bool:
    for ax, ay in a.coords:
        for bx, by in b.coords:
            if math.hypot(ax - bx, ay - by) <= _ISLAND_EPSILON:
                return True
    return False


# ---------------------------------------------------------------------------
# Geometry primitives -> segments
# ---------------------------------------------------------------------------


def _primitive_segments(p: CopperPrimitive) -> list[tuple[float, float, float, float]]:
    """Reduce a linear primitive to straight segments. Curves contribute none."""
    if p.primitive_type == "curve" or not p.coords:
        return []
    pts = p.coords
    if p.primitive_type == "track":
        segs = []
        for i in range(len(pts) - 1):
            segs.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))
        return segs
    # pad/polygon/plane: closed ring.
    segs = []
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        segs.append((x1, y1, x2, y2))
    return segs


def _point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)


def _segment_to_segment(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return min(
        _point_to_segment(ax1, ay1, bx1, by1, bx2, by2),
        _point_to_segment(ax2, ay2, bx1, by1, bx2, by2),
        _point_to_segment(bx1, by1, ax1, ay1, ax2, ay2),
        _point_to_segment(bx2, by2, ax1, ay1, ax2, ay2),
    )


def _provenance(
    prims: list[CopperPrimitive],
    curves: list[CopperPrimitive],
    algorithm: str,
    layers: list[str],
) -> GeometryProvenance:
    return GeometryProvenance(
        source_layers=list(layers),
        primitive_refs=[p.id for p in prims],
        skipped_curves=[c.id for c in curves],
        algorithm=algorithm,
    )


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def edge_to_edge(
    geom: CopperGeometry, island_a: str, island_b: str
) -> GeometryQueryResult:
    """Minimum edge-to-edge copper spacing between two net-islands."""
    prims_a = geom.island(island_a)
    prims_b = geom.island(island_b)
    if not prims_a or not prims_b:
        return GeometryQueryResult(
            query_type="edge_to_edge",
            error=MissingGeometryError(
                reason="empty_primitive_set",
                missing_items=[
                    m
                    for m, ok in ((island_a, prims_a), (island_b, prims_b))
                    if not ok
                ],
            ),
        )
    segs_a = [s for p in prims_a for s in _primitive_segments(p)]
    segs_b = [s for p in prims_b for s in _primitive_segments(p)]
    best = math.inf
    for sa in segs_a:
        for sb in segs_b:
            d = _segment_to_segment(sa, sb)
            if d < best:
                best = d
    return GeometryQueryResult(
        query_type="edge_to_edge",
        distance_mm=best,
        provenance=_provenance(
            prims_a + prims_b, geom.curves(), "segment_min_distance", geom.source_layers
        ),
    )


def point_to_copper(geom: CopperGeometry, px: float, py: float) -> GeometryQueryResult:
    """Minimum distance from a point to any copper primitive."""
    linear = geom.linear()
    if not linear:
        return GeometryQueryResult(
            query_type="point_to_copper",
            error=MissingGeometryError(
                reason="empty_primitive_set", missing_items=["no linear copper primitives"]
            ),
        )
    best = math.inf
    for p in linear:
        for x1, y1, x2, y2 in _primitive_segments(p):
            d = _point_to_segment(px, py, x1, y1, x2, y2)
            if d < best:
                best = d
    return GeometryQueryResult(
        query_type="point_to_copper",
        distance_mm=best,
        provenance=_provenance(linear, geom.curves(), "point_to_segment_min", geom.source_layers),
    )


def plane_coverage(geom: CopperGeometry, px: float, py: float) -> GeometryQueryResult:
    """Whether a point falls inside any plane/polygon primitive (ray-casting)."""
    planes = [p for p in geom.linear() if p.primitive_type in ("plane", "polygon")]
    if not planes:
        return GeometryQueryResult(
            query_type="plane_coverage",
            error=MissingGeometryError(
                reason="empty_primitive_set", missing_items=["no plane/polygon primitives"]
            ),
        )
    covered = any(_point_in_polygon(px, py, p.coords) for p in planes)
    return GeometryQueryResult(
        query_type="plane_coverage",
        covered=covered,
        provenance=_provenance(planes, geom.curves(), "ray_casting", geom.source_layers),
    )


def _point_in_polygon(px: float, py: float, poly: list[tuple[float, float]]) -> bool:
    """Deterministic even-odd ray-casting point-in-polygon."""
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside
