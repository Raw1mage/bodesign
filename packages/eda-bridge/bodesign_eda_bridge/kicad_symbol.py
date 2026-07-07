from dataclasses import dataclass, field
import json
from pathlib import Path
import re


SYMBOL_LIB_VERSION = "20241209"
DEFAULT_SYMBOL_NAME = "GENERIC_IC"
DEFAULT_FOOTPRINT_FILTER = "*"

# Symbol geometry constants (BR: four-edge physical-pinout mirror placement).
_PIN_LENGTH = 5.08        # pin graphic length; the pin `at` is its OUTER endpoint,
                          # so the body edge sits _PIN_LENGTH inward from `at`.
_PIN_PITCH = 1.27         # spacing between adjacent pins on one edge.
_EDGE_MARGIN = 2.54       # clear span each corner keeps free of pins.
_FOUR_EDGE_MIN = 25       # numeric parts with >24 pins get the QFP perimeter walk.
_BGA_RE = re.compile(r"^([A-Z]{1,2})([0-9]+)$")
_NUM_RE = re.compile(r"^[0-9]+$")


@dataclass(slots=True)
class _SymbolGeometry:
    """Resolved four-edge symbol geometry.

    - `half_w` / `half_h`: half-width / half-height of the body rectangle (the
      rectangle spans [-half_w, half_w] x [-half_h, half_h]).
    - `pin_placements`: [(pin, at_x, at_y, rotation), ...]. `at_x`/`at_y` is the
      pin's OUTER endpoint (body edge is _PIN_LENGTH inward). rotation: left=0
      (points +x into body), right=180, bottom=90 (points +y up into body),
      top=270. NOT to be read as functional grouping — it is a faithful mirror of
      the physical package pinout.
    """
    half_w: float
    half_h: float
    pin_placements: list[tuple["KiCadSymbolPin", float, float, int]]


def _assign_pin_sides(pins: list["KiCadSymbolPin"]) -> dict[str, list["KiCadSymbolPin"]]:
    """Partition pins onto four edges by their PHYSICAL package coordinate.

    Returns {"left": [...], "right": [...], "top": [...], "bottom": [...]} where
    each list is ordered faithfully to the physical package: left/right top->bottom
    by row, top/bottom left->right by column. This is a physical-pinout mirror, NOT
    a functional (power-up / gnd-down) grouping.

    Number-shape classes (repo law: no silent fallback):
      - BGA  `^[A-Z]{1,2}[0-9]+$` (A1, K16, AA3): (row letter, col number) ->
        perimeter projection to the nearest package edge.
      - numeric `^[0-9]+$`:
          * <= 24 pins  -> DIP/SOIC two-side mirror (left 1..N/2 top->bottom,
            right N/2+1..N BOTTOM->top).
          * >  24 pins  -> QFP counter-clockwise perimeter walk.
      - anything else / mixed -> ValueError (fail-fast, lists the offenders).
    """
    numbers = [p.number.strip().upper() for p in pins]
    bga = [_BGA_RE.match(n) for n in numbers]
    numeric = [bool(_NUM_RE.match(n)) for n in numbers]

    if all(m is not None for m in bga):
        return _assign_bga(pins, bga)  # type: ignore[arg-type]
    if all(numeric):
        return _assign_numeric(pins, [int(n) for n in numbers])

    offenders = [p.number for p, m, num in zip(pins, bga, numeric) if m is None and not num]
    if offenders:
        raise ValueError(
            "cannot assign four-edge pin sides: pin numbers are neither uniform "
            "BGA (^[A-Z]{1,2}[0-9]+$) nor uniform numeric; unparseable/mixed pin "
            f"numbers: {', '.join(offenders[:20])}"
            + (f" (+{len(offenders) - 20} more)" if len(offenders) > 20 else "")
        )
    # uniform-shape requirement not met (e.g. some BGA + some numeric) -> fail-fast.
    raise ValueError(
        "cannot assign four-edge pin sides: pin numbering mixes BGA and numeric "
        "styles; a symbol must have one uniform pin-number scheme"
    )


