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


def _snap_grid(value: float, grid: float = 1.27) -> float:
    """Snap a coordinate onto KiCad's connection grid (default 1.27 mm / 50 mil).

    Library pin local offsets are grid-multiples, so once a symbol origin is snapped
    its absolute pin endpoints land on-grid too — which is what lets a drawn wire end
    actually merge with the pin (off-grid endpoints surface as `pin_not_connected` in
    ERC and `endpoint_off_grid` warnings).
    """
    return round(round(value / grid) * grid, 4)


def vault_symbol(repository, mpn: str) -> dict:
    """Consult the component vault for a verified KiCad symbol mapping (R5).

    `repository` is a component-kb VaultRepository (duck-typed; this module
    takes it as a parameter and never imports component-kb). Returns the
    vault answer verbatim: {status: found, assets: [...]} with library_ref +
    verification_status, or an explicit {status: absent} — the emitter must
    NOT guess a lib_id when the vault has no mapping.
    """
    return repository.query_eda_asset(mpn, "kicad-symbol")


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
    block = _flatten_extends(block, name, source)
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


def _balanced_block(s: str, start: int) -> str:
    depth = 0
    for index in range(start, len(s)):
        if s[index] == "(":
            depth += 1
        elif s[index] == ")":
            depth -= 1
            if depth == 0:
                return s[start : index + 1]
    return s[start:]


def _symbol_children(block: str) -> list[str]:
    """Immediate child s-expressions of a ``(symbol "NAME" ...)`` block."""
    i = block.index('"')
    i = block.index('"', i + 1) + 1  # skip past the symbol name string
    children: list[str] = []
    while i < len(block):
        while i < len(block) and block[i] not in "()":
            i += 1
        if i >= len(block) or block[i] == ")":
            break
        sub = _balanced_block(block, i)
        children.append(sub)
        i += len(sub)
    return children


