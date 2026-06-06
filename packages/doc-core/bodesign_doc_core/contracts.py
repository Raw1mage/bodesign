from dataclasses import dataclass, field
from pathlib import Path
import re

from bodesign_shared import EvidenceRef


@dataclass(slots=True)
class DesignIntent:
    id: str
    title: str
    target_functions: list[str] = field(default_factory=list)
    source_evidence: list[EvidenceRef] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    knowledge_gaps: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass(slots=True)
class DocumentSourceChunk:
    source_id: str
    source_path: str
    chunk_id: str
    kind: str
    text: str
    page_hint: int | None = None
    char_start: int = 0
    char_end: int = 0
    evidence: EvidenceRef | None = None


def document_to_source_chunks(project_id: str, document_path: str, chunk_chars: int = 1600) -> list[DocumentSourceChunk]:
    path = Path(document_path)
    text = _document_text(path)
    if not text:
        return []
    source_id = _document_source_id(project_id, path)
    chunks = []
    for index, start in enumerate(range(0, len(text), chunk_chars)):
        chunk_text = text[start : start + chunk_chars].strip()
        if not chunk_text:
            continue
        chunk_id = f"{source_id}-chunk-{index + 1}"
        chunks.append(
            DocumentSourceChunk(
                source_id=source_id,
                source_path=str(path),
                chunk_id=chunk_id,
                kind="pdf-text" if path.suffix.lower() == ".pdf" else "text",
                text=chunk_text,
                page_hint=_page_hint(text, start),
                char_start=start,
                char_end=start + len(chunk_text),
                evidence=EvidenceRef(
                    source_id=source_id,
                    target_path=f"documents/{path.name}#chunk-{index + 1}",
                    confidence=0.45 if path.suffix.lower() == ".pdf" else 0.7,
                    note="PDF-to-src provenance chunk for downstream extraction.",
                ),
            )
        )
    return chunks


def plan_document_ingestion(project_id: str, artifact_paths: list[str]) -> DesignIntent:
    evidence_refs = [
        EvidenceRef(
            source_id=f"{project_id}-doc-{index}",
            target_path=path,
            confidence=0.1,
            note="Placeholder evidence reference; real PDF extraction is not implemented yet.",
        )
        for index, path in enumerate(artifact_paths)
    ]
    component_hints = [_component_hint(path) for path in artifact_paths]
    components = sorted({hint for hint in component_hints if hint})

    return DesignIntent(
        id=f"{project_id}-design-intent",
        title="Document-driven design intent placeholder",
        target_functions=["camera", "microphone", "flash", "psram", "usb", "power"],
        source_evidence=evidence_refs,
        components=components,
        constraints=[
            "Extract schematic nets from the schematic PDF.",
            "Normalize datasheet pinouts before layout generation.",
            "Identify package and footprint evidence for each selected component.",
        ],
        knowledge_gaps=[
            "PDF extraction is not implemented yet.",
            "Datasheet-to-pinout normalization is pending.",
            "Reference schematic connectivity has not been parsed.",
            "Layout constraints and stackup are not derived yet.",
        ],
        confidence=0.1 if artifact_paths else 0.0,
    )


def _component_hint(path: str) -> str | None:
    name = Path(path).name.lower()
    hints = {
        "stm32": "STM32 MCU",
        "flash": "flash memory",
        "psram": "PSRAM",
        "camera": "camera interface",
        "mipi": "MIPI interface",
        "mic": "microphone",
        "imu": "IMU",
        "ethernet": "Ethernet",
        "wifi": "WiFi/BLE",
        "usb": "USB",
        "power": "power subsystem",
        "battery": "battery subsystem",
    }
    for token, label in hints.items():
        if token in name:
            return label
    return None


def _document_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        if path.suffix.lower() in {".txt", ".md", ".csv"}:
            return path.read_text(encoding="utf-8", errors="ignore")[:500_000]
        if path.suffix.lower() == ".pdf":
            raw_text = path.read_bytes()[:4_000_000].decode("latin-1", errors="ignore")
            tokens = re.findall(r"[A-Za-z0-9_+./#µμ\-]{3,}", raw_text)
            return " ".join(tokens[:60_000])
    except OSError:
        return ""
    return ""


def _document_source_id(project_id: str, path: Path) -> str:
    safe_name = "".join(character.lower() if character.isalnum() else "-" for character in path.name).strip("-")
    return f"{project_id}-doc-src-{safe_name or 'document'}"


def _page_hint(text: str, char_start: int) -> int | None:
    prefix = text[:char_start]
    page_markers = len(re.findall(r"\bpage\s+\d+\b", prefix, flags=re.IGNORECASE))
    return page_markers + 1 if page_markers else None
