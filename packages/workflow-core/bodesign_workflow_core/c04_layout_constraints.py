"""C04 layout constraint package — constraint-first, draft only.

C04 is owned by the layout engineer (bodesign_role = "constraints"). bodesign does
NOT place parts, route, or emit Gerbers here; it assembles the explicit placement
constraints the layout engineer needs from the two upstream hard-constraint sources
that already exist in runtime:

- C01 `Interface_Constraints.json` — preferred component faces, visibility/RF/acoustic
  placement intent, exposed components.
- C03 `Mechanical_Constraint_Export.json` — component heights, connector edge openings,
  heat sources, antenna keepouts, battery envelope, ESD/EMC notes.

Board outline, mounting holes, placement coordinates, and stackup stay PENDING and
layout-owned — they are never fabricated. Inputs may be passed explicitly or, when a
project folder already holds the upstream exports, auto-loaded from it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .c03_mechanical_constraints import C03_OUTPUT

C04_FOLDER = Path("C04-Layout")
C04_CONSTRAINTS_OUTPUT = C04_FOLDER / "Layout_Constraints.json"
C04_PLACEMENT_OUTPUT = C04_FOLDER / "Placement_Constraints.md"

_C01_CONSTRAINTS_REL = Path("C01-ID") / "Interface_Constraints.json"

# Constraint groups the layout engineer owns — bodesign never guesses these.
_LAYOUT_OWNED_PENDING = [
    {"item": "board_outline", "owner": "layout engineer", "note": "Final board outline/dimensions are layout/ME owned."},
    {"item": "mounting_holes", "owner": "layout engineer", "note": "Mounting hole positions come from the enclosure (C02) + board."},
    {"item": "placement_coordinates", "owner": "layout engineer", "note": "Exact XY placement and rotation are layout decisions."},
    {"item": "layer_stackup", "owner": "layout engineer", "note": "Stackup/impedance targets are layout/fab decisions unless given."},
]


@dataclass(slots=True)
class C04LayoutReadiness:
    folder: str
    present_groups: list[str]
    pending: list[dict[str, Any]]
    constraints_present: bool
    placement_doc_present: bool
    status: str
    next_step: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "present_groups": list(self.present_groups),
            "pending": list(self.pending),
            "constraints_present": self.constraints_present,
            "placement_doc_present": self.placement_doc_present,
            "status": self.status,
            "next_step": self.next_step,
            "board_ready": False,
            "gerber_ready": False,
            "layout_approval": False,
        }


@dataclass(slots=True)
class C04LayoutResult:
    folder: str
    files: list[str]
    constraints: dict[str, Any]
    readiness: C04LayoutReadiness
    pending: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "files": list(self.files),
            "constraints": self.constraints,
            "pending": list(self.pending),
            "readiness": self.readiness.to_dict(),
            "layout_approval": False,
        }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _c03_constraints(c03: dict[str, Any] | None) -> dict[str, Any]:
    if not c03:
        return {}
    # Accept either the raw export payload ({constraints: {...}}) or the inner dict.
    return c03.get("constraints", c03) if isinstance(c03, dict) else {}


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return len(value) > 0
    return True


def _build_layout_constraints(c01: dict[str, Any] | None, c03: dict[str, Any] | None) -> dict[str, Any]:
    c03c = _c03_constraints(c03)
    c01 = c01 or {}
    placement_intent = []
    if isinstance(c01.get("downstream_targets"), dict):
        placement_intent = c01["downstream_targets"].get("C04") or []

    return {
        "schema": "bodesign.c04.layout_constraints.v1",
        "state": "drafted",
        "source": {
            "layer": "C04",
            "from_c01": bool(c01),
            "from_c03": bool(c03c),
            "notes": "Assembled from C01 interface intent + C03 mechanical constraints. Board outline/placement/stackup remain layout-owned.",
        },
        "placement_intent": placement_intent,
        "exposed_components": c01.get("exposed_components", []),
        "component_heights": c03c.get("component_heights", []),
        "connector_edge_openings": c03c.get("connector_openings", []),
        "heat_zones": c03c.get("heat_sources", []),
        "antenna_keepouts": c03c.get("antenna_keepouts", []),
        "battery_zone": c03c.get("battery_envelope"),
        "emc_esd_notes": c03c.get("esd_emc_notes", []),
        "open_decisions": [
            "board outline, mounting holes, and exact placement remain layout-engineer decisions",
            "layer stackup / impedance targets require layout + fab confirmation",
        ],
    }


_GROUP_KEYS = [
    "placement_intent", "exposed_components", "component_heights",
    "connector_edge_openings", "heat_zones", "antenna_keepouts", "battery_zone", "emc_esd_notes",
]


def _render_placement_md(constraints: dict[str, Any]) -> str:
    lines = [
        "# C04 Layout — Placement Constraints (DRAFT)",
        "",
        "> Constraint-first handoff for the layout engineer. bodesign does not place, route, or",
        "> emit Gerbers here. Board outline, mounting holes, exact placement, and stackup are",
        "> layout-owned and remain open below.",
        "",
        "## Inputs",
        f"- From C01 interface constraints: {'yes' if constraints['source']['from_c01'] else 'MISSING'}",
        f"- From C03 mechanical constraints: {'yes' if constraints['source']['from_c03'] else 'MISSING'}",
        "",
        "## Assembled constraints",
    ]
    for key in _GROUP_KEYS:
        value = constraints.get(key)
        present = _nonempty(value)
        lines.append(f"- **{key}**: {'present' if present else '— (not provided upstream)'}")
    lines += [
        "",
        "## Layout-owned (open — not fabricated)",
    ]
    for item in _LAYOUT_OWNED_PENDING:
        lines.append(f"- **{item['item']}** — owner: {item['owner']}. {item['note']}")
    lines += ["", "## Open decisions"]
    for dec in constraints.get("open_decisions", []):
        lines.append(f"- {dec}")
    return "\n".join(lines) + "\n"


def emit_c04_layout_package(
    out_dir: str | Path,
    c01: dict[str, Any] | None = None,
    c03: dict[str, Any] | None = None,
) -> C04LayoutResult:
    """Assemble the C04 layout constraint package from C01/C03 inputs.

    Inputs may be passed explicitly; when omitted, they are auto-loaded from the
    project folder's existing C01/C03 exports if present. Nothing is fabricated:
    absent upstream data simply leaves a constraint group empty and pending.
    """
    root = Path(out_dir)
    if c01 is None:
        c01 = _load_json(root / _C01_CONSTRAINTS_REL)
    if c03 is None:
        c03 = _load_json(root / C03_OUTPUT)

    constraints = _build_layout_constraints(c01, c03)
    files: list[str] = []
    for rel, content in (
        (C04_CONSTRAINTS_OUTPUT, json.dumps(constraints, ensure_ascii=False, indent=2) + "\n"),
        (C04_PLACEMENT_OUTPUT, _render_placement_md(constraints)),
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        files.append(str(rel))

    readiness = assess_c04_layout_readiness(root)
    return C04LayoutResult(str(root), files, constraints, readiness, pending=list(_LAYOUT_OWNED_PENDING))


def assess_c04_layout_readiness(folder: str | Path) -> C04LayoutReadiness:
    root = Path(folder)
    constraints_path = root / C04_CONSTRAINTS_OUTPUT
    placement_path = root / C04_PLACEMENT_OUTPUT
    constraints = _load_json(constraints_path) or {}
    present_groups = [k for k in _GROUP_KEYS if _nonempty(constraints.get(k))]
    constraints_present = constraints_path.exists()
    placement_present = placement_path.exists()

    if not constraints_present:
        status = "missing"
        next_step = "Run bodesign_c04_emit_layout_package with C01/C03 constraints."
    elif not present_groups:
        status = "blocked"
        next_step = "No upstream constraints provided — supply C01 interface and C03 mechanical constraints."
    else:
        status = "layout_constraints_drafted"
        next_step = "Hand to the layout engineer for board outline, placement, and stackup decisions."

    return C04LayoutReadiness(
        folder=str(root),
        present_groups=present_groups,
        pending=list(_LAYOUT_OWNED_PENDING),
        constraints_present=constraints_present,
        placement_doc_present=placement_present,
        status=status,
        next_step=next_step,
    )
