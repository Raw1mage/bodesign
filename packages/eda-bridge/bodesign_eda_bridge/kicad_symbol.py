from dataclasses import dataclass, field
import json
from pathlib import Path
import re


SYMBOL_LIB_VERSION = "20241209"
DEFAULT_SYMBOL_NAME = "STM32N657L0_VFBGA223"
DEFAULT_FOOTPRINT_FILTER = "*VFBGA*223*"


@dataclass(slots=True)
class KiCadSymbolPin:
    number: str
    name: str
    kind: str
    functions: list[str] = field(default_factory=list)
    source_id: str = ""
    source_table: str = ""
    page_start: int | None = None
    page_end: int | None = None


@dataclass(slots=True)
class KiCadSymbolEmitResult:
    symbol_name: str
    library_path: str
    pin_count: int
    source_artifact: str
    evidence_property: str


def emit_kicad_symbol_library_from_pin_table(
    pin_table_path: str | Path,
    output_path: str | Path,
    symbol_name: str = DEFAULT_SYMBOL_NAME,
) -> KiCadSymbolEmitResult:
    pin_table = json.loads(Path(pin_table_path).read_text(encoding="utf-8"))
    if not pin_table.get("validation", {}).get("passed"):
        raise ValueError("pin table validation did not pass")
    rows = pin_table.get("rows", [])
    if pin_table.get("row_count") != 223 or len(rows) != 223:
        raise ValueError("expected a complete 223-row VFBGA223 pin table")

    pins = [_pin_from_row(row) for row in rows]
    library = _symbol_library(symbol_name, pins, pin_table)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(library, encoding="utf-8")
    return KiCadSymbolEmitResult(
        symbol_name=symbol_name,
        library_path=str(destination),
        pin_count=len(pins),
        source_artifact=str(pin_table_path),
        evidence_property=_evidence_property(pin_table),
    )


def _pin_from_row(row: dict[str, object]) -> KiCadSymbolPin:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    return KiCadSymbolPin(
        number=str(row.get("ball", "")),
        name=str(row.get("pin_name", "")),
        kind=_kicad_pin_kind(str(row.get("pin_name", "")), str(row.get("pin_type", ""))),
        functions=[str(function) for function in row.get("functions", []) if str(function) and str(function) != "-"],
        source_id=str(evidence.get("source_id", "")),
        source_table=str(evidence.get("table", "")),
        page_start=evidence.get("page_start") if isinstance(evidence.get("page_start"), int) else None,
        page_end=evidence.get("page_end") if isinstance(evidence.get("page_end"), int) else None,
    )


def _kicad_pin_kind(name: str, source_kind: str) -> str:
    upper_name = name.upper()
    if upper_name == "NC":
        return "no_connect"
    if re.match(r"^(VDD|VSS|VREF|VDDA|VSSA|VBAT|VCAP|USB_VDD)", upper_name):
        return "power_in"
    return {
        "I": "input",
        "O": "output",
        "I/O": "bidirectional",
        "A": "bidirectional",
        "S": "passive",
        "-": "unspecified",
    }.get(source_kind, "unspecified")