def _flatten_extends(block: str, name: str, source: str, _depth: int = 0) -> str:
    """Resolve a derived symbol (``(extends "Base")``) into a standalone one.

    KiCad schematic ``lib_symbols`` cannot carry ``extends`` — eeschema flattens
    derived symbols on save, and ``kicad-cli`` refuses to load a schematic whose
    embedded symbol still references an unresolved base. We reconstruct the
    derived symbol from the base's graphics/pins (its unit sub-symbols renamed to
    the derived name) plus the derived symbol's own property overrides.
    """
    match = re.search(r'\(extends "([^"]+)"\)', block)
    if match is None or _depth > 8:
        return block
    base_name = match.group(1)
    base = _extract_symbol_block(source, base_name)
    if base is None:
        return block  # base absent from this library; leave as-is rather than crash
    base = _flatten_extends(base, base_name, source, _depth + 1)  # base may itself extend
    derived_props = [c for c in _symbol_children(block) if c.startswith("(property")]
    base_children = _symbol_children(base)
    base_attrs = [c for c in base_children
                  if not c.startswith("(property") and not c.startswith('(symbol "')]
    base_units = [c.replace(f"{base_name}_", f"{name}_") for c in base_children
                  if c.startswith(f'(symbol "{base_name}_')]
    body = "\n".join(base_attrs + derived_props + base_units)
    return f'(symbol "{name}"\n{body}\n)'


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
    connection_style: str = "label",
) -> SchematicEmitResult:
    """Emit a `.kicad_sch` + `.kicad_pro` from placed components and a net list.

    connection_style taxonomy (the AI/tool split — Level 1):
      - "label" (default, unchanged): every pin of every net gets a global label.
        Electrically correct, visually sparse; no drawn wires. Back-compat path.
      - "wire": a 2-node net is joined by a drawn orthogonal wire between its two
        pin endpoints (tool auto-routes the geometry from the AI-supplied placement),
        plus ONE local label at the wire midpoint to preserve the net name. Nets with
        !=2 resolvable nodes fall back to global labels (buses / power / single-pin),
        so the result is always ERC-valid.
      - "auto": alias of "wire" (kept for forward-compat naming).

    Only the connectivity emission differs by style; placement is the caller's job
    (AI supplies component.x / component.y). The tool never invents placement here.
    """
    drawn = connection_style in ("wire", "auto")
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

    # Snap every component onto KiCad's 1.27 mm connection grid. Library pin local
    # offsets are grid-multiples, so once the symbol origin is on-grid the absolute
    # pin endpoint is too — which is what lets a drawn wire end actually merge with
    # the pin (off-grid endpoints read as `pin_not_connected` in ERC). Harmless to
    # label mode (global labels don't require grid alignment).
    for component in components:
        component.x = _snap_grid(component.x)
        component.y = _snap_grid(component.y)

    placements = {component.ref: component for component in components}
    symbol_blocks = [
        _symbol_instance_block(component, project_name, root_uuid)
        for component in components
        if component.lib_id in embedded_defs
    ]

    def _pin_abs(ref: str, pin: str) -> tuple[float, float] | None:
        component = placements.get(ref)
        if component is None or component.lib_id not in pin_maps:
            return None
        endpoint = pin_maps[component.lib_id].get(pin)
        if endpoint is None:
            return None
        return (round(component.x + endpoint[0], 4), round(component.y - endpoint[1], 4))

    label_blocks: list[str] = []
    wire_blocks: list[str] = []
    junction_blocks: list[str] = []
    unresolved: list[str] = []
    for net in nets:
        endpoints: list[tuple[float, float]] = []
        net_unresolved = False
        for ref, pin in net.nodes:
            abs_pt = _pin_abs(ref, pin)
            if abs_pt is None:
                unresolved.append(f"{ref}.{pin}")
                net_unresolved = True
                continue
            endpoints.append(abs_pt)

        # Drawn-wire mode: 2 pins → L-route; 3+ pins → trunk + stubs + junctions.
        if drawn and not net_unresolved and len(endpoints) == 2:
            waypoints = _orthogonal_route(endpoints[0], endpoints[1])
            for a, b in zip(waypoints, waypoints[1:]):
                wire_blocks.append(_wire_segment_block(a[0], a[1], b[0], b[1]))
            mid = waypoints[len(waypoints) // 2]
            label_blocks.append(_local_label_block(net.name, mid[0], mid[1]))
        elif drawn and not net_unresolved and len(endpoints) >= 3:
            segments, junctions = _bus_route(endpoints)
            for (a, b) in segments:
                wire_blocks.append(_wire_segment_block(a[0], a[1], b[0], b[1]))
            for (jx, jy) in junctions:
                junction_blocks.append(_junction_block(jx, jy))
            # one local label on the trunk's left end to name the net
            trunk = segments[0]
            label_blocks.append(_local_label_block(net.name, trunk[0][0], trunk[0][1]))
        else:
            # label fallback: power, single-pin, unresolved, or style=label
            for abs_pt in endpoints:
                label_blocks.append(_global_label_block(net.name, abs_pt[0], abs_pt[1]))

    schematic = _schematic_document(
        root_uuid, embedded_defs.values(), symbol_blocks, label_blocks, wire_blocks, junction_blocks
    )
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


def _local_label_block(name: str, x: float, y: float) -> str:
    """A plain (label ...) names a wire net locally without the global-label glyph.

    Used in drawn-wire mode so a 2-pin point-to-point net keeps its declared name
    (otherwise kicad-cli's netlist would auto-name it Net-(U1-Pad1)). Placed at the
    wire's mid-segment so it sits on copper, not on a pin.
    """
    return (
        f'  (label "{name}" (at {x} {y} 0)\n'
        f'    (effects (font (size 1.27 1.27)) (justify left)) (uuid "{_uid()}"))'
    )


def _wire_segment_block(x1: float, y1: float, x2: float, y2: float) -> str:
    """One straight wire segment between two absolute schematic points."""
    return (
        f'  (wire (pts (xy {round(x1, 4)} {round(y1, 4)}) (xy {round(x2, 4)} {round(y2, 4)}))\n'
        f'    (stroke (width 0) (type default)) (uuid "{_uid()}"))'
    )


def _junction_block(x: float, y: float) -> str:
    """A junction dot marks an electrical connection where 3+ wires meet."""
    return f'  (junction (at {round(x, 4)} {round(y, 4)}) (diameter 0) (color 0 0 0 0) (uuid "{_uid()}"))'


def _orthogonal_route(p1: tuple[float, float], p2: tuple[float, float]) -> list[tuple[float, float]]:
    """Level-1 auto-router: return the polyline waypoints for an orthogonal (Manhattan)
    connection between two pin endpoints.

    Taxonomy:
      - input  p1, p2: absolute schematic (x, y) of the two pin endpoints to join.
      - output: ordered list of >=2 waypoints; consecutive pairs are axis-aligned
                segments. NOT allowed to return a diagonal segment.
      - rule: collinear pins (same x or same y) → single straight segment [p1, p2];
              otherwise an L-route through one elbow [p1, (p2.x, p1.y), p2]
              (horizontal-first), which KiCad renders as two segments + the elbow
              needs no junction (a 2-wire corner is implicit).
      - done when: every returned consecutive pair shares an axis (dx==0 or dy==0).
    """
    (x1, y1), (x2, y2) = p1, p2
    if abs(x1 - x2) < 1e-6 or abs(y1 - y2) < 1e-6:
        return [p1, p2]
    return [p1, (x2, y1), p2]


def _bus_route(endpoints: list[tuple[float, float]]) -> tuple[list[tuple[tuple[float, float], tuple[float, float]]], list[tuple[float, float]]]:
    """Multi-node (3+ pin) net router: a routing-channel daisy-chain.

    Rationale (root cause of the trunk approach's failure): a single horizontal trunk
    spanning all component x-columns crosses each (vertical) part's axis, so it can
    collide with the OTHER pin of a 2-pin part — producing phantom shorts and leaving
    pins unconnected. Instead we route every pin out to a shared horizontal CHANNEL that
    sits in clear space below all pins, then run ONE channel wire along it, tapping each
    pin's drop-wire with a junction. The drops are vertical (pin.x → channel_y); the
    channel is horizontal at a y strictly below every pin, so it never overlaps a symbol
    body or the part's other pin.

    Taxonomy:
      - input  endpoints: >=3 absolute pin (x, y) on one net (duplicate x allowed).
      - output (segments, junctions):
          segments  = vertical drop per pin (pin → channel_y) + one horizontal channel
                      wire spanning [min_x, max_x] at channel_y. All axis-aligned.
          junctions = a dot at every (pin_x, channel_y) tap that is interior to the
                      channel span (the electrically-required 3-way meets); the two
                      extreme taps are channel endpoints and need none.
      - NOT allowed: a diagonal segment; a channel y that is not strictly below every pin.
      - rule: channel_y = max(pin_y) + 5.08 mm (grid: 4×1.27), guaranteed below all pins
              so drops never cross a symbol. Each distinct pin.x gets one drop; shared-x
              pins share a drop. Junctions only at interior taps.
      - done when: every pin reaches the channel by one vertical drop and the channel is
              a single horizontal wire covering [min_x, max_x].
    """
    # Dedupe coincident pins, order left→right (then top→bottom) for a stable chain.
    pts: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for p in sorted(endpoints, key=lambda q: (q[0], q[1])):
        if p in seen:
            continue
        seen.add(p)
        pts.append(p)

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    junctions: list[tuple[float, float]] = []
    # Daisy-chain consecutive pins with the proven 2-pin orthogonal router.
    for a, b in zip(pts, pts[1:]):
        waypoints = _orthogonal_route(a, b)
        for s, e in zip(waypoints, waypoints[1:]):
            segments.append((s, e))
    # An interior pin has a chain wire arriving AND leaving at its endpoint → with the
    # symbol pin that is a 3-way meet, so it needs a junction dot. The two end pins of
    # the chain are simple endpoint-to-endpoint joins and need none.
    for p in pts[1:-1]:
        junctions.append(p)
    return segments, junctions


def _schematic_document(root_uuid: str, definitions, symbol_blocks, label_blocks, wire_blocks=(), junction_blocks=()) -> str:
    lib_symbols = "\n".join(definitions)
    body = "\n".join([*symbol_blocks, *wire_blocks, *junction_blocks, *label_blocks])
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
