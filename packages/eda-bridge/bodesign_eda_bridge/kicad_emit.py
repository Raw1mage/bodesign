"""Emit a real, KiCad-openable schematic from BoardDesign-style IR.

This is the first *real* (non-represented) EDA bridge capability: given a small
set of placed components (each referencing a KiCad symbol `lib_id`) and a net
list, write a `.kicad_pro` + `.kicad_sch` that KiCad 9 accepts, then validate it
with `kicad-cli` (ERC + netlist export).

Design choices, validated against `kicad-cli` 9.0.9:
  - Used symbol definitions are embedded into the schematic `lib_symbols`
    section (renamed with their `Lib:Name` id) so the file is self-contained.
  - Connectivity uses *global labels* placed exactly on each pin endpoint
    instead of drawn wires, so the emitter never has to solve wire-routing
    geometry. KiCad merges pins that share a net label.
  - A library symbol's pin local coordinate `(px, py)` maps to a schematic
    endpoint of `(Sx + px, Sy - py)` for a symbol placed at `(Sx, Sy)` with
    rotation 0 (the library Y axis is inverted on instantiation).

Only single-unit symbols and rotation-0 placement are supported in this slice;
multi-unit symbols and rotated placement are explicit future work.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import subprocess
import uuid as _uuid

DEFAULT_SYMBOL_DIR = os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
DEFAULT_PROJECT_TEMPLATE = os.environ.get("KICAD_PROJECT_TEMPLATE", "/usr/share/kicad/template/kicad.kicad_pro")
SCHEMATIC_VERSION = "20250114"
PIN_RE = re.compile(r"\(pin\s+\S+\s+\S+\s*\(at\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)")
NUMBER_RE = re.compile(r'\(number\s+"([^"]+)"')


@dataclass(slots=True)
class EmitComponent:
    ref: str
    lib_id: str
    value: str = ""
    footprint: str = ""
    x: float = 0.0
    y: float = 0.0


@dataclass(slots=True)
class EmitNet:
    name: str
    nodes: list[tuple[str, str]] = field(default_factory=list)  # (ref, pin)


@dataclass(slots=True)
class SchematicEmitResult:
    project_dir: str
    schematic_path: str
    project_path: str
    embedded_symbols: list[str] = field(default_factory=list)
    component_count: int = 0
    net_count: int = 0
    label_count: int = 0
    unresolved_pins: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KiCadValidationResult:
    kicad_cli: str = "unavailable"
    status: str = "skipped-no-kicad-cli"
    erc_violations: int | None = None
    erc_errors: int | None = None
    netlist_components: int = 0
    netlist_nets: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _uid() -> str:
    return str(_uuid.uuid4())


def load_symbol(lib_id: str, symbol_dir: str | Path | list = DEFAULT_SYMBOL_DIR) -> tuple[str, dict[str, tuple[float, float]]]:
    """Return (embedded symbol definition text, {pin_number: (x, y)}).

    `symbol_dir` may be a single directory or a list of directories (tried in
    order) — so stdlib symbols and project-local generated libraries
    (e.g. `openmv_generated.kicad_sym`) can be resolved together.

    Raises FileNotFoundError if the library is found in none of the dirs, and
    KeyError if the symbol is not present in the located library.
    """
    library, _, name = lib_id.partition(":")
    if not name:
        raise KeyError(f"lib_id must be 'Library:Symbol', got {lib_id!r}")
    dirs = [symbol_dir] if isinstance(symbol_dir, (str, Path)) else list(symbol_dir)
    lib_path = next((Path(d) / f"{library}.kicad_sym" for d in dirs if (Path(d) / f"{library}.kicad_sym").exists()), None)
    if lib_path is None:
        raise FileNotFoundError(f"KiCad symbol library '{library}.kicad_sym' not found in: {[str(d) for d in dirs]}")
    source = lib_path.read_text(encoding="utf-8", errors="ignore")
    block = _extract_symbol_block(source, name)
    if block is None:
        raise KeyError(f"Symbol {name!r} not found in {lib_path}")
    embedded = block.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
    return embedded, _pin_endpoints(block)


def _extract_symbol_block(source: str, name: str) -> str | None:
    marker = f'(symbol "{name}"'
    start = source.find(marker)
    if start == -1:
        return None
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return None


def _pin_endpoints(block: str) -> dict[str, tuple[float, float]]:
    endpoints: dict[str, tuple[float, float]] = {}
    for pin_match in PIN_RE.finditer(block):
        x, y = float(pin_match.group(1)), float(pin_match.group(2))
        number_match = NUMBER_RE.search(block, pin_match.end())
        if number_match is None:
            continue
        endpoints.setdefault(number_match.group(1), (x, y))
    return endpoints


def emit_kicad_schematic(
    project_dir: str | Path,
    project_name: str,
    components: list[EmitComponent],
    nets: list[EmitNet],
    symbol_dir: str | Path = DEFAULT_SYMBOL_DIR,
) -> SchematicEmitResult:
    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    root_uuid = _uid()

    embedded_defs: dict[str, str] = {}
    pin_maps: dict[str, dict[str, tuple[float, float]]] = {}
    warnings: list[str] = []
    for component in components:
        if component.lib_id in embedded_defs:
            continue
        try:
            definition, pins = load_symbol(component.lib_id, symbol_dir)
        except (FileNotFoundError, KeyError) as error:
            warnings.append(f"{component.ref}: {error}")
            continue
        embedded_defs[component.lib_id] = definition
        pin_maps[component.lib_id] = pins

    placements = {component.ref: component for component in components}
    symbol_blocks = [
        _symbol_instance_block(component, project_name, root_uuid)
        for component in components
        if component.lib_id in embedded_defs
    ]

    label_blocks: list[str] = []
    unresolved: list[str] = []
    for net in nets:
        for ref, pin in net.nodes:
            component = placements.get(ref)
            if component is None or component.lib_id not in pin_maps:
                unresolved.append(f"{ref}.{pin}")
                continue
            endpoint = pin_maps[component.lib_id].get(pin)
            if endpoint is None:
                unresolved.append(f"{ref}.{pin}")
                continue
            label_x = round(component.x + endpoint[0], 4)
            label_y = round(component.y - endpoint[1], 4)
            label_blocks.append(_global_label_block(net.name, label_x, label_y))

    schematic = _schematic_document(root_uuid, embedded_defs.values(), symbol_blocks, label_blocks)
    schematic_path = root / f"{project_name}.kicad_sch"
    schematic_path.write_text(schematic, encoding="utf-8")
    project_path = root / f"{project_name}.kicad_pro"
    project_path.write_text(_project_document(), encoding="utf-8")

    return SchematicEmitResult(
        project_dir=str(root),
        schematic_path=str(schematic_path),
        project_path=str(project_path),
        embedded_symbols=sorted(embedded_defs),
        component_count=len(symbol_blocks),
        net_count=len(nets),
        label_count=len(label_blocks),
        unresolved_pins=unresolved,
        warnings=warnings,
    )


def _symbol_instance_block(component: EmitComponent, project_name: str, root_uuid: str) -> str:
    ref_uuid = _uid()
    pin_uuids = "\n".join(f'    (pin "{number}" (uuid "{_uid()}"))' for number in ("1", "2"))
    return f'''  (symbol
    (lib_id "{component.lib_id}")
    (at {component.x} {component.y} 0)
    (unit 1)
    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid "{ref_uuid}")
    (property "Reference" "{component.ref}" (at {component.x + 2.54} {component.y - 1.27} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{component.value}" (at {component.x + 2.54} {component.y + 1.27} 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "{component.footprint}" (at {component.x} {component.y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
{pin_uuids}
    (instances (project "{project_name}" (path "/{root_uuid}" (reference "{component.ref}") (unit 1))))
  )'''


def _global_label_block(name: str, x: float, y: float) -> str:
    return (
        f'  (global_label "{name}" (shape bidirectional) (at {x} {y} 0)\n'
        f'    (effects (font (size 1.27 1.27)) (justify left)) (uuid "{_uid()}"))'
    )


def _schematic_document(root_uuid: str, definitions, symbol_blocks, label_blocks) -> str:
    lib_symbols = "\n".join(definitions)
    body = "\n".join([*symbol_blocks, *label_blocks])
    return (
        "(kicad_sch\n"
        f'  (version {SCHEMATIC_VERSION})\n'
        '  (generator "bodesign")\n'
        '  (generator_version "9.0")\n'
        f'  (uuid "{root_uuid}")\n'
        '  (paper "A4")\n'
        f"  (lib_symbols\n{lib_symbols}\n  )\n"
        f"{body}\n"
        '  (sheet_instances (path "/" (page "1")))\n'
        ")\n"
    )


def _project_document() -> str:
    template = Path(DEFAULT_PROJECT_TEMPLATE)
    if template.exists():
        return template.read_text(encoding="utf-8", errors="ignore")
    return '{\n  "board": {},\n  "schematic": {},\n  "sheets": [],\n  "version": 1\n}\n'


def validate_kicad_schematic(schematic_path: str | Path, output_dir: str | Path | None = None) -> KiCadValidationResult:
    import shutil

    cli = shutil.which("kicad-cli")
    if cli is None:
        return KiCadValidationResult(warnings=["kicad-cli not found on PATH; emitted files were not validated."])

    schematic = Path(schematic_path)
    out_root = Path(output_dir) if output_dir is not None else schematic.parent
    out_root.mkdir(parents=True, exist_ok=True)
    erc_report = out_root / f"{schematic.stem}.erc.rpt"
    netlist_path = out_root / f"{schematic.stem}.net"
    result = KiCadValidationResult(kicad_cli=cli, status="validated")

    erc = subprocess.run([cli, "sch", "erc", str(schematic), "-o", str(erc_report)], capture_output=True, text=True)
    if erc_report.exists():
        report_text = erc_report.read_text(encoding="utf-8", errors="ignore")
        result.erc_violations = _int_after(report_text, r"ERC messages:\s*(\d+)")
        result.erc_errors = _int_after(report_text, r"Errors\s+(\d+)")
    elif erc.returncode != 0:
        result.status = "erc-failed"
        result.warnings.append((erc.stderr or erc.stdout or "kicad-cli sch erc failed").strip()[:300])

    netlist = subprocess.run(
        [cli, "sch", "export", "netlist", str(schematic), "-o", str(netlist_path)],
        capture_output=True,
        text=True,
    )
    if netlist_path.exists():
        net_text = netlist_path.read_text(encoding="utf-8", errors="ignore")
        result.netlist_components = len(re.findall(r'\(comp\s+\(ref\b', net_text))
        result.netlist_nets = _parse_netlist_nets(net_text)
    elif netlist.returncode != 0:
        result.status = "netlist-failed"
        result.warnings.append((netlist.stderr or netlist.stdout or "kicad-cli sch export netlist failed").strip()[:300])

    return result


def _int_after(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _parse_netlist_nets(net_text: str) -> list[dict[str, object]]:
    nets: list[dict[str, object]] = []
    for net_match in re.finditer(r'\(net\s+\(code\s+"[^"]*"\)\s+\(name\s+"([^"]*)"\)(.*?)(?=\(net\s+\(code|\)\s*\)\s*$)', net_text, re.DOTALL):
        name = net_match.group(1)
        nodes = [f"{ref}.{pin}" for ref, pin in re.findall(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', net_match.group(2))]
        if nodes:
            nets.append({"name": name, "nodes": nodes})
    return nets
