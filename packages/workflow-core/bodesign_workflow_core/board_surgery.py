"""Castellated / stamp-module board-surgery wrapper (EPIC refs-derived-design, 切面 3 / DD-5).

Castellated (half-plated-through) edge pads — the defining feature of a stamp /
SoM module — cannot be safely produced through the pcbnew Python API paths that
are known to segfault the interpreter (direct SetTextSize on a freshly-built
PCB_TEXT, certain pad-primitive mutations on an unsaved board). DD-5's answer:
generate the castellation geometry as an S-EXPRESSION text-layer injection into
the ``.kicad_pcb`` file — a byte-level, deterministic, segfault-free path — and
HARD-REFUSE any request that would drive the known-unsafe pcbnew mutation path.

This module is pure-python + core-side: it emits the S-expression fragments and
validates the request; the ee worker applies the injection to a real board file.
No pcbnew import here (so it is testable on a bare host, and cannot itself hit
the segfault path).

Data taxonomy (BINDING):
  * CastellationRequest — validated spec for a castellated edge: which edge,
    pad pitch/count/size, plating. NOT a free-form dict — every field checked.
  * CastellatedPad      — one half-hole edge pad's geometry + S-expr fragment.
  * BoardSurgeryError   — typed fail-fast (BOARD_SURGERY_UNSAFE_PATH etc.).
  * build_castellation  — request → list[CastellatedPad] + injectable S-expr.
    Done IFF every pad's geometry is on-edge and the path is the safe S-expr one.
  * assert_safe_surgery_path — DD-5 guard: raises if a caller asks for the
    known-segfault pcbnew mutation path instead of S-expr injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── typed error codes (plan errors.md, BINDING) ─────────────────────────────
BOARD_SURGERY_UNSAFE_PATH = "BOARD_SURGERY_UNSAFE_PATH"
CASTELLATION_SPEC_INVALID = "CASTELLATION_SPEC_INVALID"

_EDGES = {"LEFT", "RIGHT", "TOP", "BOTTOM"}

# Known-unsafe pcbnew mutation entry points that segfault on an unsaved/partial
# board (DD-5 evidence). A request routing through any of these is refused; the
# only sanctioned path is "sexpr_injection".
UNSAFE_PATHS = frozenset({
    "pcbnew_settextsize",       # SetTextSize on a fresh PCB_TEXT → segfault
    "pcbnew_pad_primitive",     # direct pad-primitive mutation on unsaved board
    "pcbnew_direct",            # any generic "just call pcbnew" path
})
SAFE_PATH = "sexpr_injection"


class BoardSurgeryError(ValueError):
    """Deterministic fail-fast error for the board-surgery family."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        self.code = code
        self.detail: dict[str, Any] = dict(detail)
        super().__init__(f"{code}: {message}")


@dataclass(slots=True)
class CastellationRequest:
    edge: str            # one of _EDGES — the frozen board edge to castellate
    pad_count: int
    pitch_mm: float
    pad_width_mm: float
    pad_height_mm: float
    drill_mm: float
    net_names: list[str] = field(default_factory=list)  # optional per-pad nets
    provenance: str = ""  # SSOT anchor (stamp-module footprint spec)

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge": self.edge,
            "pad_count": self.pad_count,
            "pitch_mm": self.pitch_mm,
            "pad_width_mm": self.pad_width_mm,
            "pad_height_mm": self.pad_height_mm,
            "drill_mm": self.drill_mm,
            "net_names": list(self.net_names),
            "provenance": self.provenance,
        }


@dataclass(slots=True)
class CastellatedPad:
    index: int
    net: str | None
    x_mm: float
    y_mm: float
    sexpr: str  # the injectable S-expression pad fragment

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "net": self.net,
            "x_mm": round(self.x_mm, 4),
            "y_mm": round(self.y_mm, 4),
            "sexpr": self.sexpr,
        }


def parse_castellation_request(data: dict[str, Any]) -> CastellationRequest:
    """Validate + parse a castellation spec (fail-fast on bad shape / no fabrication)."""
    if not isinstance(data, dict):
        raise BoardSurgeryError(CASTELLATION_SPEC_INVALID, "castellation spec must be an object")
    edge = data.get("edge")
    if edge not in _EDGES:
        raise BoardSurgeryError(
            CASTELLATION_SPEC_INVALID,
            f"edge {edge!r} invalid (allowed: {sorted(_EDGES)})", edge=edge)
    numeric = ("pad_count", "pitch_mm", "pad_width_mm", "pad_height_mm", "drill_mm")
    vals: dict[str, float] = {}
    for key in numeric:
        v = data.get(key)
        if not isinstance(v, (int, float)) or v <= 0:
            raise BoardSurgeryError(
                CASTELLATION_SPEC_INVALID,
                f"`{key}` must be a positive number, got {v!r}", field=key)
        vals[key] = float(v)
    if int(vals["pad_count"]) != vals["pad_count"]:
        raise BoardSurgeryError(
            CASTELLATION_SPEC_INVALID, "pad_count must be an integer", field="pad_count")
    # No-fabrication: a stamp-module castellation must trace to an SSOT anchor.
    if not data.get("provenance"):
        raise BoardSurgeryError(
            CASTELLATION_SPEC_INVALID,
            "castellation spec missing `provenance` — a stamp-module edge must "
            "trace to an SSOT footprint anchor (天條 2 no-fabrication)")
    net_names = data.get("net_names") or []
    if not isinstance(net_names, list):
        raise BoardSurgeryError(CASTELLATION_SPEC_INVALID, "net_names must be a list")
    return CastellationRequest(
        edge=edge,
        pad_count=int(vals["pad_count"]),
        pitch_mm=vals["pitch_mm"],
        pad_width_mm=vals["pad_width_mm"],
        pad_height_mm=vals["pad_height_mm"],
        drill_mm=vals["drill_mm"],
        net_names=[str(n) for n in net_names],
        provenance=str(data["provenance"]),
    )