def _assign_bga(pins: list["KiCadSymbolPin"],
                matches: list[re.Match]) -> dict[str, list["KiCadSymbolPin"]]:
    # row letter -> y index (order of appearance sorted), col number -> x index.
    row_letters = sorted({m.group(1) for m in matches})
    row_index = {letter: i for i, letter in enumerate(row_letters)}
    col_numbers = sorted({int(m.group(2)) for m in matches})
    col_index = {num: i for i, num in enumerate(col_numbers)}
    n_rows = len(row_letters)
    n_cols = len(col_numbers)

    sides: dict[str, list[tuple[float, "KiCadSymbolPin"]]] = {"left": [], "right": [], "top": [], "bottom": []}
    for pin, m in zip(pins, matches):
        ri = row_index[m.group(1)]           # 0 = top row (A)
        ci = col_index[int(m.group(2))]      # 0 = left col
        # normalized distance (0..1) to each of the four edges.
        d_left = ci / max(n_cols - 1, 1)
        d_right = 1.0 - d_left
        d_top = ri / max(n_rows - 1, 1)
        d_bottom = 1.0 - d_top
        # nearest edge; tie -> prefer left/right (per BR).
        best = min(
            (("left", d_left), ("right", d_right), ("top", d_top), ("bottom", d_bottom)),
            key=lambda kv: (kv[1], {"left": 0, "right": 1, "top": 2, "bottom": 3}[kv[0]]),
        )[0]
        # edge-local order key: left/right by row (top->bottom); top/bottom by col.
        order = ri if best in ("left", "right") else ci
        sides[best].append((order, pin))

    return {edge: [p for _o, p in sorted(items, key=lambda t: t[0])] for edge, items in sides.items()}


def _assign_numeric(pins: list["KiCadSymbolPin"],
                    values: list[int]) -> dict[str, list["KiCadSymbolPin"]]:
    # order pins by ascending pin number (physical sequence around the package).
    order = sorted(range(len(pins)), key=lambda i: values[i])
    seq = [pins[i] for i in order]
    n = len(seq)
    result: dict[str, list["KiCadSymbolPin"]] = {"left": [], "right": [], "top": [], "bottom": []}

    if n <= 24:
        # DIP/SOIC two-side mirror: left 1..ceil(N/2) top->bottom, right rest BOTTOM->top.
        half = (n + 1) // 2
        result["left"] = seq[:half]
        result["right"] = list(reversed(seq[half:]))
        return result

    # QFP counter-clockwise perimeter walk. Distribute as evenly as possible,
    # remainder favours left then bottom (per BR).
    base, rem = divmod(n, 4)
    counts = [base, base, base, base]  # [left, bottom, right, top]
    for i in range(rem):
        counts[i] += 1  # order left, bottom, right, top -> left/bottom get extras
    left_n, bottom_n, right_n, top_n = counts
    idx = 0
    result["left"] = seq[idx:idx + left_n]; idx += left_n              # top->bottom
    result["bottom"] = seq[idx:idx + bottom_n]; idx += bottom_n        # left->right
    result["right"] = list(reversed(seq[idx:idx + right_n])); idx += right_n  # bottom->top
    result["top"] = list(reversed(seq[idx:idx + top_n]))               # right->left
    return result


def _symbol_geometry(pins: list["KiCadSymbolPin"], min_half_h: float = 20.0,
                     pin_pitch: float = _PIN_PITCH,
                     pin_length: float = _PIN_LENGTH) -> _SymbolGeometry:
    """Compute the four-edge body rectangle + per-pin placements.

    Left/right pin counts set the body HEIGHT; top/bottom counts set the WIDTH.
    Each edge keeps `_EDGE_MARGIN` clear at both corners so a pin never sits on a
    corner. Pins are laid on a `pin_pitch` grid, centred on each edge.

    `pin_pitch` defaults to `_PIN_PITCH` (1.27 mm) so existing callers are
    unchanged. A caller drawing a dense subset on ONE symbol (e.g. a per-page
    50–74-ball MCU subset) can pass a larger pitch so adjacent pin NAME text
    (1.27 mm tall) does not overlap into a vertical smear.
    """
    sides = _assign_pin_sides(pins)
    left, right, top, bottom = sides["left"], sides["right"], sides["top"], sides["bottom"]

    vert_max = max(len(left), len(right))
    horiz_max = max(len(top), len(bottom))
    # body span each edge needs: (count-1) pitch for the pins + a margin each end.
    need_h = (vert_max - 1) * pin_pitch + 2 * _EDGE_MARGIN if vert_max else 0.0
    need_w = (horiz_max - 1) * pin_pitch + 2 * _EDGE_MARGIN if horiz_max else 0.0
    half_h = round(max(min_half_h, need_h / 2 + 2.54), 2)
    half_w = round(max(15.24, need_w / 2 + 2.54), 2)

    placements: list[tuple["KiCadSymbolPin", float, float, int]] = []

    def _lay(edge_pins: list["KiCadSymbolPin"], axis_span: float) -> list[float]:
        # centred coordinates along an edge of half-span `axis_span`, top/left first.
        c = len(edge_pins)
        if c == 0:
            return []
        total = (c - 1) * pin_pitch
        start = total / 2  # first pin sits at +start (top for vertical, left for horiz)
        return [round(start - i * pin_pitch, 2) for i in range(c)]

    # left edge: x = outer endpoint (body edge -half_w, pin extends further -x),
    # y descends from top. rot=0 (points +x into body).
    for pin, y in zip(left, _lay(left, half_h)):
        placements.append((pin, round(-half_w - pin_length, 2), y, 0))
    # right edge: rot=180, y descends top->bottom.
    for pin, y in zip(right, _lay(right, half_h)):
        placements.append((pin, round(half_w + pin_length, 2), y, 180))
    # bottom edge: y = -half_h - pin_length (outer, below body), rot=90 (points +y up).
    # _lay gives left->right when we negate (start is +, but x should go left->right).
    bx = _lay(bottom, half_w)
    for pin, x in zip(bottom, bx):
        placements.append((pin, round(-x, 2), round(-half_h - pin_length, 2), 90))
    # top edge: y = +half_h + pin_length (above body), rot=270. left->right visually
    # but `top` list is already right->left (QFP walk) / left->right (assign) — we lay
    # by the same negated-x mapping so index0 -> +x (right) matching list order.
    tx = _lay(top, half_w)
    for pin, x in zip(top, tx):
        placements.append((pin, round(x, 2), round(half_h + pin_length, 2), 270))

    return _SymbolGeometry(half_w=half_w, half_h=half_h, pin_placements=placements)


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
    if not rows:
        raise ValueError("pin table has no rows")

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


