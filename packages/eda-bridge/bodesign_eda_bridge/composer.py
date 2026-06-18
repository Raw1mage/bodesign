"""Generalized subsystem composer (G3 / N10): design spec → schematic IR → emit.

Turns a declarative design spec (components + named-net interconnect) into the
EmitComponent/EmitNet IR and emits a `kicad-cli`-validatable schematic. This is
the generic, spec-driven generalization of the OpenMV-specific subsystem
emitter: auto-places components on a grid, parses `"REF.PIN"` node strings,
resolves symbols across multiple sources (stdlib + project-local generated
libraries), and reuses `emit_kicad_schematic` for the actual S-expr + global-
label connectivity.

Spec shape:
    {
      "components": [{"ref": "U5", "symbol": "Device:R", "value": "10k", "footprint": "..."}],
      "nets": [{"name": "VCC_3.3V", "nodes": ["U5.1", "C1.1"]}],
    }
"""

from dataclasses import dataclass, field
from pathlib import Path

from .kicad_emit import DEFAULT_SYMBOL_DIR, EmitComponent, EmitNet, SchematicEmitResult, emit_kicad_schematic, validate_kicad_schematic


@dataclass(slots=True)
class ComposeResult:
    emit: SchematicEmitResult
    validation: object | None = None
    placed: int = 0
    nets: int = 0
    warnings: list[str] = field(default_factory=list)


def _auto_place(index: int, columns: int = 4, dx: float = 45.0, dy: float = 45.0, x0: float = 35.0, y0: float = 35.0) -> tuple[float, float]:
    return (round(x0 + (index % columns) * dx, 3), round(y0 + (index // columns) * dy, 3))


def _parse_node(node: str) -> tuple[str, str]:
    ref, _, pin = node.partition(".")
    return ref.strip(), pin.strip()


def compose_schematic(
    out_dir: str | Path,
    project_name: str,
    spec: dict,
    symbol_dirs: str | Path | list = DEFAULT_SYMBOL_DIR,
    columns: int = 4,
    validate: bool = False,
    connection_style: str = "label",
) -> ComposeResult:
    raw_components = spec.get("components", [])
    raw_nets = spec.get("nets", [])
    warnings: list[str] = []

    components: list[EmitComponent] = []
    for index, comp in enumerate(raw_components):
        ref = str(comp.get("ref", "")).strip()
        symbol = str(comp.get("symbol", "")).strip()
        if not ref or not symbol:
            warnings.append(f"component #{index} missing ref/symbol; skipped")
            continue
        # Level-1 AI/tool split: honour caller-supplied placement (x, y) when present;
        # only fall back to the naive grid when the spec omits coordinates. The AI owns
        # placement (the spatial/aesthetic judgement); the tool owns wire geometry.
        if comp.get("x") is not None and comp.get("y") is not None:
            x, y = float(comp["x"]), float(comp["y"])
        else:
            x, y = _auto_place(index, columns)
        components.append(EmitComponent(
            ref=ref, lib_id=symbol, value=str(comp.get("value", "")),
            footprint=str(comp.get("footprint", "")), x=x, y=y,
        ))

    nets: list[EmitNet] = []
    for net in raw_nets:
        name = str(net.get("name", "")).strip()
        nodes = [_parse_node(str(n)) for n in net.get("nodes", []) if "." in str(n)]
        if name and nodes:
            nets.append(EmitNet(name=name, nodes=nodes))

    emit = emit_kicad_schematic(out_dir, project_name, components, nets, symbol_dir=symbol_dirs, connection_style=connection_style)
    warnings.extend(emit.warnings)
    result = ComposeResult(emit=emit, placed=emit.component_count, nets=emit.net_count, warnings=warnings)
    if validate:
        result.validation = validate_kicad_schematic(emit.schematic_path)
    return result
