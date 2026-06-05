from dataclasses import dataclass, field
from pathlib import Path

from bodesign_design_ir import BoardDesign, BoardLayer, BoardObject, ComponentInstance, Net
from bodesign_shared import EvidenceRef
from bodesign_shared.detection import detect_artifact_type


@dataclass(slots=True)
class RockboxInputManifest:
    project_id: str
    component_files: list[str] = field(default_factory=list)
    gerber_files: list[str] = field(default_factory=list)
    drill_files: list[str] = field(default_factory=list)
    ipc_files: list[str] = field(default_factory=list)
    routing_reports: list[str] = field(default_factory=list)
    unknown_files: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IpcSummary:
    nets: dict[str, set[str]] = field(default_factory=dict)
    via_count: int = 0
    pad_count: int = 0


def build_rockbox_input_manifest(project_id: str, artifact_paths: list[str]) -> RockboxInputManifest:
    manifest = RockboxInputManifest(project_id=project_id)
    for artifact_path in artifact_paths:
        artifact_type = detect_artifact_type(artifact_path)
        if artifact_type == "bom_placement":
            manifest.component_files.append(artifact_path)
        elif artifact_type == "gerber":
            manifest.gerber_files.append(artifact_path)
        elif artifact_type == "drill":
            manifest.drill_files.append(artifact_path)
        elif artifact_type == "ipc356":
            manifest.ipc_files.append(artifact_path)
        elif artifact_type == "routing_report":
            manifest.routing_reports.append(artifact_path)
        else:
            manifest.unknown_files.append(artifact_path)
    return manifest


def reconstruct_rockbox_placeholder(project_id: str = "rockbox", artifact_paths: list[str] | None = None) -> BoardDesign:
    manifest = build_rockbox_input_manifest(project_id, artifact_paths or [])
    components = _parse_component_files(project_id, manifest.component_files)
    ipc_summary = _parse_ipc_files(manifest.ipc_files)
    layers = _layers_from_manifest(manifest)
    nets = [
        Net(
            name=net_name,
            connected_pads=sorted(connected_pads),
            evidence_refs=[EvidenceRef(source_id="rockbox-ipc", target_path=f"net/{net_name}", confidence=0.55)],
        )
        for net_name, connected_pads in sorted(ipc_summary.nets.items())
    ]
    board_objects = [
        BoardObject(
            id="rockbox-ipc-vias",
            object_type="via-summary",
            geometry={"count": ipc_summary.via_count},
            evidence_refs=[EvidenceRef(source_id="rockbox-ipc", target_path="vias", confidence=0.45)],
        )
    ]
    artifact_counts = {
        "component_files": float(len(manifest.component_files)),
        "gerber_files": float(len(manifest.gerber_files)),
        "drill_files": float(len(manifest.drill_files)),
        "ipc_files": float(len(manifest.ipc_files)),
        "routing_reports": float(len(manifest.routing_reports)),
        "unknown_files": float(len(manifest.unknown_files)),
        "components": float(len(components)),
        "nets": float(len(nets)),
        "ipc_pads": float(ipc_summary.pad_count),
        "ipc_vias": float(ipc_summary.via_count),
    }
    has_real_evidence = bool(components or nets or layers)
    return BoardDesign(
        id=f"{project_id}-board-design",
        version="0.2.0-rockbox-summary",
        title="Rockbox reconstructed board summary",
        components=components,
        nets=nets,
        layers=layers,
        board_objects=board_objects,
        evidence_refs=[
            EvidenceRef(
                source_id="rockbox-fixture",
                target_path="BoardDesign",
                confidence=0.45 if has_real_evidence else 0.1 if artifact_paths else 0.0,
                note="Summary reconstruction from placement and IPC evidence; Gerber geometry parsing is still pending.",
            )
        ],
        confidence_summary={
            "overall": 0.45 if has_real_evidence else 0.1 if artifact_paths else 0.0,
            "status": "summary-reconstructed" if has_real_evidence else "placeholder-manifest",
            **artifact_counts,
        },
    )


def _parse_component_files(project_id: str, component_files: list[str]) -> list[ComponentInstance]:
    components: list[ComponentInstance] = []
    for component_file in component_files:
        path = Path(component_file)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.startswith("S!"):
                continue
            fields = line.split("!")
            if len(fields) < 14:
                continue
            refdes = fields[1].strip()
            if not refdes or fields[7].strip().upper() != "PACKAGE" or not _looks_like_refdes(refdes):
                continue
            part_number = fields[3].strip() or fields[13].strip() or None
            footprint = fields[8].strip() or None
            components.append(
                ComponentInstance(
                    refdes=refdes,
                    part_number=part_number,
                    footprint=footprint,
                    placement={
                        "side": "bottom" if fields[9].strip().upper() == "YES" else "top",
                        "rotation_deg": _float_or_zero(fields[10]),
                        "x_mil": _float_or_zero(fields[11]),
                        "y_mil": _float_or_zero(fields[12]),
                        "value": fields[13].strip(),
                    },
                    evidence_refs=[
                        EvidenceRef(
                            source_id=f"{project_id}-{path.name}",
                            target_path=f"component/{refdes}",
                            confidence=0.75,
                            note="Parsed from Allegro component placement export.",
                        )
                    ],
                )
            )
    return components


def _parse_ipc_files(ipc_files: list[str]) -> IpcSummary:
    summary = IpcSummary()
    for ipc_file in ipc_files:
        path = Path(ipc_file)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            record_type = line[:3]
            if record_type not in {"317", "327"}:
                continue
            tokens = line.split()
            if len(tokens) < 3:
                continue
            net_name = tokens[0][3:].strip()
            refdes = tokens[1].strip()
            pin = tokens[2].strip().lstrip("-")
            if not net_name:
                continue
            if record_type == "317" or refdes == "VIA":
                summary.via_count += 1
                connected_pad = f"VIA.{summary.via_count}"
            else:
                summary.pad_count += 1
                connected_pad = f"{refdes}.{pin}" if pin else refdes
            summary.nets.setdefault(net_name, set()).add(connected_pad)
    return summary


def _layers_from_manifest(manifest: RockboxInputManifest) -> list[BoardLayer]:
    layer_names = []
    for gerber_file in manifest.gerber_files:
        filename = Path(gerber_file).name
        if filename.startswith("L1_"):
            layer_names.append(("L1_top", filename))
        elif filename.startswith("L2_"):
            layer_names.append(("L2_GND", filename))
        elif filename.startswith("L3_"):
            layer_names.append(("L3_IN1", filename))
        elif filename.startswith("L4_"):
            layer_names.append(("L4_IN2", filename))
        elif filename.startswith("L5_"):
            layer_names.append(("L5_IN3", filename))
        elif filename.startswith("L6_"):
            layer_names.append(("L6_bot", filename))
    return [BoardLayer(name=layer_name, layer_type="copper", source_artifact_id=filename) for layer_name, filename in layer_names]


def _float_or_zero(value: str) -> float:
    try:
        return float(value.strip())
    except ValueError:
        return 0.0


def _looks_like_refdes(value: str) -> bool:
    if not value or not value[0].isalpha():
        return False
    return any(character.isdigit() for character in value)
