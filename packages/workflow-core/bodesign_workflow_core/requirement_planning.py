"""Requirement intake -> clarifying questions -> DesignIntent + architecture plan.

This is the deterministic skeleton of the "vibe design" front end (R5): the user
states a board in natural language, the planner extracts what it can, asks back
for what's missing, and decomposes the request into subsystems grounded in
reference designs (per the north star). It is rule-based on purpose so the
contract is testable and reproducible; a language model can enrich the
extraction/questions later without changing the shape.

It never fabricates a finished design: subsystems carry the evidence they still
need (datasheet / dev-board reference design), and the plan stays in
`needs-clarification` until the required fields are answered.
"""

from dataclasses import dataclass, field
from typing import Any

from .c00_prd_template import load_c00_prd_template

@dataclass(frozen=True, slots=True)
class RequirementFieldBinding:
    key: str
    section_id: str
    field: str
    label: str
    keywords: tuple[str, ...]
    question: str
    binding_note: str = ""


C00_REQUIREMENT_FIELD_BINDINGS: tuple[RequirementFieldBinding, ...] = (
    RequirementFieldBinding("compute", "s06_electrical_requirements", "compute", "Compute (MCU/SoC/NPU)", ("stm32", "mcu", "soc", "processor", "npu", "cortex", "fpga", "mpu", "晶片", "處理器", "处理器", "運算", "运算", "主控"), "Which exact MCU/SoC part and package? (e.g. STM32N657 VFBGA223)"),
    RequirementFieldBinding("comms", "s06_electrical_requirements", "connectivity", "Connectivity", ("nordic", "nrf", "9151", "cellular", "lte", "nb-iot", "wifi", "wi-fi", "ble", "bluetooth", "ethernet", "lora", "zigbee", "通訊", "通信", "無線", "无线", "蜂巢", "網路", "网络"), "Which connectivity standard(s) and exact module? (cellular / Wi-Fi / BLE / Ethernet)"),
    RequirementFieldBinding("memory", "s06_electrical_requirements", "memory", "Memory / storage", ("flash", "gb", "gbit", "mbit", "emmc", "nand", "nor", "psram", "sdram", "ddr", "sd card", "microsd", "記憶體", "内存", "儲存", "存储", "快閃"), "Flash/RAM type, density, and interface? (e.g. 8 GB eMMC vs octal-SPI NOR)"),
    RequirementFieldBinding("power_input", "s06_electrical_requirements", "power_input", "Power input", ("usb-c", "usb type-c", "type-c", "typec", "type c", "usb c", "dc jack", "barrel", "power input", "vbus", "pd", "供電", "供电", "電源", "电源", "輸入電"), "Power input connector and voltage range? (USB-C PD profile? DC input?)"),
    RequirementFieldBinding("charging", "s06_electrical_requirements", "battery_or_charging", "Charging", ("charge", "charging", "charger", "power delivery", "充電", "充电", "充放電"), "Charging current and charger IC preference? cell chemistry to charge?"),
    RequirementFieldBinding("battery", "s06_electrical_requirements", "battery_or_charging", "Battery", ("18650", "battery", "li-ion", "lithium", "lipo", "lifepo4", "cell", "coin cell", "電池", "电池", "鋰電", "锂电"), "Battery: cell count/config, capacity, and protection/fuel-gauge needs?"),
    RequirementFieldBinding("dimensions", "s05_id_me_requirements", "dimensions", "Form factor / dimensions", ("mm", "dimension", "form factor", "board size", "outline", "footprint size", "enclosure", "尺寸", "外形", "板框", "大小"), "Target board dimensions / form-factor or enclosure constraints?"),
    RequirementFieldBinding("certification", "s06_electrical_requirements", "compliance_targets", "Compliance targets", ("fcc", "ce mark", "ce ", "emc", "certif", "compliance", "rohs", "iec", "認證", "认证", "法規", "法规"), "Any compliance targets (FCC / CE / EMC / safety)?"),
    RequirementFieldBinding("volume", "s10_project_management", "milestones", "Build volume", ("prototype", "production", "quantity", "qty", "units", "volume", "mass production", "原型", "樣品", "样品", "量產", "量产", "數量", "数量"), "Prototype or production volume? (affects part sourcing and DFM)", "C00 template has no dedicated production-volume field; volume currently gates milestone/phase planning."),
)


