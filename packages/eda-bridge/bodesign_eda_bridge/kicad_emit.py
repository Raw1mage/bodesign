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
NAME_RE = re.compile(r'\(name\s+"([^"]+)"')
# A pin's NAME text is drawn INSIDE the symbol body, starting one pin-name offset
# in from the pin endpoint and running toward the body centre. A net label placed
# at that same pin endpoint (justify left => text runs +x) collides with this
# in-body name text — the dominant black-blob cause the label-vs-label stagger
# never saw. We model each pin-name's rendered box so the label placer can avoid it.
_PIN_NAME_OFFSET_MM = 0.508   # KiCad default pin_names offset from the pin endpoint
_PIN_NAME_CH_MM = 1.27        # rendered pin-name text height
_PIN_NAME_CW_MM = 1.05        # per-char advance (matches _LABEL_CW_MM)


@dataclass(slots=True)
class EmitComponent:
    ref: str
    lib_id: str
    value: str = ""
    footprint: str = ""
    x: float = 0.0
    y: float = 0.0
    unit: int = 1  # KiCad multi-unit symbol unit index (1-based); default single-unit


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
    no_connect_count: int = 0
    # DD-11 (A3 control): nets the anti-fusion guard down-graded to label
    # fallback because a deterministic jog could not clear a cross-net collinear
    # collision. Visible (never silent) so route stats mirror reality.
    fusion_label_fallbacks: list[dict] = field(default_factory=list)
    # Nets whose wire geometry the guard deterministically jogged to avoid a
    # cross-net collinear overlap / endpoint-on-wire (kept as drawn wire).
    fusion_jogged_nets: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ErcClassification:
    """Deterministic three-way classification of KiCad ERC violations.

    A senior reviewer does not treat every ERC short/unconnected as a real defect
    (knowledge object: concept.no-connect-classification). This buckets each parsed
    violation into one of five categories; `intentional_nc` is INFO (not blocking),
    all other populated buckets are defects.

    Buckets
    -------
    - ``real_shorts``   : two distinct named nets touch -> CRITICAL, board will fault.
    - ``pad_net_bugs``  : a net-less pad touched by a trace (second net empty / single
                          net) -> generator bug.
    - ``unconnected``   : a pin that should be connected is open (not in ``declared_nc``).
    - ``intentional_nc``: a pin deliberately left open (declared no-connect, e.g.
                          power-only USB-C D+/D-/SBU) -> INFO, demoted from error.
    - ``other``         : any violation line that does not match a known shape. NEVER
                          dropped (no silent fallback); the raw description is kept.

    Each list element preserves the raw violation description line for traceability.
    """

    real_shorts: list[str] = field(default_factory=list)
    pad_net_bugs: list[str] = field(default_factory=list)
    unconnected: list[str] = field(default_factory=list)
    intentional_nc: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)

    @property
    def real_short_count(self) -> int:
        return len(self.real_shorts)

    @property
    def pad_net_bug_count(self) -> int:
        return len(self.pad_net_bugs)

    @property
    def unconnected_count(self) -> int:
        return len(self.unconnected)

    @property
    def intentional_nc_count(self) -> int:
        return len(self.intentional_nc)

    @property
    def other_count(self) -> int:
        return len(self.other)

    @property
    def blocking_count(self) -> int:
        """Defects that must block a fab release. ``intentional_nc`` is excluded;
        ``other`` is excluded (unclassified, surfaced for human review, not auto-gated)."""
        return len(self.real_shorts) + len(self.pad_net_bugs) + len(self.unconnected)


@dataclass(slots=True)
class KiCadValidationResult:
    kicad_cli: str = "unavailable"
    status: str = "skipped-no-kicad-cli"
    erc_violations: int | None = None
    erc_errors: int | None = None
    netlist_components: int = 0
    netlist_nets: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    erc_classification: "ErcClassification | None" = None


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


_RECT_RE = re.compile(
    r"\(rectangle\s*\(start\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)\s*\(end\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)"
)


def _body_rect(block: str) -> tuple[float, float, float, float] | None:
    """Union bbox of every `(rectangle ...)` in a symbol block, SYMBOL-LOCAL.

    Returns (x0, y0, x1, y1) with x0<=x1, y0<=y1 (KiCad y grows upward here — the
    caller flips to sheet coords). This is the TRUE body extent, independent of
    per-symbol pin length; guard C uses it instead of reconstructing the body from
    outer pin tips. None when the symbol draws no rectangle (rare; caller falls
    back to the pin-tip extent)."""
    xs: list[float] = []
    ys: list[float] = []
    for m in _RECT_RE.finditer(block):
        sx, sy, ex, ey = (float(m.group(i)) for i in range(1, 5))
        xs.extend((sx, ex))
        ys.extend((sy, ey))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _pin_name_extents(block: str) -> list[tuple[str, float, float, float]]:
    """Per-pin in-body NAME text geometry, in SYMBOL-LOCAL coords.

    Returns [(name, endpoint_x, endpoint_y, rot), ...]. rot picks the direction the
    pin STICKS OUT (0=+x/right side, 180=-x/left side, 90=up, 270=down); the NAME
    text is drawn on the OPPOSITE side (into the body). No-name pins are skipped.
    Used to reserve the pin-name box so net labels avoid the in-body text smear.
    """
    out: list[tuple[str, float, float, float]] = []
    for pin_match in PIN_RE.finditer(block):
        x = float(pin_match.group(1)); y = float(pin_match.group(2)); rot = float(pin_match.group(3))
        window = block[pin_match.end():pin_match.end() + 400]
        name_match = NAME_RE.search(window)
        if name_match is None:
            continue
        nm = name_match.group(1)
        if nm in ("~", ""):
            continue
        out.append((nm, x, y, rot))
    return out


def _pin_name_box_abs(name: str, ex: float, ey: float, rot: float,
                      comp_x: float, comp_y: float) -> tuple[float, float, float, float]:
    """Absolute rendered box of a pin's in-body NAME text.

    Local pin endpoint (ex,ey) maps to sheet coords (comp_x+ex, comp_y-ey) exactly
    like `_pin_abs`. The pin's SIDE is decided by the sign of its symbol-local x,
    NOT by rot: a left-side pin (ex<0) has the body to its +x, so its in-body name
    runs +x and occupies [px+off, px+off+w]; a right-side pin (ex>=0) has the body
    to its -x and occupies [px-off-w, px-off]. (rot 0 vs 180 is orientation, not
    side, in these generated variant symbols where both sides carry rot 0/180
    inconsistently.) Pins on the vertical axis (ex==0) reserve a centred H span.
    """
    px = comp_x + ex
    py = comp_y - ey
    w = len(name) * _PIN_NAME_CW_MM
    h = _PIN_NAME_CH_MM + _LABEL_VMARGIN_MM
    off = _PIN_NAME_OFFSET_MM
    if ex < -0.01:                         # left-side pin: body is +x, name runs +x
        x0, x1 = px + off, px + off + w
    elif ex > 0.01:                        # right-side pin: body is -x, name runs -x
        x0, x1 = px - off - w, px - off
    else:
        x0, x1 = px - w / 2, px + w / 2
    return (x0, x1, py - h / 2, py + h / 2)


def _prop_text_box(text: str, x: float, y: float) -> tuple[float, float, float, float]:
    """Rendered box of a symbol Reference/Value property text (justify left by
    KiCad default => runs +x from its anchor). Same char/height model as pin
    names so the QA and the emitter agree."""
    w = len(text) * _PIN_NAME_CW_MM
    h = _PIN_NAME_CH_MM + _LABEL_VMARGIN_MM
    return (x, x + w, y - h / 2, y + h / 2)


def _place_symbol_props(component: "EmitComponent",
                        pin_boxes: list[tuple[float, float, float, float]],
                        occupied: list[tuple[float, float, float, float]]
                        ) -> tuple[float, float, float, float, tuple, tuple]:
    """Pick clear anchor positions for a component's Reference and Value text.

    The legacy fixed offset (x+2.54, y-/+1.27) drops both texts INTO the symbol
    body, colliding with in-body pin-name text on multi-pin / connector parts
    (the `2 X SW1`, `GND X 100nF`, `19 X Stamp Edge A/B` smears). We try a ladder
    of candidate offsets (right of body, above, below, further out) and take the
    first pair whose rendered boxes clear every pin-name box AND every already
    placed prop box. Returns (rx, ry, vx, vy, ref_box, val_box)."""
    ref, val = component.ref, component.value or ""
    cx, cy = component.x, component.y
    # candidate anchor ladder: (ref_dx, ref_dy, val_dx, val_dy). Reference above,
    # Value below by default; escalate outward until both clear.
    ladder = [
        (2.54, -1.27, 2.54, 1.27),      # legacy (tried first: byte-stable when clear)
        (2.54, -3.81, 2.54, -6.35),     # both above the body
        (2.54, 3.81, 2.54, 6.35),       # both below the body
        (-2.54, -3.81, -2.54, 3.81),    # left, split
        (5.08, -5.08, 5.08, 5.08),      # far right, split
        (2.54, -7.62, 2.54, 7.62),      # far above / far below
        (-5.08, -7.62, -5.08, 7.62),    # far left, wide split
    ]
    for rdx, rdy, vdx, vdy in ladder:
        rb = _prop_text_box(ref, cx + rdx, cy + rdy)
        vb = _prop_text_box(val, cx + vdx, cy + vdy) if val else None
        clash = any(_bbox_overlap(rb, pb) for pb in pin_boxes) or \
                any(_bbox_overlap(rb, pb) for pb in occupied)
        if vb is not None:
            clash = clash or _bbox_overlap(rb, vb) or \
                    any(_bbox_overlap(vb, pb) for pb in pin_boxes) or \
                    any(_bbox_overlap(vb, pb) for pb in occupied)
        if not clash:
            occupied.append(rb)
            if vb is not None:
                occupied.append(vb)
            return (cx + rdx, cy + rdy, cx + vdx, cy + vdy, rb, vb)
    # exhausted: use the last (far) tier so at least they leave the body
    rdx, rdy, vdx, vdy = ladder[-1]
    rb = _prop_text_box(ref, cx + rdx, cy + rdy)
    vb = _prop_text_box(val, cx + vdx, cy + vdy) if val else None
    occupied.append(rb)
    if vb is not None:
        occupied.append(vb)
    return (cx + rdx, cy + rdy, cx + vdx, cy + vdy, rb, vb)


