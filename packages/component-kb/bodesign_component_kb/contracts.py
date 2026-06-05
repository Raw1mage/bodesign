from dataclasses import dataclass, field
from pathlib import Path

from bodesign_shared import EvidenceRef


@dataclass(slots=True)
class ComponentPin:
    name: str
    number: str | None = None
    role: str | None = None
    electrical_type: str | None = None


@dataclass(slots=True)
class ComponentKnowledge:
    part_number: str
    aliases: list[str] = field(default_factory=list)
    package: str | None = None
    pinout: list[ComponentPin] = field(default_factory=list)
    power_pins: list[str] = field(default_factory=list)
    interface_pins: dict[str, list[str]] = field(default_factory=dict)
    layout_guidelines: list[str] = field(default_factory=list)
    source_evidence: list[EvidenceRef] = field(default_factory=list)
    confidence: float = 0.0
    knowledge_gaps: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DatasheetIngestionResult:
    project_id: str
    part_number: str
    reusable_key: str
    document_paths: list[str] = field(default_factory=list)
    component: ComponentKnowledge | None = None
    status: str = "placeholder-ingested"
    warnings: list[str] = field(default_factory=list)


def ingest_datasheet_knowledge(
    project_id: str,
    part_number: str,
    document_paths: list[str],
    package_hint: str | None = None,
) -> DatasheetIngestionResult:
    normalized_part_number = part_number.strip() or "unknown-part"
    evidence_refs = [
        EvidenceRef(
            source_id=_source_id(project_id, document_path),
            target_path=f"component/{normalized_part_number}",
            confidence=0.35,
            note="Placeholder datasheet evidence; full PDF extraction is pending.",
        )
        for document_path in document_paths
    ]
    component = ComponentKnowledge(
        part_number=normalized_part_number,
        aliases=[normalized_part_number.upper()] if normalized_part_number.upper() != normalized_part_number else [],
        package=package_hint,
        layout_guidelines=[
            "Treat datasheet layout guidance as required evidence before fabrication use.",
            "Record pinout, package, power rails, interfaces, and decoupling rules before routing.",
        ],
        source_evidence=evidence_refs,
        confidence=0.35 if document_paths else 0.1,
        knowledge_gaps=[
            "Pinout extraction is pending.",
            "Electrical characteristics extraction is pending.",
            "Package/footprint verification is pending.",
        ],
    )
    return DatasheetIngestionResult(
        project_id=project_id,
        part_number=normalized_part_number,
        reusable_key=component_knowledge_key(normalized_part_number),
        document_paths=document_paths,
        component=component,
        warnings=["Placeholder knowledge record only; no external datasheet search or PDF parsing was performed."],
    )


def component_knowledge_key(part_number: str) -> str:
    safe_part = "".join(character.lower() if character.isalnum() else "-" for character in part_number).strip("-")
    return f"component:{safe_part or 'unknown-part'}"


def reuse_component_knowledge(project_id: str, part_number: str, knowledge: ComponentKnowledge) -> DatasheetIngestionResult:
    return DatasheetIngestionResult(
        project_id=project_id,
        part_number=knowledge.part_number,
        reusable_key=component_knowledge_key(part_number),
        component=knowledge,
        status="placeholder-reused",
        warnings=["Reused normalized ComponentKnowledge placeholder; freshness and source trust checks are pending."],
    )


def _source_id(project_id: str, document_path: str) -> str:
    filename = Path(document_path).name or "datasheet"
    safe_filename = "".join(character.lower() if character.isalnum() else "-" for character in filename).strip("-")
    return f"{project_id}-{safe_filename or 'datasheet'}"
