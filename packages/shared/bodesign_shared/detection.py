from pathlib import Path

from .contracts import ArtifactType, InputArtifact


DATASHEET_HINTS = (
    "datasheet",
    "data-sheet",
    "ds_",
    "stm32",
    "nrf",
    "nordic",
    "raytac",
    "winbond",
    "flash",
    "psram",
    "imu",
    "mic",
    "pmic",
    "charger",
)
SCHEMATIC_HINTS = ("schematic", "sch", "circuit", "電路圖", "原理圖")
BOM_PLACEMENT_HINTS = ("bom", "placement", "pick", "place", "centroid", "cds2f")


def detect_artifact_type(path: str) -> ArtifactType:
    if not path or not path.strip():
        raise ValueError("path must not be empty")

    candidate = Path(path)
    suffix = candidate.suffix.lower()
    name = candidate.name.lower()

    if suffix == ".pdf":
        if _contains_any(name, SCHEMATIC_HINTS):
            return "schematic"
        if _contains_any(name, DATASHEET_HINTS):
            return "datasheet"
        return "reference_doc"

    if suffix in {".sch", ".kicad_sch"} or _contains_any(name, SCHEMATIC_HINTS):
        return "schematic"
    if suffix in {".art", ".gbr", ".ger"}:
        return "gerber"
    if suffix in {".drl", ".xln"}:
        return "drill"
    if suffix == ".ipc":
        return "ipc356"
    if suffix == ".rou":
        return "routing_report"
    if suffix in {".txt", ".csv"} and _contains_any(name, BOM_PLACEMENT_HINTS):
        return "bom_placement"

    return "unknown"


def detect_input_artifact(path: str, project_id: str = "detected") -> InputArtifact:
    artifact_type = detect_artifact_type(path)
    candidate = Path(path)
    return InputArtifact(
        id=_artifact_id(project_id, candidate.name),
        project_id=project_id,
        filename=candidate.name,
        path=path,
        artifact_type=artifact_type,
        detected_format=candidate.suffix.lower().lstrip(".") or None,
        status="detected",
    )


def _contains_any(value: str, hints: tuple[str, ...]) -> bool:
    return any(hint in value for hint in hints)


def _artifact_id(project_id: str, filename: str) -> str:
    safe_name = "".join(character.lower() if character.isalnum() else "-" for character in filename).strip("-")
    return f"{project_id}-{safe_name or 'artifact'}"
