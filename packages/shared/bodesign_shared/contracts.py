from dataclasses import dataclass, field
from typing import Literal


ArtifactType = Literal[
    "datasheet",
    "schematic",
    "bom_placement",
    "gerber",
    "drill",
    "ipc356",
    "routing_report",
    "reference_doc",
    "unknown",
]


@dataclass(slots=True)
class EvidenceSource:
    id: str
    artifact_type: ArtifactType
    path: str
    label: str | None = None
    confidence: float = 0.0


@dataclass(slots=True)
class EvidenceRef:
    source_id: str
    target_path: str
    confidence: float = 0.0
    note: str | None = None


@dataclass(slots=True)
class InputArtifact:
    id: str
    project_id: str
    filename: str
    path: str | None = None
    artifact_type: ArtifactType = "unknown"
    detected_format: str | None = None
    status: str = "detected"
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


@dataclass(slots=True)
class ProjectSummary:
    id: str
    name: str
    status: str = "created"
    artifact_count: int = 0
    board_design_id: str | None = None


@dataclass(slots=True)
class JobSummary:
    id: str
    project_id: str
    job_type: str
    status: str = "queued"
    message: str | None = None
