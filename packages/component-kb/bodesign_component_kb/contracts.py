from dataclasses import dataclass, field
from pathlib import Path
import re

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
    extracted_text_chars: int = 0
    extracted_fields: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ComponentKnowledgeQueueItem:
    reusable_key: str
    part_number: str
    footprint: str | None = None
    refdes: list[str] = field(default_factory=list)
    occurrence_count: int = 0
    priority: str = "normal"
    status: str = "needs-datasheet"
    knowledge_gaps: list[str] = field(default_factory=list)


def ingest_datasheet_knowledge(
    project_id: str,
    part_number: str,
    document_paths: list[str],
    package_hint: str | None = None,
) -> DatasheetIngestionResult:
    normalized_part_number = part_number.strip() or "unknown-part"
    extracted_text = "\n".join(_extract_document_text(document_path) for document_path in document_paths)
    inferred_package = package_hint or _extract_package_hint(extracted_text)
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
        package=inferred_package,
        layout_guidelines=[
            "Treat datasheet layout guidance as required evidence before fabrication use.",
            "Record pinout, package, power rails, interfaces, and decoupling rules before routing.",
        ],
        source_evidence=evidence_refs,
        confidence=0.45 if extracted_text else 0.2 if document_paths else 0.1,
        knowledge_gaps=_datasheet_knowledge_gaps(extracted_text, inferred_package),
    )
    return DatasheetIngestionResult(
        project_id=project_id,
        part_number=normalized_part_number,
        reusable_key=component_knowledge_key(normalized_part_number),
        document_paths=document_paths,
        component=component,
        warnings=["User-provided datasheet extraction is best-effort; no external datasheet search was performed."],
        extracted_text_chars=len(extracted_text),
        extracted_fields={"package": inferred_package} if inferred_package else {},
    )


def component_knowledge_key(part_number: str) -> str:
    safe_part = "".join(character.lower() if character.isalnum() else "-" for character in part_number).strip("-")
    return f"component:{safe_part or 'unknown-part'}"


def build_component_knowledge_queue(components: list[dict[str, object]], limit: int = 80) -> list[ComponentKnowledgeQueueItem]:
    grouped: dict[str, dict[str, object]] = {}
    for component in components:
        placement = component.get("placement") if isinstance(component.get("placement"), dict) else {}
        part_number = str(component.get("part_number") or placement.get("value") or "unknown-part").strip() or "unknown-part"
        footprint = str(component.get("footprint") or "").strip() or None
        key = component_knowledge_key(part_number)
        entry = grouped.setdefault(key, {"part_number": part_number, "footprint": footprint, "refdes": []})
        if footprint and not entry.get("footprint"):
            entry["footprint"] = footprint
        refdes = str(component.get("refdes", "")).strip()
        if refdes:
            entry["refdes"].append(refdes)
    items = []
    for key, entry in grouped.items():
        refdes_values = sorted(set(str(refdes) for refdes in entry["refdes"]))
        occurrence_count = len(refdes_values)
        items.append(
            ComponentKnowledgeQueueItem(
                reusable_key=key,
                part_number=str(entry["part_number"]),
                footprint=str(entry["footprint"]) if entry.get("footprint") else None,
                refdes=refdes_values[:24],
                occurrence_count=occurrence_count,
                priority=_knowledge_priority(str(entry["part_number"]), occurrence_count),
                knowledge_gaps=[
                    "Datasheet source is not attached yet.",
                    "Pinout/package/layout guidance normalization is pending.",
                ],
            )
        )
    items.sort(key=lambda item: (_priority_rank(item.priority), -item.occurrence_count, item.part_number.lower()))
    return items[:limit]


def _knowledge_priority(part_number: str, occurrence_count: int) -> str:
    if part_number.upper().startswith(("MDBT", "W25Q", "STM", "NRF")):
        return "high"
    if occurrence_count >= 8:
        return "high"
    if occurrence_count >= 3:
        return "normal"
    return "low"


def _priority_rank(priority: str) -> int:
    return {"high": 0, "normal": 1, "low": 2}.get(priority, 9)


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


def _extract_document_text(document_path: str) -> str:
    path = Path(document_path)
    if not path.exists() or not path.is_file():
        return ""
    suffix = path.suffix.lower()
    try:
        if suffix in {".txt", ".md", ".csv"}:
            return path.read_text(encoding="utf-8", errors="ignore")[:200_000]
        if suffix == ".pdf":
            raw_text = path.read_bytes()[:2_000_000].decode("latin-1", errors="ignore")
            tokens = re.findall(r"[A-Za-z0-9_+./#µμ\-]{3,}", raw_text)
            return " ".join(tokens[:20_000])
    except OSError:
        return ""
    return ""


def _extract_package_hint(text: str) -> str | None:
    package_match = re.search(r"(?:package|footprint)\s*[:=]\s*([A-Za-z0-9_./#\- ]{2,40})", text, flags=re.IGNORECASE)
    if package_match:
        return package_match.group(1).strip()
    known_match = re.search(r"\b(QFN|BGA|LGA|SOP|SOIC|TSSOP|DFN|MODULE|0402|0603|0805)\b", text, flags=re.IGNORECASE)
    return known_match.group(1) if known_match else None


def _datasheet_knowledge_gaps(text: str, package_hint: str | None) -> list[str]:
    gaps = []
    if not text:
        gaps.append("Readable datasheet text extraction is pending or unavailable.")
    if "pin" not in text.lower():
        gaps.append("Pinout extraction is pending.")
    if not package_hint:
        gaps.append("Package/footprint verification is pending.")
    gaps.append("Electrical characteristics extraction is pending.")
    return gaps