def emit_kicad_schematic(
    project_dir: str | Path,
    project_name: str,
    components: list[EmitComponent],
    nets: list[EmitNet],
    symbol_dir: str | Path = DEFAULT_SYMBOL_DIR,
    connection_style: str = "label",
    paper: str = "A4",
    nc: list[str] | None = None,
    label_nets: set[str] | frozenset | None = None,
    power_ports: bool = True,
    page_scale: float = 1.0,
) -> SchematicEmitResult:
    """Emit a `.kicad_sch` + `.kicad_pro` from placed components and a net list.

    page_scale (CCM sheet-coherence contract): the per-page symbols were drawn at
    a large in-symbol pin pitch (pin_pitch / 2.54). At page_scale == 1.0 EVERY
    path below is byte-identical to the legacy emitter (existing callers untouched).
    At page_scale > 1.0 the label/stub geometry scales COHERENTLY with the symbol
    so a huge symbol does not carry 1.27 mm text on固定 offsets:
      - label / power-port stub lengths and stagger pitches grow ×page_scale;
      - a global label anchors at the stub OUTER end (not the pin root / body edge);
      - the collision y-nudge is suppressed — scaled pitch already separates
        neighbours, so stubs run straight out (no top-⅓-up / bottom-⅓-down fan).

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

    nc: optional list of "REF.PIN" strings to mark with a KiCad `(no_connect ...)`
    glyph (T1). Every entry MUST resolve to a placed pin endpoint; any
    unresolvable entry raises ValueError listing ALL bad items (fail-fast, no
    silent skip).

    label_nets: optional set of net names forced onto global-label connectivity
    even when connection_style is "wire"/"auto" (T3 — per-net override so the
    composer's route stats and the actual emission cannot drift apart).
    """
    drawn = connection_style in ("wire", "auto")
    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    root_uuid = _uid()

    embedded_defs: dict[str, str] = {}
    pin_maps: dict[str, dict[str, tuple[float, float]]] = {}
    # lib_id -> (x0, y0, x1, y1) SYMBOL-LOCAL body rectangle (guard C true body box).
    body_rects: dict[str, tuple[float, float, float, float] | None] = {}
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
        body_rects[component.lib_id] = _body_rect(definition)

    # Snap every component onto KiCad's 1.27 mm connection grid. Library pin local
    # offsets are grid-multiples, so once the symbol origin is on-grid the absolute
    # pin endpoint is too — which is what lets a drawn wire end actually merge with
    # the pin (off-grid endpoints read as `pin_not_connected` in ERC). Harmless to
    # label mode (global labels don't require grid alignment).
    for component in components:
        component.x = _snap_grid(component.x)
        component.y = _snap_grid(component.y)

    placements = {component.ref: component for component in components}
    # symbol_blocks are generated AFTER pin_name_boxes so each part's Reference/
    # Value text can be positioned clear of in-body pin-name text (see below).
    symbol_blocks: list[str] = []

    def _pin_abs(ref: str, pin: str) -> tuple[float, float] | None:
        component = placements.get(ref)
        if component is None or component.lib_id not in pin_maps:
            return None
        endpoint = pin_maps[component.lib_id].get(pin)
        if endpoint is None:
            return None
        return (round(component.x + endpoint[0], 4), round(component.y - endpoint[1], 4))

    def _pin_edge(ref: str, pin: str) -> tuple[float, float]:
        """Outward stub direction (in SHEET coords) for the edge a pin sticks out of.

        From the pin's symbol-LOCAL endpoint (ex, ey), the dominant axis + its sign
        pick the edge; the returned unit vector points AWAY from the body so a stub /
        power port / label expands to the outside (BR: four-edge pin placement):
          - left   (ex<0, |ex|>=|ey|) -> (-1,  0)   stub runs -x
          - right  (ex>0, |ex|>=|ey|) -> (+1,  0)   stub runs +x
          - top    (ey>0, |ey|> |ex|) -> ( 0, -1)   sheet y = cy-ey, so up = -y
          - bottom (ey<0, |ey|> |ex|) -> ( 0, +1)   down = +y
        A pin exactly on the origin (ex==ey==0) defaults to right (+x). NOTE: KiCad
        schematic y grows DOWNWARD, so a symbol-local +y (top pin) maps to a SMALLER
        sheet y; expanding the stub further up therefore uses sheet -y."""
        component = placements.get(ref)
        if component is None or component.lib_id not in pin_maps:
            return (1.0, 0.0)
        endpoint = pin_maps[component.lib_id].get(pin)
        if endpoint is None:
            return (1.0, 0.0)
        ex, ey = endpoint[0], endpoint[1]
        if abs(ex) >= abs(ey):
            return (-1.0, 0.0) if ex < -0.01 else (1.0, 0.0)
        return (0.0, -1.0) if ey > 0.01 else (0.0, 1.0)

    # T1: resolve declared no-connect pins BEFORE net emission; fail-fast on any
    # unresolvable entry (ref missing, symbol not embedded, or pin absent).
    nc_blocks: list[str] = []
    bad_nc: list[str] = []
    for item in (nc or []):
        text = str(item).strip()
        ref, _, pin = text.partition(".")
        abs_pt = _pin_abs(ref.strip(), pin.strip()) if ref.strip() and pin.strip() else None
        if abs_pt is None:
            bad_nc.append(text)
            continue
        nc_blocks.append(_no_connect_block(abs_pt[0], abs_pt[1]))
    if bad_nc:
        raise ValueError(
            "no_connect entries could not be resolved to a placed pin "
            f"(expected 'REF.PIN' of an emitted component): {', '.join(bad_nc)}"
        )

    label_blocks: list[str] = []
    wire_blocks: list[str] = []
    junction_blocks: list[str] = []
    unresolved: list[str] = []
    # (net_name, x, y) endpoints routed to global-label fallback; emitted after
    # the net loop with a per-column anti-overlap pass so dense same-side pin
    # stacks (e.g. a large BGA drawn as a per-page subset) do not collide.
    label_endpoints: list[tuple[str, float, float, tuple[float, float]]] = []
    # (net_name, kind, x, y) endpoints routed to a power-port symbol instead of a
    # label (GND/supply nets on a dense side). Emitted after the net loop.
    # (net, kind, x, y, edge, host_ref): host_ref is the component the pin belongs
    # to, so guard C can skip "port inside its OWN body" (a legitimate interior /
    # displaced power pin) and only flag a port intruding a DIFFERENT component.
    power_endpoints: list[tuple] = []
    # Occupied local-label anchor coords (drawn-wire mode). Two independent
    # L-route/trunk labels can resolve to the SAME midpoint (e.g. HSPI_IO1 and
    # HSPI_IO15, both U1<->U2 2-node nets, landing on one coord => overlapping
    # local-label text). Track placed anchors and nudge a colliding label along
    # the wire by one grid until its coord is free, so no two local labels stack.
    # In-body pin-NAME text boxes for every placed component. A net label anchored
    # at a pin endpoint runs +x (justify left) straight into these; seeding them as
    # pre-occupied lets BOTH label placers (drawn-wire local labels and the global
    # -label stagger) nudge clear of the pin-name smear — the black-blob root cause
    # the label-vs-label test never saw.
    pin_name_defs: dict[str, list[tuple[str, float, float, float]]] = {
        lib_id: _pin_name_extents(definition) for lib_id, definition in embedded_defs.items()
    }
    pin_name_boxes: list[tuple[float, float, float, float]] = []
    for component in components:
        extents = pin_name_defs.get(component.lib_id)
        if not extents:
            continue
        for nm, ex, ey, rot in extents:
            pin_name_boxes.append(
                _pin_name_box_abs(nm, ex, ey, rot, component.x, component.y)
            )

    # Now place each symbol, choosing Reference/Value anchors that clear both the
    # pin-name boxes and every prior prop box (the `2 X SW1` / `GND X 100nF` /
    # `19 X Stamp Edge A/B` self-overlaps). The resulting prop boxes join the
    # pin-name occupancy so net labels also steer clear of the refdes/value text.
    prop_boxes: list[tuple[float, float, float, float]] = []
    for component in components:
        if component.lib_id not in embedded_defs:
            continue
        rx, ry, vx, vy, rb, vb = _place_symbol_props(component, pin_name_boxes, prop_boxes)
        symbol_blocks.append(
            _symbol_instance_block(component, project_name, root_uuid, rx, ry, vx, vy)
        )
    # Reserved occupancy for the label/power placers: pin names + prop texts.
    reserved_boxes: list[tuple[float, float, float, float]] = pin_name_boxes + prop_boxes

    _local_label_boxes: list[tuple[float, float, float, float]] = list(reserved_boxes)

    def _place_local_label(name: str, x: float, y: float, wp: list[tuple[float, float]]):
        """Emit a local label at (x,y), nudged along the route so its RENDERED text
        box clears every earlier local label. The old version only guarded the
        anchor coord, so two short labels one grid apart (e.g. HSPI_IO4/HSPI_IO8 on
        the memory page) still overlapped horizontally. We now test the full bbox
        against all placed boxes and pick the first candidate coord that is clear."""
        candidates: list[tuple[float, float]] = [(x, y)] + list(wp)
        # also add intra-segment grid points for a finer nudge
        for a, b in zip(wp, wp[1:]):
            if abs(a[0] - b[0]) > abs(a[1] - b[1]):  # horizontal seg
                step = 1.27 if b[0] >= a[0] else -1.27
                cx = a[0]
                while (step > 0 and cx <= b[0]) or (step < 0 and cx >= b[0]):
                    candidates.append((round(cx, 2), a[1])); cx += step
            else:  # vertical seg
                step = 1.27 if b[1] >= a[1] else -1.27
                cy = a[1]
                while (step > 0 and cy <= b[1]) or (step < 0 and cy >= b[1]):
                    candidates.append((a[0], round(cy, 2))); cy += step
        for cx, cy in candidates:
            box = _label_bbox(name, cx, cy, False)
            if not any(_bbox_overlap(box, pb) for pb in _local_label_boxes):
                _local_label_boxes.append(box)
                label_blocks.append(_local_label_block(name, cx, cy))
                return
        # exhausted (degenerate): place at original and record (last resort)
        _local_label_boxes.append(_label_bbox(name, x, y, False))
        label_blocks.append(_local_label_block(name, x, y))

    # DD-11 anti-fusion registry: net_name -> its list of registered wire segments
    # ((x1,y1),(x2,y2)). A new net's segments are checked against EVERY OTHER
    # net's registered segments; on a cross-net collinear overlap / endpoint-on-
    # wire the whole net's geometry is deterministically jogged (net-hash offset),
    # retried ≤ 3 times, else the net is down-graded to label fallback (visible).
    fusion_registry: dict[str, list[tuple]] = {}
    fusion_label_fallbacks: list[dict] = []
    fusion_jogged_nets: list[str] = []

    def _other_net_segments(this_net: str) -> list[tuple]:
        segs: list[tuple] = []
        for nm, ss in fusion_registry.items():
            if nm != this_net:
                segs.extend(ss)
        return segs

    def _segments_of(waypoints: list[tuple[float, float]]) -> list[tuple]:
        return [(waypoints[i], waypoints[i + 1]) for i in range(len(waypoints) - 1)]

    def _guard_route(net_name: str, base_waypoints: list[tuple[float, float]]):
        """Return (waypoints, jogged: bool) whose segments clear every other net,
        or (None, False) when ≤ 3 deterministic jogs still fuse (→ caller down-
        grades to label). Guard only mutates geometry when a collision exists, so
        collision-free input is byte-equivalent (R6)."""
        others = _other_net_segments(net_name)
        segs = _segments_of(base_waypoints)
        if not any(_segment_fuses(s, others) for s in segs):
            return base_waypoints, False        # clean → untouched (byte-stable)
        for attempt in range(3):
            offset = _net_jog_steps(net_name, attempt)
            jogged = _jog_free_axis(base_waypoints, offset)
            jsegs = _segments_of(jogged)
            if not any(_segment_fuses(s, others) for s in jsegs):
                return jogged, True
        return None, False

    for net in nets:
        force_label = label_nets is not None and net.name in label_nets
        endpoints: list[tuple[float, float]] = []
        # side[i] = outward stub unit vector (dx, dy) in SHEET coords for endpoints[i]
        # (BR: four-edge pin placement). Power-port stubs expand along this vector
        # AWAY from the symbol body: left (-1,0)/right (+1,0)/top (0,-1)/bottom (0,+1).
        endpoint_sides: list[tuple[float, float]] = []
        endpoint_refs: list[str] = []  # host component of endpoints[i] (guard C skip-self)
        net_unresolved = False
        for ref, pin in net.nodes:
            abs_pt = _pin_abs(ref, pin)
            if abs_pt is None:
                unresolved.append(f"{ref}.{pin}")
                net_unresolved = True
                continue
            endpoints.append(abs_pt)
            endpoint_sides.append(_pin_edge(ref, pin))
            endpoint_refs.append(ref)

        # Drawn-wire mode: 2 pins → L-route; 3+ pins → trunk + stubs + junctions.
        if drawn and not force_label and not net_unresolved and len(endpoints) == 2:
            waypoints = _orthogonal_route(endpoints[0], endpoints[1])
            guarded, jogged = _guard_route(net.name, waypoints)
            if guarded is None:
                # DD-11 fallback: jog exhausted → down-grade this net to label
                # (collinearity-free by construction). Recorded, never silent.
                fusion_label_fallbacks.append({"net": net.name, "reason": "anti-fusion"})
                kind = _power_net_kind(net.name) if power_ports else None
                for abs_pt, edge, ep_ref in zip(endpoints, endpoint_sides, endpoint_refs):
                    if kind is not None:
                        power_endpoints.append((net.name, kind, abs_pt[0], abs_pt[1], edge, ep_ref))
                    else:
                        label_endpoints.append((net.name, abs_pt[0], abs_pt[1], edge))
                continue
            waypoints = guarded
            if jogged:
                fusion_jogged_nets.append(net.name)
            fusion_registry[net.name] = _segments_of(waypoints)
            for a, b in zip(waypoints, waypoints[1:]):
                wire_blocks.append(_wire_segment_block(a[0], a[1], b[0], b[1]))
            mid = waypoints[len(waypoints) // 2]
            _place_local_label(net.name, mid[0], mid[1], waypoints)
        elif drawn and not force_label and not net_unresolved and len(endpoints) >= 3:
            segments, junctions = _bus_route(endpoints)
            # Register the multi-node net's segments and check cross-net fusion.
            others = _other_net_segments(net.name)
            fuses = any(_segment_fuses(s, others) for s in segments)
            if fuses:
                # Multi-node bus geometry has no single free axis to jog
                # deterministically → down-grade to label fallback (visible).
                fusion_label_fallbacks.append({"net": net.name, "reason": "anti-fusion"})
                kind = _power_net_kind(net.name) if power_ports else None
                for abs_pt, edge, ep_ref in zip(endpoints, endpoint_sides, endpoint_refs):
                    if kind is not None:
                        power_endpoints.append((net.name, kind, abs_pt[0], abs_pt[1], edge, ep_ref))
                    else:
                        label_endpoints.append((net.name, abs_pt[0], abs_pt[1], edge))
                continue
            fusion_registry[net.name] = list(segments)
            for (a, b) in segments:
                wire_blocks.append(_wire_segment_block(a[0], a[1], b[0], b[1]))
            for (jx, jy) in junctions:
                junction_blocks.append(_junction_block(jx, jy))
            # one local label on the trunk's left end to name the net
            trunk = segments[0]
            _place_local_label(net.name, trunk[0][0], trunk[0][1], [trunk[0], trunk[1]])
        else:
            # label fallback: power, single-pin, unresolved, or style=label
            # power_ports=False (dense castellated-edge / connector pages, e.g. the
            # stamp ICD sheet): power nets take the ordinary global-label path too,
            # NOT a power-port glyph. On a Conn_01x36 edge connector many GND/supply
            # pins share one x column; power-port stubs would run collinear and KiCad
            # would fuse them into one net (the stamp-page short). Per-pin net labels
            # are the industry convention for edge connectors and are collinearity-
            # free by construction. Net membership is identical either way.
            kind = _power_net_kind(net.name) if power_ports else None
            for abs_pt, edge, ep_ref in zip(endpoints, endpoint_sides, endpoint_refs):
                if kind is not None:
                    power_endpoints.append((net.name, kind, abs_pt[0], abs_pt[1], edge, ep_ref))
                else:
                    label_endpoints.append((net.name, abs_pt[0], abs_pt[1], edge))

    label_blocks.extend(_staggered_label_blocks(label_endpoints, reserved=reserved_boxes,
                                                page_scale=page_scale,
                                                avail_y=_paper_avail_y(paper),
                                                avail_x=_paper_avail_x(paper)))

    # Power ports: one KiCad power-port symbol per GND/supply endpoint, replacing
    # the label stack. A stub wire joins the pin endpoint to the port so the port
    # sits clear of the symbol body (gnd points down, supply up). Net membership
    # is unchanged — a power port names its net exactly as a label would.
    # Each distinct power net also gets ONE PWR_FLAG on its first port so ERC does
    # not report `power_pin_not_driven` (the power ports themselves are power_in,
    # matching KiCad's stock GND/VCC symbols; the flag is the single driver).
    # Anti-overlap: dozens of power ports on one symbol side share an x column at
    # ~2 mm pitch; their Value text (the net name) would stack into a blob just
    # like raw labels did. Group by x column, sort by y, and when consecutive
    # ports are crowded push every other one outward on a longer stub — the same
    # staggering the label path uses, so the net-name text separates vertically.
    flagged_nets: set[str] = set()
    # Group by (edge line, outward vector). Facing comes from the pin's own edge
    # (BR: four-edge pin placement) — the outward unit vector (nx, ny) expands the
    # port AWAY from the body: left (-1,0)/right (+1,0)/top (0,-1)/bottom (0,+1).
    # Ports that share the same EDGE LINE are anti-overlap staggered: left/right
    # pins share an x column (line key = x, stagger jogs in x); top/bottom pins
    # share a y row (line key = y, stagger jogs in y). The stagger tier pushes each
    # crowded port further out along its outward vector so the net-name text splits.
    def _edge_of(ep) -> tuple[float, float]:
        v = ep[4] if len(ep) > 4 else (1.0, 0.0)
        return v if isinstance(v, tuple) else (float(v), 0.0)  # back-compat scalar

    # page_scale coherence: a scaled per-page symbol carries larger pins/text, so
    # the port stub length, stagger step, min-pitch and the modelled net-name text
    # box all grow ×page_scale. At page_scale == 1.0 these equal the legacy module
    # constants (byte-identical).
    _pwr_scale = page_scale if page_scale > 1.0 else 1.0
    _pwr_stub_step = _PWR_STUB_STEP_MM * _pwr_scale
    _pwr_stub = _STUB_MM * _pwr_scale
    _pwr_min_pitch = _PWR_MIN_PITCH_MM * _pwr_scale
    _pwr_name_ch = _PIN_NAME_CH_MM * _pwr_scale
    _pwr_name_cw = _PIN_NAME_CW_MM * _pwr_scale
    _pwr_columns: dict[tuple[float, float, float], list] = {}
    for ep in power_endpoints:
        nx, ny = _edge_of(ep)
        horizontal = abs(nx) >= abs(ny)  # left/right edge vs top/bottom edge
        line = round(ep[2], 2) if horizontal else round(ep[3], 2)  # shared x (col) or y (row)
        _pwr_columns.setdefault((line, nx, ny), []).append(ep)
    for (line, nx, ny) in sorted(_pwr_columns):
        horizontal = abs(nx) >= abs(ny)
        # sort along the edge so crowding is detected between physical neighbours:
        # a shared x column sorts by y; a shared y row sorts by x.
        col_items = sorted(_pwr_columns[(line, nx, ny)], key=lambda t: (t[3] if horizontal else t[2]))
        # Track the last edge-parallel coord placed at EACH tier so we only advance
        # tiers until the current port clears the nearest already-placed one.
        tier_last: dict[int, float] = {}
        n_tiers = 8
        for net_name, kind, px, py, *_rest in col_items:
            parallel = py if horizontal else px  # coord ALONG the edge
            tier = 0
            for t in range(n_tiers):
                last = tier_last.get(t)
                # candidate port anchor pushed t tiers outward along (nx, ny).
                cand_x = round(px + nx * t * _pwr_stub_step, 4)
                cand_y = round(py + ny * t * _pwr_stub_step, 4)
                cand_port_x = round(cand_x + nx * _pwr_stub, 4)
                cand_port_y = round(cand_y + ny * _pwr_stub, 4)
                # the port's net-name Value text renders centred at (cand_x, cand_y);
                # model its box and reject any tier whose text lands on an IC pin-name.
                vw = len(net_name) * _pwr_name_cw
                vbox = (cand_x - vw / 2, cand_x + vw / 2,
                        cand_y - (_pwr_name_ch + _LABEL_VMARGIN_MM) / 2,
                        cand_y + (_pwr_name_ch + _LABEL_VMARGIN_MM) / 2)
                free = last is None or abs(parallel - last) >= _pwr_min_pitch
                pin_free = not any(_bbox_overlap(vbox, pb) for pb in reserved_boxes)
                # ANTI-FUSION (缺陷一): the stub wires this tier would emit — the
                # jog leg (pin→anchor) plus the anchor→port stub — must not
                # collinearly overlap or endpoint-touch a DIFFERENT power net's
                # already-registered segments. Adjacent same-column supply/GND
                # pins whose stubs run collinear are exactly the U1 left-edge
                # short (F1/G1/G2/H1/H2 fused into one vertical line).
                cand_segs = [((cand_x, cand_y), (cand_port_x, cand_port_y))]
                if t:
                    cand_segs.append(((px, py), (cand_x, cand_y)))
                others = _other_net_segments(net_name)
                fuse_free = not any(_segment_fuses(s, others) for s in cand_segs)
                if free and pin_free and fuse_free:
                    tier = t
                    break
            else:
                tier = n_tiers - 1
            tier_last[tier] = parallel
            # anchor: pin endpoint jogged `tier` steps outward along (nx, ny).
            anchor_x = round(px + nx * tier * _PWR_STUB_STEP_MM, 4)
            anchor_y = round(py + ny * tier * _PWR_STUB_STEP_MM, 4)
            lib_id = _power_symbol_lib_id(net_name, kind)
            if lib_id not in embedded_defs:
                embedded_defs[lib_id] = _power_symbol_def(lib_id, net_name, kind)
            # port sits one stub-length further out from the (possibly jogged) anchor,
            # ALONG the outward vector, so it clears the body regardless of edge.
            port_x = round(anchor_x + nx * _STUB_MM, 4)
            port_y = round(anchor_y + ny * _STUB_MM, 4)
            final_stub_segs = [((anchor_x, anchor_y), (port_x, port_y))]
            if tier:
                # jog out to the staggered lane (from the pin to the anchor), then
                # the stub from the anchor to the port along the outward vector.
                wire_blocks.append(_wire_segment_block(px, py, anchor_x, anchor_y))
                final_stub_segs.append(((px, py), (anchor_x, anchor_y)))
            wire_blocks.append(_wire_segment_block(anchor_x, anchor_y, port_x, port_y))
            # ANTI-FUSION registry (缺陷一): record this port's stub segments so the
            # NEXT same-column power net sees them and its tier search jogs clear —
            # without this the guard was blind across power nets (the U1 F1/G1/G2/
            # H1/H2 stubs all landed on one collinear column = short).
            fusion_registry.setdefault(net_name, []).extend(final_stub_segs)
            pwr_rot = _power_symbol_rotation(kind, (nx, ny))
            symbol_blocks.append(_power_symbol_instance(lib_id, net_name, port_x, port_y, project_name, root_uuid, rotation=pwr_rot))
            if net_name not in flagged_nets:
                flagged_nets.add(net_name)
                if "PWR_FLAG" not in embedded_defs:
                    embedded_defs["PWR_FLAG"] = _pwr_flag_def()
                # The flag pin must land on a WIRE ENDPOINT to be seen as connected;
                # extend the stub one grid further out and drop the flag there so
                # port pin + flag pin + stub end all coincide on the same net node.
                flag_x = round(port_x + nx * _STUB_MM, 4)
                flag_y = round(port_y + ny * _STUB_MM, 4)
                wire_blocks.append(_wire_segment_block(port_x, port_y, flag_x, flag_y))
                symbol_blocks.append(_pwr_flag_instance(flag_x, flag_y, project_name, root_uuid))

    # Post-emit bbox assert (BR: left-pin stub orientation blind, guard C). Every
    # power-port glyph must sit OUTSIDE every component's symbol-body bbox — a port
    # landing inside a body is the exact "stub drawn into the symbol" defect. The
    # body bbox is the pin-endpoint extent (symbol-local) shifted to the placement,
    # shrunk by a margin so a port legitimately abutting the body edge is allowed.
    _body_boxes: list[tuple[str, tuple[float, float, float, float]]] = []
    for component in components:
        pmap = pin_maps.get(component.lib_id)
        if not pmap:
            continue
        # The body extent is the symbol's own `(rectangle ...)` — the SINGLE source
        # of truth for where the body actually ends. Do NOT reconstruct it from pin
        # `at` tips: a pin's `at` is its OUTER endpoint, sitting one pin-graphic
        # length OUTSIDE the body edge, and that length is per-symbol (engine
        # variants use 5.08 mm, hand-drawn authentic libs use 2.54 mm), so any
        # fixed tip-inset misjudges one of them. rect gives the true body box; the
        # power-port endpoint (the pin `at`) legitimately hugs that edge, so a port
        # exactly on/just outside the rect is NOT an intrusion.
        rect = body_rects.get(component.lib_id)
        if rect is not None:
            rx0, ry0, rx1, ry1 = rect
            xs = [component.x + rx0, component.x + rx1]
            ys = [component.y - ry0, component.y - ry1]
        else:
            # no rectangle in the symbol (rare): fall back to pin-tip extent.
            xs = [component.x + ex for (ex, _ey) in pmap.values()]
            ys = [component.y - ey for (_ex, ey) in pmap.values()]
        if not xs:
            continue
        inset = _PWR_STUB_STEP_MM / 4.0  # tolerate a port hugging the body edge
        _body_boxes.append((component.ref,
            (min(xs) + inset, max(xs) - inset, min(ys) + inset, max(ys) - inset)))
    _port_intrusions: list[str] = []
    for ep in power_endpoints:
        ex_pt, ey_pt = ep[2], ep[3]
        host_ref = ep[5] if len(ep) > 5 else None
        for ref, (bx0, bx1, by0, by1) in _body_boxes:
            # A power pin legitimately sits inside its OWN symbol body (interior
            # BGA balls; a body shifted by macro-compact/page-fill after the pin's
            # abs endpoint was frozen). Guard C targets the real defect: a port
            # drawn into a DIFFERENT component. Skip the endpoint's own host.
            if ref == host_ref:
                continue
            if bx0 < ex_pt < bx1 and by0 < ey_pt < by1:
                _port_intrusions.append(f"{ep[0]}@({ex_pt},{ey_pt}) inside {ref}")
                break
    if _port_intrusions:
        raise ValueError(
            "POWER_PORT_INSIDE_SYMBOL_BODY: power-port endpoints fell inside a "
            "component symbol body (stub orientation defect — BR left-pin stub "
            f"blind): {'; '.join(_port_intrusions[:12])}"
            + (f" (+{len(_port_intrusions) - 12} more)" if len(_port_intrusions) > 12 else "")
        )

    schematic = _schematic_document(
        root_uuid, embedded_defs.values(), symbol_blocks, label_blocks, wire_blocks, junction_blocks,
        nc_blocks=nc_blocks, paper=paper,
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
        no_connect_count=len(nc_blocks),
        fusion_label_fallbacks=fusion_label_fallbacks,
        fusion_jogged_nets=fusion_jogged_nets,
    )


def _symbol_instance_block(component: EmitComponent, project_name: str, root_uuid: str,
                          rx: float | None = None, ry: float | None = None,
                          vx: float | None = None, vy: float | None = None) -> str:
    """Emit one placed-symbol s-expr. rx/ry/vx/vy override the Reference/Value text
    anchors (chosen by `_place_symbol_props` to clear pin-name text); when omitted
    they fall back to the legacy fixed offset so callers that don't need collision
    avoidance stay byte-stable."""
    ref_uuid = _uid()
    pin_uuids = "\n".join(f'    (pin "{number}" (uuid "{_uid()}"))' for number in ("1", "2"))
    rx = component.x + 2.54 if rx is None else rx
    ry = component.y - 1.27 if ry is None else ry
    vx = component.x + 2.54 if vx is None else vx
    vy = component.y + 1.27 if vy is None else vy
    return f'''  (symbol
    (lib_id "{component.lib_id}")
    (at {component.x} {component.y} 0)
    (unit 1)
    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid "{ref_uuid}")
    (property "Reference" "{component.ref}" (at {round(rx, 4)} {round(ry, 4)} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{component.value}" (at {round(vx, 4)} {round(vy, 4)} 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "{component.footprint}" (at {component.x} {component.y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
{pin_uuids}
    (instances (project "{project_name}" (path "/{root_uuid}" (reference "{component.ref}") (unit 1))))
  )'''


def _edge_label_angle(edge: tuple[float, float]) -> int:
    """KiCad global-label (at x y ANGLE): the text runs AWAY from the anchor along
    ANGLE (0=+x/right, 90=up, 180=-x/left, 270=down). Point it along the pin's
    OUTWARD edge vector so a left-edge pin's label extends left (off the body),
    never justify-left into the body — the EN_1V8-inside-U6 defect."""
    nx, ny = edge
    if abs(nx) >= abs(ny):
        return 0 if nx >= 0 else 180
    return 270 if ny >= 0 else 90  # sheet +y = screen down


def _global_label_block(name: str, x: float, y: float, edge: tuple[float, float] = (1.0, 0.0), text_scale: float = 1.0) -> str:
    angle = _edge_label_angle(edge)
    # KiCad renders a global label with justify LEFT so its text starts at the
    # anchor and runs along ANGLE; the angle alone steers the text off the body.
    fs = round(1.27 * text_scale, 4)
    return (
        f'  (global_label "{name}" (shape bidirectional) (at {round(x, 4)} {round(y, 4)} {angle})\n'
        f'    (effects (font (size {fs} {fs})) (justify left)) (uuid "{_uid()}"))'
    )


# Minimum vertical gap (mm) two 1.27 mm-tall labels need so their text boxes do
# not touch. Below this, same-column labels are staggered outward on a stub.
_LABEL_MIN_PITCH_MM = 2.0
_LABEL_STUB_STEP_MM = 5.08  # x offset added per stagger tier (2 grid units)
_LABEL_CH_MM = 1.27         # rendered text height
_LABEL_CW_MM = 1.05         # per-char advance (conservative)
_LABEL_GLYPH_MM = 2.0       # global-label shape glyph width
_LABEL_VMARGIN_MM = 0.3
_LABEL_HMARGIN_MM = 0.4
# Vertical-label multi-column spillover (design-time capacity budget). A dense
# castellated edge draws dozens of vertical (ang90/270) labels sharing ONE x
# column; each label's text box extends ALONG the column axis (y) by up to
# len(name)*CW*scale. When the label count exceeds what the usable y-span holds,
# the greedy per-pin stagger pushes labels off-sheet (y=1008 mm). Instead we
# compute the column CAPACITY up front and, when count > capacity, split the
# column into ceil(count/capacity) sub-columns fanned outward along x. The
# per-column usable y-span is unknown to the emitter (paper is chosen in the
# composer AFTER this runs), so we budget it from the column's own pin y-extent
# scaled by _LABEL_SPAN_BUDGET (allow modest outward growth, capped).
_LABEL_SPAN_BUDGET = 1.6   # usable y-span = pin-row y-extent * this (>=1 grow cap)
_LABEL_COL_GAP_MM = 2.54   # extra gap between adjacent vertical labels in a column

# Frame-first slot budget (BR: sparse-page offpage / cap=1 degeneracy). The
# composer picks the paper BEFORE emit runs (composer._fit_sheet -> emit paper=),
# so the emitter CAN know the real usable-y corridor and MUST bind the vertical
# slot ladder to it instead of estimating from the pin-row extent (which degrades
# to cap=1 on a dense column and pushes labels to y=1008 mm off-sheet). These
# mirror composer.STANDARD_PAPERS / SHEET_MARGIN_MM (kept emit-local to avoid an
# import cycle; a mismatch would surface as a fail-loud utilization/overflow gate).
_EMIT_PAPER_DIMS_MM: dict[str, tuple[float, float]] = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}
_EMIT_SHEET_MARGIN_MM = 12.7


