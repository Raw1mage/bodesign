"""C04 → professional-EDA SI constraint handoff (Tier-3 clean handoff).

When the feasibility triage puts a product at Tier 3 (HDI / ≤0.4 mm BGA / DDR/RF), C04
does not route on KiCad + the MCP — it produces the **SI constraint set** as a neutral,
machine-readable package a professional tool (Allegro / Xpedition / Altium) + a human SI
engineer can pick up. This turns the routing wall into a *clean handoff* rather than a
half-routed dead-end.

Nothing is fabricated: a constraint field that bodesign did not derive stays null and is
listed under `tbd[]`. The JSON is the source of truth; the CSV is the table EDA tools
import; the Markdown explains the package and maps bodesign's net-classes onto each tool's
constraint system. See `skills/bodesign/references/si-constraint-handoff.md`.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SI_HANDOFF_SCHEMA = "bodesign.si_constraints.v1"


@dataclass(slots=True)
class NetClassConstraint:
    name: str                                  # e.g. "DDR_DQ", "USB_HS", "RF_50"
    nets: list[str] = field(default_factory=list)
    kind: str = "single_ended"                 # single_ended | differential
    target_impedance_ohm: float | None = None
    impedance_tol_pct: float | None = None
    diff_skew_ps: float | None = None          # intra-pair, differential only
    length_match_group: str | None = None
    length_match_tol_mm: float | None = None
    max_length_mm: float | None = None
    topology: str | None = None                # point_to_point | multi_drop | fly_by
    termination: str | None = None
    routing_layers: list[str] = field(default_factory=list)
    return_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "nets": self.nets, "kind": self.kind,
            "target_impedance_ohm": self.target_impedance_ohm,
            "impedance_tol_pct": self.impedance_tol_pct, "diff_skew_ps": self.diff_skew_ps,
            "length_match_group": self.length_match_group,
            "length_match_tol_mm": self.length_match_tol_mm, "max_length_mm": self.max_length_mm,
            "topology": self.topology, "termination": self.termination,
            "routing_layers": self.routing_layers, "return_path": self.return_path,
        }

    def _missing(self) -> list[str]:
        miss = []
        if self.target_impedance_ohm is None:
            miss.append("target_impedance_ohm")
        if self.kind == "differential" and self.diff_skew_ps is None:
            miss.append("diff_skew_ps")
        if self.length_match_group and self.length_match_tol_mm is None:
            miss.append("length_match_tol_mm")
        return [f"{self.name}.{m}" for m in miss]


@dataclass(slots=True)
class StackupSpec:
    layers: int | None = None
    hdi_type: str | None = None                # "any-layer" | "2+N+2" | "1+N+1" | None
    finest_bga_pitch_mm: float | None = None
    via_in_pad: bool | None = None
    layer_map: list[dict] = field(default_factory=list)   # [{layer,type,ref_plane,dielectric_mm,copper_oz,target_z0}]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "layers": self.layers, "hdi_type": self.hdi_type,
            "finest_bga_pitch_mm": self.finest_bga_pitch_mm, "via_in_pad": self.via_in_pad,
            "layer_map": self.layer_map, "notes": self.notes,
        }


@dataclass(slots=True)
class SiHandoffResult:
    out_dir: str
    json_path: str
    csv_path: str
    md_path: str
    net_class_count: int
    tbd: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SI_HANDOFF_SCHEMA, "out_dir": self.out_dir,
            "files": {"json": self.json_path, "csv": self.csv_path, "md": self.md_path},
            "net_class_count": self.net_class_count, "tbd": self.tbd,
        }


_CSV_COLS = [
    "net_class", "kind", "target_impedance_ohm", "impedance_tol_pct", "diff_skew_ps",
    "length_match_group", "length_match_tol_mm", "max_length_mm", "topology", "termination",
]

# How bodesign's neutral net-classes map onto each major EDA tool's constraint system.
_TOOL_MAP = [
    ("Cadence Allegro", "Constraint Manager → Electrical CSets: impedance + relative/matched-length "
     "groups; assign nets to the CSet named by `net_class`."),
    ("Siemens Xpedition", "Constraint Manager → Net Classes + Differential Pairs; map `target_impedance_ohm` "
     "to the trace-impedance rule, `length_match_group` to a Match group."),
    ("Altium Designer", "xSignals for length/match groups; Net Classes + Design Rules for impedance "
     "(Routing Width / Differential Pair); import `SI_Net_Classes.csv` as the class table."),
]


def emit_si_constraint_export(
    *,
    project_name: str,
    tier: int,
    stackup: StackupSpec,
    net_classes: list[NetClassConstraint],
    out_dir: str | Path,
    placement_notes: list[str] | None = None,
    keepouts: list[str] | None = None,
    source: str = "C03/C04 bodesign",
) -> SiHandoffResult:
    """Emit the neutral SI constraint package (JSON + CSV + Markdown) for pro-EDA handoff."""
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    tbd: list[str] = []
    for nc in net_classes:
        tbd.extend(nc._missing())
    if stackup.layers is None:
        tbd.append("stackup.layers")
    if not stackup.layer_map:
        tbd.append("stackup.layer_map")

    payload = {
        "schema": SI_HANDOFF_SCHEMA,
        "project_name": project_name,
        "feasibility_tier": tier,
        "handoff_reason": (
            "Tier-3 product — HDI/DDR/RF routing is beyond KiCad + the bodesign MCP; this is the "
            "complete SI constraint set for a professional EDA tool + human SI engineer to route."
        ),
        "source": source,
        "stackup": stackup.to_dict(),
        "net_classes": [nc.to_dict() for nc in net_classes],
        "placement_notes": list(placement_notes or []),
        "keepouts": list(keepouts or []),
        "tbd": tbd,
        "authority": (
            "Routing, final stackup/impedance realisation, and SI sign-off are owned by the "
            "receiving EDA flow + human SI engineer. bodesign authored the constraints, not the copper."
        ),
    }
    json_path = out / "SI_Constraint_Export.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = out / "SI_Net_Classes.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(_CSV_COLS)
        for nc in net_classes:
            d = nc.to_dict()
            d["net_class"] = d["name"]  # CSV uses `net_class` as the first column header
            w.writerow([d[c] if d.get(c) is not None else "" for c in _CSV_COLS])

    md_path = out / "SI_Constraint_Handoff.md"
    md_path.write_text(_render_md(payload, net_classes), encoding="utf-8")

    return SiHandoffResult(
        out_dir=str(out), json_path=str(json_path), csv_path=str(csv_path), md_path=str(md_path),
        net_class_count=len(net_classes), tbd=tbd,
    )


def _render_md(payload: dict[str, Any], net_classes: list[NetClassConstraint]) -> str:
    su = payload["stackup"]
    lines = [
        f"# SI Constraint Handoff — {payload['project_name']} (Tier {payload['feasibility_tier']})",
        "",
        f"> {payload['handoff_reason']}",
        "",
        f"**Authority.** {payload['authority']}",
        "",
        "## Stackup target",
        f"- Layers: {su['layers'] if su['layers'] is not None else '**TBD**'}"
        f" · HDI: {su['hdi_type'] or '—'} · finest BGA pitch: {su['finest_bga_pitch_mm'] or '—'} mm"
        f" · via-in-pad: {su['via_in_pad']}",
        (su["notes"] or ""),
        "",
        "## Net classes (source of truth: `SI_Constraint_Export.json`; table: `SI_Net_Classes.csv`)",
        "",
        "| class | kind | Z0 Ω | tol % | match group | max len mm | topology |",
        "|---|---|---|---|---|---|---|",
    ]
    for nc in net_classes:
        lines.append(
            f"| {nc.name} | {nc.kind} | {nc.target_impedance_ohm or '—'} | "
            f"{nc.impedance_tol_pct or '—'} | {nc.length_match_group or '—'} | "
            f"{nc.max_length_mm or '—'} | {nc.topology or '—'} |"
        )
    lines += ["", "## Importing into your EDA tool", ""]
    for tool, how in _TOOL_MAP:
        lines.append(f"- **{tool}** — {how}")
    if payload["placement_notes"]:
        lines += ["", "## Placement / floorplan intent"] + [f"- {n}" for n in payload["placement_notes"]]
    if payload["keepouts"]:
        lines += ["", "## Keepouts (honour these)"] + [f"- {k}" for k in payload["keepouts"]]
    if payload["tbd"]:
        lines += ["", "## TBD — bodesign did not derive these (do not assume a value)"] + \
                 [f"- {t}" for t in payload["tbd"]]
    return "\n".join(lines) + "\n"
