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

from .occupancy import LedgerRect, OccupancyLedger

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
    # M6-2 (DD-12): local labels the placer could NOT fit clear of every other
    # label / pin-name, so it down-graded to the route far-end (never stacked).
    # Each entry {"net": name, "at": [x, y]}. Empty == every local label found a
    # clear slot (the good case). Visible so a reviewer sees crowded pages.
    label_local_downgrades: list[dict] = field(default_factory=list)
    # BR_20260708 machine check: drawn wire segments that still cross a NON-host
    # component body AABB (keep-out-inflated). Empty == every drawn wire clears all
    # symbol bodies (the BR acceptance geometry check). Each entry:
    #   {"seg": [[x1,y1],[x2,y2]], "through": ref}. Queryable; never silent.
    wire_body_intrusions: list[dict] = field(default_factory=list)
    # BR_20260710: power-port endpoints that fell inside a NON-host symbol body
    # (guard C, POWER_PORT_INSIDE_SYMBOL_BODY). By default this defect is fail-loud
    # (raises in emit). When the caller opts into `power_port_gate="warn"` — the
    # ERC-only / netlist-only path that must not be held hostage by a purely-visual
    # layout defect — the intrusions are recorded here (observation, same pattern as
    # wire_body_intrusions) and a warning is appended instead of raising.
    #
    # This is the LOSSLESS channel: the warning string truncates at 12 entries and
    # appends "(+N more)", so entries 13.. are unrecoverable from it. Read this
    # field, not the warning, when you need the individual `ref@(x,y) inside ref`.
    #
    # BR_20260804f: this field was declared here with the paragraph above ALREADY
    # promising "recorded here" — and was never assigned (grep: one hit, the
    # declaration; `git log -S 'power_port_intrusions='`: zero commits; control
    # `wire_body_intrusions=`: 3c019df). So an instrument that read it per the
    # docstring got [] while the SAME compose emitted a guard-C warning naming one
    # intrusion. Empty now means exactly one thing: no intrusions were found.
    #
    # Observable ONLY on the warn path. On the default fail-loud path emit raises,
    # so no result object exists to carry it — the previous wording ("Empty on the
    # default fail-loud path") described a state nobody can observe, which is the
    # same defect one level down.
    power_port_intrusions: list[str] = field(default_factory=list)
    # M7-3b-i (DD-11): L2.5 SlotTable slot-consumption OBSERVATION (never a driving
    # gate). When the caller passes `clusters=`, emit builds a SlotTable
    # (l1_geometry→gap_topology→build_capacity_plan) and, for every ACCEPTED drawn
    # wire, records whether the wire's trunk lands on its reserved lane. Geometry is
    # NOT changed — this is the作用面 measurement that feeds M7-3b-ii's greyscale
    # slot consumption. Each entry is a slot_observe wire record (net/has_slot/hit/
    # lane_coord/gap/axis/nearest_delta); `slot_observe_skips` records front-stage
    # fail-fasts caught in observation mode (net/gap unplannable — explicit, never
    # silent). Empty when clusters is None (byte-identical legacy path).
    slot_observe_wires: list[dict] = field(default_factory=list)
    slot_observe_skips: list[dict] = field(default_factory=list)


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


def _scale_symbol_geometry(block: str, scale: float) -> str:
    """Multiply every geometry-bearing coordinate in a symbol block by `scale`.

    v11 review bug 2 (「副圖 pin 間距沒有跟主圖一致」): peripheral parts drawn from
    a STORED KiCad .kicad_sym (Device:C / Device:Crystal / Conn_* / PWR_FLAG / the
    project ldo/buck/psram libs) keep their native 1.27 mm pin pitch — they are NOT
    re-generated per-page like the U1 variant (which is emitted at pin_pitch/scale
    by build_u1_variant). Loading them verbatim leaves the sub-figure dense while
    the main symbol is spread at scale×1.27, so the densities never match. Scaling
    the stored symbol's geometry by page_scale gives every peripheral pin the SAME
    adjacent-pin density as the main part — by construction, not a post-hoc nudge.

    Scales ONLY spatial coordinates so the drawn geometry grows uniformly:
      - (at x y [rot])  -> x,y ×scale; rot UNCHANGED (an angle, not a length)
      - (length N) (radius N)                                   -> ×scale
      - (start|end|mid|center|xy X Y)                           -> ×scale
      - (size w h)  (font text height — grows with the symbol)  -> ×scale
    A `(name/number ...)` string is never numeric-matched, so text CONTENT is safe.
    scale==1.0 is a byte-identical no-op (round-trips the same literals).
    """
    if scale == 1.0:
        return block

    def _at(m: "re.Match") -> str:
        x = round(float(m.group(1)) * scale, 4)
        y = round(float(m.group(2)) * scale, 4)
        rot = m.group(3)
        return f"(at {_fmt_num(x)} {_fmt_num(y)}" + (f" {rot})" if rot is not None else ")")

    block = re.sub(r'\(at\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+(-?[\d.]+))?\)', _at, block)
    block = re.sub(r'\(length\s+(-?[\d.]+)\)',
                   lambda m: f"(length {_fmt_num(round(float(m.group(1)) * scale, 4))})", block)
    block = re.sub(r'\(radius\s+(-?[\d.]+)\)',
                   lambda m: f"(radius {_fmt_num(round(float(m.group(1)) * scale, 4))})", block)
    for _kw in ("start", "end", "mid", "center", "xy"):
        block = re.sub(
            r'\(' + _kw + r'\s+(-?[\d.]+)\s+(-?[\d.]+)\)',
            lambda m, _kw=_kw: f"({_kw} {_fmt_num(round(float(m.group(1)) * scale, 4))} "
                               f"{_fmt_num(round(float(m.group(2)) * scale, 4))})",
            block)
    block = re.sub(
        r'\(size\s+(-?[\d.]+)\s+(-?[\d.]+)\)',
        lambda m: f"(size {_fmt_num(round(float(m.group(1)) * scale, 4))} "
                  f"{_fmt_num(round(float(m.group(2)) * scale, 4))})",
        block)
    return block


def _fmt_num(v: float) -> str:
    """KiCad literal: drop the trailing .0 on integers so scale==1.0 is byte-stable."""
    r = round(float(v), 4)
    return str(int(r)) if r == int(r) else repr(r)


def _vendor_sym_scale(page_scale: float, native_pitch: float,
                      page_floor: float, pin_count: int) -> float:
    """Per-symbol geometry scale for a STORED (vendor/system) peripheral symbol.

    DD-29/30/31 (user review v23/v24, 「所有晶片的pin密度要跟大晶片一致」): the legacy
    rule was `_sym_scale = page_scale` — but page_scale (1.0~1.1) is a PAPER-fit
    ratio, not a pitch-align ratio. A 2.54 mm connector × 1.1 = 2.79 mm stays far
    denser than the page's main chip (7.62~11.43 mm rendered pitch). This lifts the
    scale so the symbol's rendered pin pitch reaches `page_floor`:

        scale = max(page_scale, page_floor / native_pitch)

    - `page_floor` (DD-29/30): the page's main-chip rendered pitch, or 7.62 mm on a
      chip-less peripheral page.
    - Only ≥4-pin IC/connectors are lifted (DD-29 scope). 2-pin R/C/L keep the plain
      page_scale (their density is not the「小晶片」complaint and lifting them would
      explode the cap farm). A symbol whose native_pitch is unknown (<=0) also keeps
      page_scale.
    - page_scale is a hard floor: the paper-fit ratio is never undercut.

    Returns page_scale unchanged when the symbol already clears the floor, so a
    page whose peripherals are already wide enough is a no-op (byte-stable).
    """
    if pin_count < 4 or native_pitch <= 0.0:
        return page_scale
    return max(page_scale, page_floor / native_pitch)


# DD-30 project-wide main-chip minimum rendered pitch, used as the floor on a
# chip-less peripheral page (06a/06b/06c) that has no u1_ variant of its own.
_PROJECT_MAIN_PITCH_FLOOR_MM = 7.62


def _adjacent_pitch(pins: dict) -> float:
    """Minimum adjacent same-edge pin pitch (mm) from a pin-endpoint map.

    Pins on one edge share an x (vertical edge) or y (horizontal edge); the
    density the user sees is the smallest gap between two neighbours on the same
    edge. Group by the shared coordinate, take the min consecutive delta on the
    other axis. Returns 0.0 when <2 pins share any edge (no meaningful pitch).
    """
    from collections import defaultdict
    by_x: dict = defaultdict(list)
    by_y: dict = defaultdict(list)
    for p in pins.values():
        px, py = round(p[0], 3), round(p[1], 3)
        by_x[px].append(py)
        by_y[py].append(px)
    best = float("inf")
    for group in (*by_x.values(), *by_y.values()):
        if len(group) < 2:
            continue
        s = sorted(group)
        for a, b in zip(s, s[1:]):
            d = b - a
            if d > 1e-6:
                best = min(best, d)
    return 0.0 if best == float("inf") else best


def _native_pitch_and_count(lib_id: str, symbol_dir,
                            cache: dict[str, tuple[float, int]]) -> tuple[float, int]:
    """UNSCALED native adjacent pin pitch + pin count of a stored symbol.

    Loaded once per lib_id (page_scale=1.0) and cached so a symbol reused across
    many instances is parsed a single time. Missing symbols return (0.0, 0) so
    the caller's _vendor_sym_scale falls back to page_scale (no lift).
    """
    if lib_id in cache:
        return cache[lib_id]
    try:
        _def, pins = load_symbol(lib_id, symbol_dir, page_scale=1.0)
    except (FileNotFoundError, KeyError):
        cache[lib_id] = (0.0, 0)
        return cache[lib_id]
    result = (_adjacent_pitch(pins), len(pins))
    cache[lib_id] = result
    return result


def _page_pitch_floor(components, symbol_dir) -> float:
    """The page's pitch floor (DD-29/30): the main chip's RENDERED pin pitch.

    The main chip is the u1_ variant, ALREADY emitted at page_scale, so its
    in-symbol adjacent pitch IS the rendered pitch (the number the user reads).
    A chip-less peripheral page (no u1_ variant) borrows the project-wide
    _PROJECT_MAIN_PITCH_FLOOR_MM (DD-30).
    """
    _cache: dict[str, tuple[float, int]] = {}
    for component in components:
        if component.lib_id.partition(":")[0].startswith("u1_"):
            pitch, _n = _native_pitch_and_count(component.lib_id, symbol_dir, _cache)
            if pitch > 0.0:
                return pitch
    return _PROJECT_MAIN_PITCH_FLOOR_MM


def load_symbol(lib_id: str, symbol_dir: str | Path | list = DEFAULT_SYMBOL_DIR,
                page_scale: float = 1.0) -> tuple[str, dict[str, tuple[float, float]]]:
    """Return (embedded symbol definition text, {pin_number: (x, y)}).

    `symbol_dir` may be a single directory or a list of directories (tried in
    order) — so stdlib symbols and project-local generated libraries
    (e.g. `openmv_generated.kicad_sym`) can be resolved together.

    page_scale (CCM sheet-coherence, v11 bug 2): >1.0 scales a STORED symbol's
    geometry so peripheral parts match the per-page main-symbol pin density. The
    per-page U1 variant is ALREADY emitted at scale (build_u1_variant), so the
    caller passes page_scale=1.0 for it to avoid double-scaling. page_scale==1.0
    is byte-identical to the legacy loader (every existing caller stays stable).

    Raises FileNotFoundError if the library is found in none of the dirs, and
    KeyError if the symbol is not present in the located library.
    """
    lib_path = resolve_symbol_library(lib_id, symbol_dir)
    name = lib_id.partition(":")[2]
    source = lib_path.read_text(encoding="utf-8", errors="ignore")
    block = _extract_symbol_block(source, name)
    if block is None:
        raise KeyError(f"Symbol {name!r} not found in {lib_path}")
    block = _flatten_extends(block, name, source)
    if page_scale != 1.0:
        block = _scale_symbol_geometry(block, page_scale)
    embedded = block.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
    return embedded, _pin_endpoints(block)


def resolve_symbol_library(lib_id: str, symbol_dir: str | Path | list = DEFAULT_SYMBOL_DIR) -> Path:
    """Which file on disk a lib_id resolves to, without reading it."""
    library, _, name = lib_id.partition(":")
    if not name:
        raise KeyError(f"lib_id must be 'Library:Symbol', got {lib_id!r}")
    dirs = [symbol_dir] if isinstance(symbol_dir, (str, Path)) else list(symbol_dir)
    lib_path = next((Path(d) / f"{library}.kicad_sym"
                     for d in dirs if (Path(d) / f"{library}.kicad_sym").exists()), None)
    if lib_path is None:
        raise FileNotFoundError(
            f"KiCad symbol library '{library}.kicad_sym' not found in: {[str(d) for d in dirs]}")
    return lib_path


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