def _paper_avail_y(paper: str) -> tuple[float, float] | None:
    """Usable y corridor (lo, hi) of the CHOSEN paper, in mm.

    paper   : one of _EMIT_PAPER_DIMS_MM keys (the composer-selected sheet).
    returns : (y_lo, y_hi) = (margin, height - margin) — the vertical band a
              label anchor may occupy; None for an unknown paper (caller then
              falls back to the legacy pin-extent budget, byte-stable).
    NOT: an x corridor; NOT the full sheet height (margins are subtracted).
    Done when: hi > lo, or None for unknown paper.
    """
    dims = _EMIT_PAPER_DIMS_MM.get(paper)
    if dims is None:
        return None
    _pw, ph = dims
    lo = _EMIT_SHEET_MARGIN_MM
    hi = ph - _EMIT_SHEET_MARGIN_MM
    if hi <= lo:
        return None
    return (lo, hi)


def _paper_avail_x(paper: str) -> tuple[float, float] | None:
    """Usable x corridor (lo, hi) of the CHOSEN paper, in mm.

    paper   : one of _EMIT_PAPER_DIMS_MM keys (the composer-selected sheet).
    returns : (x_lo, x_hi) = (margin, width - margin) — the horizontal band a
              label's rendered text box must stay inside; None for an unknown
              paper (caller then skips the x-corridor check, byte-stable).
    NOT: a y corridor; NOT the full sheet width (margins are subtracted).
    Done when: hi > lo, or None for unknown paper.
    """
    dims = _EMIT_PAPER_DIMS_MM.get(paper)
    if dims is None:
        return None
    pw, _ph = dims
    lo = _EMIT_SHEET_MARGIN_MM
    hi = pw - _EMIT_SHEET_MARGIN_MM
    if hi <= lo:
        return None
    return (lo, hi)