def emit_kicad_symbol(
    symbol_name: str,
    pins: list,
    output_path: str | Path,
    *,
    footprint_filter: str = "",
    datasheet: str = "",
    evidence: str = "bodesign generated; raw_pdf_text_committed=false",
    description: str = "",
) -> KiCadSymbolEmitResult:
    """Generic part symbol generator (G6): any pin list → a valid `.kicad_sym`.

    `pins` is a list of `KiCadSymbolPin` or simple dicts `{number, name, type}`
    (type ∈ I/O/A/S/-; power/NC inferred from the name). Use this for any part
    whose pinout was harvested from a datasheet (orchestrate the `datasheets`
    skill), beyond the ST-specific `emit_kicad_symbol_library_from_pin_table`.
    """
    norm: list[KiCadSymbolPin] = []
    for p in pins:
        if isinstance(p, KiCadSymbolPin):
            norm.append(p)
        else:
            name = str(p.get("name", ""))
            norm.append(KiCadSymbolPin(number=str(p.get("number", "")), name=name,
                                       kind=_kicad_pin_kind(name, str(p.get("type", "")))))
    if not norm:
        raise ValueError("no pins provided")
    library = _generic_symbol_library(symbol_name, norm, footprint_filter, datasheet, evidence,
                                      description or f"{symbol_name} project-local generated symbol")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(library, encoding="utf-8")
    return KiCadSymbolEmitResult(
        symbol_name=symbol_name, library_path=str(destination), pin_count=len(norm),
        source_artifact="(generic pin list)", evidence_property=evidence,
    )


