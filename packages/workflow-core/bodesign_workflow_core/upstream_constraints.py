"""Upstream frozen-constraint contract + lifecycle gate (EPIC refs-derived-design, 切面 2/4).

The paradigm inversion's second half: downstream C04 generation must CONSUME
frozen upstream constraints rather than invent geometry. Two enforcement points:

  * lifecycle directionality (切面 4): a placement/castellated verb REQUIRES the
    upstream frozen-constraint JSON as a mandatory input; absent → typed
    ``UPSTREAM_CONSTRAINT_MISSING`` (fail-fast, no fabrication).
  * connector-face freeze (切面 2 / DD-4): a connector's board face/edge is a
    FROZEN upstream constraint owned by C01 face-layout, NOT a C04 degree of
    freedom. An attempt to move a connector off its owner-specified face raises
    ``CONNECTOR_FACE_CONFLICT``. C04 may only place WITHIN the frozen face.

Pure-python, core-side (no pcbnew). The face-placement solver is deterministic
(same input → same output) so it is reproducible and unit-testable on a bare
host; the actual pcbnew mutation lives in the ee worker and consumes this
solver's output.

Data taxonomy (BINDING — every name is a contract, not decoration):
  * FaceLayout          — C01's frozen connector→face map. input: a dict/JSON;
                          output: validated {schema, frozen, connectors[]}.
                          NOT re-authorable by C04.
  * ConnectorPlacement  — one connector's resolved board face + edge span +
                          provenance. output of solve_face_placement.
  * UpstreamConstraintError — typed fail-fast (code + detail). NOT a warning.
  * require_upstream_constraints — lifecycle chokepoint a downstream verb calls
                          FIRST; returns loaded constraints or raises. Done IFF
                          every required upstream JSON is present + well-formed.
  * assert_face_frozen  — DD-4 guard: raises if a requested face != frozen face.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .c03_mechanical_constraints import C03_OUTPUT

# ── typed error codes (plan errors.md, BINDING) ─────────────────────────────
UPSTREAM_CONSTRAINT_MISSING = "UPSTREAM_CONSTRAINT_MISSING"
CONNECTOR_FACE_CONFLICT = "CONNECTOR_FACE_CONFLICT"
CONSTRAINT_SCHEMA_INVALID = "CONSTRAINT_SCHEMA_INVALID"

FACE_LAYOUT_SCHEMA = "bodesign.c01.face_layout.v1"
ENVELOPE_SCHEMA = "bodesign.c02.envelope.v1"

# Board faces/edges a connector may be frozen to. A stamp/edge connector binds
# to a board EDGE (its opening cuts that edge); a top/bottom-mounted part binds
# to a board SURFACE. Both are frozen upstream degrees, never C04's to change.
_EDGES = {"LEFT", "RIGHT", "TOP", "BOTTOM"}          # in-plane board edges
_SURFACES = {"FRONT", "BACK"}                         # copper surfaces (F.Cu/B.Cu)
VALID_FACES = _EDGES | _SURFACES

# The upstream JSON files each downstream C04 verb may require, by logical key.
UPSTREAM_FILES: dict[str, tuple[Path, str]] = {
    "face_layout": (Path("C01-ID") / "Face_Layout.json", FACE_LAYOUT_SCHEMA),
    "envelope": (Path("C02-ME") / "Envelope_Constraint.json", ENVELOPE_SCHEMA),
    # BR_20260901e: derived from C03's own emitter constant, not spelled again.
    # C01/C02 entries below are NOT the same case — they are C04's independent
    # expectations of upstream files that no C0x_OUTPUTS constant declares (see
    # the BR's "measured NOT duplicate" table), so there is nothing to derive
    # them from and inventing a link would be worse than the literal.
    "mechanical": (C03_OUTPUT, ""),
}


class UpstreamConstraintError(ValueError):
    """Deterministic fail-fast error for the upstream-constraint family.

    Attributes:
      code: stable code (UPSTREAM_CONSTRAINT_MISSING / CONNECTOR_FACE_CONFLICT / ...).
      detail: structured payload the caller MUST act on (never a default sub).
    """

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        self.code = code
        self.detail: dict[str, Any] = dict(detail)
        super().__init__(f"{code}: {message}")


@dataclass(slots=True)
class ConnectorPlacement:
    ref: str
    component: str
    face: str          # frozen upstream face/edge (one of VALID_FACES)
    edge_span: dict[str, Any]  # deterministic placement band within the frozen face
    provenance: str    # SSOT anchor this face binding traces back to
    movable_by_c04: bool = False  # DD-4: face is frozen; C04 cannot move it off-face

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "component": self.component,
            "face": self.face,
            "edge_span": dict(self.edge_span),
            "provenance": self.provenance,
            "movable_by_c04": self.movable_by_c04,
        }


@dataclass(slots=True)
class FaceLayout:
    """C01's frozen connector→face map (schema bodesign.c01.face_layout.v1)."""

    schema: str
    frozen: bool
    connectors: list[dict[str, Any]]
    board_outline: dict[str, Any] = field(default_factory=dict)

    def face_of(self, ref: str) -> str | None:
        for c in self.connectors:
            if c.get("ref") == ref:
                return c.get("face")
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "frozen": self.frozen,
            "connectors": list(self.connectors),
            "board_outline": dict(self.board_outline),
        }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise UpstreamConstraintError(
            CONSTRAINT_SCHEMA_INVALID,
            f"upstream constraint file is not valid JSON: {path}: {exc}",
            path=str(path),
        ) from exc