def _vlabel_extent_mm(names: list[str], page_scale: float) -> float:
    """Largest vertical-label y-occupancy (mm) over a set of net names.

    name  : the net names sharing one column.
    returns: max over names of the _label_bbox `w` term (text run + glyph +
             hmargin) at this page_scale — i.e. how far a vertical label's box
             extends along the column (y) axis.
    NOT: the horizontal glyph-column width `h`; NOT a per-label value (it is the
    MAX, the tier step the column must reserve per slot).
    Done when: returns a positive float; empty list => 0.0.
    """
    if not names:
        return 0.0
    return max(
        len(nm) * (_LABEL_CW_MM * page_scale) + (_LABEL_GLYPH_MM * page_scale) + _LABEL_HMARGIN_MM
        for nm in names
    )


def _column_capacity(usable_span_mm: float, extent_mm: float, gap_mm: float) -> int:
    """How many vertical labels fit in one column before it must spill columns.

    usable_span_mm : available y length for this column's label boxes.
    extent_mm      : per-label y occupancy (from _vlabel_extent_mm).
    gap_mm         : minimum inter-label gap.
    returns        : max(1, floor(usable_span / (extent + gap))) — always >=1 so
                     a single over-long label never yields 0 columns.
    NOT: a float ratio; NOT a utilisation percentage. It is an integer slot count.
    Done when: returns an int >= 1.
    """
    denom = extent_mm + gap_mm
    if denom <= 0:
        return 1
    import math
    return max(1, int(math.floor(usable_span_mm / denom)))