def _pin_endpoints(block: str) -> dict[str, tuple[float, float, float]]:
    # DD-26/27 (user review v6/v7): capture the pin's KiCad rotation (3rd `at`
    # field) alongside (x, y). The rotation is the pin's TRUE outward direction
    # (0=+x/right of body, 90=+y, 180=-x/left of body, 270=-y) and is the ONLY
    # reliable edge signal: a narrow tall symbol (single-row Conn_01x36, 36 pins
    # stacked on ONE left edge) has far-from-origin endpoints where |ey|>>|ex|,
    # so the old abs(ex)>=abs(ey) axis test mis-classified them as top/bottom pins
    # and emitted rotated (90/270) labels — the "亂七八糟 vertical label 疊柱" defect.
    # (x, y, rotation); consumers index [0]/[1] as before so this stays compatible.
    endpoints: dict[str, tuple[float, float, float]] = {}
    for pin_match in PIN_RE.finditer(block):
        x, y = float(pin_match.group(1)), float(pin_match.group(2))
        rot = float(pin_match.group(3))
        number_match = NUMBER_RE.search(block, pin_match.end())
        if number_match is None:
            continue
        endpoints.setdefault(number_match.group(1), (x, y, rot))
    return endpoints


_RECT_RE = re.compile(
    r"\(rectangle\s*\(start\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)\s*\(end\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)"
)

# DD-14 (user review v18): passive symbols (inductor L, capacitor C) draw their
# body as (polyline)/(arc)/(circle) primitives and NO (rectangle). `_body_rect`
# returns None for them, so the refdes/value / net-label obstacle-avoidance had
# an EMPTY body-graphics set and dropped text straight onto the arc/plates
# (L_U5 refdes over the inductor arc; 100nF refdes+value over the cap plates).
# `_graphics_bbox` unions EVERY drawn primitive's coordinate so the true body
# extent is known regardless of which primitive the symbol uses.
_PT_RE = re.compile(r"\(xy\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)")
_ARC_PT_RE = re.compile(
    r"\((?:start|mid|end|center)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)"
)


def _graphics_bbox(block: str) -> tuple[float, float, float, float] | None:
    """Union bbox of ALL drawn graphic primitives in a symbol block, SYMBOL-LOCAL.

    Covers (rectangle), (polyline ... (xy ..)), (arc (start/mid/end ..)), and
    (circle (center ..)). Returns (x0, y0, x1, y1) with x0<=x1, y0<=y1 (KiCad
    y grows upward; caller flips to sheet coords). None when the block draws no
    graphic at all (caller falls back to the pin-tip extent).

    Unlike `_body_rect` (rectangles only), this sees the polyline plates / arc
    bumps that passives use, so the body-graphics obstacle set is never empty
    for a drawn part (DD-14).
    """
    xs: list[float] = []
    ys: list[float] = []
    r = _body_rect(block)
    if r is not None:
        xs.extend((r[0], r[2]))
        ys.extend((r[1], r[3]))
    for m in _PT_RE.finditer(block):
        xs.append(float(m.group(1)))
        ys.append(float(m.group(2)))
    for m in _ARC_PT_RE.finditer(block):
        xs.append(float(m.group(1)))
        ys.append(float(m.group(2)))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _guard_c_body_box(x0: float, x1: float, y0: float, y1: float,
                      inset: float | None = None) -> tuple[float, float, float, float]:
    """Guard C's keep-out box for one placed component: the body extent shrunk by
    `inset` so a power port legitimately hugging the body edge is not reported.

    BR_20260804b -- the degrade is CONDITIONAL, not `min(inset, span*k)`.

    A fixed inset INVERTS the interval on a narrow body (bx0 > bx1), making
    `bx0 < ex < bx1` unsatisfiable: the guard then reports nothing for that
    component, which is byte-identical to "no intrusion found".

    All figures below share ONE convention -- blind <=> the box width is <= 0,
    i.e. exactly when the guard's own strict predicate cannot be satisfied. They
    come from one sweep of /usr/share/kicad/symbols via `load_symbol` (so
    `(extends ...)` is flattened -- what the engine actually sees), 18217 symbols
    with a rectangle out of 22583 scanned; the 150 load failures are name-lookup
    misses and are reported, never swallowed.

        INVERTED under the old fixed inset   513
        fixed by this degrade                511
        still blind after it                   2      (513 - 511 = 2)
        non-blind bodies perturbed             0

    `Device:R` -- the most common symbol there is -- was among the 513.

    Why CONDITIONAL and not `min(inset, span*k)`: any min() form perturbs every
    body in the band `span < inset/k`, including ones whose unclamped box was
    perfectly valid. Same sweep, `min(inset, span/4)`: 512 fixed but **1617
    never-blind bodies perturbed** (e.g. `Regulator_Linear:AMS1117-3.3`, y-span
    6.985mm). Tightening the guard on already-verified pages is how a fix
    manufactures new raises. The conditional form is a no-op by construction
    whenever `span - 2*inset > 0`, so that count is 0 rather than merely small.

    Note the `>` (not `>=`): at exactly `span == 2*inset` (17 symbols, e.g.
    `Connector_Audio:SpeakON_NL2`) the unclamped box has ZERO width, so the strict
    comparison is unsatisfiable there too -- they are blind and must degrade.

    KNOWN RESIDUAL -- 2 symbols stay blind, for two different reasons:
      * `74xGxx:74LVC1GU04DRL`  x-span 0.0 -- the rectangle itself is degenerate;
        no inset rule can help.
      * `Mechanical:Housing_Pad` x-span 3.8100000000000005 -- a FLOATING-POINT
        boundary. It is `> 2*inset` by 5e-16, so the condition takes the "wide
        enough" branch and shrinks by the full inset, leaving a box 5e-16 wide:
        still unsatisfiable. Same 1.27mm-boundary family as BR_20260804c.
    Do not "fix" this by loosening the comparison without measuring -- a tolerance
    wide enough to catch it also moves real bodies.

    Effect on emitted verdicts is bounded WITHOUT re-running compose, by squeeze:
    for all 18217 symbols the conditional box is a SUBSET of the span/4 box
    (0 violations; controls: 1756 are strictly narrower so the claim is not
    vacuous, and the reverse subset does NOT hold for all). A narrower box can
    only contain the same points or fewer, since the predicate is `bx0 < ex < bx1`.
    With baseline and span/4 both measured at 1 intrusion on
    `experiments/e2e-led-driver/C03-EE/e2e-led-driver-npn.spec.json`, the
    conditional form is squeezed to 1 as well -- delta 0. (An earlier note here
    justified this by claiming the two forms agree on `Device:R`; they do not --
    they differ on its y axis, 5.08mm > 2*inset. Monotonicity is the reason, not
    similarity.)

    Whether `_PWR_STUB_STEP_MM/4` is the right keep-out width is a separate
    product question -- the same question before and after this. What this fixes
    is that on narrow bodies the chosen width was not being applied at all.
    """
    if inset is None:
        inset = _PWR_STUB_STEP_MM / 4.0
    ix = inset if (x1 - x0) > 2 * inset else (x1 - x0) / 4.0
    iy = inset if (y1 - y0) > 2 * inset else (y1 - y0) / 4.0
    return (x0 + ix, x1 - ix, y0 + iy, y1 - iy)


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


def _body_wh_from_rect(
    rect: tuple[float, float, float, float] | None,
    pin_map: dict | None,
) -> tuple[float, float] | None:
    """M7-3b-i: symbol body (w, h) for the L1 BoxRect bbox (slot observation).

    Prefers the symbol's true `(rectangle ...)` extent (rect = x0,y0,x1,y1); falls
    back to the pin-endpoint extent when the symbol draws no rectangle; None when
    neither is available (l1_geometry then uses its conservative 2*BBOX_MARGIN_MM
    default). Read-only helper — changes no geometry.
    """
    if rect is not None:
        x0, y0, x1, y1 = rect
        return (abs(x1 - x0), abs(y1 - y0))
    if pin_map:
        xs = [p[0] for p in pin_map.values()]
        ys = [p[1] for p in pin_map.values()]
        if xs and ys:
            return (max(xs) - min(xs), max(ys) - min(ys))
    return None


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
                      comp_x: float, comp_y: float,
                      page_scale: float = 1.0) -> tuple[float, float, float, float]:
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
    # M3-1 (DD-4): the in-symbol pin-name text renders at _PIN_NAME_CH_MM*page_scale
    # (the symbol was drawn at a large in-body pitch); at page_scale==1.0 this equals
    # the legacy fixed box (byte-stable). Modeling the box at the TRUE rendered size
    # is what lets the intra-symbol overlap gate actually SEE the smear (a 1.27 box
    # measuring a 5.715 render was structurally blind).
    w = len(name) * (_PIN_NAME_CW_MM * page_scale)
    h = _PIN_NAME_CH_MM * page_scale + _LABEL_VMARGIN_MM
    off = _PIN_NAME_OFFSET_MM * page_scale
    if ex < -0.01:                         # left-side pin: body is +x, name runs +x
        x0, x1 = px + off, px + off + w
    elif ex > 0.01:                        # right-side pin: body is -x, name runs -x
        x0, x1 = px - off - w, px - off
    else:
        x0, x1 = px - w / 2, px + w / 2
    return (x0, x1, py - h / 2, py + h / 2)


def _prop_text_box(text: str, x: float, y: float,
                   page_scale: float = 1.0) -> tuple[float, float, float, float]:
    """Rendered box of a symbol Reference/Value property text (justify left by
    KiCad default => runs +x from its anchor). Same char/height model as pin
    names so the QA and the emitter agree. M3-1 (DD-4): ×page_scale so the box
    reflects the true rendered text size (byte-stable at page_scale==1.0)."""
    w = len(text) * (_PIN_NAME_CW_MM * page_scale)
    h = _PIN_NAME_CH_MM * page_scale + _LABEL_VMARGIN_MM
    return (x, x + w, y - h / 2, y + h / 2)


