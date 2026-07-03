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
from .feasibility import classify_product_feasibility
from .readiness_common import boundary_next_step, root_guard
from .guide_dod import guide_compliance_for

C04_FOLDER = Path("C04-Layout")
C04_CONSTRAINTS_OUTPUT = C04_FOLDER / "Layout_Constraints.json"
C04_PLACEMENT_OUTPUT = C04_FOLDER / "Placement_Constraints.md"

_C01_CONSTRAINTS_REL = Path("C01-ID") / "Interface_Constraints.json"
_C03_FOLDER = Path("C03-EE")

# Feasibility-triage signals bodesign accepts. Anything else is ignored (not guessed).
_FEASIBILITY_KEYS = {
    "layer_count", "finest_bga_pitch_mm", "hdi_required", "high_speed_nets",
    "rf", "component_count", "board_area_mm2", "source",
}

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
    root_visible: bool = True
    warnings: list[str] = field(default_factory=list)
    upstream: dict[str, Any] = field(default_factory=dict)
    feasibility: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "folder": self.folder,
            "present_groups": list(self.present_groups),
            "pending": list(self.pending),
            "constraints_present": self.constraints_present,
            "placement_doc_present": self.placement_doc_present,
            "status": self.status,
            "next_step": self.next_step,
            "root_visible": self.root_visible,
            "warnings": list(self.warnings),
            "upstream": dict(self.upstream),
            "upstream_fulfilled": bool(self.upstream.get("fulfilled")) if self.upstream else None,
            "feasibility": dict(self.feasibility),
            "feasibility_tier": self.feasibility.get("tier") if self.feasibility else None,
            "board_ready": False,
            "gerber_ready": False,
            "layout_approval": False,
        }
        gc = guide_compliance_for(self.folder, "c04", root_visible=self.root_visible)
        if gc is not None:
            d["guide_compliance"] = gc
            d["dod_ok"] = bool(gc.get("dod_ok"))
        return d


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


def _c03_netlist_present(root: Path) -> bool:
    """True when C03 has emitted at least one KiCad netlist (.net) — the disk-of-truth
    evidence that C00's components were realised into electrical connectivity and can
    actually land on the board."""
    c03 = root / _C03_FOLDER
    return c03.is_dir() and any(c03.glob("*.net"))


def _assess_upstream_fulfilment(root: Path) -> dict[str, Any]:
    """Honest cross-stage check: has C03 electrical design actually happened?

    C04 layout constraints are premature — and misleading — when no netlist exists,
    because it means C00's main_components have NOT been realised into a board. No
    silent pass: an empty upstream produces an explicit gap list, not a clean draft.
    """
    c03_dir = root / _C03_FOLDER
    mech = root / C03_OUTPUT
    netlist = _c03_netlist_present(root)
    gaps: list[str] = []
    if not c03_dir.is_dir():
        gaps.append("C03-EE/ absent — the electrical-design stage has not run; no schematic/BOM/netlist exists")
    if not netlist:
        gaps.append(
            "C03 netlist (.net) missing — C00 main_components have not been realised into an "
            "electrical netlist, so nothing has landed on the board yet"
        )
    if not mech.exists():
        gaps.append("C03-EE/Mechanical_Constraint_Export.json missing — no mechanical constraints exported from C03")
    return {
        "c03_dir_present": c03_dir.is_dir(),
        "c03_netlist_present": netlist,
        "c03_mechanical_export_present": mech.exists(),
        "gaps": gaps,
        "fulfilled": not gaps,
    }


def _assess_feasibility(signals: dict[str, Any] | None) -> dict[str, Any]:
    """Run the feasibility triage when signals are supplied.

    Honesty model (no-silent-fallback): with no complexity signals bodesign does NOT
    guess a tier — a fabricated Tier 1 would understate the routing wall. It returns
    tier=None / label=not-assessed and asks for the signals instead.
    """
    kwargs = {k: v for k, v in (signals or {}).items() if k in _FEASIBILITY_KEYS}
    if not kwargs:
        return {
            "tier": None,
            "label": "not-assessed",
            "reason": (
                "No feasibility signals supplied (layer_count / finest_bga_pitch_mm / hdi_required / "
                "high_speed_nets / rf). bodesign does not guess a tier — supply C00/C03 complexity "
                "signals to classify the C04 delivery ceiling."
            ),
        }
    return classify_product_feasibility(**kwargs).to_dict()


def _render_feasibility_upstream(constraints: dict[str, Any]) -> list[str]:
    feas = constraints.get("feasibility") or {}
    up = constraints.get("upstream_fulfilment") or {}
    if not feas and not up:
        return []
    lines = ["", "## Feasibility & upstream fulfilment"]
    tier = feas.get("tier")
    lines.append(
        f"- **Feasibility tier**: {tier if tier is not None else 'not assessed'}"
        + (f" — {feas['label']}" if feas.get("label") else "")
    )
    if feas.get("c04_target"):
        lines.append(f"- **C04 delivery target**: {feas['c04_target']}")
    if feas.get("reason"):
        lines.append(f"- {feas['reason']}")
    fulfilled = up.get("fulfilled")
    lines.append(f"- **Upstream C03 fulfilled**: {'yes' if fulfilled else 'NO — see gaps below'}")
    for g in up.get("gaps", []):
        lines.append(f"  - GAP: {g}")
    return lines