def _label_bbox(name: str, x: float, y: float, is_global: bool,
                edge: tuple[float, float] = (1.0, 0.0),
                text_scale: float = 1.0) -> tuple[float, float, float, float]:
    """Rendered text box. The text runs from the anchor along the OUTWARD edge
    vector (angle-steered), so the box extends toward (nx, ny) rather than always
    +x. Returns (x0, x1, y0, y1). Mirrors qa_bbox.py so QA and emitter agree.

    text_scale (CCM sheet-coherence): 1.0 == legacy byte-identical box. At >1.0
    the rendered label text height/width AND the global-label glyph scale ×
    text_scale so the overlap check models the ACTUAL scaled ink (the box the
    collision resolver and frame-fit must both see)."""
    w = len(name) * (_LABEL_CW_MM * text_scale) + (_LABEL_GLYPH_MM * text_scale if is_global else 0.0) + _LABEL_HMARGIN_MM
    h = _LABEL_CH_MM * text_scale + _LABEL_VMARGIN_MM
    nx, ny = edge
    if abs(nx) >= abs(ny):
        # horizontal text run
        if nx >= 0:
            return (x, x + w, y - h / 2, y + h / 2)
        return (x - w, x, y - h / 2, y + h / 2)
    # vertical text run (top/bottom edge): the glyph column is `h` wide, `w` tall
    if ny >= 0:  # screen down
        return (x - h / 2, x + h / 2, y, y + w)
    return (x - h / 2, x + h / 2, y - w, y)


def _bbox_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2])


def _resolve_label_y(name: str, x: float, y: float, is_global: bool, placed: list[tuple[float, float, float, float]], direction: float,
                     edge: tuple[float, float] = (1.0, 0.0)) -> float:
    """Nudge a label's y upward in _LABEL_MIN_PITCH steps until its rendered box
    clears every already-placed box, then register it. Returns the final y.
    Global overlap check (not per-column) so cross-column horizontal collisions
    (short labels crowded around a dense IC) are resolved too. The bbox extends
    along the label's OUTWARD edge vector (缺陷三b: collision must model the real
    text direction, or a left-facing label's box is checked on the wrong side)."""
    ly = y
    for _ in range(400):
        bx = _label_bbox(name, x + (direction * _LABEL_STUB_STEP_MM if abs(ly - y) > 1e-6 else 0.0), ly, is_global, edge)
        if not any(_bbox_overlap(bx, pb) for pb in placed):
            placed.append(bx)
            return ly
        ly = round(ly + _LABEL_MIN_PITCH_MM, 4)
    placed.append(_label_bbox(name, x, ly, is_global, edge))
    return ly

# --- Power symbol emission (industry convention: GND glyph points down, supply
# rail glyph points up). A dense symbol side (e.g. a per-page BGA subset) carries
# dozens of single-pin GND/+1V8/+3V3/VDDA net endpoints; drawing a global label
# on each stacks their text into an unreadable blob. Instead we drop a KiCad
# power-port symbol on each such endpoint — the eeschema-native way — so the page
# reads as a conventional schematic. This is a DRAWING-layer change only: a power
# port names its net exactly like a label (same electrical meaning), so netlist
# net membership is byte-for-byte unchanged.
_GND_NET_RE = re.compile(r"^(gnd|gndd?|agnd|dgnd|pgnd|vss[a-z0-9_]*|vssa)$", re.IGNORECASE)
_SUPPLY_NET_RE = re.compile(
    r"^(\+?\d+v\d*|v\d+v\d+|vdd[a-z0-9_]*|vcc[a-z0-9_]*|vdda[a-z0-9_]*|"
    r"vbat|vsys|vbus|vin|vout|vref[a-z0-9_]*|\+?\d+vd?)$",
    re.IGNORECASE,
)

_STUB_MM = 2.54  # length of the wire stub from pin endpoint to the power port
# A power port glyph + its net-name text occupies ~3.8 mm vertically, far more
# than a bare label's 1.27 mm. Same-column ports closer than this must stagger.
_PWR_MIN_PITCH_MM = 4.0
_PWR_STUB_STEP_MM = 7.62  # x jog per stagger tier (6 grid units) to clear the text


def _power_net_kind(name: str) -> str | None:
    """Classify a net name as a power port target.

    Returns "gnd" (glyph drawn pointing down), "supply" (glyph pointing up), or
    None (not a power net → caller keeps the ordinary label path). Matching is
    conservative and name-shape based; anything ambiguous falls through to None
    so we never convert a signal net into a power port.
    """
    n = name.strip()
    if _GND_NET_RE.match(n):
        return "gnd"
    if _SUPPLY_NET_RE.match(n):
        return "supply"
    return None


def _power_symbol_lib_id(net_name: str, kind: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_+]", "_", net_name)
    return f"power_{kind}_{slug}"


def _power_symbol_def(lib_id: str, net_name: str, kind: str) -> str:
    """Synthesize a self-contained power-port symbol definition for lib_symbols.

    Geometry mirrors KiCad's stock power ports:
      - supply: a short vertical stem up from the pin, a horizontal bar at the
        top, and the net name above it (convention: rail points UP).
      - gnd: a short vertical stem down from the pin and the three shrinking GND
        bars below it (convention: ground points DOWN).
    The single pin is at (0,0), type power_in, so ERC treats the port as the
    net driver exactly like KiCad's own power symbols. The `power` + `pin_names
    hide` flags match stock power-port metadata.
    """
    if kind == "gnd":
        graphics = (
            '    (pin power_in line (at 0 0 270) (length 0)\n'
            f'      (name "{net_name}" (effects (font (size 0 0))))\n'
            '      (number "1" (effects (font (size 0 0)))))\n'
            '    (polyline (pts (xy 0 0) (xy 0 -1.27)) (stroke (width 0) (type default)))\n'
            '    (polyline (pts (xy -1.27 -1.27) (xy 1.27 -1.27)) (stroke (width 0) (type default)))\n'
            '    (polyline (pts (xy -0.762 -1.905) (xy 0.762 -1.905)) (stroke (width 0) (type default)))\n'
            '    (polyline (pts (xy -0.254 -2.54) (xy 0.254 -2.54)) (stroke (width 0) (type default)))'
        )
        label_at = "(at 0 -3.81 0)"
    else:
        graphics = (
            '    (pin power_in line (at 0 0 90) (length 0)\n'
            f'      (name "{net_name}" (effects (font (size 0 0))))\n'
            '      (number "1" (effects (font (size 0 0)))))\n'
            '    (polyline (pts (xy 0 0) (xy 0 1.27)) (stroke (width 0) (type default)))\n'
            '    (polyline (pts (xy -1.016 1.27) (xy 1.016 1.27)) (stroke (width 0) (type default)))'
        )
        label_at = "(at 0 2.032 0)"
    return (
        f'    (symbol "{lib_id}"\n'
        '      (power) (pin_names (offset 0) hide) (in_bom no) (on_board yes) (exclude_from_sim no)\n'
        f'      (property "Reference" "#PWR" {label_at} (effects (font (size 0 0)) hide))\n'
        f'      (property "Value" "{net_name}" {label_at} (effects (font (size 1.27 1.27))))\n'
        f'      (symbol "{lib_id}_0_1"\n{graphics}\n      )\n'
        '    )'
    )


def _pwr_flag_def() -> str:
    """KiCad's PWR_FLAG symbol: a hidden power_out pin that declares a power net
    is externally driven, silencing ERC's ``power_pin_not_driven`` without adding
    a real driver. One per power net is the eeschema-native convention."""
    return (
        '    (symbol "PWR_FLAG"\n'
        '      (power) (pin_numbers hide) (pin_names (offset 0) hide) (in_bom no) (on_board yes) (exclude_from_sim yes)\n'
        '      (property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 0 0)) hide))\n'
        '      (property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))\n'
        '      (symbol "PWR_FLAG_0_0"\n'
        '        (pin power_out line (at 0 0 90) (length 0)\n'
        '          (name "pwr" (effects (font (size 1.27 1.27))))\n'
        '          (number "1" (effects (font (size 1.27 1.27)))))\n'
        '      )\n'
        '      (symbol "PWR_FLAG_0_1"\n'
        '        (polyline (pts (xy 0 0) (xy 0 1.016) (xy -1.016 1.524) (xy 0 2.032) (xy 1.016 1.524) (xy 0 1.016))\n'
        '          (stroke (width 0) (type default)) (fill (type none)))\n'
        '      )\n'
        '    )'
    )


_FLG_REF_COUNTER = [0]


def _pwr_flag_instance(x: float, y: float, project_name: str, root_uuid: str) -> str:
    _FLG_REF_COUNTER[0] += 1
    ref = f"#FLG{_FLG_REF_COUNTER[0]:04d}"
    return (
        '  (symbol\n'
        '    (lib_id "PWR_FLAG")\n'
        f'    (at {round(x, 4)} {round(y, 4)} 0)\n'
        '    (unit 1)\n'
        '    (exclude_from_sim yes) (in_bom no) (on_board yes) (dnp no)\n'
        f'    (uuid "{_uid()}")\n'
        f'    (property "Reference" "{ref}" (at {round(x, 4)} {round(y - 3.81, 4)} 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (property "Value" "PWR_FLAG" (at {round(x, 4)} {round(y + 3.81, 4)} 0) (effects (font (size 1.27 1.27)) hide))\n'
        '    (pin "1" (uuid "' + _uid() + '"))\n'
        f'    (instances (project "{project_name}" (path "/{root_uuid}" (reference "{ref}") (unit 1))))\n'
        '  )'
    )


_PWR_REF_COUNTER = [0]


def _power_symbol_rotation(kind: str, edge: tuple[float, float]) -> int:
    """Rotation (deg, KiCad CCW) so the glyph faces AWAY from the body along the
    pin's outward edge vector, and the stem runs from the port back toward the pin
    — eliminating the "wire crosses the symbol body" cross when a bottom-edge pin's
    net runs DOWN into a supply rail, or a top-edge pin's runs UP into GND.

    Pin-local +y maps to sheet -y (screen up). The stock defs draw: supply glyph
    toward local +y (screen up, rot 0), gnd glyph toward local -y (screen down,
    rot 0). Outward edge vector (nx, ny) is in SHEET coords (ny>0 = screen down).
    """
    nx, ny = edge
    horizontal = abs(nx) >= abs(ny)
    if horizontal:
        outward_right = nx >= 0
        if kind == "gnd":
            return 90 if outward_right else 270
        return 270 if outward_right else 90
    outward_down = ny >= 0  # sheet +y is screen down
    if kind == "gnd":
        return 0 if outward_down else 180
    return 180 if outward_down else 0


