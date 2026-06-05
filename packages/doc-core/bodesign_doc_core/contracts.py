from dataclasses import dataclass, field
from pathlib import Path

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


def plan_openmv_document_ingestion(project_id: str, artifact_paths: list[str]) -> DesignIntent:
    evidence_refs = [
        EvidenceRef(
            source_id=f"{project_id}-openmv-doc-{index}",
            target_path=path,
            confidence=0.1,
            note="Placeholder evidence reference; real PDF extraction is not implemented yet.",
        )
        for index, path in enumerate(artifact_paths)
    ]
    component_hints = [_component_hint(path) for path in artifact_paths]
    components = sorted({hint for hint in component_hints if hint})

    return DesignIntent(
        id=f"{project_id}-openmv-design-intent",
        title="OpenMV document-driven design intent placeholder",
        target_functions=["camera", "microphone", "flash", "psram", "usb", "power"],
        source_evidence=evidence_refs,
        components=components,
        constraints=[
            "Extract schematic nets from OpenMV schematic PDF.",
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
        "stm32": "STM32N657 processor",
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