def parse_face_layout(data: dict[str, Any]) -> FaceLayout:
    """Validate + parse a C01 Face_Layout.json payload (fail-fast on bad shape)."""
    if not isinstance(data, dict):
        raise UpstreamConstraintError(
            CONSTRAINT_SCHEMA_INVALID, "face layout must be a JSON object")
    connectors = data.get("connectors")
    if not isinstance(connectors, list) or not connectors:
        raise UpstreamConstraintError(
            CONSTRAINT_SCHEMA_INVALID,
            "face layout requires a non-empty `connectors` list",
            got=type(connectors).__name__,
        )
    for i, c in enumerate(connectors):
        if not isinstance(c, dict):
            raise UpstreamConstraintError(
                CONSTRAINT_SCHEMA_INVALID, f"connectors[{i}] must be an object")
        for key in ("ref", "face"):
            if not c.get(key):
                raise UpstreamConstraintError(
                    CONSTRAINT_SCHEMA_INVALID,
                    f"connectors[{i}] missing required `{key}`", index=i)
        face = c["face"]
        if face not in VALID_FACES:
            raise UpstreamConstraintError(
                CONSTRAINT_SCHEMA_INVALID,
                f"connectors[{i}].face {face!r} invalid (allowed: {sorted(VALID_FACES)})",
                index=i, face=face)
        # No-fabrication: a frozen face binding must trace to an SSOT anchor.
        if not c.get("provenance"):
            raise UpstreamConstraintError(
                CONSTRAINT_SCHEMA_INVALID,
                f"connectors[{i}] ({c['ref']}) missing `provenance` — a frozen face "
                "must trace to an SSOT anchor (天條 2 no-fabrication)",
                index=i, ref=c["ref"])
    return FaceLayout(
        schema=str(data.get("schema", FACE_LAYOUT_SCHEMA)),
        frozen=bool(data.get("frozen", True)),
        connectors=connectors,
        board_outline=data.get("board_outline") or {},
    )


def require_upstream_constraints(
    folder: str | Path, layer: str, required: list[str]
) -> dict[str, Any]:
    """Lifecycle chokepoint (切面 4): a downstream verb calls this FIRST.

    ``required`` is a list of logical keys from UPSTREAM_FILES (e.g.
    ["face_layout", "mechanical"]). Every one must exist + parse, else
    UPSTREAM_CONSTRAINT_MISSING with the full missing list (all gaps at once,
    not just the first). Returns {key: loaded_json}. No silent fallback.
    """
    root = Path(folder)
    loaded: dict[str, Any] = {}
    missing: list[dict[str, str]] = []
    for key in required:
        if key not in UPSTREAM_FILES:
            raise UpstreamConstraintError(
                CONSTRAINT_SCHEMA_INVALID,
                f"unknown upstream constraint key {key!r} "
                f"(allowed: {sorted(UPSTREAM_FILES)})", key=key)
        rel, _schema = UPSTREAM_FILES[key]
        path = root / rel
        data = _load_json(path)
        if data is None:
            missing.append({"key": key, "expected_path": str(rel)})
        else:
            loaded[key] = data
    if missing:
        raise UpstreamConstraintError(
            UPSTREAM_CONSTRAINT_MISSING,
            f"{layer}: required upstream frozen-constraint input(s) absent — "
            "downstream generation refuses (切面 4 lifecycle directionality). "
            f"Freeze them upstream first: {[m['key'] for m in missing]}",
            layer=layer, missing=missing, required=list(required),
        )
    return loaded


def assert_face_frozen(face_layout: FaceLayout, ref: str, requested_face: str) -> None:
    """DD-4 guard: a connector's face is a FROZEN upstream constraint.

    Raises CONNECTOR_FACE_CONFLICT when C04 requests a face != the frozen face.
    The connector's face is not a C04 degree of freedom — C04 places WITHIN it.
    """
    frozen = face_layout.face_of(ref)
    if frozen is None:
        raise UpstreamConstraintError(
            CONNECTOR_FACE_CONFLICT,
            f"connector {ref} has no frozen face in the C01 face layout — "
            "it must be frozen upstream before C04 may place it.",
            ref=ref, requested_face=requested_face)
    if requested_face != frozen:
        raise UpstreamConstraintError(
            CONNECTOR_FACE_CONFLICT,
            f"connector {ref}: C04 requested face {requested_face!r} but the "
            f"frozen upstream face is {frozen!r} (DD-4: face is not a C04 "
            "degree of freedom).",
            ref=ref, requested_face=requested_face, frozen_face=frozen)


