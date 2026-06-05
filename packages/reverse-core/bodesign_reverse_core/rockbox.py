from dataclasses import dataclass, field

from bodesign_design_ir import BoardDesign
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
    artifact_counts = {
        "component_files": float(len(manifest.component_files)),
        "gerber_files": float(len(manifest.gerber_files)),
        "drill_files": float(len(manifest.drill_files)),
        "ipc_files": float(len(manifest.ipc_files)),
        "routing_reports": float(len(manifest.routing_reports)),
        "unknown_files": float(len(manifest.unknown_files)),
    }
    return BoardDesign(
        id=f"{project_id}-board-design",
        version="0.1.0-placeholder",
        title="Rockbox reconstructed board placeholder",
        evidence_refs=[
            EvidenceRef(
                source_id="rockbox-fixture",
                target_path="BoardDesign",
                confidence=0.1 if artifact_paths else 0.0,
                note="Placeholder manifest only; no Gerber/drill/IPC geometry parsing has been performed.",
            )
        ],
        confidence_summary={
            "overall": 0.1 if artifact_paths else 0.0,
            "status": "placeholder-manifest",
            **artifact_counts,
        },
    )
