"""Spatial fusion of drill hits and IPC-D-356A copper features.

This module advances board reconstruction from the non-spatial component/net
summary into a *spatially-verified* fusion: every plated drill hit is matched to
an IPC via record by nearest-neighbour in a shared coordinate frame, so drill
holes gain net identity and unmatched holes are classified as tooling/mounting.

Coordinate frames (empirically validated on the reference board fixture):
  - IPC-D-356A 317/327 records: raw integer / 100  -> fusion units
  - Excellon drill X/Y:         raw integer / 1000 -> fusion units
Both resolve to the same physical point (e.g. drill X0000178400 == IPC via
X+017840), so drill<->via matching is exact (<=0.01 fusion-unit residual).

The Allegro component placement export (`cds2f_*.txt`) uses a *different* origin
and is NOT spatially co-registered with the IPC frame, so placement<->IPC pad
fusion is intentionally left out and reported as a known gap rather than faked.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re

from bodesign_design_ir import GeometryPrimitive
from bodesign_shared import EvidenceRef

IPC_XY_RE = re.compile(r"X([+-]\d+)Y([+-]\d+)")
DRILL_XY_RE = re.compile(r"^X(-?\d+)Y(-?\d+)")
IPC_COORD_DIVISOR = 100.0
DRILL_COORD_DIVISOR = 1000.0
DEFAULT_MATCH_TOLERANCE = 2.0


@dataclass(slots=True)
class IpcFeature:
    feature_type: str  # "via" | "pad"
    net: str
    refdes: str
    pin: str
    x: float
    y: float


@dataclass(slots=True)
class DrillViaMatch:
    x: float
    y: float
    net: str | None
    residual: float
    classification: str  # "net-via" | "unmatched-hole"


@dataclass(slots=True)
class SpatialFusionSummary:
    project_id: str
    status: str = "spatial-fusion"
    frame: str = "ipc-drill-mil-scale"
    ipc_via_count: int = 0
    ipc_pad_count: int = 0
    drill_hit_count: int = 0
    matched_via_hits: int = 0
    unmatched_holes: int = 0
    match_tolerance: float = DEFAULT_MATCH_TOLERANCE
    match_ratio: float = 0.0
    distinct_via_nets: int = 0
    top_via_nets: list[dict[str, object]] = field(default_factory=list)
    bounds: dict[str, float] = field(default_factory=dict)
    sample_matches: list[dict[str, object]] = field(default_factory=list)
    geometry_primitives: list[GeometryPrimitive] = field(default_factory=list)
    confidence: float = 0.0
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_ipc_features(ipc_files: list[str]) -> list[IpcFeature]:
    features: list[IpcFeature] = []
    for ipc_file in ipc_files:
        path = Path(ipc_file)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            record_type = line[:3]
            if record_type not in {"317", "327"}:
                continue
            coord_match = IPC_XY_RE.search(line)
            if coord_match is None:
                continue
            tokens = line.split()
            if len(tokens) < 2:
                continue
            net = tokens[0][3:].strip()
            refdes = tokens[1].strip()
            pin = tokens[2].strip().lstrip("-") if len(tokens) > 2 else ""
            features.append(
                IpcFeature(
                    feature_type="via" if record_type == "317" else "pad",
                    net=net,
                    refdes=refdes,
                    pin=pin,
                    x=int(coord_match.group(1)) / IPC_COORD_DIVISOR,
                    y=int(coord_match.group(2)) / IPC_COORD_DIVISOR,
                )
            )
    return features


def parse_drill_hits(drill_files: list[str]) -> list[tuple[float, float]]:
    hits: list[tuple[float, float]] = []
    for drill_file in drill_files:
        path = Path(drill_file)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            coord_match = DRILL_XY_RE.match(line.strip())
            if coord_match is None:
                continue
            hits.append(
                (
                    int(coord_match.group(1)) / DRILL_COORD_DIVISOR,
                    int(coord_match.group(2)) / DRILL_COORD_DIVISOR,
                )
            )
    return hits


def fuse_drill_and_ipc(
    project_id: str,
    ipc_files: list[str],
    drill_files: list[str],
    tolerance: float = DEFAULT_MATCH_TOLERANCE,
    sample_limit: int = 40,
    primitive_limit: int = 200,
) -> SpatialFusionSummary:
    features = parse_ipc_features(ipc_files)
    drill_hits = parse_drill_hits(drill_files)
    vias = [feature for feature in features if feature.feature_type == "via"]
    pads = [feature for feature in features if feature.feature_type == "pad"]

    summary = SpatialFusionSummary(
        project_id=project_id,
        ipc_via_count=len(vias),
        ipc_pad_count=len(pads),
        drill_hit_count=len(drill_hits),
        match_tolerance=tolerance,
    )
    if not vias or not drill_hits:
        summary.status = "no-spatial-evidence"
        summary.warnings.append("IPC via records and drill hits are both required for spatial fusion.")
        return summary

    matches = [_match_hit_to_via(x, y, vias, tolerance) for x, y in drill_hits]
    summary.matched_via_hits = sum(1 for match in matches if match.classification == "net-via")
    summary.unmatched_holes = len(matches) - summary.matched_via_hits
    summary.match_ratio = round(summary.matched_via_hits / len(matches), 4)

    via_net_counts: dict[str, int] = {}
    for via in vias:
        if via.net:
            via_net_counts[via.net] = via_net_counts.get(via.net, 0) + 1
    summary.distinct_via_nets = len(via_net_counts)
    summary.top_via_nets = [
        {"net": net, "vias": count}
        for net, count in sorted(via_net_counts.items(), key=lambda item: (-item[1], item[0]))[:12]
    ]

    summary.bounds = _bounds(features)
    summary.sample_matches = [
        {
            "x": round(match.x, 3),
            "y": round(match.y, 3),
            "net": match.net,
            "residual": round(match.residual, 4),
            "classification": match.classification,
        }
        for match in matches
        if match.classification == "net-via"
    ][:sample_limit]

    summary.geometry_primitives = _via_primitives(project_id, vias, primitive_limit)
    summary.evidence_refs = [
        EvidenceRef(
            source_id=f"{project_id}-ipc-drill-fusion",
            target_path="spatial-fusion/drill-via",
            confidence=summary.match_ratio,
            note=(
                f"{summary.matched_via_hits}/{len(matches)} drill hits matched IPC vias within "
                f"{tolerance} fusion units; unmatched holes classified as tooling/mounting."
            ),
        )
    ]
    summary.confidence = round(0.4 + 0.5 * summary.match_ratio, 4)
    summary.warnings.append(
        "Allegro placement (cds2f) coordinates are not co-registered with the IPC/drill frame; "
        "placement<->pad spatial fusion is pending an origin transform and is not asserted here."
    )
    return summary


def _match_hit_to_via(x: float, y: float, vias: list[IpcFeature], tolerance: float) -> DrillViaMatch:
    best_via: IpcFeature | None = None
    best_distance_sq = float("inf")
    tolerance_sq = tolerance * tolerance
    for via in vias:
        distance_sq = (x - via.x) ** 2 + (y - via.y) ** 2
        if distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
            best_via = via
            if distance_sq <= tolerance_sq and distance_sq == 0.0:
                break
    residual = best_distance_sq ** 0.5
    if best_via is not None and best_distance_sq <= tolerance_sq:
        return DrillViaMatch(x=x, y=y, net=best_via.net or None, residual=residual, classification="net-via")
    return DrillViaMatch(x=x, y=y, net=None, residual=residual, classification="unmatched-hole")


def _via_primitives(project_id: str, vias: list[IpcFeature], limit: int) -> list[GeometryPrimitive]:
    primitives: list[GeometryPrimitive] = []
    for index, via in enumerate(vias[:limit]):
        primitives.append(
            GeometryPrimitive(
                id=f"{project_id}-via-{index}",
                primitive_type="via",
                x=round(via.x, 3),
                y=round(via.y, 3),
                net=via.net or None,
                refdes=via.refdes or None,
                attributes={"source": "ipc-356-317"},
                evidence_refs=[
                    EvidenceRef(
                        source_id=f"{project_id}-ipc",
                        target_path=f"via/{index}",
                        confidence=0.6,
                    )
                ],
            )
        )
    return primitives


def _bounds(features: list[IpcFeature]) -> dict[str, float]:
    xs = [feature.x for feature in features]
    ys = [feature.y for feature in features]
    if not xs or not ys:
        return {}
    return {
        "min_x": round(min(xs), 3),
        "min_y": round(min(ys), 3),
        "max_x": round(max(xs), 3),
        "max_y": round(max(ys), 3),
    }