def _build_layout_constraints(
    c01: dict[str, Any] | None,
    c03: dict[str, Any] | None,
    upstream: dict[str, Any] | None = None,
    feasibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    c03c = _c03_constraints(c03)
    c01 = c01 or {}
    placement_intent = []
    if isinstance(c01.get("downstream_targets"), dict):
        placement_intent = c01["downstream_targets"].get("C04") or []

    upstream = upstream or {}
    fulfilled = bool(upstream.get("fulfilled", True))
    return {
        "schema": "bodesign.c04.layout_constraints.v1",
        # Honest state: constraints are only a normal draft when C03 has actually
        # realised the netlist. With no upstream electrical design, the package is
        # blocked-on-upstream, not a clean draft.
        "state": "drafted" if fulfilled else "blocked_on_upstream",
        "source": {
            "layer": "C04",
            "from_c01": bool(c01),
            "from_c03": bool(c03c),
            "notes": "Assembled from C01 interface intent + C03 mechanical constraints. Board outline/placement/stackup remain layout-owned.",
        },
        "upstream_fulfilment": upstream,
        "feasibility": feasibility or {},
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
    lines += _render_feasibility_upstream(constraints)
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
    feasibility_signals: dict[str, Any] | None = None,
) -> C04LayoutResult:
    """Assemble the C04 layout constraint package from C01/C03 inputs.

    Inputs may be passed explicitly; when omitted, they are auto-loaded from the
    project folder's existing C01/C03 exports if present.

    Honesty model (no-silent-fallback): absent upstream is NOT silently treated as a
    clean draft. The emitted package records an explicit `upstream_fulfilment` block
    (C03 dir / netlist / mechanical export presence + a gap list) and, when C03 has
    not realised a netlist, the package `state` is `blocked_on_upstream` rather than
    `drafted` — so a product whose C00 components never landed on a board can never
    look delivered. `feasibility_signals` (optional) runs the tier triage; with no
    signals the tier is reported `not-assessed`, never guessed.
    """
    root = Path(out_dir)
    if c01 is None:
        c01 = _load_json(root / _C01_CONSTRAINTS_REL)
    if c03 is None:
        c03 = _load_json(root / C03_OUTPUT)

    upstream = _assess_upstream_fulfilment(root)
    feasibility = _assess_feasibility(feasibility_signals)
    constraints = _build_layout_constraints(c01, c03, upstream=upstream, feasibility=feasibility)
    files: list[str] = []
    for rel, content in (
        (C04_CONSTRAINTS_OUTPUT, json.dumps(constraints, ensure_ascii=False, indent=2) + "\n"),
        (C04_PLACEMENT_OUTPUT, _render_placement_md(constraints)),
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        files.append(str(rel))

    readiness = assess_c04_layout_readiness(root, feasibility_signals=feasibility_signals)
    return C04LayoutResult(str(root), files, constraints, readiness, pending=list(_LAYOUT_OWNED_PENDING))


def assess_c04_layout_readiness(
    folder: str | Path,
    feasibility_signals: dict[str, Any] | None = None,
) -> C04LayoutReadiness:
    root, visible, warning = root_guard(folder)
    if not visible:
        return C04LayoutReadiness(
            folder=str(root), present_groups=[], pending=list(_LAYOUT_OWNED_PENDING),
            constraints_present=False, placement_doc_present=False,
            status="path-not-visible", next_step=boundary_next_step(folder),
            root_visible=False, warnings=[warning] if warning else [],
        )
    constraints_path = root / C04_CONSTRAINTS_OUTPUT
    placement_path = root / C04_PLACEMENT_OUTPUT
    constraints = _load_json(constraints_path) or {}
    present_groups = [k for k in _GROUP_KEYS if _nonempty(constraints.get(k))]
    constraints_present = constraints_path.exists()
    placement_present = placement_path.exists()

    # Cross-stage fulfilment: has C03 actually realised C00's components into a
    # netlist? This is independent of whether the constraint groups are non-empty.
    upstream = _assess_upstream_fulfilment(root)
    # Prefer the feasibility recorded in the emitted package; else compute from signals.
    feasibility = constraints.get("feasibility") or _assess_feasibility(feasibility_signals)
    tier = feasibility.get("tier")
    warnings: list[str] = []

    if not constraints_present:
        status = "missing"
        next_step = "Run bodesign_c04_emit_layout_package with C01/C03 constraints."
    elif not upstream["fulfilled"]:
        # The load-bearing fix: upstream electrical design is incomplete. Never report
        # 'drafted' — that reads as 'a delivered draft' when in truth no component has
        # landed on the board. This is BLOCKING (no-silent-fallback).
        status = "blocked_upstream_c03_missing"
        warnings.append(
            "C04 constraints exist but upstream C03 has not realised a netlist — C00 "
            "main_components have NOT landed on a board. This is not a delivered draft."
        )
        gap_txt = "; ".join(upstream["gaps"]) or "C03 electrical design incomplete"
        if tier == 3:
            next_step = (
                "Tier-3 product: complete C03 (schematic + netlist), then emit the SI "
                "constraint handoff (emit_si_constraint_export) for pro-EDA routing. "
                f"Upstream gaps: {gap_txt}"
            )
        else:
            next_step = (
                "Run C03 electrical design first (compose_schematic → export_netlist) so "
                f"C00 components are realised, then re-run C04. Upstream gaps: {gap_txt}"
            )
    elif not present_groups:
        status = "blocked"
        next_step = "No upstream constraints provided — supply C01 interface and C03 mechanical constraints."
    elif tier == 3:
        status = "layout_constraints_drafted_tier3_handoff"
        next_step = (
            "Tier-3 delivery ceiling = placement + SI constraints; routing goes to a "
            "professional EDA tool + human SI. Emit the SI constraint handoff "
            "(emit_si_constraint_export), then hand to the layout/SI engineer."
        )
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
        warnings=warnings,
        upstream=upstream,
        feasibility=feasibility,
    )
