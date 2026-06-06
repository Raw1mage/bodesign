from dataclasses import dataclass, field
import json
from pathlib import Path
import uuid

from .kicad_emit import DEFAULT_SYMBOL_DIR, _extract_symbol_block, _pin_endpoints, _project_document, load_symbol


SCHEMATIC_VERSION = "20250114"
PROJECT_NAME = "openmv_n6_subsystem"
MCU_LIB_ID = "openmv_generated:STM32N657L0_VFBGA223"
FLASH_LIB_ID = "openmv_generated:MX25UM25645GXDI00_24BGA"
CAP_LIB_ID = "Device:C"

# Voltage-unambiguous power-rail mapping: only connect MCU power balls whose
# voltage is encoded in the pin name, so no rail assignment is guessed. The
# evidence rail names come from openmv-n6-subsystem-constraints.json (power).
DECOUPLED_RAILS = ("VCC_1.8V", "VCC_3.3V")


def _rail_for_power_pin(pin_name: str) -> str | None:
    upper = pin_name.upper()
    if upper.startswith("VSS") or upper == "VREF-":
        return "GND"
    if upper == "VBAT":
        return "V_BATT"
    if upper.startswith("VDDA") and "18" in upper:
        return "VCC_1.8V"
    if upper.startswith("VDD") and "33" in upper:
        return "VCC_3.3V"
    return None  # ambiguous IO/core rail (VDD, VDDIO*, VDDCORE, VDDSMPS, VREF+, ...) -> deferred


@dataclass(slots=True)
class OpenMVSubsystemEmitResult:
    project_dir: str
    schematic_path: str
    project_path: str
    component_count: int
    net_count: int
    label_count: int
    evidence_artifacts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def emit_openmv_n6_subsystem_schematic(
    plan_dir: str | Path,
    output_dir: str | Path | None = None,
) -> OpenMVSubsystemEmitResult:
    plan_root = Path(plan_dir)
    generated_root = Path(output_dir) if output_dir is not None else plan_root / "generated" / PROJECT_NAME
    generated_root.mkdir(parents=True, exist_ok=True)

    symbol_library = plan_root / "libraries" / "symbols" / "openmv_generated.kicad_sym"
    pin_table_path = plan_root / "stm32n657-vfbga223-pin-table.json"
    flash_path = plan_root / "mx25um25645g-component-knowledge.json"
    constraints_path = plan_root / "openmv-n6-subsystem-constraints.json"

    symbol_source = symbol_library.read_text(encoding="utf-8")
    mcu_symbol = _extract_symbol_block(symbol_source, "STM32N657L0_VFBGA223")
    if mcu_symbol is None:
        raise ValueError("STM32N657L0_VFBGA223 symbol not found in project-local library")
    mcu_symbol = mcu_symbol.replace('(symbol "STM32N657L0_VFBGA223"', f'(symbol "{MCU_LIB_ID}"', 1)
    mcu_pins = _pin_endpoints(mcu_symbol)

    pin_table = json.loads(pin_table_path.read_text(encoding="utf-8"))
    flash = json.loads(flash_path.read_text(encoding="utf-8"))
    constraints = json.loads(constraints_path.read_text(encoding="utf-8"))
    flash_symbol, flash_pins = _flash_symbol(flash)

    cap_symbol, cap_pins = load_symbol(CAP_LIB_ID, DEFAULT_SYMBOL_DIR)

    components = [
        _component_block("U5", MCU_LIB_ID, "STM32N657L0_VFBGA223", 75.0, 120.0, sorted(mcu_pins), PROJECT_NAME),
        _component_block("U7", FLASH_LIB_ID, flash["resolved_part"]["mpn"], 195.0, 120.0, sorted(flash_pins), PROJECT_NAME),
    ]
    labels = []
    for net_name, mcu_pin, flash_pin in _xspi_nets(pin_table, flash):
        labels.append(_label_at(net_name, "U5", 75.0, 120.0, mcu_pins[mcu_pin]))
        labels.append(_label_at(net_name, "U7", 195.0, 120.0, flash_pins[flash_pin]))
    for net_name, flash_pin in [("VCC_1.8V_GATED", "B4"), ("VCC_1.8V_GATED", "D1"), ("GND", "B3"), ("GND", "C1"), ("GND", "E5")]:
        labels.append(_label_at(net_name, "U7", 195.0, 120.0, flash_pins[flash_pin]))

    # Power backbone: connect voltage-unambiguous MCU power balls to named rails.
    power_connections, deferred_power_pins = _power_connections(pin_table)
    for rail, ball in power_connections:
        labels.append(_label_at(rail, "U5", 75.0, 120.0, mcu_pins[ball]))

    # Decoupling capacitors on each main rail to GND (standard practice).
    cap_index = 0
    for rail in DECOUPLED_RAILS:
        if not any(connected_rail == rail for connected_rail, _ball in power_connections):
            continue
        for _ in range(2):
            cap_index += 1
            ref = f"C{cap_index}"
            cx, cy = 40.0 + cap_index * 14.0, 170.0
            components.append(_component_block(ref, CAP_LIB_ID, "100nF", cx, cy, ["1", "2"], PROJECT_NAME))
            labels.append(_label_at(rail, ref, cx, cy, cap_pins["1"]))
            labels.append(_label_at("GND", ref, cx, cy, cap_pins["2"]))

    schematic = _schematic_document([mcu_symbol, flash_symbol, cap_symbol], components, labels)
    schematic_path = generated_root / f"{PROJECT_NAME}.kicad_sch"
    project_path = generated_root / f"{PROJECT_NAME}.kicad_pro"
    schematic_path.write_text(schematic, encoding="utf-8")
    project_path.write_text(_project_document(), encoding="utf-8")
    warnings = list(constraints.get("global_gaps", []))
    if deferred_power_pins:
        warnings.append(
            "Power pins with ambiguous (non-name-encoded) rail voltage were left unconnected pending "
            "datasheet rail confirmation: " + ", ".join(deferred_power_pins)
        )
    warnings.append(
        "USB-C/USB-HS and peripheral subsystems (charger, regulators, PHYs, connectors) are not emitted yet: "
        "their symbols are not in the project library and the MCU USB data balls are not verified — deferred to "
        "symbol generation + pin verification (no guessed parts/pins per stop gate)."
    )

    return OpenMVSubsystemEmitResult(
        project_dir=str(generated_root),
        schematic_path=str(schematic_path),
        project_path=str(project_path),
        component_count=len(components),
        net_count=len({label[0] for label in labels}),
        label_count=len(labels),
        evidence_artifacts=[str(pin_table_path), str(flash_path), str(constraints_path)],
        warnings=warnings,
    )