def _symbol_library(symbol_name: str, pins: list[KiCadSymbolPin], pin_table: dict[str, object]) -> str:
    ordered = sorted(pins, key=_pin_sort_key)
    height = max(80.0, len(ordered) * 1.27 / 2 + 20.0)
    top = round(height / 2, 2)
    bottom = -top
    middle = len(ordered) // 2
    pin_blocks = []
    for index, pin in enumerate(ordered):
        left = index < middle
        side_index = index if left else index - middle
        x = -38.1 if left else 38.1
        y = round(top - 10.16 - side_index * 1.27, 2)
        rotation = 0 if left else 180
        pin_blocks.append(_pin_block(pin, x, y, rotation))

    evidence = _evidence_property(pin_table)
    description = "OpenMV N6 derived STM32N657L0 VFBGA223 project-local symbol; evidence-backed generated library."
    return (
        "(kicad_symbol_lib\n"
        f"\t(version {SYMBOL_LIB_VERSION})\n"
        "\t(generator \"bodesign\")\n"
        "\t(generator_version \"1.0\")\n"
        f"\t(symbol \"{_escape(symbol_name)}\"\n"
        "\t\t(exclude_from_sim no)\n"
        "\t\t(in_bom yes)\n"
        "\t\t(on_board yes)\n"
        f"{_property('Reference', 'U', -30.48, top + 3.81, visible=True)}\n"
        f"{_property('Value', symbol_name, 7.62, top + 3.81, visible=True)}\n"
        f"{_property('Footprint', '', -30.48, bottom - 3.81, visible=False)}\n"
        f"{_property('Datasheet', 'stm32n657l0_datasheet#Table 18 pages 89-130', 0, 0, visible=False)}\n"
        f"{_property('Description', description, 0, 0, visible=False)}\n"
        f"{_property('BodesignEvidence', evidence, 0, 0, visible=False)}\n"
        f"{_property('ki_keywords', 'OpenMV STM32N657 STM32N6 VFBGA223 B0GK', 0, 0, visible=False)}\n"
        f"{_property('ki_fp_filters', DEFAULT_FOOTPRINT_FILTER, 0, 0, visible=False)}\n"
        f"\t\t(symbol \"{_escape(symbol_name)}_0_1\"\n"
        "\t\t\t(rectangle\n"
        f"\t\t\t\t(start -33.02 {bottom})\n"
        f"\t\t\t\t(end 33.02 {top})\n"
        "\t\t\t\t(stroke (width 0.254) (type default))\n"
        "\t\t\t\t(fill (type background))\n"
        "\t\t\t)\n"
        "\t\t)\n"
        f"\t\t(symbol \"{_escape(symbol_name)}_1_1\"\n"
        + "\n".join(pin_blocks)
        + "\n\t\t)\n"
        "\t)\n"
        ")\n"
    )


def _pin_sort_key(pin: KiCadSymbolPin) -> tuple[int, str, str]:
    name = pin.name.upper()
    if pin.kind == "power_in":
        group = 0
    elif name in {"NRST", "BOOT0", "PDR_ON", "PWR_ON", "OSC32_IN", "OSC32_OUT"}:
        group = 1
    elif pin.kind == "no_connect":
        group = 9
    else:
        group = 5
    return (group, name, pin.number)


def _pin_block(pin: KiCadSymbolPin, x: float, y: float, rotation: int) -> str:
    return (
        f"\t\t\t(pin {pin.kind} line\n"
        f"\t\t\t\t(at {x} {y} {rotation})\n"
        "\t\t\t\t(length 5.08)\n"
        f"\t\t\t\t(name \"{_escape(pin.name)}\" (effects (font (size 1.27 1.27))))\n"
        f"\t\t\t\t(number \"{_escape(pin.number)}\" (effects (font (size 1.27 1.27))))\n"
        "\t\t\t)"
    )


def _property(name: str, value: str, x: float, y: float, visible: bool) -> str:
    hide = "" if visible else " (hide yes)"
    return (
        f"\t\t(property \"{_escape(name)}\" \"{_escape(value)}\"\n"
        f"\t\t\t(at {x} {y} 0)\n"
        f"\t\t\t(effects (font (size 1.27 1.27)){hide})\n"
        "\t\t)"
    )


def _evidence_property(pin_table: dict[str, object]) -> str:
    return "; ".join(
        [
            f"artifact={pin_table.get('artifact_id', '')}",
            f"source={pin_table.get('source_id', '')}",
            f"pages={pin_table.get('source_pages', '')}",
            f"package={pin_table.get('package', '')}",
            f"rows={pin_table.get('row_count', '')}",
            "raw_pdf_text_committed=false",
        ]
    )


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