def _generic_symbol_library(symbol_name: str, pins: list[KiCadSymbolPin], footprint_filter: str,
                            datasheet: str, evidence: str, description: str) -> str:
    geom = _symbol_geometry(pins)
    left = round(-geom.half_w - _PIN_LENGTH, 2)
    right = round(geom.half_w + _PIN_LENGTH, 2)
    top = geom.half_h
    bottom = -geom.half_h
    return (
        "(kicad_symbol_lib\n"
        f"\t(version {SYMBOL_LIB_VERSION})\n"
        "\t(generator \"bodesign\")\n"
        "\t(generator_version \"1.0\")\n"
        f"\t(symbol \"{_escape(symbol_name)}\"\n"
        "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
        f"{_property('Reference', 'U', left, top + 3.81, visible=True)}\n"
        f"{_property('Value', symbol_name, right - 15.24, top + 3.81, visible=True)}\n"
        f"{_property('Footprint', '', left, bottom - 3.81, visible=False)}\n"
        f"{_property('Datasheet', datasheet, 0, 0, visible=False)}\n"
        f"{_property('Description', description, 0, 0, visible=False)}\n"
        f"{_property('BodesignEvidence', evidence, 0, 0, visible=False)}\n"
        f"{_property('ki_fp_filters', footprint_filter, 0, 0, visible=False)}\n"
        f"\t\t(symbol \"{_escape(symbol_name)}_0_1\"\n"
        "\t\t\t(rectangle\n"
        f"\t\t\t\t(start {-geom.half_w} {bottom})\n\t\t\t\t(end {geom.half_w} {top})\n"
        "\t\t\t\t(stroke (width 0.254) (type default))\n\t\t\t\t(fill (type background))\n"
        "\t\t\t)\n\t\t)\n"
        f"\t\t(symbol \"{_escape(symbol_name)}_1_1\"\n"
        + "\n".join(_pin_block(pin, x, y, rot) for pin, x, y, rot in geom.pin_placements)
        + "\n\t\t)\n\t)\n)\n"
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
    geom = _symbol_geometry(pins, min_half_h=40.0)
    left = round(-geom.half_w - _PIN_LENGTH, 2)
    right = round(geom.half_w + _PIN_LENGTH, 2)
    top = geom.half_h
    bottom = -geom.half_h

    evidence = _evidence_property(pin_table)
    description = "Project-local symbol generated from a verified pin table."
    return (
        "(kicad_symbol_lib\n"
        f"\t(version {SYMBOL_LIB_VERSION})\n"
        "\t(generator \"bodesign\")\n"
        "\t(generator_version \"1.0\")\n"
        f"\t(symbol \"{_escape(symbol_name)}\"\n"
        "\t\t(exclude_from_sim no)\n"
        "\t\t(in_bom yes)\n"
        "\t\t(on_board yes)\n"
        f"{_property('Reference', 'U', left, top + 3.81, visible=True)}\n"
        f"{_property('Value', symbol_name, right - 15.24, top + 3.81, visible=True)}\n"
        f"{_property('Footprint', '', left, bottom - 3.81, visible=False)}\n"
        f"{_property('Datasheet', '', 0, 0, visible=False)}\n"
        f"{_property('Description', description, 0, 0, visible=False)}\n"
        f"{_property('BodesignEvidence', evidence, 0, 0, visible=False)}\n"
        f"{_property('ki_keywords', '', 0, 0, visible=False)}\n"
        f"{_property('ki_fp_filters', DEFAULT_FOOTPRINT_FILTER, 0, 0, visible=False)}\n"
        f"\t\t(symbol \"{_escape(symbol_name)}_0_1\"\n"
        "\t\t\t(rectangle\n"
        f"\t\t\t\t(start {-geom.half_w} {bottom})\n"
        f"\t\t\t\t(end {geom.half_w} {top})\n"
        "\t\t\t\t(stroke (width 0.254) (type default))\n"
        "\t\t\t\t(fill (type background))\n"
        "\t\t\t)\n"
        "\t\t)\n"
        f"\t\t(symbol \"{_escape(symbol_name)}_1_1\"\n"
        + "\n".join(_pin_block(pin, x, y, rot) for pin, x, y, rot in geom.pin_placements)
        + "\n\t\t)\n"
        "\t)\n"
        ")\n"
    )


def _fmt(v: float) -> str:
    """Render a mm float the way the legacy literals were written: no trailing\n    zeros, integers as bare ints. `_fmt(5.08)=='5.08'`, `_fmt(1.27)=='1.27'` so a\n    scale==1.0 caller is byte-identical to the old hard-coded `5.08`/`1.27`."""
    r = round(float(v), 4)
    if r == int(r):
        return str(int(r))
    return repr(r)


def _pin_block(pin: KiCadSymbolPin, x: float, y: float, rotation: int,
               pin_length: float = _PIN_LENGTH, text_scale: float = 1.0) -> str:
    # text_scale==1.0 & pin_length==_PIN_LENGTH => byte-identical to the legacy
    # literals (5.08 / 1.27). A scaled per-page symbol (large pin_pitch) passes a
    # matching pin_length and text_scale so the pin graphic AND its name/number
    # text grow with the pitch instead of staying a 1.27 mm smear on a huge body.
    ln = _fmt(pin_length)
    ch = _fmt(round(1.27 * text_scale, 4))
    return (
        f"\t\t\t(pin {pin.kind} line\n"
        f"\t\t\t\t(at {x} {y} {rotation})\n"
        f"\t\t\t\t(length {ln})\n"
        f"\t\t\t\t(name \"{_escape(pin.name)}\" (effects (font (size {ch} {ch}))))\n"
        f"\t\t\t\t(number \"{_escape(pin.number)}\" (effects (font (size {ch} {ch}))))\n"
        "\t\t\t)"
    )


def _property(name: str, value: str, x: float, y: float, visible: bool,
              text_scale: float = 1.0) -> str:
    # text_scale==1.0 => byte-identical 1.27 literal (legacy). Scaled per-page
    # symbols grow the Reference/Value text with the pin pitch.
    hide = "" if visible else " (hide yes)"
    ch = _fmt(round(1.27 * text_scale, 4))
    return (
        f"\t\t(property \"{_escape(name)}\" \"{_escape(value)}\"\n"
        f"\t\t\t(at {x} {y} 0)\n"
        f"\t\t\t(effects (font (size {ch} {ch})){hide})\n"
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