def assert_safe_surgery_path(path: str) -> None:
    """DD-5 guard: refuse the known-segfault pcbnew mutation paths.

    The only sanctioned castellation path is S-expression injection. Any request
    naming an UNSAFE_PATHS entry raises BOARD_SURGERY_UNSAFE_PATH (fail-fast) —
    bodesign never drives a path known to crash the interpreter and corrupt the
    board file.
    """
    if path in UNSAFE_PATHS:
        raise BoardSurgeryError(
            BOARD_SURGERY_UNSAFE_PATH,
            f"refused board-surgery path {path!r} — a known segfault path (DD-5). "
            f"Use {SAFE_PATH!r} (S-expression text-layer injection) instead.",
            requested_path=path, safe_path=SAFE_PATH)
    if path != SAFE_PATH:
        raise BoardSurgeryError(
            BOARD_SURGERY_UNSAFE_PATH,
            f"unknown board-surgery path {path!r}; only {SAFE_PATH!r} is sanctioned.",
            requested_path=path, safe_path=SAFE_PATH)


def _pad_sexpr(index: int, net: str | None, x: float, y: float,
               req: CastellationRequest) -> str:
    """Emit one castellated pad as an injectable KiCad S-expression fragment.

    A castellated pad is a rectangular SMD-on-edge pad with a plated half-hole:
    modelled as an ``oval`` thru-hole pad clipped to the board edge. Deterministic
    text — no pcbnew object construction (that is the segfault path we avoid)."""
    net_clause = f' (net {index} "{net}")' if net else ""
    return (
        f'(pad "{index + 1}" thru_hole oval '
        f'(at {x:.4f} {y:.4f}) '
        f'(size {req.pad_width_mm:.4f} {req.pad_height_mm:.4f}) '
        f'(drill {req.drill_mm:.4f}) '
        f'(layers "*.Cu" "*.Mask"){net_clause} '
        f'(property "castellated" "true"))'
    )


def build_castellation(
    req: CastellationRequest,
    board_outline: dict[str, Any],
    *,
    path: str = SAFE_PATH,
) -> dict[str, Any]:
    """Build castellated edge pads as S-expression injection (segfault-free).

    Validates the surgery path (DD-5), lays ``pad_count`` pads evenly along the
    frozen ``edge`` of the board outline at ``pitch_mm``, and emits each pad's
    injectable S-expression. Returns {path, edge, pads[], sexpr_block}. Pure +
    deterministic; the ee worker injects ``sexpr_block`` into the real board file.
    """
    assert_safe_surgery_path(path)
    w = float(board_outline.get("width_mm", 0) or 0)
    h = float(board_outline.get("height_mm", 0) or 0)
    if w <= 0 or h <= 0:
        raise BoardSurgeryError(
            CASTELLATION_SPEC_INVALID,
            "board_outline must carry positive width_mm/height_mm to place "
            "castellated pads on an edge (never guessed).",
            board_outline=board_outline)

    n = req.pad_count
    total_span = (n - 1) * req.pitch_mm
    # center the pad row along the edge
    if req.edge in {"TOP", "BOTTOM"}:
        start = (w - total_span) / 2.0
        y = 0.0 if req.edge == "TOP" else h
        coords = [(start + i * req.pitch_mm, y) for i in range(n)]
    else:  # LEFT / RIGHT
        start = (h - total_span) / 2.0
        x = 0.0 if req.edge == "LEFT" else w
        coords = [(x, start + i * req.pitch_mm) for i in range(n)]

    pads: list[CastellatedPad] = []
    for i, (x, y) in enumerate(coords):
        net = req.net_names[i] if i < len(req.net_names) else None
        pads.append(CastellatedPad(index=i, net=net, x_mm=x, y_mm=y,
                                   sexpr=_pad_sexpr(i, net, x, y, req)))

    sexpr_block = "\n".join(p.sexpr for p in pads)
    return {
        "path": path,
        "edge": req.edge,
        "pad_count": n,
        "provenance": req.provenance,
        "pads": [p.to_dict() for p in pads],
        "sexpr_block": sexpr_block,
        "safe": True,
    }
