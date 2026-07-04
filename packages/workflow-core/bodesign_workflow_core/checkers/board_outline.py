"""M2-2 — board-outline geometry (core port of proven skills logic).

Ports the deterministic edge→segment expansion and point-to-segment distance
math from the proven skills implementation
(`skills/bodesign/engines/kicad/scripts/analyze_pcb.py:5797-5868`,
`extract_board_outline` at :1212) into an importable, pure-python core module —
NO pcbnew, NO LLM. This is the parser that retires the M1-3 board-edge-keepout
stub and unlocks the board-outline-dependent T-B controls
(mech.board-edge-keepout, mech.mounting-hole-clearance, flex.*).

Input contract (per the M2 scope decision): the board outline is materialized
UPSTREAM into `ir["board_outline"]["edges"]` in the already-parsed shape that
`extract_board_outline` emits — a list of edge dicts:
  {"type": "line", "start": [x, y], "end": [x, y]}
  {"type": "rect", "start": [x, y], "end": [x, y]}
  {"type": "arc"|"circle"|"polygon"|"curve", ...}
This module does NOT parse .kicad_pcb s-expr itself (that stays in the skills
engine / an upstream materialiser); it consumes the parsed edges. Feeding a
gerber-only board with no Edge.Cuts remains a backlog gap (a board with no
edges yields no segments → the caller must fail fast, never silently pass).

Determinism: pure float math; same edges + same point → byte-identical distance.
"""

import math
from typing import Any


def edges_to_segments(edges: list[dict[str, Any]]) -> list[tuple[float, float, float, float]]:
    """Expand board-outline edges into straight (x1,y1,x2,y2) segments.

    Taxonomy:
      - name: edges_to_segments
      - represents: the deterministic reduction of Edge.Cuts primitives to the
        straight segments a point-to-segment distance can run against.
      - input: the parsed `ir["board_outline"]["edges"]` list (line/rect/... dicts).
      - output: list of (x1,y1,x2,y2) segment tuples. A `line` → one segment; a
        `rect` → its four sides. arc/circle/polygon/curve are NOT linearised here
        (they contribute no straight segments) — an honest limitation, not a
        silent approximation.
      - must NOT be read as: a full outline tessellation — curved primitives are
        deliberately skipped rather than crudely chorded, to avoid fabricating a
        clearance number from an approximated edge.
      - complete when: every line/rect edge has been expanded.
    """
    segs: list[tuple[float, float, float, float]] = []
    for edge in edges:
        etype = edge.get("type", "")
        if etype == "line":
            s = edge.get("start")
            e = edge.get("end")
            if s and e:
                segs.append((float(s[0]), float(s[1]), float(e[0]), float(e[1])))
        elif etype == "rect":
            s = edge.get("start")
            e = edge.get("end")
            if s and e:
                x1, y1, x2, y2 = float(s[0]), float(s[1]), float(e[0]), float(e[1])
                segs.append((x1, y1, x2, y1))
                segs.append((x2, y1, x2, y2))
                segs.append((x2, y2, x1, y2))
                segs.append((x1, y2, x1, y1))
        # arc/circle/polygon/curve: not linearised (see taxonomy) — skipped.
    return segs


def point_to_segment_distance(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """2D point-to-segment distance (EQ-104 port, analyze_pcb.py:5808).

    Taxonomy:
      - name: point_to_segment_distance
      - represents: the exact deterministic clearance metric — shortest distance
        from a point to a line segment (clamped to the segment, not the infinite
        line).
      - input: point (px,py) and segment endpoints (x1,y1)-(x2,y2).
      - output: the Euclidean distance (float, mm).
      - must NOT be read as: distance to the infinite line — the parameter t is
        clamped to [0,1] so endpoints are honoured.
      - complete when: returns the clamped distance (degenerate zero-length
        segment → distance to the shared endpoint).
    """
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - x1 - t * dx, py - y1 - t * dy)


def min_clearance_to_edge(
    px: float, py: float, segments: list[tuple[float, float, float, float]]
) -> float:
    """Minimum distance from a point to any board-edge segment.

    Returns math.inf when there are no segments — the CALLER must treat that as
    "no board outline available" and fail fast (no-silent-fallback), never as a
    passing clearance.
    """
    best = math.inf
    for x1, y1, x2, y2 in segments:
        d = point_to_segment_distance(px, py, x1, y1, x2, y2)
        if d < best:
            best = d
    return best