def _power_symbol_instance(lib_id: str, net_name: str, x: float, y: float, project_name: str, root_uuid: str,
                           rotation: int = 0) -> str:
    _PWR_REF_COUNTER[0] += 1
    ref = f"#PWR{_PWR_REF_COUNTER[0]:04d}"
    # The Value (net-name) text offset must follow the glyph so it stays on the
    # OUTWARD side of the port rather than diving back over the body. rot 0 keeps
    # the legacy -y (above) offset; each 90° turn rotates the offset vector CCW.
    off = (0.0, -5.08)
    for _ in range((rotation // 90) % 4):
        off = (-off[1], off[0])  # CCW 90°: (ox,oy)->(-oy,ox)
    vx = round(x + off[0], 4)
    vy = round(y + off[1], 4)
    return (
        '  (symbol\n'
        f'    (lib_id "{lib_id}")\n'
        f'    (at {round(x, 4)} {round(y, 4)} {rotation})\n'
        '    (unit 1)\n'
        '    (exclude_from_sim no) (in_bom no) (on_board yes) (dnp no)\n'
        f'    (uuid "{_uid()}")\n'
        f'    (property "Reference" "{ref}" (at {round(x, 4)} {round(y - 3.81, 4)} 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (property "Value" "{net_name}" (at {vx} {vy} 0) (effects (font (size 1.27 1.27))))\n'
        '    (pin "1" (uuid "' + _uid() + '"))\n'
        f'    (instances (project "{project_name}" (path "/{root_uuid}" (reference "{ref}") (unit 1))))\n'
        '  )'
    )


def _staggered_label_blocks(endpoints: list[tuple[str, float, float]],
                            reserved: list[tuple[float, float, float, float]] | None = None,
                            page_scale: float = 1.0,
                            avail_y: tuple[float, float] | None = None,
                            avail_x: tuple[float, float] | None = None) -> list[str]:
    """Emit global labels with per-column anti-overlap staggering.

    avail_y (frame-first slot budget): the (y_lo, y_hi) usable-y corridor of the
    ALREADY-CHOSEN paper (composer picks the sheet BEFORE this runs and threads it
    here). When given, the vertical slot ladder is budgeted from the REAL corridor
    instead of the pin-row extent (which degrades to cap=1 on a dense column and
    pushes labels off-sheet), and every slot / collision candidate is rejected if
    it leaves the corridor. None => legacy pin-extent budget (byte-stable).

    Pins on one side of a dense symbol (a large BGA drawn as a per-page subset)
    share an x coordinate and sit at ~2.0 mm pitch; a 1.27 mm-tall label on each
    would collide into an unreadable blob. We group endpoints by their x column,
    sort each column by y, and when consecutive labels are closer than
    ``_LABEL_MIN_PITCH_MM`` we push every other one outward by a stub wire so the
    text boxes separate. A single label (or a sparse column) is emitted verbatim,
    so low-density pages are byte-unchanged.

    page_scale (CCM sheet-coherence): 1.0 == legacy (byte-identical). At >1.0 the
    per-page symbol was drawn on a large pin pitch (>= 4x), so adjacent label rows
    are already far apart; we therefore (C) DROP the vertical collision-nudge so
    every stub runs STRAIGHT OUT (no top-⅓-up / bottom-⅓-down fan), and (B) anchor
    the label at the stub OUTER end on a scaled-length stub so the label text sits
    off the body instead of over the pin name.
    """
    scaled = page_scale > 1.0
    stub_len = _LABEL_STUB_STEP_MM * (page_scale if scaled else 1.0)
    blocks: list[str] = []
    # Global bbox occupancy: two labels FAIL when their rendered text boxes overlap
    # in BOTH axes. The prior per-column y-stagger left cross-column horizontal
    # collisions unresolved (short labels crowded around a dense IC on adjacent x
    # columns still overlapped). We now register every emitted label's box and, for
    # each new label, nudge its y upward in _LABEL_MIN_PITCH steps until its box is
    # clear of ALL placed boxes. Process column-by-column (left to right, bottom to
    # top) for determinism; a label shifted off its pin row gets a stub jog so the
    # electrical endpoint is unchanged. Sparse pages never trip the overlap test, so
    # they stay byte-unchanged.
    columns: dict[float, list[tuple[str, float, float, tuple[float, float]]]] = {}
    for name, x, y, *rest in endpoints:
        edge = rest[0] if rest else (1.0, 0.0)
        columns.setdefault(round(x, 2), []).append((name, x, y, edge))
    # Seed the occupancy with the in-body pin-NAME boxes so a global label never
    # gets placed on top of the IC's own pin-name text (the cross pin/label smear).
    placed: list[tuple[float, float, float, float]] = list(reserved or [])
    for col_x in sorted(columns):
        items = sorted(columns[col_x], key=lambda t: t[2])
        # ---- design-time per-column capacity reservation (vertical labels) ----
        # Before placing ANY label in this column, decide whether the column can
        # hold all its VERTICAL (ang90/270) labels within a usable y-span. If the
        # count exceeds capacity, pre-assign each label a sub-column so the greedy
        # per-pin stagger never pushes labels off-sheet. Horizontal-text labels and
        # legacy (page_scale==1.0) columns are unaffected (subcol stays 0 for all).
        # value-keyed (net_name, y-rounded) -> sub-column index. NOT id()-keyed:
        # the placement loop re-destructures each item into a FRESH tuple, so an
        # id()-based map would never hit (the exact "measure never took effect"
        # trap). y is unique within a pin column, so (name, round(y,4)) is stable.
        subcol_of: dict[tuple[str, float], int] = {}
        # (name, y-rounded) -> (slot_index_within_subcol, slot_pitch, subcol_y0):
        # DESIGN-TIME y placement. Once a label is assigned to a sub-column, its y
        # is the k-th evenly-spaced slot in the usable span — NOT the pin y pushed
        # by a greedy nudge (which left 6 labels crammed at the original pin rows,
        # the 18-pair same-x residue). slot_y = subcol_y0 + k * slot_pitch.
        slot_of: dict[tuple[str, float], tuple[int, float, float]] = {}
        col_step = 0.0
        if scaled:
            vitems = [it for it in items if abs(it[3][0]) < abs(it[3][1])]
            if len(vitems) > 1:
                vnames = [it[0] for it in vitems]
                # usable y-span: frame-first — bind to the CHOSEN paper's real
                # usable-y corridor (avail_y) when the composer threaded it, so a
                # dense column's capacity reflects the actual sheet, not the pin-row
                # extent (which degrades to cap=1 and pushes labels off-sheet). The
                # slot ladder is then anchored at the corridor and can never emit an
                # off-sheet y. avail_y is None => legacy pin-extent budget (byte-stable).
                ys = [it[2] for it in vitems]
                pin_extent = max(ys) - min(ys)
                extent = _vlabel_extent_mm(vnames, page_scale)
                gap = _LABEL_MIN_PITCH_MM * page_scale
                if avail_y is not None:
                    y_lo, y_hi = avail_y
                    usable_span = max(y_hi - y_lo, extent + gap)
                else:
                    y_lo = min(ys)
                    usable_span = max(pin_extent * _LABEL_SPAN_BUDGET, extent + gap)
                cap = _column_capacity(usable_span, extent, gap)
                if len(vitems) > cap:
                    import math as _math
                    cols = _math.ceil(len(vitems) / cap)
                    # sub-column step = the vertical label's own x footprint. A
                    # vertical (ang90/270) label's box is `h` wide in x (the glyph
                    # column) — see _label_bbox: (x-h/2, x+h/2, y, y+w). Two sub-
                    # columns must be at least h + gap apart or their glyph columns
                    # touch. (Earlier bug: used the 1-line text height ~6 mm which is
                    # coincidentally h, but the real driver is the x footprint h.)
                    h = _LABEL_CH_MM * page_scale + _LABEL_VMARGIN_MM
                    col_step = h + _LABEL_COL_GAP_MM * page_scale
                    # BLOCK assignment (idx // cap), NOT interleave (idx % cols):
                    # each sub-column takes a CONTIGUOUS y-run of <=cap labels, so a
                    # sub-column's labels are far apart in y and never collide with
                    # its own siblings. Interleave put y-adjacent labels in adjacent
                    # sub-columns (same y, x one step apart) => horizontal text-band
                    # overlap (the 25-pair regression).
                    # slot geometry: distribute cap labels across usable_span,
                    # anchored at the corridor low edge (y_lo already = avail_y low
                    # when threaded, else the pin-row min) so slots are evenly spread
                    # within the real sheet and never run past y_hi.
                    slot_pitch = usable_span / cap
                    for idx, it in enumerate(vitems):
                        sc = idx // cap
                        k = idx % cap                       # slot index within sub-col
                        subcol_of[(it[0], round(it[2], 4))] = sc
                        # each sub-column reuses the SAME usable-span slot ladder;
                        # they are separated in x by col_step, so identical y is fine.
                        slot_of[(it[0], round(it[2], 4))] = (k, slot_pitch, y_lo)
        for name, x, y, edge in items:
            # jog direction follows the pin's OUTWARD edge vector (left edge => -x),
            # so a staggered label steps AWAY from the body, not toward it.
            nx, ny = edge
            direction = 1.0 if nx >= 0 else -1.0
            if scaled:
                # Fix B: anchor at the stub OUTER end so the label text sits off the
                # body (not over the pin name). Fix C: the stub runs STRAIGHT OUT
                # first (no systematic top-⅓-up/bottom-⅓-down fan). Overlap fix:
                # scaled label boxes on a dense column still collide, so — ONLY when
                # a box actually overlaps a placed box — displace the label along the
                # column axis in _LABEL_MIN_PITCH×scale steps until clear, adding an
                # L-jog wire so the electrical endpoint (pin) is unchanged. An
                # uncrowded label stays perfectly straight (byte-stable intent).
                horiz = abs(nx) >= abs(ny)
                pitch = _LABEL_MIN_PITCH_MM * page_scale
                subcol = subcol_of.get((name, round(y, 4)), 0)
                if horiz:
                    # MIXED-AXIS convergence. A horizontal-text label (a0/a180)
                    # extends its box ALONG x (~len*CW*scale, up to ~40 mm). When it
                    # collides with a VERTICAL label's text band (a90/a270) that hangs
                    # across the plane, a pure-y nudge can never escape: the vertical
                    # band spans a wide y range at a fixed x, so stepping y keeps the
                    # horizontal box inside the band's y-extent. The 37-pair residue is
                    # exactly this (all xy-overlap, horizontal×vertical crossing). So:
                    # (1) try the legacy y-ladder first (cheap, byte-stable for the
                    #     common horizontal×horizontal crowding);
                    # (2) if the y-ladder exhausts, FAIL OVER to an x-ladder that
                    #     lengthens the stub so the text-band START moves clear of the
                    #     vertical band's x column;
                    # each candidate is checked against the WHOLE placed ledger.
                    base_lx = round(x + direction * stub_len, 4)
                    base_y = y
                    lx = base_lx
                    ly2 = base_y
                    resolved = False
                    # X-CORRIDOR guard (mirror of the vertical branch's avail_y): a
                    # horizontal label's box extends ALONG x toward the outward edge
                    # (_label_bbox: nx>=0 => [x, x+w]; nx<0 => [x-w, x]). The x-ladder
                    # fans the anchor OUTWARD, so an ang180 (nx<0) label's box marches
                    # LEFT and its x0 = lx - w runs off the left sheet edge (x<0) with
                    # no bound check — the 05-page 25 offpage. Bind every candidate's
                    # x-box to the chosen paper's usable-x corridor (avail_x); a
                    # candidate whose box leaves [x_lo, x_hi] is rejected, never
                    # emitted. avail_x is None => legacy unbounded (byte-stable).
                    def _hbox_in_corridor(cand_lx: float) -> bool:
                        if avail_x is None:
                            return True
                        bx0 = _label_bbox(name, cand_lx, base_y, True, edge, text_scale=page_scale)
                        return bx0[0] >= avail_x[0] - 1e-6 and bx0[1] <= avail_x[1] + 1e-6
                    # x-tier 0 == legacy stub; escalate x outward per tier. If the
                    # outward tier leaves the corridor, the ladder is exhausted for
                    # this direction — the label physically cannot fan further out
                    # without going off-sheet, so we stop escalating x (a further tier
                    # would only worsen the excursion) and rely on the y-ladder / the
                    # fail-loud below rather than emit an off-sheet candidate.
                    for xt in range(24):
                        lx = round(base_lx + direction * xt * stub_len, 4)
                        if not _hbox_in_corridor(lx):
                            break
                        disp = 0.0
                        for _ in range(400):
                            cand = round(base_y + disp, 4)
                            bx = _label_bbox(name, lx, cand, True, edge, text_scale=page_scale)
                            if not any(_bbox_overlap(bx, pb) for pb in placed):
                                ly2 = cand
                                resolved = True
                                break
                            disp += pitch
                        if resolved:
                            break
                    if not resolved:
                        raise ValueError(
                            f"LABEL_DENSITY_UNRESOLVED: horizontal label {name!r} at "
                            f"pin ({x},{y}) could not clear placed boxes within the "
                            f"usable-x corridor after 24 x-tiers x 400 y-steps "
                            f"(page_scale={page_scale}, avail_x={avail_x})")
                    if abs(lx - base_lx) > 1e-6 and abs(ly2 - y) > 1e-6:
                        # L-jog with extended stub: pin -> out to lx (at pin y) -> up to ly2
                        blocks.append(_wire_segment_block(x, y, lx, y))
                        blocks.append(_wire_segment_block(lx, y, lx, ly2))
                    elif abs(ly2 - y) > 1e-6:
                        # L-jog: pin -> outward -> up to the cleared row -> label
                        blocks.append(_wire_segment_block(x, y, lx, y))
                        blocks.append(_wire_segment_block(lx, y, lx, ly2))
                    else:
                        blocks.append(_wire_segment_block(x, y, lx, ly2))
                else:
                    # Vertical text run (top/bottom edge): the label box extends
                    # ALONG the column axis (y), so two crowded vertical labels
                    # separate by pushing their ANCHORS apart along y — NOT along x
                    # (an x nudge only shifts the ~6 mm-wide glyph column and leaves
                    # the tall y text band overlapping). Displace ly2 outward along
                    # the pin's vdir in pitch steps until the box clears all placed.
                    vdir = 1.0 if ny >= 0 else -1.0
                    # Design-time multi-column spillover: a label pre-assigned to
                    # sub-column N is fanned outward along x by N*col_step so a
                    # single over-packed pin column becomes several parallel label
                    # columns instead of one that runs off-sheet. subcol==0 (the
                    # common / sparse case) keeps lx==x, byte-stable. The stub then
                    # jogs pin -> sub-column x -> outward y, and the y collision
                    # nudge only has to separate the ~capacity labels now sharing
                    # this sub-column (never the whole overloaded stack).
                    xdir = direction if abs(direction) > 1e-9 else 1.0
                    base_lx = round(x + subcol * col_step * xdir, 4)
                    slot = slot_of.get((name, round(y, 4)))
                    if slot is not None:
                        # DESIGN-TIME y: the label sits at its evenly-spaced slot in
                        # the usable span (k-th of cap), so a sub-column's labels are
                        # spread across the whole span instead of crammed at the pin
                        # rows. This is what makes same-x siblings NOT overlap (the
                        # 18-pair residue). We STILL run the collision loop from the
                        # slot as a safety net, but the slot base already clears.
                        k, slot_pitch, y0 = slot
                        base_ly2 = round(y0 + k * slot_pitch, 4)
                    else:
                        base_ly2 = round(y + vdir * stub_len, 4)
                    # MIXED-AXIS convergence (mirror of the horizontal branch). A pure
                    # y-nudge cannot escape a horizontal label's text band that crosses
                    # this column (the cross-type residue). So escalate an x-ladder:
                    # for each x-tier fan the sub-column further outward, then run the
                    # y-collision loop; a vertical-label anchor y is REJECTED if it (or
                    # its box) leaves the paper's usable-y corridor (avail_y), so the
                    # ladder can never re-introduce an off-sheet label. First clear tier
                    # wins; exhausting all tiers is fail-loud, never a silent overlap.
                    def _vbox_in_corridor(cy: float) -> bool:
                        if avail_y is None:
                            return True
                        bx0 = _label_bbox(name, 0.0, cy, True, edge, text_scale=page_scale)
                        return bx0[2] >= avail_y[0] - 1e-6 and bx0[3] <= avail_y[1] + 1e-6
                    # Clamp the anchor so the label BOX sits fully inside the corridor
                    # before searching. A base near a boundary (e.g. NRST whose box
                    # low edge = 2.8 mm < margin 12.7) would otherwise fail every step
                    # because the pure-vdir search only pushes it FURTHER out. The box
                    # y-span is [cy - w, cy] (ny<0) or [cy, cy + w] (ny>=0); pick the
                    # cy that puts the whole span inside [lo, hi].
                    def _clamp_anchor(cy: float) -> float:
                        if avail_y is None:
                            return cy
                        lo, hi = avail_y
                        bx0 = _label_bbox(name, 0.0, cy, True, edge, text_scale=page_scale)
                        blo, bhi = bx0[2], bx0[3]
                        if blo < lo:
                            cy += (lo - blo)
                        elif bhi > hi:
                            cy -= (bhi - hi)
                        return round(cy, 4)
                    base_ly2 = _clamp_anchor(base_ly2)
                    # x-ladder step: reuse col_step when multi-column spillover set
                    # it, else derive the label's own x footprint (h + gap) so the
                    # ladder still fans on a SPARSE column (col_step==0 there) — a
                    # zero step would collapse every tier onto the same x and make the
                    # x-ladder a no-op (the 01_power NRST fail-loud).
                    x_step = col_step if col_step > 1e-6 else (
                        _LABEL_CH_MM * page_scale + _LABEL_VMARGIN_MM
                        + _LABEL_COL_GAP_MM * page_scale)
                    # X-CORRIDOR guard for the vertical branch's glyph column: a
                    # vertical (ang90/270) label's box is `h` wide in x centred on lx
                    # (_label_bbox: [lx-h/2, lx+h/2]); the x-ladder fans lx outward per
                    # tier, so a column near the left/right sheet edge can push its
                    # glyph column off-sheet in x. Reject any tier whose x-box leaves
                    # the usable-x corridor (symmetric to the horizontal branch's
                    # _hbox_in_corridor). avail_x is None => legacy unbounded.
                    def _vbox_in_x_corridor(cand_lx: float) -> bool:
                        if avail_x is None:
                            return True
                        bx0 = _label_bbox(name, cand_lx, base_ly2, True, edge, text_scale=page_scale)
                        return bx0[0] >= avail_x[0] - 1e-6 and bx0[1] <= avail_x[1] + 1e-6
                    lx = base_lx
                    ly2 = base_ly2
                    resolved = False
                    for xt in range(24):
                        lx = round(base_lx + xdir * xt * x_step, 4)
                        if not _vbox_in_x_corridor(lx):
                            break
                        # BIDIRECTIONAL y-search within the corridor: try the clamped
                        # base, then alternate outward/inward (vdir and -vdir) so a
                        # label near a boundary can move AWAY from the wall instead of
                        # only pushing into it. Candidates outside the corridor are
                        # skipped, never accepted. First clear candidate wins.
                        found = False
                        for step in range(400):
                            for sign in ((vdir,) if step == 0 else (vdir, -vdir)):
                                cand = round(base_ly2 + sign * step * pitch, 4)
                                if not _vbox_in_corridor(cand):
                                    continue
                                bx = _label_bbox(name, lx, cand, True, edge, text_scale=page_scale)
                                if not any(_bbox_overlap(bx, pb) for pb in placed):
                                    ly2 = cand
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            resolved = True
                            break
                    if not resolved:
                        raise ValueError(
                            f"LABEL_DENSITY_UNRESOLVED: vertical label {name!r} at "
                            f"pin ({x},{y}) could not clear placed boxes within the "
                            f"usable-y corridor after 24 x-tiers x 400 y-steps "
                            f"(page_scale={page_scale}, avail_y={avail_y})")
                    if abs(lx - x) > 1e-6 or abs(ly2 - y) > 1e-6:
                        # L-jog: pin -> out to sub-column x (at pin y) -> up to slot y
                        blocks.append(_wire_segment_block(x, y, lx, y))
                        blocks.append(_wire_segment_block(lx, y, lx, ly2))
                    else:
                        blocks.append(_wire_segment_block(x, y, lx, ly2))
                _label_bbox_reg = _label_bbox(name, lx, ly2, True, edge, text_scale=page_scale)
                placed.append(_label_bbox_reg)
                blocks.append(_global_label_block(name, lx, ly2, edge, text_scale=page_scale))
                continue
            ly = _resolve_label_y(name, x, y, True, placed, direction, edge)
            if abs(ly - y) > 1e-6:
                lx = round(x + direction * _LABEL_STUB_STEP_MM, 4)
                blocks.append(_wire_segment_block(x, y, lx, y))
                blocks.append(_wire_segment_block(lx, y, lx, ly))
                blocks.append(_global_label_block(name, lx, ly, edge))
            else:
                blocks.append(_global_label_block(name, x, ly, edge))
    return blocks


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


def _no_connect_block(x: float, y: float) -> str:
    """A no-connect cross on a pin endpoint declares the pin intentionally open,
    so ERC does not report `pin_not_connected` for it (T1)."""
    return f'  (no_connect (at {round(x, 4)} {round(y, 4)}) (uuid "{_uid()}"))'


# ---------------------------------------------------------------------------
# DD-11 (A3 control): wire anti-fusion guard. KiCad's wire connectivity is
# GEOMETRIC — two collinear overlapping wire segments (or an endpoint landing on
# another net's wire) are electrically FUSED into one net. The wire geometry
# generators (_orthogonal_route / _bus_route / power stubs) only guarantee
# correct endpoints, never that DIFFERENT nets' segments stay disjoint. On dense
# connector columns this fuses nets into shorts (aiguard stamp page GND←141,
# product board BAT_SENSE←177). This guard, run before segments hit the sheet,
# registers every net's segments and rejects any new segment that collinearly
# overlaps — or whose endpoints land on — a DIFFERENT net's registered segment.
# ---------------------------------------------------------------------------
_FUSION_EPS = 1e-4


def _seg_axis(a: tuple[float, float], b: tuple[float, float]) -> str | None:
    """'h' if horizontal, 'v' if vertical, None if degenerate/diagonal."""
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    if dx < _FUSION_EPS and dy < _FUSION_EPS:
        return None            # zero-length
    if dy < _FUSION_EPS:
        return "h"
    if dx < _FUSION_EPS:
        return "v"
    return None                # diagonal (routers never emit these)


def _collinear_overlap(s1: tuple, s2: tuple) -> bool:
    """True iff two axis-aligned segments are collinear (same axis + same line)
    AND their intervals overlap with non-zero length (a shared touch-point at a
    single coordinate is NOT a fusing overlap — that is a legal T/corner)."""
    a1, b1 = s1
    a2, b2 = s2
    ax1 = _seg_axis(a1, b1)
    ax2 = _seg_axis(a2, b2)
    if ax1 is None or ax2 is None or ax1 != ax2:
        return False
    if ax1 == "h":
        if abs(a1[1] - a2[1]) > _FUSION_EPS:
            return False       # different horizontal lines
        lo1, hi1 = sorted((a1[0], b1[0]))
        lo2, hi2 = sorted((a2[0], b2[0]))
    else:
        if abs(a1[0] - a2[0]) > _FUSION_EPS:
            return False       # different vertical lines
        lo1, hi1 = sorted((a1[1], b1[1]))
        lo2, hi2 = sorted((a2[1], b2[1]))
    overlap = min(hi1, hi2) - max(lo1, lo2)
    return overlap > _FUSION_EPS


def _point_on_segment(pt: tuple[float, float], seg: tuple) -> bool:
    """True iff pt lies ON seg (endpoints included). A shared endpoint between two
    nets is itself a fusion (KiCad merges a wire END that touches another wire)."""
    a, b = seg
    ax = _seg_axis(a, b)
    if ax is None:
        return abs(pt[0] - a[0]) < _FUSION_EPS and abs(pt[1] - a[1]) < _FUSION_EPS
    if ax == "h":
        if abs(pt[1] - a[1]) > _FUSION_EPS:
            return False
        lo, hi = sorted((a[0], b[0]))
        return lo - _FUSION_EPS <= pt[0] <= hi + _FUSION_EPS
    if abs(pt[0] - a[0]) > _FUSION_EPS:
        return False
    lo, hi = sorted((a[1], b[1]))
    return lo - _FUSION_EPS <= pt[1] <= hi + _FUSION_EPS


def _segment_fuses(seg: tuple, other_net_segs: list[tuple]) -> bool:
    """True iff `seg` would electrically fuse with any segment belonging to a
    DIFFERENT net: collinear interval overlap, or either endpoint on the other
    segment (and vice versa, to catch a foreign endpoint on THIS segment)."""
    for o in other_net_segs:
        if _collinear_overlap(seg, o):
            return True
        if _point_on_segment(seg[0], o) or _point_on_segment(seg[1], o):
            return True
        if _point_on_segment(o[0], seg) or _point_on_segment(o[1], seg):
            return True
    return False


def _net_jog_steps(net_name: str, attempt: int) -> float:
    """Deterministic jog offset (mm) for a net, by net-name hash. Returns 1..3
    grid steps (1.27 mm multiples). `attempt` (0-based) rotates the magnitude so
    successive retries try distinct offsets. Sign is folded into the hash so
    different nets deterministically diverge instead of all jogging one way."""
    import hashlib
    h = int(hashlib.sha256(f"{net_name}#{attempt}".encode()).hexdigest(), 16)
    steps = (h % 3) + 1                      # 1, 2, or 3 grid steps
    sign = 1.0 if (h >> 2) & 1 else -1.0
    return round(sign * steps * 1.27, 4)


def _jog_free_axis(waypoints: list[tuple[float, float]], offset: float) -> list[tuple[float, float]]:
    """Shift an L-route's elbow along its FREE axis by `offset`, keeping both pin
    endpoints fixed. For a 2-waypoint straight run this inserts a jog so the
    middle no longer lies on the original line. For a 3-waypoint L, it moves the
    elbow's swing so the two legs shift off the colliding column/row.

    A horizontal-first L [p1,(x2,y1),p2] has its VERTICAL leg on column x2; jog
    it to (x2+offset). A collinear straight [p1,p2] (dx==0 or dy==0) is split
    into a 3-segment jog so it detours off the shared line.
    """
    if len(waypoints) == 2:
        (x1, y1), (x2, y2) = waypoints
        if abs(x1 - x2) < _FUSION_EPS:       # vertical run → detour x
            mx = round(x1 + offset, 4)
            return [(x1, y1), (mx, y1), (mx, y2), (x2, y2)]
        # horizontal run → detour y
        my = round(y1 + offset, 4)
        return [(x1, y1), (x1, my), (x2, my), (x2, y2)]
    if len(waypoints) == 3:
        (x1, y1), (ex, ey), (x2, y2) = waypoints
        # horizontal-first elbow: vertical leg on column ex → move the column.
        nex = round(ex + offset, 4)
        return [(x1, y1), (nex, y1), (nex, y2), (x2, y2)]
    return waypoints


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


def _schematic_document(root_uuid: str, definitions, symbol_blocks, label_blocks, wire_blocks=(), junction_blocks=(), nc_blocks=(), paper: str = "A4") -> str:
    lib_symbols = "\n".join(definitions)
    body = "\n".join([*symbol_blocks, *wire_blocks, *junction_blocks, *nc_blocks, *label_blocks])
    return (
        "(kicad_sch\n"
        f'  (version {SCHEMATIC_VERSION})\n'
        '  (generator "bodesign")\n'
        '  (generator_version "9.0")\n'
        f'  (uuid "{root_uuid}")\n'
        f'  (paper "{paper}")\n'
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


def validate_kicad_schematic(
    schematic_path: str | Path,
    output_dir: str | Path | None = None,
    declared_nc: list[str] | None = None,
) -> KiCadValidationResult:
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
        result.erc_classification = classify_erc_report(report_text, declared_nc)
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


# ERC report line shapes -------------------------------------------------------
#
# `pin_not_connected` shape is verified against real kicad-cli 9.0.9 output
# (experiments/e2e-led-driver/C03-EE/e2e-led-driver.erc.rpt):
#
#   [pin_not_connected]: Pin not connected
#       ; error
#       @(350.52 mm, 116.84 mm): Symbol J1 Pin A7 [D-, Bidirectional, Line]
#
# i.e. the violation code sits on a `[code]: message` header line and the
# affected symbol/pin sits on a following `@(...): Symbol <REF> Pin <NUM> [...]`
# detail line. `<REF>.<NUM>` is what a spec no_connect declaration references.
#
# The short / net-conflict shapes below are an ASSUMPTION grounded in
# concept.no-connect-classification semantics (two named nets => real short;
# a second net that is empty / a single net => pad-net bug). No real kicad-cli
# short-violation fixture was available to verify the exact wording, so the
# matcher keys on the SEMANTIC signature (count of quoted/named nets in the
# description) rather than an unverified literal string, and anything it cannot
# place is preserved verbatim in `other` (no silent fallback).
_ERC_HEADER_RE = re.compile(r"^\[(?P<code>[a-z0-9_]+)\]:\s*(?P<msg>.*)$")
_ERC_SYMBOL_PIN_RE = re.compile(r"Symbol\s+(?P<ref>\S+)\s+Pin\s+(?P<pin>\S+)\b")
# Named nets appear as `nets FOO and BAR` or quoted `"FOO"`. Capture both a
# `nets X and Y` construction and any quoted net tokens so we can count them.
_ERC_NETS_AND_RE = re.compile(r"\bnets?\s+(?P<a>[^\s]+)\s+and\s+(?P<b>[^\s]*)", re.IGNORECASE)
_ERC_QUOTED_NET_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")
_ERC_SHORT_CODES = frozenset({
    "net_conflict",
    "different_units_net",
    "conflicting_netclasses",
    "multiple_net_names",
    "pin_to_pin",
})


def _erc_short_kind(description: str) -> str | None:
    """Sub-classify a short-like violation from its description text.

    Returns ``"real_short"`` when two distinct named nets are present, ``"pad_net_bug"``
    when the second net is empty / only one net is named, or ``None`` when the line
    carries no short signature at all (caller falls through to `other`).

    Signature source: concept.no-connect-classification (ASSUMPTION — see module note).
    """
    m = _ERC_NETS_AND_RE.search(description)
    if m is not None:
        a = m.group("a").strip().strip("'\"),;")
        b = m.group("b").strip().strip("'\"),;")
        if a and b and a != b:
            return "real_short"
        return "pad_net_bug"
    quoted = [g1 or g2 for g1, g2 in _ERC_QUOTED_NET_RE.findall(description)]
    named = [q for q in quoted if q.strip()]
    if len(named) >= 2:
        # two distinct quoted nets touching
        if named[0] != named[1]:
            return "real_short"
        return "pad_net_bug"
    if len(quoted) >= 2 and len(named) < 2:
        # a second net token exists but is empty -> pad has no net
        return "pad_net_bug"
    return None


def classify_erc_report(report_text: str, declared_nc: list[str] | None = None) -> ErcClassification:
    """Classify a KiCad ERC report into deterministic reviewer buckets (pure-python, zero-LLM).

    Parameters
    ----------
    report_text:
        Full text of a `<stem>.erc.rpt` file (as emitted by `kicad-cli sch erc`).
        This function NEVER runs a subprocess; it only parses the text passed in,
        so it is independently unit-testable without kicad-cli.
    declared_nc:
        Optional list of ``"REF.PIN"`` strings that the spec declares as intentional
        no-connect. A `pin_not_connected` violation whose ``REF.PIN`` appears here is
        demoted to `intentional_nc` (INFO) instead of `unconnected` (defect).

    Determinism
    -----------
    Same ``report_text`` + ``declared_nc`` yields byte-identical output. No hidden
    state, no ordering dependence beyond the report's own line order.

    No silent fallback
    ------------------
    A violation line that matches no known shape is preserved verbatim in `other`;
    nothing is dropped.
    """
    declared = frozenset(declared_nc or ())
    result = ErcClassification()

    lines = report_text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        header = _ERC_HEADER_RE.match(lines[i].strip())
        if header is None:
            i += 1
            continue
        code = header.group("code")
        # Gather this violation's detail lines: everything up to the next header
        # or a blank line. The raw description we keep is the header + detail block
        # so traceability is preserved.
        block = [lines[i].rstrip()]
        j = i + 1
        while j < n:
            stripped = lines[j].strip()
            if not stripped or _ERC_HEADER_RE.match(stripped):
                break
            block.append(lines[j].rstrip())
            j += 1
        raw = "\n".join(block)
        detail = " ".join(block)

        if code == "pin_not_connected":
            sym = _ERC_SYMBOL_PIN_RE.search(detail)
            ref_pin = f"{sym.group('ref')}.{sym.group('pin')}" if sym else None
            if ref_pin is not None and ref_pin in declared:
                result.intentional_nc.append(raw)
            else:
                result.unconnected.append(raw)
        elif code in _ERC_SHORT_CODES:
            kind = _erc_short_kind(detail)
            if kind == "real_short":
                result.real_shorts.append(raw)
            elif kind == "pad_net_bug":
                result.pad_net_bugs.append(raw)
            else:
                # short-family code but no recognizable net signature -> keep, do not guess
                result.other.append(raw)
        else:
            # Unknown-but-net-shaped lines: still try a short signature before giving up.
            kind = _erc_short_kind(detail)
            if kind == "real_short":
                result.real_shorts.append(raw)
            elif kind == "pad_net_bug":
                result.pad_net_bugs.append(raw)
            else:
                result.other.append(raw)

        i = j

    return result


def _parse_netlist_nets(net_text: str) -> list[dict[str, object]]:
    nets: list[dict[str, object]] = []
    for net_match in re.finditer(r'\(net\s+\(code\s+"[^"]*"\)\s+\(name\s+"([^"]*)"\)(.*?)(?=\(net\s+\(code|\)\s*\)\s*$)', net_text, re.DOTALL):
        name = net_match.group(1)
        nodes = [f"{ref}.{pin}" for ref, pin in re.findall(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', net_match.group(2))]
        if nodes:
            nets.append({"name": name, "nodes": nodes})
    return nets