def validate_requirement_bindings(template_data: dict[str, Any], bindings: tuple[RequirementFieldBinding, ...] = C00_REQUIREMENT_FIELD_BINDINGS) -> None:
    section_fields: dict[str, set[str]] = {}
    for document in template_data.get("documents", []):
        if not isinstance(document, dict):
            continue
        for section in document.get("sections", []):
            if isinstance(section, dict) and isinstance(section.get("id"), str):
                fields = section.get("required_fields")
                if isinstance(fields, list):
                    section_fields[section["id"]] = {field for field in fields if isinstance(field, str)}
    for binding in bindings:
        if binding.section_id not in section_fields:
            raise ValueError(f"Requirement binding `{binding.key}` references missing C00 section `{binding.section_id}`")
        if binding.field not in section_fields[binding.section_id]:
            raise ValueError(f"Requirement binding `{binding.key}` references missing C00 field `{binding.section_id}.{binding.field}`")


def c00_bound_requirement_fields() -> tuple[RequirementFieldBinding, ...]:
    template = load_c00_prd_template()
    validate_requirement_bindings(template.data)
    return C00_REQUIREMENT_FIELD_BINDINGS


def requirement_field_bindings_as_tuples() -> tuple[tuple[str, str, tuple[str, ...], str], ...]:
    return tuple((binding.key, binding.label, binding.keywords, binding.question) for binding in c00_bound_requirement_fields())


REQUIREMENT_FIELDS = requirement_field_bindings_as_tuples()

# Functional interface keywords (EN + zh) -> interface subsystem label.
INTERFACE_KEYWORDS = {
    "camera": ("camera", "csi", "dcmi", "mipi", "image sensor", "相機", "攝", "镜头", "鏡頭"),
    "display": ("display", "lcd", "oled", "screen", "dsi", "顯示", "显示", "螢幕", "屏"),
    "audio": ("audio", "microphone", "mic", "speaker", "i2s", "codec", "音訊", "音频", "麥克風", "麦克", "喇叭"),
    "imu/sensor": ("imu", "accelerometer", "gyro", "sensor", "magnetometer", "感測", "传感", "陀螺", "加速度"),
    "usb-data": ("usb hs", "usb high-speed", "usb device", "usb host", "otg", "資料傳輸"),
}


@dataclass(slots=True)
class ExtractedRequirement:
    key: str
    label: str
    state: str  # "stated" | "answered" | "missing"
    evidence: str = ""


@dataclass(slots=True)
class ClarifyingQuestion:
    key: str
    label: str
    question: str


@dataclass(slots=True)
class SubsystemPlan:
    id: str
    role: str
    rationale: str
    needs_evidence: str


@dataclass(slots=True)
class DesignIntentPlan:
    spec_summary: str
    status: str  # "needs-clarification" | "planned"
    requirements: list[ExtractedRequirement] = field(default_factory=list)
    open_questions: list[ClarifyingQuestion] = field(default_factory=list)
    subsystems: list[SubsystemPlan] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "spec_summary": self.spec_summary,
            "status": self.status,
            "requirements": [{"key": r.key, "label": r.label, "state": r.state, "evidence": r.evidence} for r in self.requirements],
            "open_questions": [{"key": q.key, "label": q.label, "question": q.question} for q in self.open_questions],
            "subsystems": [{"id": s.id, "role": s.role, "rationale": s.rationale, "needs_evidence": s.needs_evidence} for s in self.subsystems],
            "interfaces": self.interfaces,
            "assumptions": self.assumptions,
        }