def _edge_span_for(face: str, outline: dict[str, Any], slot: int, total: int) -> dict[str, Any]:
    """Deterministically band a connector along its frozen edge/surface.

    For an in-plane EDGE, connectors sharing that edge are evenly distributed
    along it (slot/total). For a SURFACE, the whole face is the placement zone.
    Pure geometry from the outline; no pcbnew. When the outline is unknown the
    span is normalized [0,1] fractions (the ee worker scales to real board mm).
    """
    w = float(outline.get("width_mm", 0) or 0)
    h = float(outline.get("height_mm", 0) or 0)
    # normalized fractional band along the edge, deterministic by slot
    lo = slot / total if total else 0.0
    hi = (slot + 1) / total if total else 1.0
    span: dict[str, Any] = {"face": face, "band_lo": round(lo, 4), "band_hi": round(hi, 4)}
    if face in _EDGES and w and h:
        if face in {"TOP", "BOTTOM"}:
            span["x_mm"] = [round(lo * w, 3), round(hi * w, 3)]
            span["y_mm"] = 0.0 if face == "TOP" else round(h, 3)
        else:  # LEFT / RIGHT
            span["y_mm"] = [round(lo * h, 3), round(hi * h, 3)]
            span["x_mm"] = 0.0 if face == "LEFT" else round(w, 3)
    return span


# Rotation (deg) that orients a connector body so its opening faces OUTWARD from
# the frozen edge. Deterministic per edge; a SURFACE-mounted part keeps 0.
_EDGE_ROTATION = {"TOP": 0.0, "BOTTOM": 180.0, "LEFT": 90.0, "RIGHT": 270.0}


def placement_to_coords(
    placements: list[ConnectorPlacement], outline: dict[str, Any]
) -> dict[str, list[float]]:
    """Adapter (切面 2 worker-side): ConnectorPlacement[] → net2pcb_board `placement`.

    `net2pcb_board` consumes a concrete ``{ref: [x_mm, y_mm, rot_deg]}`` map. This
    converts each frozen-face placement's ``edge_span`` into that concrete anchor:
    the connector lands at the CENTRE of its deterministic band along the frozen
    edge, rotated so its opening faces outward. Pure geometry, no pcbnew, so the
    conversion is unit-testable on a bare host; the ee worker feeds the result to
    net2pcb_board to actually mutate the .kicad_pcb.

    Requires a real board outline (width_mm/height_mm > 0) — a frozen face without
    a physical board to land on is fail-fast (no fabricated coordinate, 天條 2).
    """
    w = float(outline.get("width_mm", 0) or 0)
    h = float(outline.get("height_mm", 0) or 0)
    if w <= 0 or h <= 0:
        raise UpstreamConstraintError(
            CONSTRAINT_SCHEMA_INVALID,
            "placement_to_coords needs a real board outline (positive "
            "width_mm/height_mm) to resolve a frozen-face band into a coordinate "
            "(天條 2: never fabricate a placement on an unknown board).",
            outline=outline,
        )
    coords: dict[str, list[float]] = {}
    for p in placements:
        face = p.face
        lo = float(p.edge_span.get("band_lo", 0.0))
        hi = float(p.edge_span.get("band_hi", 1.0))
        mid = (lo + hi) / 2.0
        if face in {"TOP", "BOTTOM"}:
            x = round(mid * w, 3)
            y = 0.0 if face == "TOP" else round(h, 3)
        elif face in {"LEFT", "RIGHT"}:
            x = 0.0 if face == "LEFT" else round(w, 3)
            y = round(mid * h, 3)
        else:  # SURFACE (FRONT/BACK): centre of the board face
            x = round(w / 2.0, 3)
            y = round(h / 2.0, 3)
        coords[p.ref] = [x, y, _EDGE_ROTATION.get(face, 0.0)]
    return coords


def solve_face_placement(face_layout: FaceLayout) -> list[ConnectorPlacement]:
    """Deterministic constraint-driven placement (切面 2): bind each connector to
    its frozen face/edge and compute a placement band. Same input → same output.

    Connectors on the same edge are evenly distributed along it (stable order by
    ref) so a USB-C frozen to BOTTOM lands on the bottom edge — a fact C04 cannot
    override. Returns one ConnectorPlacement per connector, all movable_by_c04=False.
    """
    outline = face_layout.board_outline
    # group by face, stable by ref for determinism
    by_face: dict[str, list[dict[str, Any]]] = {}
    for c in sorted(face_layout.connectors, key=lambda x: str(x.get("ref"))):
        by_face.setdefault(c["face"], []).append(c)
    placements: list[ConnectorPlacement] = []
    for face, group in by_face.items():
        total = len(group)
        for slot, c in enumerate(group):
            placements.append(
                ConnectorPlacement(
                    ref=c["ref"],
                    component=c.get("component", c["ref"]),
                    face=face,
                    edge_span=_edge_span_for(face, outline, slot, total),
                    provenance=c.get("provenance", ""),
                    movable_by_c04=False,
                )
            )
    # stable global order by ref
    placements.sort(key=lambda p: p.ref)
    return placements