def _place_symbol_props(component: "EmitComponent",
                        pin_boxes: list[tuple[float, float, float, float]],
                        occupied: list[tuple[float, float, float, float]],
                        page_scale: float = 1.0,
                        body_box: tuple[float, float, float, float] | None = None,
                        frame_box: tuple[float, float, float, float] | None = None
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
    # DD-20: the legacy ladder was a FIXED-mm ladder (max ±7.62). For a large part
    # whose drawn body half-extent scales with pin count (a HEXASPI PSRAM body is
    # ~40mm half-width, a buck ~28mm), EVERY fixed tier still lands the refdes/value
    # box INSIDE the body, overlapping the in-body pin-name text AND the body rect
    # (the dominant body↔pin_extent intra hits, 85/72/86/69 on 01/02/03a/03b — NOT
    # vertical-edge name stacking). The clearing distance must be RELATIVE to this
    # component's own body: derive its half-extent from the pin-name boxes (each
    # pin box is placed relative to the body) and escalate the outer tiers past it,
    # so refdes/value clears the body by construction at ANY size/scale.
    # Bug2 (user review v4): an ORPHAN two-pin part (decoupling cap C1..C6) has NO
    # in-body pin-NAME text, so pin_boxes is empty here -> half_w/half_h collapse to
    # 0 and the ladder's FIRST tier (legacy +2.54/-1.27) is judged "clear" and drops
    # the refdes/value straight onto the capacitor's DRAWN plates. The body graphic
    # is the real obstacle, not the (absent) pin-name text. Seed the collision域 with
    # the symbol's body-rect box (sheet coords, threaded by the caller from
    # `_body_rect`) AND derive the clearing half-extents from it, so a nameless part
    # clears its own body by construction. body_box is (x0,x1,y0,y1) sheet-abs or None.
    # half-extents of THIS symbol's OWN in-body footprint, from its centre. The
    # source MUST be this component's own boxes only: `pin_boxes` is the SHARED
    # page-wide pin-name occupancy (every component's boxes, collected once by the
    # caller for the clash test below) — taking its min/max here spanned the WHOLE
    # page (a small buck near U1's opposite edge inherited half_h≈U1's 467 mm),
    # inflating _oy so the refdes/value was flung ~470 mm off-body → ink overran
    # the paper. This component's own extent is its DRAWN body-rect (`body_box`,
    # threaded per-component by the caller) UNION its own pin-name boxes. A pin-name
    # box is "own" iff it lies within the body-rect's x-or-y band (pin names sit on
    # the body edges); when no body_box exists (rare), fall back to nothing so the
    # clearing distance collapses to `_clear` (one row past centre) rather than the
    # whole page. This is the closed-form "own footprint" the docstring promised.
    _own: list[tuple[float, float, float, float]] = []
    if body_box is not None:
        _own.append(body_box)
        _bbx0, _bbx1, _bby0, _bby1 = body_box
        for pb in (pin_boxes or ()):
            # a pin-name box belongs to THIS symbol when it abuts this body-rect:
            # its box overlaps the body's x-span AND y-span (a pin name is drawn
            # just inside/along an edge of its own body, never a page away).
            if pb[1] >= _bbx0 and pb[0] <= _bbx1 and pb[3] >= _bby0 and pb[2] <= _bby1:
                _own.append(pb)
    if _own:
        _bx0 = min(pb[0] for pb in _own); _bx1 = max(pb[1] for pb in _own)
        _by0 = min(pb[2] for pb in _own); _by1 = max(pb[3] for pb in _own)
        half_w = max(cx - _bx0, _bx1 - cx)
        half_h = max(cy - _by0, _by1 - cy)
    else:
        half_w = half_h = 0.0
    _prop_h = _PIN_NAME_CH_MM * page_scale + _LABEL_VMARGIN_MM
    _clear = _PIN_NAME_OFFSET_MM * page_scale + _prop_h  # one row + offset past edge
    _ox = half_w + _clear   # x distance that clears the body's right/left edge
    _oy = half_h + _clear   # y distance that clears the body's bottom/top edge
    # candidate anchor ladder: (ref_dx, ref_dy, val_dx, val_dy). Reference above,
    # Value below by default; escalate outward until both clear. The first tier is
    # the legacy fixed offset (byte-stable when it already clears — small parts);
    # the escalation tiers are BODY-RELATIVE so large bodies clear too (DD-20).
    # DD-25 (user review v22): refdes/value must seat at the box GEOMETRIC CENTER
    # band when it is clear (名字印在方塊正中央，不跟 pinouts 攜位置). The legacy
    # first tier (cy-1.27) is exactly the TOP pin-name row, which is what the user
    # saw "searching for space with the pinouts". Try centering FIRST: ref just
    # above the center line, value just below, both on the box x-center. On a
    # symbol whose pin names hug the edges (short names, clear center band) this
    # wins; on a dense-center BGA the clash test rejects it and the body-relative
    # tiers below take over (fallback, never force-center onto pin text).
    _row = _prop_h  # one text-row height (ref above center, value below)
    ladder = [
        (0.0, -_row, 0.0, _row),        # DD-25: geometric center band (tried first)
        (2.54, -1.27, 2.54, 1.27),      # legacy (byte-stable when center is occupied)
        (2.54, -_oy, 2.54, _oy),        # above / below, past the body height
        (_ox, -_prop_h, _ox, _prop_h),  # right of body, split by one row
        (-_ox, -_prop_h, -_ox, _prop_h),# left of body, split by one row
        (_ox, -_oy, _ox, _oy),          # far right, past body corner
        (-_ox, -_oy, -_ox, _oy),        # far left, past body corner
    ]
    # Bug2: the body graphic is an obstacle for EVERY tier's clash test, so a tier
    # that clears the (empty) pin_boxes but sits on the plates is correctly rejected.
    # DD-25 exception: the geometric-CENTER tier (index 0) INTENTIONALLY sits inside
    # the body — that is where the user wants the refdes. It must only clear the
    # pin-name text + prior prop boxes, NOT be rejected by the body rect it is meant
    # to live inside. Every other tier still treats body_box as an obstacle so it
    # never drops text onto a passive's plates (the Bug2 orphan-cap case).
    # DD-26/v24 Fix B (DD-25 regression): the earlier center-tier exemption dropped
    # the WHOLE body_box, which on a 2-pin passive (Device:C) IS its plates —
    # centering then sat the refdes/value straight onto the plate graphics again
    # (the v23 cap regression). Narrow it: the center tier exempts only the OUTER
    # FRAME (`frame_box`, the body rectangle the refdes legitimately lives inside),
    # but still treats INTERIOR graphics (plates/arcs = body_box when it is the
    # drawn-graphics extent, distinct from the frame) as an obstacle. When no
    # separate frame_box is threaded (frame_box is None) fall back to the legacy
    # full-body exemption so large-IC centering (03a U1/U2, whose graphics extent
    # IS the frame and whose center band is clear) is unchanged.
    _obstacles = ([body_box] if body_box is not None else [])
    if frame_box is not None and body_box is not None and frame_box != body_box:
        # interior graphics = the drawn-graphics box; the center tier must clear it.
        _center_obstacles = [body_box]
    else:
        _center_obstacles = []
    for _tier_i, (rdx, rdy, vdx, vdy) in enumerate(ladder):
        _tier_obstacles = _center_obstacles if _tier_i == 0 else _obstacles
        rb = _prop_text_box(ref, cx + rdx, cy + rdy, page_scale)
        vb = _prop_text_box(val, cx + vdx, cy + vdy, page_scale) if val else None
        clash = any(_bbox_overlap(rb, pb) for pb in pin_boxes) or \
                any(_bbox_overlap(rb, pb) for pb in occupied) or \
                any(_bbox_overlap(rb, pb) for pb in _tier_obstacles)
        if vb is not None:
            clash = clash or _bbox_overlap(rb, vb) or \
                    any(_bbox_overlap(vb, pb) for pb in pin_boxes) or \
                    any(_bbox_overlap(vb, pb) for pb in occupied) or \
                    any(_bbox_overlap(vb, pb) for pb in _tier_obstacles)
        if not clash:
            occupied.append(rb)
            if vb is not None:
                occupied.append(vb)
            return (cx + rdx, cy + rdy, cx + vdx, cy + vdy, rb, vb)
    # exhausted: use the last (far) tier so at least they leave the body
    rdx, rdy, vdx, vdy = ladder[-1]
    rb = _prop_text_box(ref, cx + rdx, cy + rdy, page_scale)
    vb = _prop_text_box(val, cx + vdx, cy + vdy, page_scale) if val else None
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
    ledger: "OccupancyLedger | None" = None,
    power_port_gate: str = "error",
    clusters: list | None = None,
    l6_avoidance: bool = False,
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
    # DD-14: lib_id -> SYMBOL-LOCAL union bbox of ALL drawn graphics (arc/plate/
    # polyline/rect). Superset of body_rects; never empty for a drawn passive.
    graphics_rects: dict[str, tuple[float, float, float, float] | None] = {}
    warnings: list[str] = []
    # DD-29/30/31: the per-page pitch floor is the main chip's (u1_ variant) rendered
    # pin pitch; a chip-less peripheral page borrows the project-wide 7.62 mm floor
    # (DD-30). Peek every stored symbol's native pitch UNSCALED once so the floor is
    # known before we choose each symbol's scale (a two-pass over lib_ids).
    _page_floor = _page_pitch_floor(components, symbol_dir)
    _native_cache: dict[str, tuple[float, int]] = {}
    for component in components:
        if component.lib_id in embedded_defs:
            continue
        _is_u1 = component.lib_id.partition(":")[0].startswith("u1_")
        try:
            # v11 bug 2 + DD-31: scale stored peripheral symbols so their RENDERED
            # pin pitch reaches the page floor (not just page_scale, a paper-fit
            # ratio). The U1 variant (lib prefix `u1_`) is ALREADY emitted at
            # page_scale by build_u1_variant, so it loads unscaled (no double-scale).
            if _is_u1:
                _sym_scale = 1.0
            else:
                _npitch, _ncount = _native_pitch_and_count(
                    component.lib_id, symbol_dir, _native_cache)
                _sym_scale = _vendor_sym_scale(
                    page_scale, _npitch, _page_floor, _ncount)
            definition, pins = load_symbol(component.lib_id, symbol_dir, page_scale=_sym_scale)
        except (FileNotFoundError, KeyError) as error:
            warnings.append(f"{component.ref}: {error}")
            continue
        embedded_defs[component.lib_id] = definition
        pin_maps[component.lib_id] = pins
        body_rects[component.lib_id] = _body_rect(definition)
        # DD-14: full drawn-graphics extent (arc/plate/polyline/rect), used as a
        # sheet-abs obstacle so refdes/value AND net labels clear the body even
        # when the part draws no (rectangle) (passives — L_U5 arc, cap plates).
        graphics_rects[component.lib_id] = _graphics_bbox(definition)

    # Snap every component onto KiCad's 1.27 mm connection grid. Library pin local
    # offsets are grid-multiples, so once the symbol origin is on-grid the absolute
    # pin endpoint is too — which is what lets a drawn wire end actually merge with
    # the pin (off-grid endpoints read as `pin_not_connected` in ERC). Harmless to
    # label mode (global labels don't require grid alignment).
    for component in components:
        component.x = _snap_grid(component.x)
        component.y = _snap_grid(component.y)

    placements = {component.ref: component for component in components}

    # M6-8d (user 03a ruling): cross-IC bus policy. When >=2 signals cross the SAME
    # pair of ICs, force every cross-IC signal between them onto a global label
    # (all-label for that pair) — killing the 12+ unordered wire crossings a drawn
    # cross-IC bus produced. Drawn wires survive ONLY for short IC<->satellite-passive
    # / intra-cluster links. An IC = a >2-pin part (passives are <=2-pin); a signal
    # "crosses" an IC pair when its nodes touch >=2 ICs.
    #
    # M7-3.3 (DD-9 方案 B): this decision's SINGLE SOURCE OF TRUTH is now the L2.5
    # capacity layer's decide_route_policy (capacity_plan.py); the once-duplicated
    # per-pair inference here is deleted and delegated. Lazy import breaks the cycle
    # (capacity_plan imports LANE_PITCH_MM from this module).
    from .capacity_plan import NetConn as _NetConn, decide_route_policy as _decide_policy
    _pin_ct = {ref: len(pin_maps.get(c.lib_id, {})) for ref, c in placements.items()}
    _policy = _decide_policy(
        [_NetConn(name=_net.name, nodes=tuple(_net.nodes)) for _net in nets],
        _pin_ct,
    )
    _crossic_label = {name for name, style in _policy.items() if style == "label"}
    if _crossic_label:
        label_nets = (set(label_nets) if label_nets else set()) | _crossic_label

    # M7-3b-i (DD-11): build the L2.5 SlotTable OBSERVATION here — pin_maps (→pin
    # count) and placements are ready, and the caller has passed `clusters` (the one
    # datum only composer holds). This is the missing wiring that takes the once-
    # island modules (l1_geometry→gap_topology→build_capacity_plan) into the render
    # main path. It changes NO geometry: `_slot_reserved` is only READ by the wire
    # observation below to record whether each accepted wire lands on its reserved
    # lane. Front-stage fail-fasts are caught in OBSERVATION mode (explicit skips,
    # never silent) so the render still completes and the作用面 is measured for
    # M7-3b-ii. clusters is None on every legacy caller → byte-identical.
    _slot_reserved: dict = {}
    _slot_gap_axis: dict = {}
    _slot_route_gap: dict = {}
    slot_observe_wires: list[dict] = []
    slot_observe_skips: list[dict] = []
    if clusters:
        from .slot_observe import build_slot_observation
        _slot_bboxes = {
            ref: (
                None if c.lib_id not in pin_maps
                else _body_wh_from_rect(body_rects.get(c.lib_id), pin_maps.get(c.lib_id))
            )
            for ref, c in placements.items()
        }
        _slot_obs = build_slot_observation(
            clusters, components, nets, _pin_ct, _slot_bboxes,
        )
        slot_observe_skips = list(_slot_obs.skips)
        _slot_gap_axis = dict(_slot_obs.gap_axis)
        if _slot_obs.slot_table is not None and _slot_obs.slot_table.reserved:
            _slot_reserved = dict(_slot_obs.slot_table.reserved)
            _slot_route_gap = _slot_obs.route_gap

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
        # DD-26/27: edge is decided by the pin's KiCad ROTATION (its true outward
        # direction), NOT by comparing endpoint |x| vs |y|. The old axis test broke
        # on a narrow-tall symbol (single-row connector, all pins on one edge): a
        # far-from-origin pin has |ey|>>|ex| and was mis-read as a top/bottom pin,
        # firing a rotated 90/270 label. KiCad pin `at ANGLE` points from the body
        # toward the endpoint: 0=+x (pin on LEFT edge, stub runs +x? no — the pin
        # graphic extends +x FROM its `at`, body is further +x, so outward is -x).
        # Concretely KiCad convention: angle 0 => pin sits on the symbol's LEFT side
        # and its wire attaches to the LEFT (outward -x); 180 => RIGHT side (outward
        # +x); 90 => BOTTOM side (outward, sheet +y down); 270 => TOP side (outward
        # sheet -y up). endpoint[2] is that rotation (see _pin_endpoints).
        rot = int(round(endpoint[2])) % 360 if len(endpoint) > 2 else None
        if rot is not None:
            if rot == 0:
                return (-1.0, 0.0)   # left edge, stub runs -x
            if rot == 180:
                return (1.0, 0.0)    # right edge, stub runs +x
            if rot == 90:
                return (0.0, 1.0)    # bottom edge, stub runs +y (screen down)
            if rot == 270:
                return (0.0, -1.0)   # top edge, stub runs -y (screen up)
        # Fallback (rotation absent — legacy 2-tuple pin map): axis test as before.
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
    # M4-3a-1 (occupancy-ledger, DD-10a): owner保真 — carry the SOURCE component ref
    # alongside each pin-name box so the ledger can tell intra-symbol text (which
    # legitimately coexists) from cross-entity collisions. Without this the reserve
    # owner was a loop index (`reserved[i]`) and owner-aware exclusion is impossible.
    pin_name_owners: list[str] = []
    for component in components:
        extents = pin_name_defs.get(component.lib_id)
        if not extents:
            continue
        for nm, ex, ey, rot in extents:
            pin_name_boxes.append(
                _pin_name_box_abs(nm, ex, ey, rot, component.x, component.y, page_scale)
            )
            pin_name_owners.append(component.ref)

    # Now place each symbol, choosing Reference/Value anchors that clear both the
    # pin-name boxes and every prior prop box (the `2 X SW1` / `GND X 100nF` /
    # `19 X Stamp Edge A/B` self-overlaps). The resulting prop boxes join the
    # pin-name occupancy so net labels also steer clear of the refdes/value text.
    prop_boxes: list[tuple[float, float, float, float]] = []
    prop_owners: list[str] = []  # M4-3a-1: parallel owner ref per prop box
    for component in components:
        if component.lib_id not in embedded_defs:
            continue
        # Bug2: thread this component's DRAWN body-rect (symbol-local, KiCad y-up)
        # as a sheet-abs obstacle box so a nameless orphan part (decoupling cap)
        # never drops its refdes/value onto its own plates. Local->sheet: x adds,
        # y flips (sheet_y = comp.y - local_y). None when the symbol draws no rect.
        # DD-14: prefer the full drawn-graphics extent (covers polyline plates /
        # arc bumps on passives that draw no rectangle) over the rect-only box.
        _br = graphics_rects.get(component.lib_id) or body_rects.get(component.lib_id)
        _body_box = None
        if _br is not None:
            _lx0, _ly0, _lx1, _ly1 = _br
            _sy_a = component.y - _ly0
            _sy_b = component.y - _ly1
            _body_box = (component.x + _lx0, component.x + _lx1,
                         min(_sy_a, _sy_b), max(_sy_a, _sy_b))
        # DD-26/v24 Fix B: also thread the OUTER FRAME (the plain body rectangle,
        # distinct from the drawn-graphics extent). The center tier exempts the
        # frame (refdes lives inside it) but still clears interior graphics
        # (plates/arcs). When the symbol draws only a rectangle (frame == graphics)
        # frame_box == _body_box and the exemption stays the legacy full-body one.
        _fr = body_rects.get(component.lib_id)
        _frame_box = None
        if _fr is not None:
            _flx0, _fly0, _flx1, _fly1 = _fr
            _fsy_a = component.y - _fly0
            _fsy_b = component.y - _fly1
            _frame_box = (component.x + _flx0, component.x + _flx1,
                          min(_fsy_a, _fsy_b), max(_fsy_a, _fsy_b))
        rx, ry, vx, vy, rb, vb = _place_symbol_props(component, pin_name_boxes, prop_boxes, page_scale, _body_box, _frame_box)
        prop_owners.append(component.ref)          # rb (Reference box) always appended
        if vb is not None:
            prop_owners.append(component.ref)      # vb (Value box) appended when present
        symbol_blocks.append(
            _symbol_instance_block(component, project_name, root_uuid, rx, ry, vx, vy)
        )
    # Reserved occupancy for the label/power placers: pin names + prop texts.
    reserved_boxes: list[tuple[float, float, float, float]] = pin_name_boxes + prop_boxes
    # M4-3a-1: owners parallel to reserved_boxes (pin_name_owners then prop_owners),
    # index-aligned so the ledger reserve below can stamp each box with its real ref.
    reserved_owners: list[str] = pin_name_owners + prop_owners

    # M2-1 (occupancy-ledger): the single 2D occupancy SSOT for this emit. The
    # label/stub/power geometry solvers below register every rendered box into
    # this ledger (reserve-then-draw), so placement and emit share ONE space
    # account instead of the old emit-local `placed` list that placement could
    # not see. Batch-reserve the already-placed component bodies + in-body pin-
    # name text up front; a body/pin-name conflict here means PLACEMENT already
    # overlaps (composer's job, M3) — record a warning but do NOT block (this
    # stage only mirrors existing behaviour; the label placers still run their
    # byte-stable collision math and merely ALSO register into the ledger).
    #
    # M3-2 (occupancy-ledger): accept an EXTERNAL ledger from the composer so
    # placement and emit share ONE instance (DD-1 「同一實例」貫穿). When the
    # caller passes ledger=None (every non-composer caller), self-build the
    # emit-local ledger exactly as before — byte-identical to the M2 path.
    if ledger is None:
        ledger = OccupancyLedger(paper=paper)

    def _ledger_reserve_box(box: tuple[float, float, float, float], owner: str, kind: str) -> None:
        """Register a rendered (x0,x1,y0,y1) box into the shared ledger.

        _label_bbox / _pin_name_box_abs return (x0, x1, y0, y1); LedgerRect wants
        (x0, y0, x1, y1). Degenerate boxes (zero span) are skipped — a real
        collision is what the ledger tracks, and a zero-area rect is not one.
        """
        bx0, bx1, by0, by1 = box
        if not (bx1 > bx0 and by1 > by0):
            return
        # M7-1.3 (DD-6) 分段落帳：body → L1；pin_extent 等非分層 kind 不標（source_layer=None）。
        _src = "L1" if kind == "body" else None
        ledger.try_reserve(LedgerRect(bx0, by0, bx1, by1, owner, kind, source_layer=_src))

    # M4-3a-1 (DD-10a): register each in-body text box with its REAL source ref as
    # owner and kind="pin_extent" (in-body pin-name / refdes / value text, which
    # legitimately coexists inside its own symbol). The composer already reserved
    # the element BODY outer frame as kind="body" (owner=ref) up front, so these
    # are the intra-symbol text, NOT a second body. Owner-aware exclusion (M4-3a-2)
    # then treats same-owner body/pin_extent as non-conflicting and only flags
    # cross-owner structural overlap.
    for _bi, _bbox in enumerate(reserved_boxes):
        _bx_owner = reserved_owners[_bi] if _bi < len(reserved_owners) else f"reserved[{_bi}]"
        _ledger_reserve_box(_bbox, _bx_owner, "pin_extent")

    _local_label_boxes: list[tuple[float, float, float, float]] = list(reserved_boxes)

    def _place_local_label(name: str, x: float, y: float, wp: list[tuple[float, float]]):
        """Emit a local label at (x,y), nudged along the route so its RENDERED text
        box clears every earlier label AND every in-body pin-name (M6-2 / DD-12).

        The old version only checked a private `_local_label_boxes` list, so a
        local label could still land on a pin-name box or a global label owned by
        another symbol (the cross pin/label smear). We now test each candidate
        coord against the SHARED ledger (label + pin_extent kinds, cross-owner) so
        the label sees EVERY placed text box. When every candidate collides we
        DOWN-GRADE (place at the route's far end, recorded) rather than the old
        「last resort 原位硬放」 which stacked text (使用者鐵律：label 永不疊放).
        The accepted box is reserved into the ledger so later labels avoid it too.
        """
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

        def _clear(box: tuple[float, float, float, float]) -> bool:
            # private list (byte-stable legacy guard) AND the shared ledger
            # (label + pin_extent, cross-owner). A label box is (x0,x1,y0,y1);
            # the ledger overlap test wants a rect, so probe via _bbox_overlap on
            # the ledger's label/pin_extent rects.
            if any(_bbox_overlap(box, pb) for pb in _local_label_boxes):
                return False
            bx0, bx1, by0, by1 = box
            for r in ledger.rects:
                # M6-8 (缺陷B): a local/net label must also clear power-port boxes,
                # not only label/pin_extent — the power-port Value box (kind="power",
                # the "GND"/rail glyph text) is reserved into the SAME ledger, and a
                # label landing on it is the HSE_OUT⨯GND overlap the user flagged.
                if r.kind not in ("label", "pin_extent", "power"):
                    continue
                if not (bx1 <= r.x0 or r.x1 <= bx0 or by1 <= r.y0 or r.y1 <= by0):
                    return False
            return True

        def _commit(cx: float, cy: float, box: tuple[float, float, float, float]) -> None:
            _local_label_boxes.append(box)
            bx0, bx1, by0, by1 = box
            if bx1 > bx0 and by1 > by0:
                ledger.try_reserve(LedgerRect(bx0, by0, bx1, by1, name, "label"))
            label_blocks.append(_local_label_block(name, cx, cy))

        for cx, cy in candidates:
            box = _label_bbox(name, cx, cy, False)
            if _clear(box):
                _commit(cx, cy, box)
                return
        # DOWN-GRADE (never stack): place at the route's FAR endpoint (the wire
        # terminus, furthest from the crowded pin cluster) and record. This keeps
        # the net named and ERC-valid while refusing to smear text on the pin
        # cluster. Recorded via label_local_downgrades for machine observability.
        fx, fy = (wp[-1] if wp else (x, y))
        label_local_downgrades.append({"net": name, "at": [fx, fy]})
        _commit(fx, fy, _label_bbox(name, fx, fy, False))

    # DD-11 anti-fusion registry: net_name -> its list of registered wire segments
    # ((x1,y1),(x2,y2)). A new net's segments are checked against EVERY OTHER
    # net's registered segments; on a cross-net collinear overlap / endpoint-on-
    # wire the whole net's geometry is deterministically jogged (net-hash offset),
    # retried ≤ 3 times, else the net is down-graded to label fallback (visible).
    fusion_registry: dict[str, list[tuple]] = {}
    fusion_label_fallbacks: list[dict] = []
    fusion_jogged_nets: list[str] = []
    label_local_downgrades: list[dict] = []
    # BR_20260708 machine check: every DRAWN wire segment paired with the set of
    # host refs that segment's net legitimately touches (its own pin bodies). The
    # post-emit assertion tests each segment against every body box EXCEPT its own
    # hosts; a residual interior crossing is the "wire through symbol" defect.
    #   routed_segments item = ((a, b), frozenset(host_refs))
    routed_segments: list[tuple[tuple, frozenset]] = []

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

    # BR_20260708 wire keep-out: absolute SHEET body AABB per component ref, from
    # the symbol's own (rectangle ...) (the TRUE body extent — same source guard C
    # uses), inflated by WIRE_KEEPOUT_MM so a drawn wire routes AROUND every symbol
    # body, not THROUGH it. Local->sheet: x adds, y flips (sheet_y = comp.y - local_y).
    # A component whose symbol draws no rectangle falls back to its pin-tip extent.
    # keyed by ref (drawn-wire routers exclude the wire's OWN host refs so the pin
    # approach leg is allowed to touch its own body).
    wire_obstacle_boxes: dict[str, tuple[float, float, float, float]] = {}
    for component in components:
        rect = body_rects.get(component.lib_id)
        if rect is not None:
            rx0, ry0, rx1, ry1 = rect
            xs = [component.x + rx0, component.x + rx1]
            ys = [component.y - ry0, component.y - ry1]
        else:
            pmap = pin_maps.get(component.lib_id)
            if not pmap:
                continue
            xs = [component.x + p[0] for p in pmap.values()]
            ys = [component.y - p[1] for p in pmap.values()]
        if not xs:
            continue
        m = WIRE_KEEPOUT_MM
        wire_obstacle_boxes[component.ref] = (
            min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m)

    def _obstacles_excluding(host_refs) -> list[tuple[float, float, float, float]]:
        """All keep-out body boxes EXCEPT the wire's own host component(s)."""
        skip = set(host_refs)
        return [box for ref, box in wire_obstacle_boxes.items() if ref not in skip]

    # M6-1 (DD-12, 使用者鐵律「routing 不得碰到任何其他元素」): a drawn route is
    # ACCEPTED only if its polyline clears the shared ledger's FULL occupancy
    # (body / pin_extent / label / wire / power), not just the body-only keep-out
    # boxes. The body keep-out (wire_obstacle_boxes) stays as the router's INTERNAL
    # detour hint (it shapes the candidate polyline), but the FINAL accept/reject
    # gate is this ledger check — so a route that dodges bodies yet still crosses a
    # pin-name or an already-drawn wire is REJECTED and the net down-grades to a
    # global label (fail-safe, never fail-ugly). Each accepted wire is then reserved
    # into the ledger (kind="wire") so LATER nets route around it too.
    # M6-1: the ledger accept-gate guards against wire↔label and wire↔wire
    # collisions ONLY (kinds={"label","wire"}); body / pin_extent avoidance stays
    # the job of the router's own body keep-out (wire_obstacle_boxes, the verified
    # golden-baseline path). Limiting the kinds prevents double-guarding a legal
    # detour that already clears the inflated body box from being false-rejected
    # by a pin-name box that pokes a hair past the body edge.
    _ROUTE_GUARD_KINDS = frozenset({"label", "wire"})

    def _route_clears_ledger(waypoints, host_refs) -> bool:
        clear, _hit = ledger.path_clear(
            waypoints, host_owners=frozenset(host_refs), kinds=_ROUTE_GUARD_KINDS)
        return clear

    def _observe_wire_slot(waypoints, net_name) -> None:
        """M7-3b-i (DD-11): OBSERVE whether this accepted wire lands on its reserved
        lane. Read-only — records to slot_observe_wires, changes NO geometry. No-op
        unless the caller passed `clusters` (else _slot_reserved is empty)."""
        if not _slot_reserved:
            return
        from .slot_observe import observe_wire_on_lane
        gid = _slot_route_gap.get(net_name)
        axis = _slot_gap_axis.get(gid, "x") if gid else "x"
        rec = observe_wire_on_lane(net_name, waypoints, _slot_reserved, gap_axis=axis)
        if rec.get("has_slot"):
            slot_observe_wires.append(rec)

    def _reserve_wire(waypoints, net_name) -> None:
        """Register each accepted wire segment as a thin rect so later routes avoid it."""
        _observe_wire_slot(waypoints, net_name)
        for a, b in zip(waypoints, waypoints[1:]):
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            # inflate the degenerate axis to a hair so the rect is non-empty; the
            # keep-out ring makes later routes give it real berth.
            if x1 - x0 < 0.2:
                x0 -= 0.1; x1 += 0.1
            if y1 - y0 < 0.2:
                y0 -= 0.1; y1 += 0.1
            ledger.try_reserve(LedgerRect(x0, y0, x1, y1, net_name, "wire"))

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
            _obst = _obstacles_excluding(endpoint_refs)
            # M6-8 (使用者 SW-crossing feedback): give each endpoint its outward pin
            # escape vector so the wire leaves the pin STRAIGHT before elbowing —
            # the corner can no longer land back in the pin's own lane and cross the
            # SAME IC's other pin wires. A satellite passive (single-pin-ish) still
            # escapes along its own pin edge; endpoint_sides already holds the
            # outward unit vector per endpoint (BR four-edge pin placement).
            _escape = [endpoint_sides[0], endpoint_sides[1]]
            waypoints = _orthogonal_route(endpoints[0], endpoints[1], _obst, escape=_escape)
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
            # M6-1 (DD-12): final ledger clearance gate. A route that dodges bodies
            # (guard C) and other-net fusion (guard A) but still crosses a pin-name
            # box or an already-drawn wire is REJECTED here → down-grade to label.
            if not _route_clears_ledger(waypoints, endpoint_refs):
                fusion_label_fallbacks.append({"net": net.name, "reason": "ledger-collision"})
                kind = _power_net_kind(net.name) if power_ports else None
                for abs_pt, edge, ep_ref in zip(endpoints, endpoint_sides, endpoint_refs):
                    if kind is not None:
                        power_endpoints.append((net.name, kind, abs_pt[0], abs_pt[1], edge, ep_ref))
                    else:
                        label_endpoints.append((net.name, abs_pt[0], abs_pt[1], edge))
                continue
            if jogged:
                fusion_jogged_nets.append(net.name)
            fusion_registry[net.name] = _segments_of(waypoints)
            _reserve_wire(waypoints, net.name)
            _hosts = frozenset(endpoint_refs)
            for a, b in zip(waypoints, waypoints[1:]):
                wire_blocks.append(_wire_segment_block(a[0], a[1], b[0], b[1]))
                routed_segments.append(((a, b), _hosts))
            mid = waypoints[len(waypoints) // 2]
            _place_local_label(net.name, mid[0], mid[1], waypoints)
        elif drawn and not force_label and not net_unresolved and len(endpoints) >= 3:
            _obst = _obstacles_excluding(endpoint_refs)
            segments, junctions = _bus_route(endpoints, _obst)
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
            # M6-1 (DD-12): final ledger clearance gate for the multi-node bus. Flatten
            # every segment into one polyline sample; if ANY segment crosses a ledger
            # rect (body / pin_extent / label / earlier wire) that is not a host, the
            # whole bus down-grades to per-pin labels (fail-safe).
            _bus_clear = all(
                _route_clears_ledger([a, b], endpoint_refs) for (a, b) in segments
            )
            if not _bus_clear:
                fusion_label_fallbacks.append({"net": net.name, "reason": "ledger-collision"})
                kind = _power_net_kind(net.name) if power_ports else None
                for abs_pt, edge, ep_ref in zip(endpoints, endpoint_sides, endpoint_refs):
                    if kind is not None:
                        power_endpoints.append((net.name, kind, abs_pt[0], abs_pt[1], edge, ep_ref))
                    else:
                        label_endpoints.append((net.name, abs_pt[0], abs_pt[1], edge))
                continue
            fusion_registry[net.name] = list(segments)
            for (a, b) in segments:
                _reserve_wire([a, b], net.name)
            _hosts = frozenset(endpoint_refs)
            for (a, b) in segments:
                wire_blocks.append(_wire_segment_block(a[0], a[1], b[0], b[1]))
                routed_segments.append(((a, b), _hosts))
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

    # DD-14: sheet-abs AABBs of every component's drawn body graphics, threaded
    # into the label placer so L6 avoidance keeps labels CLEAR of arcs/plates
    # (local->sheet: x adds, y flips — same convention as _body_box above).
    _label_graphics_boxes: list[tuple[float, float, float, float]] = []
    for component in components:
        _gr = graphics_rects.get(component.lib_id)
        if _gr is None:
            continue
        _gx0, _gy0, _gx1, _gy1 = _gr
        _gsy_a = component.y - _gy0
        _gsy_b = component.y - _gy1
        _label_graphics_boxes.append((component.x + _gx0, component.x + _gx1,
                                      min(_gsy_a, _gsy_b), max(_gsy_a, _gsy_b)))
    # DD-26/v24 Fix A (DD-28 A1): power-label net-name boxes are placed AFTER flags
    # (the power-port loop below), so the flag avoidance never saw them and a flag
    # from component A could seat straight onto component B's power label (the X1
    # HSE_IN vs MCU +3V3 cross-component smear). Pre-budget every power-port net-
    # name box HERE (same box model the power loop registers at :_pbox — centred on
    # the pin endpoint, _pvw wide, _pbh tall) and thread them into the flag
    # avoidance `reserved` so a flag steps outward off a reserved power label. The
    # anchor is the pin endpoint (px, py) which is already known from power_endpoints
    # before the port loop runs; identical to the box the loop reserves so this is a
    # faithful pre-image, not a new estimate.
    _pwr_name_cw_pre = _PIN_NAME_CW_MM * (page_scale if page_scale > 1.0 else 1.0)
    _pwr_name_ch_pre = _PIN_NAME_CH_MM * (page_scale if page_scale > 1.0 else 1.0)
    _power_label_boxes: list[tuple[float, float, float, float]] = []
    for _pep in power_endpoints:
        _pnet, _pkind, _ppx, _ppy, *_prest = _pep
        _pvw = len(_pnet) * _pwr_name_cw_pre
        _pbh = (_pwr_name_ch_pre + _LABEL_VMARGIN_MM)
        _power_label_boxes.append((_ppx - _pvw / 2, _ppx + _pvw / 2,
                                   _ppy - _pbh / 2, _ppy + _pbh / 2))
    _flag_reserved = reserved_boxes + _power_label_boxes
    label_blocks.extend(_staggered_label_blocks(label_endpoints, reserved=_flag_reserved,
                                                page_scale=page_scale,
                                                avail_y=_paper_avail_y(paper),
                                                avail_x=_paper_avail_x(paper),
                                                ledger=ledger,
                                                # BR_20260802 (c4): this was hardcoded True, which made the
                                                # `l6_avoidance` parameter declared at the top of this function
                                                # DEAD — AST-verified 0 reads in the body, against 10 reads of
                                                # page_scale as a control. Callers could compute the flag and
                                                # thread it in, and it was silently discarded. L6 displacement
                                                # (bounded by _L6_AVOID_MAX_STEPS x 1.0mm = 64mm) is the only
                                                # path that can produce the measured 1.57-53.38mm anchor moves;
                                                # DD-20 tops out at ~7mm on this page's longest label (14 ch).
                                                l6_avoidance=l6_avoidance,
                                                graphics_boxes=_label_graphics_boxes))

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
        for net_name, kind, px, py, *_rest in col_items:
            # DD-22/23 (user review v5): EVERY pin exits STRAIGHT. The former jog
            # `tier` search pushed crowded same-column power ports outward on a
            # `pin→anchor` jog leg + `anchor→port` stub, fusing neighbours into one
            # vertical rail hugging the symbol edge (the "畫面大亂" defect). Abolished:
            # the port anchor IS the pin endpoint, and the single stub runs one
            # stub-length straight out along the outward vector. No tier, no jog leg,
            # no cross-net fusion search — adjacent-port text separation is now a
            # closed-form pitch/layout concern (DD-19b/DD-20 geometry), never a bend.
            anchor_x = px
            anchor_y = py
            lib_id = _power_symbol_lib_id(net_name, kind)
            if lib_id not in embedded_defs:
                embedded_defs[lib_id] = _power_symbol_def(lib_id, net_name, kind)
            # port sits one stub-length out from the pin endpoint, ALONG the outward
            # vector, so it clears the body regardless of edge — single straight seg.
            port_x = round(anchor_x + nx * _STUB_MM, 4)
            port_y = round(anchor_y + ny * _STUB_MM, 4)
            final_stub_segs = [((anchor_x, anchor_y), (port_x, port_y))]
            wire_blocks.append(_wire_segment_block(anchor_x, anchor_y, port_x, port_y))
            fusion_registry.setdefault(net_name, []).extend(final_stub_segs)
            pwr_rot = _power_symbol_rotation(kind, (nx, ny))
            symbol_blocks.append(_power_symbol_instance(lib_id, net_name, port_x, port_y, project_name, root_uuid, rotation=pwr_rot, edge=(nx, ny)))
            # M2-3 (occupancy-ledger): register the finalized power-port net-name
            # Value box (centred at the chosen anchor) into the shared SSOT. Same
            # box model the tier search used (vw wide, name-height tall); mirrors
            # the accepted placement into the ledger without changing the solver.
            _pvw = len(net_name) * _pwr_name_cw
            _pbh = (_pwr_name_ch + _LABEL_VMARGIN_MM)
            _pbox = (anchor_x - _pvw / 2, anchor_x + _pvw / 2,
                     anchor_y - _pbh / 2, anchor_y + _pbh / 2)
            _ledger_reserve_box((_pbox[0], _pbox[1], _pbox[2], _pbox[3]),
                                f"{net_name}#pwr", "power")
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
            xs = [component.x + p[0] for p in pmap.values()]
            ys = [component.y - p[1] for p in pmap.values()]
        if not xs:
            continue
        # BR_20260804b: the shrink is CONDITIONAL -- a fixed inset inverts the box
        # on a narrow body and silently blinds the guard. Rationale, the measured
        # figures and the known residual live in `_guard_c_body_box`; deliberately
        # NOT restated here, since a second copy is a second thing to keep true.
        _body_boxes.append((component.ref,
            _guard_c_body_box(min(xs), max(xs), min(ys), max(ys))))
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
        _pp_msg = (
            "POWER_PORT_INSIDE_SYMBOL_BODY: power-port endpoints fell inside a "
            "component symbol body (stub orientation defect — BR left-pin stub "
            f"blind): {'; '.join(_port_intrusions[:12])}"
            + (f" (+{len(_port_intrusions) - 12} more)" if len(_port_intrusions) > 12 else "")
        )
        # BR_20260710: this is a purely-VISUAL layout defect (a power-port glyph
        # drawn over a symbol body) — it does NOT affect net connectivity, so it
        # must not hold the netlist/ERC export hostage. Default `power_port_gate`
        # == "error" keeps the historic fail-loud raise (existing callers are
        # byte-identical). An ERC-only / netlist-only caller passes "warn" to
        # downgrade it to an observation (recorded on the result, same pattern as
        # wire_body_intrusions) so a clean electrical spec can still emit.
        if power_port_gate == "warn":
            warnings.append(_pp_msg)
        else:
            raise ValueError(_pp_msg)

    # BR_20260708 machine check (WIRE_THROUGH_SYMBOL_BODY): every drawn wire
    # segment ∩ any component body AABB (keep-out-inflated) must be ∅, except the
    # wire's own pin-host bodies (its approach legs legitimately touch them). A
    # residual interior crossing is the "wire through symbol" defect the BR names.
    # This is an OBSERVATION recorded on the emit result (queryable) AND a fail-loud
    # count; the caller / a standalone checker (check_wire_body_clearance) reads it.
    # Body boxes here are the keep-out-inflated obstacle boxes built for routing —
    # the SAME source the routers avoided, so the check and the router agree.
    wire_body_intrusions: list[dict] = []
    for (a, b), hosts in routed_segments:
        for ref, box in wire_obstacle_boxes.items():
            if ref in hosts:
                continue
            if _seg_hits_box(a, b, box):
                wire_body_intrusions.append({
                    "seg": [list(a), list(b)],
                    "through": ref,
                })

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
        label_local_downgrades=label_local_downgrades,
        wire_body_intrusions=wire_body_intrusions,
        # BR_20260804f: the lossless carrier for guard C. The warning string
        # truncates at 12; this does not. Assigned unconditionally so "empty"
        # means "none found" and never "nobody wrote it".
        power_port_intrusions=list(_port_intrusions),
        slot_observe_wires=slot_observe_wires,
        slot_observe_skips=slot_observe_skips,
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
    (property "Reference" "{component.ref}" (at {round(rx, 4)} {round(ry, 4)} 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "{component.value}" (at {round(vx, 4)} {round(vy, 4)} 0) (effects (font (size 1.27 1.27)) (justify left)))
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
    # Bug1 (user review v4): a global label's flag/pad glyph + text must ATTACH at
    # the anchor by its edge that faces the body (the stub endpoint), so the pad's
    # far end points AWAY off-sheet. KiCad `justify left` grows the glyph+text FROM
    # the anchor along the +reading direction; at angle 0/90 that already puts the
    # attaching edge (glyph tail) at the anchor. But at angle 180 (left-edge pin)
    # and 270 (bottom-edge pin) the reading direction is reversed, so `justify left`
    # anchors the glyph's OUTER end at the stub tip and the pad body overshoots INTO
    # the sheet toward the symbol — the "left pin pad aligned by wrong end" defect.
    # Flip to `justify right` for 180/270 so the pad's near (right/top) end sits on
    # the anchor and the body extends outward. 0/90 stay `justify left` (byte-stable).
    justify = "right" if angle in (180, 270) else "left"
    fs = round(1.27 * text_scale, 4)
    return (
        f'  (global_label "{name}" (shape bidirectional) (at {round(x, 4)} {round(y, 4)} {angle})\n'
        f'    (effects (font (size {fs} {fs})) (justify {justify})) (uuid "{_uid()}"))'
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

# ---- M6-8e/f: routing lane discipline (user 四輪審圖 rulings) ----
# M6-8e (03b memory-ospi ruling): parallel drawn-wire lanes were spaced at 1 grid
# (1.27 mm ≈ half a text row) and jammed. Lane pitch MUST be >= one text row so a
# net-name printed on one lane never collides with the adjacent lane. One rendered
# text row = _LABEL_CH_MM (1.27) → a full row of clearance = 2 grid = 2.54 mm.
LANE_PITCH_MM = 2.54       # min centre-to-centre spacing of parallel wire lanes
# M6-8f (04 wireless ruling): a lane vertical band must be repelled from an IC's
# body so it does not cut through the pin stub / pin-number / pin-name reach band.
# The keep-out band = body box inflated on every edge by the pin stub reach + the
# pin-name text reach + one text-row buffer.
_KEEPOUT_STUB_MM = 2.54    # pin stub length (2 grid) drawn outward from the body
_KEEPOUT_PINNAME_MM = _PIN_NAME_CH_MM + _PIN_NAME_OFFSET_MM  # pin-name text reach


def ic_keepout_band(body: tuple[float, float, float, float],
                    text_row_mm: float = _LABEL_CH_MM) -> tuple[float, float, float, float]:
    """M6-8f: inflate an IC body box into its routing keep-out band.

    A lane assigned to route past an IC must stay OUT of this band, which wraps the
    body with the space its own pins consume: pin stub + pin-name text reach + one
    text-row buffer. Returns (x0, y0, x1, y1) strictly containing the input body.

    - input  body      : (x0, y0, x1, y1) the component's drawn body AABB (mm).
    - input  text_row_mm: one rendered text-row height (buffer past the pin names).
    - output           : the inflated band; every edge is pushed outward by
                         stub + pin-name reach + one text row.
    - rule: symmetric inflation (pins can leave any of the four edges); the band is
            never smaller than the body on any edge.
    """
    x0, y0, x1, y1 = body
    if x1 < x0 or y1 < y0:
        raise ValueError(f"ic_keepout_band: degenerate body {body!r}")
    pad = _KEEPOUT_STUB_MM + _KEEPOUT_PINNAME_MM + max(0.0, text_row_mm)
    return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)

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


# DD-14 (user review v18): a label box that merely TOUCHES a symbol graphic
# (X1 HSE flag arrow tip on the crystal plate; VDDIO +3V3 label on the pin
# stub) passed the strict-overlap gate — no ink actually overlaps, but there
# is no breathing room and it reads as glued. `_bbox_clear` requires a real
# gap of `_CLEARANCE_MM` on the separating axis; it is the safety-margin
# analogue of `_bbox_overlap` used wherever an element must stay OFF another,
# not merely non-overlapping.
_CLEARANCE_MM = 1.27  # one grid = minimum breathing room between any two elements

# BR_20260802: float tolerance for the clearance comparison. NOT a tuned value —
# derived from two measured magnitudes that are 8 orders of magnitude apart:
#
#   noise floor   : coordinates here are grid multiples (1.27 mm) accumulated by
#                   addition, so a nominal gap of exactly one grid lands as
#                   1.2699999999999818 (worst deviation MEASURED in this defect:
#                   1.8e-14 mm, which is 0.1 ulp at the largest coordinate the
#                   emitter handles, ~1189 mm / A0 long edge).
#   signal floor  : every coordinate written to the .kicad_sch goes through
#                   round(v, 4) at the finest, so the SMALLEST geometric
#                   difference the file can even express is 1e-4 mm.
#
# 1e-9 sits ~4.7 orders ABOVE the worst float deviation and ~5 orders BELOW the
# smallest expressible real difference. It can therefore only ever absorb float
# noise; a genuine clearance violation is at minimum 1e-4 mm and stays visible.
# Safe to widen up to ~1e-6; DO NOT approach 1e-4 — that is real geometry.
#
# Why this mattered: without it, 8 labels whose nominal gaps were IDENTICAL (all
# exactly one grid) split 5/3 purely on the sign of accumulated float error. The
# 3 that compared as "not clear" had their anchors pushed 1.57 mm off their pin
# endpoints, and DD-22/23 forbids a stub wire to carry them back — so they went
# open-circuit silently. This tolerance removes the coin-flip, but see the parent
# BR: it does NOT remove the underlying contract conflict (an anchor may still be
# moved off its pin for other reasons, with the same silent consequence).
_CLEARANCE_EPS_MM = 1e-9


def _bbox_clear(a: tuple[float, float, float, float],
                b: tuple[float, float, float, float],
                clearance: float = _CLEARANCE_MM) -> bool:
    """True iff boxes a,b are separated by >= `clearance` on some axis.

    a,b are (x0, x1, y0, y1). Two boxes are "clear" when a gap of at least
    `clearance` exists on the x OR the y axis (a real corridor between them).
    Strict overlap (`_bbox_overlap` True) and edge-touching both return False.
    This is the safety-margin gate; `_bbox_overlap` remains the strict-ink gate
    (byte-stable — existing call sites are untouched).

    The comparison carries `_CLEARANCE_EPS_MM` because a gap of EXACTLY one grid
    is the common case here, and exact-equality on accumulated floats decides it
    by rounding error rather than by geometry. See the constant for the derivation.
    """
    gap_x = max(b[0] - a[1], a[0] - b[1])   # +ve => x-gap between them
    gap_y = max(b[2] - a[3], a[2] - b[3])   # +ve => y-gap between them
    thr = clearance - _CLEARANCE_EPS_MM
    return gap_x >= thr or gap_y >= thr


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
                           rotation: int = 0, edge: tuple[float, float] | None = None) -> str:
    _PWR_REF_COUNTER[0] += 1
    ref = f"#PWR{_PWR_REF_COUNTER[0]:04d}"
    # DD-29(2) (user review v8): the Value (net-name) text MUST sit at the pin's FAR
    # end — pushed AWAY from the chip along the pin's own outward edge vector — so it
    # never lands back on the pin-number / pin-name band. The legacy `off=(0,-5.08)`
    # then rotated-by-symbol-rotation put a LEFT-edge supply port's text at (+5.08,0)
    # i.e. back toward the body (+x), stacking +1V8 on the red pin numbers (the
    # K1–K5/L1–L5 ten-way smear). Anchor the text offset to the OUTWARD edge vector
    # (nx,ny) directly: text is one glyph-column (name length) clear of the port along
    # (nx,ny). When edge is None (legacy callers) fall back to the old rotation-driven
    # offset so byte-stable paths stay identical.
    if edge is not None:
        nx, ny = edge
        _mag = (nx * nx + ny * ny) ** 0.5 or 1.0
        ux, uy = nx / _mag, ny / _mag
        # clear the port glyph (~2.5mm) plus half the net-name text so the whole box
        # sits beyond the port, on the away-from-chip side.
        _reach = _STUB_MM + len(net_name) * _LABEL_CW_MM / 2 + _LABEL_HMARGIN_MM
        off = (ux * _reach, uy * _reach)
    else:
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


# DD-19 (plan D): a same-column right-edge co-point run needs >= this many flags
# before redistribution kicks in (a sparse pair reads fine — stay byte-stable).
_DD19_DENSE_MIN = 3
# outward step (mm) between consecutive flags' right edges so the column reads as
# a legible staircase instead of one ink line. One grid = the minimum breathing
# room (_CLEARANCE_MM); the test asserts >= 1.0mm adjacent step.
_DD19_EDGE_STEP_MM = _CLEARANCE_MM


def _dd19_dense_column_offsets(
    columns: dict[float, list[tuple[str, float, float, tuple[float, float]]]],
) -> dict[tuple[str, float, float], float]:
    """DD-19 plan D: for every same-column, same-edge run of >= _DD19_DENSE_MIN
    flags whose box right edges would co-point, return a per-endpoint OUTWARD
    offset (mm along the edge vector) that steps the right edges apart.

    The offset is applied purely along each flag's own outward edge vector, so the
    emitted label still points the same way with no y-nudge / wire / jog (DD-22/23
    bend-free). Keyed by (name, round(x,2), round(y,2)) so the emit loop can look
    up each endpoint's step. Sparse columns (< _DD19_DENSE_MIN) get no entry and
    stay byte-stable.
    """
    offsets: dict[tuple[str, float, float], float] = {}
    for col_x, items in columns.items():
        # group by identical outward edge vector (a co-point run shares one edge)
        by_edge: dict[tuple[float, float], list[tuple[str, float, float, tuple[float, float]]]] = {}
        for it in items:
            by_edge.setdefault(it[3], []).append(it)
        # DD-24 (user review v22): the DD-19 per-flag horizontal STAIRCASE is
        # ABOLISHED. The user rejected the "each flag shifts one more step out,
        # extending like an unbounded staircase" presentation and ruled that a
        # dense same-column run must share ONE uniform x (整齊統一排列，用同一個
        # X值). Flags anchor on the pin endpoint x already; emitting NO horizontal
        # offset keeps that single shared column. Right-edge co-point (DD-16) does
        # NOT visually regress: differing flag-text lengths fan the LEFT ends out
        # while the aligned right (anchor) edge is exactly the tidy column the user
        # wants. The DD-20 opposing-vertical separation below is retained (that is
        # the orthogonal interpenetration axis, not the horizontal staircase).
        for edge, grp in by_edge.items():
            if len(grp) < _DD19_DENSE_MIN:
                continue
            nx, ny = edge
            if abs(nx) < abs(ny):
                continue
            # DD-24: uniform x — no per-flag staircase offset (was tier * step).

        # DD-20 (v21 fresh-eyes review): the ORTHOGONAL second axis of DD-16. On a
        # shared column, an ang=90 flag (box grows -y, toward smaller y) and an
        # ang=270 flag (box grows +y, toward larger y) point TOWARD each other; when
        # their w-long (9~17mm) vertical runs meet they interpenetrate — the U9
        # right-edge `VBMEBVSYGNGND` blob, the J_CAM top GND column, the
        # LED_R/G/B<->K_R/G/B pairs. DD-19's same-edge staircase skips vertical edges,
        # and _avoid_label_overlap only runs with l6_avoidance=True (OFF on product
        # all-label pages — exactly where the blob lives). Like DD-19 this must be
        # UNCONDITIONAL. Fix: for every opposing pair on the column whose vertical
        # runs would collide, push each flag OUTWARD along its OWN edge (the +y-anchor
        # flag toward +y, the -y-anchor flag toward -y) so the runs separate. Purely
        # along the outward edge vector — no x-jog, no wire, no bend (DD-22/23 safe).
        # Split the column's vertical-edge flags into the two opposing growth
        # directions. edge=(0,1) => ang270 => box grows +y (y..y+w); edge=(0,-1) =>
        # ang90 => box grows -y (y-w..y). See _label_bbox / _edge_label_angle.
        grow_pos = []  # box grows toward +y (edge (0, +1))
        grow_neg = []  # box grows toward -y (edge (0, -1))
        for name, x, y, e in items:
            enx, eny = e
            if abs(enx) >= abs(eny):
                continue  # horizontal edge — handled above
            (grow_pos if eny > 0 else grow_neg).append((name, x, y, e))
        # A collision happens when a +y-growing flag sits BELOW (smaller y) a
        # -y-growing flag: their runs cover the y-gap between them. The label text
        # length w (chars * cw + glyph + margin) is the reach; two flags whose
        # anchor y-gap is < (w_pos + w_neg) would overlap. We resolve the tightest
        # such opposing pairs by stepping the lower (+y) flag further +y and the
        # upper (-y) flag further -y, away from the shared midline, until the boxes
        # clear. Deterministic: process each -y flag against the nearest +y flag
        # below it. Offsets ACCUMULATE with any DD-19 horizontal step already set
        # (vertical flags never get a horizontal step, so this is the sole source).
        for nm_n, xn, yn, en in grow_neg:
            wn = len(nm_n) * _LABEL_CW_MM + _LABEL_GLYPH_MM + _LABEL_HMARGIN_MM
            # nearest +y-growing flag strictly below this -y flag on the same column
            below = [p for p in grow_pos if p[2] < yn]
            if not below:
                continue
            nm_p, xp, yp, ep = max(below, key=lambda t: t[2])
            wp = len(nm_p) * _LABEL_CW_MM + _LABEL_GLYPH_MM + _LABEL_HMARGIN_MM
            # +y flag top edge = yp + wp ; -y flag bottom edge = yn - wn.
            # overlap when (yp + wp) > (yn - wn), i.e. gap < wp + wn.
            gap = yn - yp
            overlap = (wp + wn) - gap
            if overlap <= _CLEARANCE_MM:
                continue  # already clear (or clears within one grid) — leave stable
            # split the needed separation (+ one clearance grid) between the two,
            # each pushed outward along its OWN edge.
            need = overlap + _CLEARANCE_MM
            half = need / 2.0
            kp = (nm_p, round(xp, 2), round(yp, 2))
            kn = (nm_n, round(xn, 2), round(yn, 2))
            offsets[kp] = offsets.get(kp, 0.0) + half
            offsets[kn] = offsets.get(kn, 0.0) + half
    return offsets


def _staggered_label_blocks(endpoints: list[tuple[str, float, float]],
                            reserved: list[tuple[float, float, float, float]] | None = None,
                            page_scale: float = 1.0,
                            avail_y: tuple[float, float] | None = None,
                            avail_x: tuple[float, float] | None = None,
                            ledger: "OccupancyLedger | None" = None,
                            l6_avoidance: bool = False,
                            graphics_boxes: list[tuple[float, float, float, float]] | None = None,
                            ) -> list[str]:
    """Emit global labels with per-column anti-overlap staggering.

    graphics_boxes (DD-14): sheet-abs AABBs of every component's drawn body
    graphics (arc/plate/rect). When `l6_avoidance` is on, a label anchor is
    pushed out until it CLEARS these by `_CLEARANCE_MM` (not merely non-overlap)
    so a flag never seats on a crystal plate / inductor arc. None/empty =>
    byte-stable (no graphics constraint).


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
    # DD-19 (user review v20, plan D — dense-column label redistribution): on
    # connector all-label pages (J1 USB-C, J_CAM, JSA) 6~8 per-pin flags share ONE
    # x column at ~2.54mm pitch and all point the same outward edge, so every box's
    # RIGHT edge lands on the SAME x (ang180 => box right == anchor x) — the ends
    # pile into one vertical ink column (`GNONONGND`). The vertical boxes do NOT
    # overlap (box h≈1.57mm < 2.54mm pitch) so _avoid_label_overlap never nudges
    # them. Three prior rounds (DD-16→17→18) proved pin-pitch routes are no-ops
    # (connector pitch rides page_scale + paper solver). Fix: for a run of >=3
    # same-column, same-edge flags, push each anchor OUTWARD along its OWN edge
    # vector by a DISTINCT stepped amount so the right edges step apart. This stays
    # inside the DD-22/23 bend-free freedom (anchor moves purely along the outward
    # edge vector — no y-nudge, no wire, no jog; ang unchanged). Computed here as a
    # per-endpoint outward offset consumed in the emit loop below.
    # DD-19 dense-column redistribution is a STRUCTURAL defect fix (co-point right
    # edges), independent of the l6_avoidance label-vs-label overlap path. Its own
    # trigger is conservative (same column + same edge + >= _DD19_DENSE_MIN + the
    # boxes would co-point), so sparse pages get an empty map and stay byte-stable.
    # It must NOT be gated behind l6_avoidance (product all-label pages leave that
    # off, which is exactly where the connector co-point blob appears).
    _dd19_offset = _dd19_dense_column_offsets(columns)
    # Seed the occupancy with the in-body pin-NAME boxes so a global label never
    # gets placed on top of the IC's own pin-name text (the cross pin/label smear).
    placed: list[tuple[float, float, float, float]] = list(reserved or [])
    for col_x in sorted(columns):
        items = sorted(columns[col_x], key=lambda t: t[2])
        for name, x, y, edge in items:
            # DD-22/23 (user review v5): a label's wire runs STRAIGHT OUT along the
            # pin's own outward vector to a single stub endpoint — no L-jog, no
            # staggered lane, no y-nudge / x-ladder. The former anti-overlap ladders
            # bent the stub sideways/vertically to dodge crowded neighbours; the user
            # forbids every bend. Adjacent-label separation is now a closed-form
            # pitch/layout concern (the per-page pitch solver + DD-19b/DD-20 floors),
            # never a wire bend. horiz pin => horizontal stub; vertical pin (top/
            # bottom edge) => vertical stub. Box registered at the straight endpoint.
            # The label anchors DIRECTLY on the pin endpoint (x, y) — the pin's own
            # library graphic is the out-line. No extra stub wire, no displacement:
            # a stub is exactly the bend the user forbids, and a zero-displacement
            # label at the pin endpoint is byte-identical to the legacy `ly==y` path
            # (2-pin R/C nets emit a bare global_label with NO wire, TV9 byte-stable).
            # M7 DD-13 (l6_avoidance, opt-in): the DD-22/23 straight-out rule anchors
            # EVERY label on its pin endpoint (x, y). On product all-label pages this
            # stacks same-pin multi-flags and adjacent same-column pins into an
            # illegible glyph blob (v17 QA BLOCKER). L6 avoidance separates them using
            # the ONE bend-free freedom DD-6 preserves — "label 錨點外端": push the
            # anchor OUTWARD along the label's own outward edge vector (the text still
            # runs straight along that vector; no wire, no jog, no perpendicular
            # displacement) until its reach-box clears every already-placed box.
            lx, ly = x, y
            if l6_avoidance:
                lx, ly = _avoid_label_overlap(name, x, y, edge, placed, page_scale,
                                              graphics=graphics_boxes)
            # DD-19 plan D (unconditional structural fix): step a dense co-point
            # column's right edges apart so a connector column reads as a legible
            # staircase. Purely along the outward edge vector (no y change, no bend
            # — DD-22/23 safe); empty offset => byte-stable for non-dense columns.
            _dd19 = _dd19_offset.get((name, round(x, 2), round(y, 2)))
            if _dd19:
                _nx, _ny = edge
                _mag = (_nx * _nx + _ny * _ny) ** 0.5 or 1.0
                _step = _dd19 * (page_scale if page_scale > 1.0 else 1.0)
                lx += (_nx / _mag) * _step
                ly += (_ny / _mag) * _step
            _label_bbox_reg = _label_bbox(name, lx, ly, True, edge, text_scale=page_scale)
            placed.append(_label_bbox_reg)
            if ledger is not None:
                _rx0, _rx1, _ry0, _ry1 = _label_bbox_reg
                if _rx1 > _rx0 and _ry1 > _ry0:
                    ledger.try_reserve(LedgerRect(_rx0, _ry0, _rx1, _ry1, name, "label"))
            blocks.append(_global_label_block(name, lx, ly, edge, text_scale=page_scale))
    return blocks


# M7 DD-13: outward step (mm) taken per iteration when nudging a label anchor off a
# neighbour along its own outward edge vector. One text-row height keeps steps at
# the same granularity as the reach-box height so a few steps clear a stacked pair.
_L6_AVOID_STEP_MM = _LABEL_CH_MM + _LABEL_VMARGIN_MM  # == reach-box height at scale 1
_L6_AVOID_MAX_STEPS = 64  # bound the search (fail-open: keep last position, never hang)


def _avoid_label_overlap(name: str, x: float, y: float,
                         edge: tuple[float, float],
                         placed: list[tuple[float, float, float, float]],
                         page_scale: float,
                         graphics: list[tuple[float, float, float, float]] | None = None,
                         ) -> tuple[float, float]:
    """Return an anchor (lx, ly) for `name`'s label whose reach-box clears every box
    in `placed`, reached by stepping the anchor OUTWARD along `edge` only.

    Bend-free by construction: the anchor moves purely along the label's outward
    unit vector, so the emitted global label is still a straight label pointing the
    same way — just seated further out (DD-6 "label 錨點外端", never a jog/nudge/wire).
    Fail-open: if no clear seat within the step bound, keep the furthest tried
    position (all-label policy — a label is never dropped to resolve overlap).

    DD-14: `graphics` are symbol body-graphics AABBs (arc/plate/rect) the label
    must stay OFF with a real clearance gap (`_bbox_clear`), not merely avoid
    overlapping — a flag arrow-tip touching a crystal plate is unacceptable.
    `placed` (labels + pin-name text) keeps the strict-overlap gate, so callers
    that pass no `graphics` are byte-stable.
    """
    nx, ny = edge
    _mag = (nx * nx + ny * ny) ** 0.5 or 1.0
    ux, uy = nx / _mag, ny / _mag
    step = _L6_AVOID_STEP_MM * (page_scale if page_scale > 1.0 else 1.0)
    _gfx = graphics or ()
    lx, ly = x, y
    for _ in range(_L6_AVOID_MAX_STEPS):
        box = _label_bbox(name, lx, ly, True, edge, text_scale=page_scale)
        if (not any(_bbox_overlap(box, p) for p in placed)
                and all(_bbox_clear(box, g) for g in _gfx)):
            return (round(lx, 4), round(ly, 4))
        lx += ux * step
        ly += uy * step
    return (round(lx, 4), round(ly, 4))


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


# ---------------------------------------------------------------------------
# BR_20260708: wire routing obstacle (symbol-body keep-out) model.
#
# The Level-1 routers below emit ONLY endpoint-correct orthogonal polylines; on a
# dense page a straight L-route drives a segment clean through a THIRD component's
# body (ADQ5/6/7 wire through U2). A keep-out obstacle is a component-body AABB in
# absolute SHEET coords; the routers take an optional obstacle list and pick a
# candidate polyline whose INTERIOR (non-endpoint) segments clear every obstacle.
#
# ObstacleBox taxonomy:
#   - name : "ObstacleBox"
#   - repr : (x0, x1, y0, y1) — an axis-aligned rect in SHEET mm, x0<=x1, y0<=y1,
#            already inflated by the keep-out margin (WIRE_KEEPOUT_MM) on all sides.
#   - input to a router as `obstacles: list[ObstacleBox]`.
#   - NOT: a symbol-local rect; NOT a pin box; NOT the two host bodies of the wire
#          being routed (those are excluded by the caller so the pin approach leg
#          is allowed to touch its own host).
#   - a segment "clears" the box iff it does not cross the box interior except at a
#     shared endpoint coordinate (a wire may end ON a box edge — that is its pin).
# ---------------------------------------------------------------------------
WIRE_KEEPOUT_MM = 1.27  # keep-out ring (1 grid) added around each body for routing


def _seg_hits_box(a: tuple[float, float], b: tuple[float, float],
                  box: tuple[float, float, float, float],
                  endpoints: tuple | None = None) -> bool:
    """True iff axis-aligned segment a-b crosses the INTERIOR of `box`.

    Taxonomy:
      - input a, b : segment endpoints (sheet mm); the segment is axis-aligned.
      - input box  : (x0, x1, y0, y1) obstacle rect (already keep-out-inflated).
      - input endpoints: optional tuple of pin-endpoint coords for the whole route;
                 a point equal to one of these is a legal pin landing, not a hit
                 (unused here — interior-crossing test already excludes edge touch).
      - output: bool — True == the segment passes through the box interior.
      - NOT: True for a segment that merely touches the box boundary (shared edge /
             corner), which is a legal abutment.
      - done when: returns for every axis-aligned segment.
    """
    x0, x1, y0, y1 = box
    ax, ay = a
    bx, by = b
    if abs(ay - by) < 1e-6:  # horizontal segment at y=ay spanning [lo,hi] in x
        if not (y0 < ay < y1):
            return False
        lo, hi = sorted((ax, bx))
        return lo < x1 and hi > x0 and (min(hi, x1) - max(lo, x0)) > 1e-6
    if abs(ax - bx) < 1e-6:  # vertical segment at x=ax spanning [lo,hi] in y
        if not (x0 < ax < x1):
            return False
        lo, hi = sorted((ay, by))
        return lo < y1 and hi > y0 and (min(hi, y1) - max(lo, y0)) > 1e-6
    return False  # diagonal never emitted


def _waypoints_clear(waypoints: list[tuple[float, float]],
                     obstacles: list[tuple[float, float, float, float]]) -> bool:
    """True iff NO segment of `waypoints` crosses any obstacle box interior."""
    if not obstacles:
        return True
    for a, b in zip(waypoints, waypoints[1:]):
        for box in obstacles:
            if _seg_hits_box(a, b, box):
                return False
    return True


def _orthogonal_route(p1: tuple[float, float], p2: tuple[float, float],
                      obstacles: list[tuple[float, float, float, float]] | None = None,
                      escape: list[tuple[float, float]] | None = None) -> list[tuple[float, float]]:
    """Level-1 auto-router: return the polyline waypoints for an orthogonal (Manhattan)
    connection between two pin endpoints, avoiding component-body obstacles.

    Taxonomy:
      - input  p1, p2: absolute schematic (x, y) of the two pin endpoints to join.
      - input  obstacles: optional keep-out AABBs (see ObstacleBox); the two HOST
                bodies of p1/p2 must already be excluded by the caller.
      - output: ordered list of >=2 waypoints; consecutive pairs are axis-aligned
                segments. NOT allowed to return a diagonal segment. Endpoints p1/p2
                are ALWAYS preserved verbatim (FIDELITY: net partition unchanged).
      - rule: try candidate polylines in a fixed deterministic order and return the
              FIRST whose interior segments clear all obstacles:
                1. collinear straight [p1, p2] (only if actually collinear);
                2. H-first elbow  [p1, (x2, y1), p2];
                3. V-first elbow  [p1, (x1, y2), p2];
                4. mid-channel detours (Z-routes) at grid-snapped x/y columns that
                   sit OUTSIDE every obstacle's span, both axes, nearest-first.
              If none clear (fully boxed in), fall back to the legacy H-first elbow
              (endpoint-correct; a residual crossing is reported by the machine
              check, never silently "fixed" by moving a pin).
      - done when: a clear candidate is found, or the legacy fallback is returned.
    """
    (x1, y1), (x2, y2) = p1, p2
    obstacles = obstacles or []

    # M6-8 (使用者 SW-crossing feedback): pin escape corridor. When the caller
    # supplies an outward escape unit vector per endpoint, the wire must leave the
    # pin STRAIGHT along that vector for one keep-out step BEFORE any elbow, so the
    # first corner never lands back inside the pin's own lane (which is what let a
    # buck SW route corner immediately and X across the SAME IC's other pin wires).
    # The escape stub is prepended to p1 and appended to p2; the interior elbow is
    # then solved between the two escaped points. Endpoints p1/p2 stay verbatim
    # (FIDELITY). A zero vector means "no escape for this end" (e.g. a passive).
    e1 = escape[0] if escape and len(escape) >= 1 else (0.0, 0.0)
    e2 = escape[1] if escape and len(escape) >= 2 else (0.0, 0.0)
    step = WIRE_KEEPOUT_MM

    def _escape_step(px: float, py: float, ev: tuple[float, float],
                     ox: float, oy: float) -> float:
        """BR_20260804c: bound the escape stub so it cannot over-shoot the OTHER pin.

        The raw step is a fixed keep-out applied WITHOUT ever consulting how far
        apart the two endpoints are. When two pins face each other exactly one
        step apart, each end escapes precisely ONTO the other (q1 == p2 and
        q2 == p1); `_wrap` then emits p1, p2, p1, p2, so a 2-pin net renders as
        THREE wire segments with the middle one reversed. Clamping to half the
        separation is the bound that makes a swap unrepresentable: each escaped
        point stays strictly inside its own half of the span.

        The clamp applies ONLY when the escape vector points TOWARD the other
        endpoint. An outward-facing escape cannot over-shoot anything, so
        clamping it would shrink stubs on close-but-diverging pairs for no
        benefit -- and every such change would move geometry that is on the
        verified baseline. `ox, oy` is the other endpoint.

        Correctness rests on `_snap_grid` being MONOTONE NON-DECREASING (measured:
        10000 points, zero violations; a deliberately non-monotone control caught
        8). The snap happens AFTER the clamp, so "no swap before snapping" only
        implies "no swap after snapping" because of that property -- an implicit
        coupling to _snap_grid's grid worth knowing about if it is ever retuned.

        What the clamp does NOT cause: when two pins sit within ONE grid step,
        _snap_grid quantises the escape away entirely, so the wire leaves the pin
        with no interior stub at all. That is pre-existing grid behaviour, NOT a
        cost of clamping -- a side-by-side sweep of 399 separations found 20
        stub-absent cases WITH the clamp and the same 20 WITHOUT it (newly
        stub-absent because of the clamp: zero).

        And "no interior stub" is NOT a DD-22/23 violation, which is worth stating
        because it reads like one. DD-22/23 requires that every pin EXIT STRAIGHT;
        it does not mandate a stub of any particular length. At sep <= 1 step the
        route degenerates to the single segment p1->p2, and a single axis-aligned
        segment already leaves the pin straight. Measured over 798 cases (399
        separations x both axes): zero routes where the first leg out of p1 or the
        last leg into p2 departs from its own escape vector, and zero diagonal
        legs (control: a deliberately diagonal path IS flagged; comparing against
        the wrong expected vector DOES return False). So there is no outstanding
        grid-vs-DD-22/23 tension here -- an earlier draft of this docstring said
        there was, and that sentence was retracted after the sweep above.
        """
        if ev[0] and not ev[1]:
            delta, axis_dir = ox - px, ev[0]
        elif ev[1] and not ev[0]:
            delta, axis_dir = oy - py, ev[1]
        else:
            return step
        if delta == 0 or (delta > 0) != (axis_dir > 0):
            return step                  # escape points away → no over-shoot possible
        return min(step, abs(delta) / 2.0)

    def _escaped(px: float, py: float, ev: tuple[float, float],
                 ox: float, oy: float) -> tuple[float, float]:
        # Move ONLY along the escape axis (snap that axis to grid); the orthogonal
        # axis keeps the pin's exact coordinate so the escape stub stays perfectly
        # axis-aligned (a horizontal +x escape must not nudge y, else the stub is a
        # diagonal and the "leaves the pin straight" contract breaks).
        s = _escape_step(px, py, ev, ox, oy)
        if ev[0] and not ev[1]:          # horizontal escape → keep py exact
            return (_snap_grid(px + ev[0] * s), py)
        if ev[1] and not ev[0]:          # vertical escape → keep px exact
            return (px, _snap_grid(py + ev[1] * s))
        return (px, py)

    q1 = _escaped(x1, y1, e1, x2, y2) if (e1[0] or e1[1]) else p1
    q2 = _escaped(x2, y2, e2, x1, y1) if (e2[0] or e2[1]) else p2

    def _wrap(inner: list[tuple[float, float]]) -> list[tuple[float, float]]:
        # prepend p1->q1 escape and append q2->p2 escape, dropping degenerate repeats
        seq: list[tuple[float, float]] = []
        for pt in ([p1] if q1 != p1 else []) + inner + ([p2] if q2 != p2 else []):
            if not seq or seq[-1] != pt:
                seq.append(pt)
        return seq

    if q1 != p1 or q2 != p2:
        # solve the interior between the escaped points, then wrap with the stubs
        inner_wp = _orthogonal_route(q1, q2, obstacles)
        return _wrap(inner_wp)

    candidates: list[list[tuple[float, float]]] = []
    if abs(x1 - x2) < 1e-6 or abs(y1 - y2) < 1e-6:
        candidates.append([p1, p2])
    else:
        candidates.append([p1, (x2, y1), p2])   # H-first
        candidates.append([p1, (x1, y2), p2])   # V-first

    if obstacles:
        # Detour channels: a mid-column x (vertical mid-leg) or mid-row y
        # (horizontal mid-leg) offset OUTSIDE every obstacle span, grid-snapped,
        # tried nearest-to-farthest so the shortest detour wins. Bounds come from
        # the obstacle union plus a keep-out step so the mid-leg runs clear.
        ox0 = min(b[0] for b in obstacles)
        ox1 = max(b[1] for b in obstacles)
        oy0 = min(b[2] for b in obstacles)
        oy1 = max(b[3] for b in obstacles)
        step = WIRE_KEEPOUT_MM
        # vertical mid-leg columns just left / right of the obstacle union
        for mx in (_snap_grid(ox0 - step), _snap_grid(ox1 + step)):
            candidates.append([p1, (mx, y1), (mx, y2), p2])
        # horizontal mid-leg rows just above / below the obstacle union
        for my in (_snap_grid(oy0 - step), _snap_grid(oy1 + step)):
            candidates.append([p1, (x1, my), (x2, my), p2])

    for wp in candidates:
        if _waypoints_clear(wp, obstacles):
            return wp
    # fully boxed in: legacy endpoint-correct route (machine check will flag it).
    return candidates[0]


def check_wire_body_clearance(result: "SchematicEmitResult | object") -> list[dict]:
    """Standalone machine check accessor (BR_20260708).

    Taxonomy:
      - name : check_wire_body_clearance
      - input: a SchematicEmitResult (or a ComposeResult exposing the same
               `wire_body_intrusions` attribute), i.e. the object returned by
               emit_kicad_schematic / compose_schematic.
      - output: the list of drawn-wire-through-symbol-body intrusions recorded at
               emit time; each entry {"seg": [[x1,y1],[x2,y2]], "through": ref}.
               EMPTY list == PASS (every drawn wire clears all non-host bodies).
      - NOT: a re-computation from the .kicad_sch file; it returns the emit-time
             record (the routers and this record share one obstacle source, so
             the record is authoritative). A caller wanting a from-file recompute
             uses recompute_wire_body_clearance instead.
      - done when: returns the list (never raises).
    """
    return list(getattr(result, "wire_body_intrusions", []) or [])


def _bus_route(endpoints: list[tuple[float, float]],
               obstacles: list[tuple[float, float, float, float]] | None = None) -> tuple[list[tuple[tuple[float, float], tuple[float, float]]], list[tuple[float, float]]]:
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
    # Daisy-chain consecutive pins with the proven 2-pin orthogonal router. The
    # obstacles for a given hop are the shared keep-out set MINUS the two hop-host
    # bodies is unknown here (endpoints carry no ref), so pass the full obstacle
    # set; the router still preserves both hop endpoints verbatim (FIDELITY-safe)
    # and only detours the interior legs around third-party bodies.
    for a, b in zip(pts, pts[1:]):
        waypoints = _orthogonal_route(a, b, obstacles)
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