def plan_design_intent(spec_text: str, answers: dict[str, str] | None = None) -> DesignIntentPlan:
    answers = {key.lower(): value for key, value in (answers or {}).items()}
    lowered = (spec_text or "").lower()

    requirements: list[ExtractedRequirement] = []
    open_questions: list[ClarifyingQuestion] = []
    present: set[str] = set()
    for key, label, keywords, question in REQUIREMENT_FIELDS:
        if key in answers and answers[key].strip():
            requirements.append(ExtractedRequirement(key, label, "answered", answers[key].strip()))
            present.add(key)
            continue
        matched = [kw for kw in keywords if kw in lowered]
        if matched:
            requirements.append(ExtractedRequirement(key, label, "stated", _evidence_phrase(lowered, matched[0])))
            present.add(key)
        else:
            requirements.append(ExtractedRequirement(key, label, "missing"))
            open_questions.append(ClarifyingQuestion(key, label, question))

    interfaces = [name for name, keywords in INTERFACE_KEYWORDS.items() if any(kw in lowered for kw in keywords)]
    subsystems = _decompose(present, interfaces)

    status = "needs-clarification" if open_questions else "planned"
    assumptions = [
        "AI does not synthesize the netlist from scratch; each subsystem is grounded in the chip's dev-board "
        "reference design + datasheet (per north star).",
        "No layout or fabrication output is produced from this plan; it precedes IR composition and KiCad emission.",
    ]
    summary = (spec_text or "").strip().replace("\n", " ")
    if len(summary) > 240:
        summary = summary[:237] + "..."
    return DesignIntentPlan(
        spec_summary=summary,
        status=status,
        requirements=requirements,
        open_questions=open_questions,
        subsystems=subsystems,
        interfaces=interfaces,
        assumptions=assumptions,
    )


def _decompose(present: set[str], interfaces: list[str]) -> list[SubsystemPlan]:
    subsystems: list[SubsystemPlan] = []
    if "compute" in present:
        subsystems.append(SubsystemPlan("compute", "MCU/SoC core: power pins, decoupling, boot/clock, debug",
                                        "Detected a processor/NPU requirement.",
                                        "MCU datasheet pinout + dev-board reference schematic (e.g. ST Discovery/Nucleo)."))
    if "comms" in present:
        subsystems.append(SubsystemPlan("comms", "Connectivity front end + antenna/RF matching",
                                        "Detected a wireless/connectivity requirement.",
                                        "Module/transceiver datasheet + vendor reference design (e.g. Nordic DK)."))
    if "memory" in present:
        subsystems.append(SubsystemPlan("memory", "External memory/storage + interface routing",
                                        "Detected an external memory/storage requirement.",
                                        "Memory datasheet pinout + host controller reference connection."))
    if "power_input" in present or "charging" in present:
        subsystems.append(SubsystemPlan("power-input", "Input/charging path: connector, protection, charger, regulators",
                                        "Detected an external power/charging requirement.",
                                        "Charger/PD/regulator datasheets + reference application circuits."))
    if "battery" in present:
        subsystems.append(SubsystemPlan("battery", "Battery holder, protection, and (optional) fuel gauge",
                                        "Detected a battery requirement.",
                                        "Cell spec + protection/fuel-gauge reference circuit."))
    for name in interfaces:
        subsystems.append(SubsystemPlan(f"interface-{name.replace('/', '-')}", f"{name} interface front end",
                                        f"Detected a {name} interface in the spec.",
                                        "Peripheral datasheet + protection/filter reference circuit."))
    return subsystems


def _evidence_phrase(lowered: str, keyword: str) -> str:
    index = lowered.find(keyword)
    start = max(0, index - 18)
    end = min(len(lowered), index + len(keyword) + 18)
    return "..." + lowered[start:end].strip() + "..."