def _xspi_nets(pin_table: dict[str, object], flash: dict[str, object]) -> list[tuple[str, str, str]]:
    by_name = {row["pin_name"]: row["ball"] for row in pin_table["rows"]}
    flash_by_net = {row["schematic_net"]: row["ball"] for row in flash["pinout"] if row.get("schematic_net")}
    requested = [
        ("XSPIM_P2_IO0", "PN5", "XSPIM_P2_IO0"),
        ("XSPIM_P2_IO1", "PN4", "XSPIM_P2_IO1"),
        ("XSPIM_P2_IO2", "PN3", "XSPIM_P2_IO2"),
        ("XSPIM_P2_IO3", "PN2", "XSPIM_P2_IO3"),
        ("XSPIM_P2_IO4", "PP1", "XSPIM_P2_IO4"),
        ("XSPIM_P2_IO5", "PP0", "XSPIM_P2_IO5"),
        ("XSPIM_P2_IO6", "PP3", "XSPIM_P2_IO6"),
        ("XSPIM_P2_IO7", "PP2", "XSPIM_P2_IO7"),
        ("XSPIM_P2_DQS0", "PN6", "XSPIM_P2_DQS0"),
        ("XSPIM_P2_NCS1", "PN1", "XSPIM_P2_NCS1"),
        ("XSPIM_P2_CLK_P", "PN0", "XSPIM_P2_CLK_P"),
        ("XSPIM_P2_RST#", "PN7", "XSPIM_P2_RST#"),
    ]
    nets = []
    for net_name, mcu_name, flash_net in requested:
        if mcu_name in by_name and flash_net in flash_by_net:
            nets.append((net_name, by_name[mcu_name], flash_by_net[flash_net]))
    return nets


def _flash_symbol(flash: dict[str, object]) -> tuple[str, dict[str, tuple[float, float]]]:
    pins = list(flash["pinout"])
    half = len(pins) // 2
    blocks = []
    endpoints: dict[str, tuple[float, float]] = {}
    for index, pin in enumerate(pins):
        left = index < half
        side_index = index if left else index - half
        x = -25.4 if left else 25.4
        y = round(13.97 - side_index * 2.54, 2)
        rotation = 0 if left else 180
        kind = "power_in" if pin["symbol"] in {"VCC", "VCCQ", "GND", "VSSQ"} else "bidirectional"
        number = pin["ball"]
        name = pin["symbol"]
        endpoints[number] = (x, y)
        blocks.append(
            f"\t\t\t(pin {kind} line\n"
            f"\t\t\t\t(at {x} {y} {rotation})\n"
            "\t\t\t\t(length 5.08)\n"
            f"\t\t\t\t(name \"{_escape(name)}\" (effects (font (size 1.27 1.27))))\n"
            f"\t\t\t\t(number \"{_escape(number)}\" (effects (font (size 1.27 1.27))))\n"
            "\t\t\t)"
        )
    evidence = "artifact=mx25um25645g-component-knowledge; source=openmv_n6_schematic_rev4+mx25um25645g_flash_datasheet; raw_pdf_text_committed=false"
    symbol = (
        f"\t(symbol \"{FLASH_LIB_ID}\"\n"
        "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
        "\t\t(property \"Reference\" \"U\" (at -20.32 19.05 0) (effects (font (size 1.27 1.27))))\n"
        f"\t\t(property \"Value\" \"{_escape(flash['resolved_part']['mpn'])}\" (at -2.54 19.05 0) (effects (font (size 1.27 1.27))))\n"
        "\t\t(property \"Footprint\" \"\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n"
        f"\t\t(property \"BodesignEvidence\" \"{evidence}\" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n"
        "\t\t(symbol \"MX25UM25645GXDI00_24BGA_0_1\"\n"
        "\t\t\t(rectangle (start -20.32 -20.32) (end 20.32 20.32) (stroke (width 0.254) (type default)) (fill (type background)))\n"
        "\t\t)\n"
        "\t\t(symbol \"MX25UM25645GXDI00_24BGA_1_1\"\n"
        + "\n".join(blocks)
        + "\n\t\t)\n\t)"
    )
    return symbol, endpoints


def _component_block(ref: str, lib_id: str, value: str, x: float, y: float, pins: list[str], project_name: str) -> str:
    pin_blocks = "\n".join(f'    (pin "{_escape(pin)}" (uuid "{_stable_uuid(ref, pin)}"))' for pin in pins)
    return f'''  (symbol
    (lib_id "{_escape(lib_id)}")
    (at {x} {y} 0)
    (unit 1)
    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid "{_stable_uuid(ref)}")
    (property "Reference" "{_escape(ref)}" (at {x + 2.54} {y - 1.27} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{_escape(value)}" (at {x + 2.54} {y + 1.27} 0) (effects (font (size 1.27 1.27))))
    (property "BodesignEvidence" "project-local generated source; raw_pdf_text_committed=false" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
{pin_blocks}
    (instances (project "{project_name}" (path "/{_stable_uuid('root')}" (reference "{_escape(ref)}") (unit 1))))
  )'''


def _label_at(name: str, ref: str, sx: float, sy: float, endpoint: tuple[float, float]) -> tuple[str, str]:
    x = round(sx + endpoint[0], 4)
    y = round(sy - endpoint[1], 4)
    # Include the placement so multiple same-net labels on one part (e.g. the 18 ground
    # balls -> GND) get distinct UUIDs rather than colliding.
    label_uuid = _stable_uuid(ref, name, f"{x}", f"{y}")
    return name, f'  (global_label "{_escape(name)}" (shape bidirectional) (at {x} {y} 0)\n    (effects (font (size 1.27 1.27)) (justify left)) (uuid "{label_uuid}"))'


def _power_connections(pin_table: dict[str, object]) -> tuple[list[tuple[str, str]], list[str]]:
    """Map each MCU power ball to a rail when its voltage is name-encoded.

    Returns (connections, deferred) where connections is [(rail, ball)] and
    deferred lists ambiguous power pin names that were intentionally not wired.
    """
    connections: list[tuple[str, str]] = []
    deferred: set[str] = set()
    for row in pin_table["rows"]:
        name = str(row["pin_name"])
        upper = name.upper()
        rail = _rail_for_power_pin(name)
        if rail is not None:
            connections.append((rail, str(row["ball"])))
        elif upper.startswith("VDD") or upper.startswith("VREF"):
            deferred.add(name)
    return connections, sorted(deferred)


def _schematic_document(symbol_defs: list[str], component_blocks: list[str], labels: list[tuple[str, str]]) -> str:
    return (
        "(kicad_sch\n"
        f"  (version {SCHEMATIC_VERSION})\n"
        "  (generator \"bodesign\")\n"
        "  (generator_version \"9.0\")\n"
        f"  (uuid \"{_stable_uuid('root')}\")\n"
        "  (paper \"A4\")\n"
        "  (lib_symbols\n"
        + "\n".join(symbol_defs)
        + "\n  )\n"
        + "\n".join(component_blocks)
        + "\n"
        + "\n".join(label for _, label in labels)
        + "\n  (sheet_instances (path \"/\" (page \"1\")))\n"
        + ")\n"
    )


def _stable_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "bodesign/openmv-n6/" + "/".join(parts)))


def _escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
