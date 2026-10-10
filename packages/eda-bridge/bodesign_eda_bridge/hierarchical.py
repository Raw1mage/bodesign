"""Root + N leaf `.kicad_sch` emission (plan eda-bridge_multi-sheet-subsystem-schematics, A4).

Lives beside `kicad_emit` rather than inside it: the single-file emitter is 228 KB and
is being edited by other work, so the multi-sheet path is additive. It CALLS
`emit_kicad_schematic` once per leaf rather than reimplementing symbol/label geometry,
which is what keeps a leaf byte-comparable with the flat output.

ROUTE SELECTION IS BY DECLARATION, NOT BY COUNT (design.md DD-10)
------------------------------------------------------------------
    no `sheet` anywhere            -> the original flat file, untouched
    `sheet` on every component     -> root + N leaves, INCLUDING N == 1

An explicitly declared single sheet is NOT the legacy path. Collapsing them would make
a caller's explicit request indistinguishable from having asked for nothing.

CROSS-SHEET CONNECTIVITY
------------------------
A net is emitted onto every leaf holding at least one of its nodes, under its own name.
Same-named `global_label`s on two leaves join into one net -- measured on real
kicad-cli 9.0.9 in Phase 1 (TV-1 treatment, TV-2 control, plus a sheetpath witness).
A net whose nodes span sheets is forced onto label connectivity on each leaf, because a
drawn wire cannot cross a file boundary. No endpoint is ever dropped: `nets_by_sheet`
partitions NODES, and `assert_no_endpoint_lost` re-counts them against the input.

FAILURE CLEANUP REMOVES ONLY WHAT THIS CALL CREATED (DD-12c)
-------------------------------------------------------------
Paths are recorded as they are created. A path that already exists is never created --
it raises `E_OUTPUT_PATH_OCCUPIED` before anything is written -- and therefore is never
removed. Deleting by pattern would destroy pre-existing user files on a failure they
did not cause.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from .kicad_emit import (
    SCHEMATIC_VERSION,
    EmitComponent,
    EmitNet,
    SchematicEmitResult,
    _project_document,
    _native_pitch_and_count,
    _page_pitch_floor,
    _uid,
    _vendor_sym_scale,
    emit_kicad_schematic,
    load_symbol,
)
from .partition import PartitionError, ReplicaView, SheetMap, partition_components

#: DD-15: the only engine this seam knows. Any other value is refused.
LAYOUT_ENGINE_ELK = "elk-layered"
#: Ground classifier used ONLY for the engine's drawn-net policy (mirrors the
#: legacy router's `_power_net_kind(...) == "gnd"` branch).
_GND_RE = re.compile(r"^(gnd|gndd?|agnd|dgnd|pgnd|vss[a-z0-9_]*|vssa)$", re.IGNORECASE)

EMIT_MODE_LEGACY = "single-legacy"
EMIT_MODE_HIERARCHICAL = "hierarchical"

#: Root sheet-block grid (data-schema §RootSheetBlock). Deterministic: sheet order is
#: SheetMap order, so the same spec always yields the same root bytes.
_BLOCK_W_MM = 30.0
_BLOCK_H_MM = 20.0
_BLOCK_X0_MM = 30.0
_BLOCK_Y0_MM = 30.0
_BLOCK_DX_MM = 45.0
_BLOCK_DY_MM = 35.0
_BLOCKS_PER_ROW = 4

#: Root is page 1; leaves start at 2. Q2 (is that KiCad-mandated?) is still open --
#: this mirrors the one real board sampled, and is not claimed to be required.
_FIRST_LEAF_PAGE = 2


class HierarchicalEmitError(ValueError):
    """Emission contract violation. Carries `code` so callers branch on identity."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


@dataclass
class HierarchicalEmitResult:
    """Frozen in data-schema.json §HierarchicalEmitResult BEFORE implementation."""

    project_dir: str
    #: DD-10: the ROOT on the declared route, the flat file on the legacy route.
    schematic_path: str
    project_path: str
    emit_mode: str
    #: Real files only, root first. Appended only AFTER a successful write.
    files: list[str] = field(default_factory=list)
    leaf_paths: dict[str, str] = field(default_factory=dict)
    #: Exactly the paths this call created; the cleanup set (DD-12c).
    created_paths: list[str] = field(default_factory=list)
    cross_sheet_nets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: The per-leaf emit results, so a caller keeps access to counts/warnings.
    leaf_results: dict[str, SchematicEmitResult] = field(default_factory=dict)
    #: sheet -> how many replica symbols were marked netlist-neutral on it. An
    #: EMPTY dict and a dict of zeros mean different things: empty == no leaf was
    #: asked to draw a replica, zero == a leaf was processed and marked none.
    replica_marked: dict[str, int] = field(default_factory=dict)
    #: Total replica views the emission was ASKED for, from the SheetMap. Reported
    #: beside `replica_marked` so "none requested" and "requested but not drawn"
    #: cannot share an output.
    replica_views_requested: int = 0
    #: DD-14 clause 2, per subsystem-view sheet: how many cross-sheet nets already
    #: carried a global_label, how many were added, how many could not be anchored.
    #: Three counters rather than one, because "nothing needed adding" and "nothing
    #: got added" are different states with the same single-number appearance.
    continuation_labels: dict[str, dict] = field(default_factory=dict)
    #: DD-14 clause 3, per leaf: measured drawn extent, applied shift, and the
    #: paper in/out. `already_fits` is a distinct status from `measured`.
    page_fit: dict[str, dict] = field(default_factory=dict)
    #: DD-14 clause 5, per view sheet: {net: local_slice_size} for the subsystem
    #: nets that were NOT drawn locally because their slice exceeds the guarded
    #: route. Present so "this view drew everything" and "this view silently left
    #: nets on labels" cannot share an empty output.
    view_nets_label_only: dict[str, dict] = field(default_factory=dict)
    #: Round 46, per leaf: how many lib_ids the size-aware layout actually MEASURED
    #: versus how many fell back to the minimum cell because their library or symbol
    #: was absent. A defaulted cell is a guessed size, and a guess that is not
    #: counted is indistinguishable from a measurement.
    symbol_boxes: dict[str, dict] = field(default_factory=dict)
    #: DD-15: per engine-mode leaf, the engine receipt (versions, graph/solution
    #: hashes, verification). Empty == no leaf went through an engine.
    engine_reports: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "project_dir": self.project_dir,
            "schematic_path": self.schematic_path,
            "project_path": self.project_path,
            "emit_mode": self.emit_mode,
            "files": list(self.files),
            "leaf_paths": dict(self.leaf_paths),
            "created_paths": list(self.created_paths),
            "cross_sheet_nets": list(self.cross_sheet_nets),
            "warnings": list(self.warnings),
            "replica_marked": dict(self.replica_marked),
            "replica_views_requested": self.replica_views_requested,
            # DD-15: present (possibly empty) so "no engine ran" is a real state.
            "engine_reports": dict(self.engine_reports),
            "page_fit": dict(self.page_fit),
        }


class _CreationLedger:
    """Tracks paths created by ONE call, so cleanup can be exact.

    `claim` refuses a path that already exists. That refusal is what makes the
    cleanup safe: a pre-existing file is never in the ledger, so it can never be
    removed by a rollback.
    """

    def __init__(self):
        self.paths: list[Path] = []

    def claim(self, path: Path) -> Path:
        if path.exists():
            raise HierarchicalEmitError(
                "E_OUTPUT_PATH_OCCUPIED",
                f"{path} already exists and was not created by this operation. "
                f"Refusing to overwrite: cleanup removes only what this call "
                f"created, so an overwrite could not be rolled back.",
                path=str(path),
            )
        return path

    def record(self, path: Path) -> None:
        self.paths.append(path)

    def rollback(self) -> list[str]:
        removed: list[str] = []
        for path in reversed(self.paths):
            try:
                if path.exists():
                    path.unlink()
                    removed.append(str(path))
            except OSError:
                # A path we cannot remove is reported, never silently dropped.
                removed.append(f"{path} (unlink failed)")
        return removed


def nets_by_sheet(
    nets: list[EmitNet],
    ref_to_sheet: dict[str, str],
) -> tuple[dict[str, list[EmitNet]], list[str], list[str]]:
    """Split nets per leaf. Returns (per_sheet, cross_sheet_names, orphan_nodes).

    A node whose ref is on no sheet is an ORPHAN and is returned rather than dropped:
    silently discarding it would delete an endpoint the caller declared.
    """
    per_sheet: dict[str, list[EmitNet]] = {}
    cross: list[str] = []
    orphans: list[str] = []
    for net in nets:
        by_sheet: dict[str, list[tuple[str, str]]] = {}
        for ref, pin in net.nodes:
            sheet = ref_to_sheet.get(ref)
            if sheet is None:
                orphans.append(f"{net.name}:{ref}.{pin}")
                continue
            by_sheet.setdefault(sheet, []).append((ref, pin))
        if len(by_sheet) > 1:
            cross.append(net.name)
        for sheet, nodes in by_sheet.items():
            per_sheet.setdefault(sheet, []).append(EmitNet(name=net.name, nodes=nodes))
    return per_sheet, cross, orphans


def assert_no_endpoint_lost(
    nets: list[EmitNet],
    per_sheet: dict[str, list[EmitNet]],
    orphans: list[str],
) -> None:
    """Every input node lands on exactly one leaf, or is reported as an orphan.

    Raised rather than asserted so `python -O` cannot silence it.
    """
    total_in = sum(len(net.nodes) for net in nets)
    total_out = sum(len(net.nodes) for nets_ in per_sheet.values() for net in nets_)
    if total_in != total_out + len(orphans):
        raise HierarchicalEmitError(
            "E_ENDPOINT_LOST",
            f"node accounting broken: input={total_in} placed={total_out} "
            f"orphans={len(orphans)}",
            input_nodes=total_in, placed_nodes=total_out, orphans=len(orphans),
        )


#: The two NEUTRALITY flags, and only those. Measured on kicad-cli 9.0.9 (DD-13
#: clauses 1-3): `on_board no` removes the second `(comp ...)` entry and its pins
#: from the netlist, `in_bom no` removes the second BOM row. Both are required, for
#: different reasons, and `dnp yes` does NEITHER.
#:
#: `dnp yes` was carried here in round 45 as a VISUAL marker and is WITHDRAWN in
#: round 46 (DD-14 clause 4). DNP means do-not-populate -- a claim about the physical
#: board -- while a replica is the SAME populated component drawn a second time.
#: Netlist and BOM equality showed only that those two exports are insensitive to the
#: flag; it never showed the semantic was safe. The reader-visible distinction is now
#: an explicit text annotation naming the reference view and the home sheet.
_CANONICAL_FLAGS = "(in_bom yes) (on_board yes) (dnp no)"
_REPLICA_FLAGS = "(in_bom no) (on_board no) (dnp no)"

#: DD-14 clause 4: the words a reader needs, in words. `{ref}` is the canonical id
#: the user's ruling makes load-bearing; `{home}` is where its electrical truth lives.
_REPLICA_ANNOTATION = "{ref} \u2014 reference view; home: {home}"

_SYMBOL_REF_RE = re.compile(
    r'\(property "Reference" "([^"]+)"', re.M)


def _mark_replica_symbols(text: str, replica_refs: set[str]) -> tuple[str, int]:
    """Flip the two neutrality flags on exactly the replica symbols in a leaf.

    Operates on the LANDED emitter output rather than emitting a second symbol
    shape, so a replica's geometry is byte-comparable with a canonical symbol and
    only the two flags differ. Returns (text, marked_count); the CALLER compares the
    count against what it expected, because a substitution that silently matched
    nothing would leave a replica contributing real nodes to the netlist while every
    file still existed.
    """
    if not replica_refs:
        return text, 0
    out: list[str] = []
    marked = 0
    cursor = 0
    for match in re.finditer(r"^  \(symbol\n", text, re.M):
        # The balanced block starts at the '(' itself, NOT at the line start: taking
        # the line start would drop the two-space indent from the rewritten copy and
        # leave the block's last two characters behind as a stray ' )'.
        block_start = text.index("(", match.start())
        block = _balanced_sexpr(text, block_start)
        ref_match = _SYMBOL_REF_RE.search(block)
        if ref_match is None or ref_match.group(1) not in replica_refs:
            continue
        if _CANONICAL_FLAGS not in block:
            raise HierarchicalEmitError(
                "E_REPLICA_FLAGS_NOT_FOUND",
                f"the emitted symbol block for {ref_match.group(1)!r} does not "
                f"carry {_CANONICAL_FLAGS!r}, so the neutrality flags could not be "
                f"applied. Refusing rather than writing a replica that would "
                f"contribute netlist nodes and a BOM row.",
                ref=ref_match.group(1),
            )
        out.append(text[cursor:block_start])
        out.append(block.replace(_CANONICAL_FLAGS, _REPLICA_FLAGS, 1))
        cursor = block_start + len(block)
        marked += 1
    out.append(text[cursor:])
    return "".join(out), marked


def _balanced_sexpr(text: str, start: int) -> str:
    """The balanced s-expression beginning at `start` (which must be a '(')."""
    depth = 0
    in_string = False
    index = start
    while index < len(text):
        char = text[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
        index += 1
    raise HierarchicalEmitError(
        "E_LEAF_SEXPR_UNBALANCED",
        "an s-expression in the emitted leaf never closes; refusing to guess where "
        "the symbol block ends.",
        offset=start,
    )


#: DD-14 clause 3: the page geometry the fit procedure works against. Landscape
#: (width, height) in mm, matching the emitter's own paper table.
_PAPER_DIMS_MM = {
    "A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0),
    "A1": (841.0, 594.0), "A0": (1189.0, 841.0),
}
_PAPER_LADDER = ["A4", "A3", "A2", "A1", "A0"]
#: Clear of the PAPER edge is not enough: KiCad draws a sheet frame inset from the
#: paper, with the zone rulers between them. At 12.7 mm the charger page's left-edge
#: global labels were measured drawing straight through the frame rule and the zone
#: letters. 25.4 mm clears the frame, the ruler band, and the leftward glyph+text
#: growth of an angle-180 label.
_PAGE_MARGIN_MM = 25.4

#: DD-14 clause 5: the largest LOCAL SLICE a subsystem view may draw as wires.
#:
#: NOT a tuning knob and NOT a guessed threshold. `kicad_emit.py` routes a 2-endpoint
#: net through a GUARDED path (`_guard_route` + `_route_clears_ledger` +
#: `_route_clears_points`, which refuses a route that grazes a foreign pin and falls
#: back to a label). Nets with more endpoints take the trunk+stub path, whose stub
#: endpoints can land on a foreign pin and FUSE two nets -- and because a view net
#: also carries a continuation `global_label`, that short then propagates across
#: every sheet sharing the label. MEASURED on btdongle: with every cross-sheet net
#: drawn, 7 node classes collapsed into 2; scoped to subsystem nets, 5 collapsed
#: into 1, the fusers being the 9-node SYS and 7-node BATT rails.
#:
#: A net above this bound is NOT silently dropped: it stays on label continuation
#: and is reported in `view_nets_label_only` with its measured slice size.
VIEW_LOCAL_MAX_NODES = 3

_TAIL_MARKER = "  (sheet_instances"
_XY_RE = re.compile(r"\(xy (-?[\d.]+) (-?[\d.]+)\)")
_AT_RE = re.compile(r"\(at (-?[\d.]+) (-?[\d.]+)")
_PLACED_AT_RE = re.compile(
    r'\(lib_id "([^"]+)"\)\s*\(at (-?[\d.]+) (-?[\d.]+)')
_EXISTING_GLOBAL_RE = re.compile(r'\(global_label "([^"]+)"')


def _insert_blocks(text: str, blocks: list[str]) -> str:
    """Splice extra top-level blocks in before the document tail."""
    if not blocks:
        return text
    marker = text.find(_TAIL_MARKER)
    if marker < 0:
        raise HierarchicalEmitError(
            "E_LEAF_TAIL_NOT_FOUND",
            "the emitted leaf has no `(sheet_instances` tail, so there is no known "
            "insertion point for the annotation and continuation blocks. Refusing "
            "to append at a guessed offset.",
        )
    return text[:marker] + "\n".join(blocks) + "\n" + text[marker:]


def _annotation_block(message: str, x: float, y: float) -> str:
    return (
        f'  (text "{message}" (exclude_from_sim no) '
        f"(at {round(x, 4)} {round(y, 4)} 0)\n"
        f'    (effects (font (size 1.27 1.27)) (justify left bottom)) '
        f'(uuid "{_uid()}"))'
    )


def _continuation_label_block(
    name: str, x: float, y: float, angle: int = 0,
) -> str:
    # `justify right` is what makes an angle-180 label grow LEFTWARD from its pin
    # instead of drawing its text back across the symbol it is attached to.
    justify = "right" if angle == 180 else "left"
    return (
        f'  (global_label "{name}" (shape bidirectional) '
        f"(at {round(x, 4)} {round(y, 4)} {angle})\n"
        f'    (effects (font (size 1.27 1.27)) (justify {justify})) '
        f'(uuid "{_uid()}"))'
    )


def _leaf_pin_positions(text: str) -> dict[tuple[str, str], tuple[float, float]]:
    """(ref, pin) -> absolute mm, read back from the LANDED leaf bytes."""
    from .replica_fidelity import parse_placed_symbols, pin_endpoints_absolute

    marker = text.find("(lib_symbols")
    if marker < 0:
        return {}
    lib_source = _balanced_sexpr(text, marker)
    out: dict[tuple[str, str], tuple[float, float]] = {}
    for symbol in parse_placed_symbols(text):
        pins, _why = pin_endpoints_absolute(symbol, lib_source)
        for pin, position in pins.items():
            out[(symbol.ref, pin)] = position
    return out


def _replica_annotation_blocks(
    text: str,
    replica_refs: set[str],
    home_by_ref: dict[str, str],
) -> list[str]:
    """DD-14 clause 4: one visible `reference view; home: <sheet>` note per replica.

    The note is anchored just under the symbol's OWN body box, read from the leaf's
    embedded library definition. A fixed offset was measured to fail: at 20.32 mm
    below the origin the notes landed as caption rows among unrelated pin names, and
    a reviewer could only infer which symbol each belonged to.
    """
    if not replica_refs:
        return []
    from .replica_fidelity import parse_placed_symbols

    marker = text.find("(lib_symbols")
    boxes = _lib_local_boxes(_balanced_sexpr(text, marker)) if marker >= 0 else {}
    blocks: list[str] = []
    annotated: set[str] = set()
    for symbol in parse_placed_symbols(text):
        if symbol.ref not in replica_refs or symbol.ref in annotated:
            continue
        if symbol.on_board != "no":
            # The canonical placement of the same ref, if the leaf carries one.
            continue
        message = _REPLICA_ANNOTATION.format(
            ref=symbol.ref, home=home_by_ref.get(symbol.ref, "?"))
        box = boxes.get(symbol.lib_id)
        if box is None:
            # No embedded geometry: the note still gets placed, near the origin,
            # and the fallback is visible in the output rather than assumed.
            anchor_y = symbol.y + 5.08
        else:
            anchor_y = symbol.y - box[1] + 2.54
        blocks.append(_annotation_block(message, symbol.x - 5.08, anchor_y))
        annotated.add(symbol.ref)
    missing = sorted(replica_refs - annotated)
    if missing:
        raise HierarchicalEmitError(
            "E_REPLICA_ANNOTATION_NOT_PLACED",
            f"no annotation could be placed for replica ref(s) {missing}: the "
            f"landed leaf carries no `on_board no` placement for them. An "
            f"unannotated replica reads as a placed part, which is the exact "
            f"confusion the visible notation exists to prevent.",
            refs=missing,
        )
    return blocks


#: Round 46 layout constants. The 45 mm fixed pitch these replace was measured to
#: overlap: the Pico 2 W module body is 43.18 mm tall and the ETA6003 30.48 mm, so a
#: 45 mm row pitch left no room for either one's refdes and value rows and the two
#: bodies met. Cell size is now derived from each symbol's OWN drawn box.
_CELL_GUTTER_MM = 10.16   # clear band between adjacent drawn bodies
_CELL_TEXT_BAND_MM = 6.35  # refdes above and value below the body
_CELL_MIN_MM = 15.24
_LAYOUT_ORIGIN_MM = 35.56
#: Sideways shift applied to odd rows. 8 x 1.27 mm, so origins stay on the KiCad
#: connection grid. See the use site for the short it prevents.
_ROW_STAGGER_MM = 10.16
_LIB_SYMBOL_RE = re.compile(r'\(symbol "([^"]+)"')


def _library_symbol_boxes(
    symbol_dirs, lib_ids: set[str],
) -> tuple[dict[str, tuple[float, float, float, float]], dict[str, int]]:
    """lib_id -> local drawn box, read from the .kicad_sym sources on disk.

    Returns (boxes, report). `report` keeps "measured" apart from "library absent"
    apart from "symbol absent in an existing library": all three would otherwise
    arrive as a missing key, and a defaulted cell size is a guess that must be
    visible rather than inferred from a symbol that happens to look cramped.
    """
    report = {"measured": 0, "library_absent": 0, "symbol_absent": 0}
    boxes: dict[str, tuple[float, float, float, float]] = {}
    if isinstance(symbol_dirs, (str, Path)):
        dirs = [Path(symbol_dirs)]
    else:
        dirs = [Path(d) for d in (symbol_dirs or ())]
    sources: dict[str, str] = {}
    for lib_id in sorted(lib_ids):
        if ":" not in lib_id:
            report["symbol_absent"] += 1
            continue
        library, symbol_name = lib_id.split(":", 1)
        if library not in sources:
            found = None
            for directory in dirs:
                candidate = directory / f"{library}.kicad_sym"
                if candidate.is_file():
                    found = candidate.read_text(encoding="utf-8", errors="replace")
                    break
            sources[library] = found or ""
        source = sources[library]
        if not source:
            report["library_absent"] += 1
            continue
        match = next(
            (m for m in _LIB_SYMBOL_RE.finditer(source)
             if m.group(1) == symbol_name), None)
        if match is None:
            report["symbol_absent"] += 1
            continue
        block = _balanced_sexpr(source, source.index("(", match.start()))
        points = [(float(a), float(b)) for a, b in _XY_RE.findall(block)]
        points += [(float(a), float(b)) for a, b in _AT_RE.findall(block)]
        if not points:
            report["symbol_absent"] += 1
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        boxes[lib_id] = (min(xs), min(ys), max(xs), max(ys))
        report["measured"] += 1
    return boxes, report


def _drawn_symbol_boxes(
    boxes: dict[str, tuple[float, float, float, float]],
    components,
    symbol_dirs,
    page_scale: float,
) -> tuple[dict[str, tuple[float, float, float, float]], dict[str, int]]:
    """Replace each library box with the box of the definition the emitter will WRITE.

    `_library_symbol_boxes` reads the .kicad_sym source, which stores a symbol at its
    native pitch and without the pin-length extension. The emitter then lifts a stored
    symbol by `_vendor_sym_scale` so its rendered pin pitch reaches the page floor, and
    draws pins that reach beyond the stored body. Neither adjustment is a small one and
    neither is a single uniform factor: measured on this board, `local:ETA6003` stores
    38.10 x 33.02 mm and lands at 114.30 x 99.06 mm (3.00x both axes), while
    `MCU_Module:RaspberryPi_Pico_W_Debug` stores 26.67 x 87.63 mm and lands at
    137.16 x 270.51 mm -- 5.14x across and 3.09x down. Predicting the landed size by
    multiplying the library box was therefore wrong for the second symbol even after
    the scale factor was right, so the box is taken from the emitted definition itself.

    Returns (boxes, report). `report` counts the lib_ids taken from the emitted
    definition apart from those left at their library value, because a cell sized from
    an unloadable symbol is a fallback and must not look like a measurement.
    """
    report = {"drawn": 0, "library_fallback": 0}
    if not boxes:
        return boxes, report
    try:
        page_floor = _page_pitch_floor(components, symbol_dirs)
    except Exception:
        report["library_fallback"] = len(boxes)
        return boxes, report
    native_cache: dict[str, tuple[float, int]] = {}
    out: dict[str, tuple[float, float, float, float]] = {}
    for lib_id, box in boxes.items():
        try:
            if lib_id.partition(":")[0].startswith("u1_"):
                scale = 1.0
            else:
                pitch, count = _native_pitch_and_count(
                    lib_id, symbol_dirs, native_cache)
                scale = _vendor_sym_scale(page_scale, pitch, page_floor, count)
            definition, _pins = load_symbol(lib_id, symbol_dirs, page_scale=scale)
            points = [(float(a), float(b))
                      for a, b in _XY_RE.findall(definition)]
            points += [(float(a), float(b))
                       for a, b in _AT_RE.findall(definition)]
            if not points:
                raise ValueError("no drawable points in emitted definition")
        except Exception:
            out[lib_id] = box
            report["library_fallback"] += 1
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        out[lib_id] = (min(xs), min(ys), max(xs), max(ys))
        report["drawn"] += 1
    return out, report


def _entry_area(entry: tuple[str, str], boxes) -> float:
    """Drawn area of one (ref, lib_id), or the default cell area when unmeasured."""
    box = boxes.get(entry[1])
    if box is None:
        return _CELL_MIN_MM * _CELL_MIN_MM
    return max(_CELL_MIN_MM, box[2] - box[0]) * max(_CELL_MIN_MM, box[3] - box[1])


def layout_sheet(
    entries: list[tuple[str, str]],
    boxes: dict[str, tuple[float, float, float, float]],
) -> dict[str, tuple[float, float]]:
    """ref -> (x, y) origin, on a grid whose cells are as large as their occupant.

    `entries` is [(ref, lib_id)] in draw order. Column count is derived from the
    member count so a five-part page does not reserve four columns of blank paper,
    and every column is as wide as its widest member rather than a fixed pitch.
    A lib_id with no measured box gets `_CELL_MIN_MM`, which is the same cell the
    old fixed grid would have given it.
    """
    count = len(entries)
    if count == 0:
        return {}
    # Round 47: cells are filled SMALLEST FIRST, so the tall multi-pin bodies land in
    # the last cells rather than between the page's left label gutter and everything
    # else. This is a placement decision with an electrical consequence, not a
    # cosmetic one: the emitter routes a continuation label to its pin as a straight
    # horizontal run, and such a run shorts every pin it passes MID-SEGMENT. Sizing
    # U1's cell correctly (which fixed the body intrusion) made its pin column three
    # times taller, so more pin rows fell on those runs -- measured on this board,
    # mid-segment pin contacts rose from 6 to 18 and three declared net classes fused
    # into one. Ordering big bodies last keeps them off the corridor between the
    # gutter and the small parts.
    order = sorted(range(count), key=lambda i: _entry_area(entries[i], boxes))
    entries = [entries[i] for i in order]
    sizes = []
    for _ref, lib_id in entries:
        box = boxes.get(lib_id)
        if box is None:
            sizes.append((_CELL_MIN_MM, _CELL_MIN_MM, 0.0, 0.0))
        else:
            sizes.append((max(_CELL_MIN_MM, box[2] - box[0]),
                          max(_CELL_MIN_MM, box[3] - box[1]),
                          box[0], box[3]))

    def grid_for(columns: int) -> tuple[list[float], list[float]]:
        widths = [0.0] * columns
        heights = [0.0] * math.ceil(count / columns)
        for index, (width, height, _lx, _ty) in enumerate(sizes):
            col = index % columns
            row = index // columns
            widths[col] = max(widths[col], width)
            heights[row] = max(heights[row], height + _CELL_TEXT_BAND_MM * 2)
        return widths, heights

    # Column count is CHOSEN, not fixed at four. A fixed count was measured to
    # produce a 141 x 270 mm portrait block for the ten-part mcu_swd page, which
    # no landscape paper below A2 accepts -- the escalation then bought a sheet
    # that was mostly blank. Picking the count whose block best matches the paper
    # aspect keeps the page on the smallest sheet that fits it.
    target_aspect = _PAPER_DIMS_MM["A4"][0] / _PAPER_DIMS_MM["A4"][1]
    best_columns = 1
    best_score = None
    for columns in range(1, count + 1):
        widths, heights = grid_for(columns)
        total_w = sum(widths) + _CELL_GUTTER_MM * (len(widths) - 1)
        total_h = sum(heights) + _CELL_GUTTER_MM * (len(heights) - 1)
        if total_h <= 0:
            continue
        score = abs(math.log((total_w / total_h) / target_aspect))
        if best_score is None or score < best_score:
            best_columns, best_score = columns, score
    columns = best_columns
    col_w, row_h = grid_for(columns)
    # Target frame usage: > 50% of A4 usable area (~175mm wide, ~105mm high)
    if len(col_w) > 1:
        raw_gx = (175.0 - sum(col_w)) / (len(col_w) - 1)
        gutter_x = max(_CELL_GUTTER_MM, min(38.1, round(raw_gx / 2.54) * 2.54))
    else:
        gutter_x = _CELL_GUTTER_MM
    if len(row_h) > 1:
        raw_gy = (105.0 - sum(row_h)) / (len(row_h) - 1)
        gutter_y = max(_CELL_GUTTER_MM, min(33.02, round(raw_gy / 2.54) * 2.54))
    else:
        gutter_y = _CELL_GUTTER_MM
    col_x = []
    cursor = _LAYOUT_ORIGIN_MM
    for width in col_w:
        col_x.append(cursor)
        cursor += width + gutter_x
    row_y = []
    cursor = _LAYOUT_ORIGIN_MM
    for height in row_h:
        row_y.append(cursor)
        cursor += height + gutter_y
    out: dict[str, tuple[float, float]] = {}
    for index, (ref, _lib_id) in enumerate(entries):
        _width, _height, local_min_x, local_max_y = sizes[index]
        col = index % columns
        row = index // columns
        # Alternate rows are shifted sideways by _ROW_STAGGER_MM so no two rows share
        # a pin x-axis. The emitter routes a connection between two rows as a straight
        # VERTICAL run down one pin's x, and such a run shorts both pins of any part
        # standing on that axis in a row between them -- measured here as R3.1+R3.2 and
        # R4.1+R4.2 sitting mid-run of the same wire, which fused two declared net
        # classes into one. The offset is 8 x 1.27 mm so every origin stays on KiCad's
        # connection grid; an off-grid origin would leave wire ends that no longer
        # merge with their pin.
        stagger = _ROW_STAGGER_MM if row % 2 else 0.0
        # screen_x = origin_x + local_x, screen_y = origin_y - local_y, so the
        # origin is offset by the symbol's own box to left/top-align the drawn
        # content in its cell instead of aligning the (often off-centre) origin.
        out[ref] = (round(col_x[col] + stagger - local_min_x, 4),
                    round(row_y[row] + local_max_y + _CELL_TEXT_BAND_MM, 4))
    return out


_WIRE_RE = re.compile(r"\(wire \(pts \(xy (-?[\d.]+) (-?[\d.]+)\) \(xy (-?[\d.]+) (-?[\d.]+)\)\)")

#: Glyph advance and line height at the 1.27 mm font the label blocks emit. Used to
#: build the rectangle a label's TEXT will occupy, which is what a reader sees
#: crossing a wire -- the anchor point alone occupies nothing.
_LABEL_GLYPH_W_MM = 0.85
_LABEL_PENNANT_MM = 2.54
_LABEL_HALF_H_MM = 1.6


def _wire_segments(text: str) -> list[tuple[float, float, float, float]]:
    """Every drawn wire run in the landed leaf, as (x1, y1, x2, y2) mm."""
    return [(float(a), float(b), float(c), float(d))
            for a, b, c, d in _WIRE_RE.findall(text)]


def _label_rect(name: str, x: float, y: float, angle: int) -> tuple[float, float, float, float]:
    """The area a continuation label's pennant plus text will cover on the page."""
    span = _LABEL_PENNANT_MM + len(name) * _LABEL_GLYPH_W_MM
    if angle == 180:
        return (x - span, y - _LABEL_HALF_H_MM, x, y + _LABEL_HALF_H_MM)
    return (x, y - _LABEL_HALF_H_MM, x + span, y + _LABEL_HALF_H_MM)


def _segment_hits_rect(seg, rect) -> bool:
    """True when a wire run enters the rectangle. Sampled, not solved analytically.

    Sampling at 0.5 mm along a run that is at most a few hundred mm is exact enough
    for a 1.6 mm-tall text band, and it keeps the check readable. A run whose
    endpoints straddle the rect without any sample inside cannot exist at this
    step size for a band this tall.
    """
    x1, y1, x2, y2 = seg
    min_x, min_y, max_x, max_y = rect
    if max(x1, x2) < min_x or min(x1, x2) > max_x:
        return False
    if max(y1, y2) < min_y or min(y1, y2) > max_y:
        return False
    length = math.hypot(x2 - x1, y2 - y1)
    steps = max(2, int(length / 0.5) + 1)
    for step in range(steps + 1):
        t = step / steps
        px = x1 + (x2 - x1) * t
        py = y1 + (y2 - y1) * t
        if min_x <= px <= max_x and min_y <= py <= max_y:
            return True
    return False


def _body_rects(text: str) -> list[tuple[float, float, float, float]]:
    """Screen-space rectangle of every placed symbol body on this leaf."""
    from .replica_fidelity import parse_placed_symbols

    marker = text.find("(lib_symbols")
    if marker < 0:
        return []
    boxes = _lib_local_boxes(_balanced_sexpr(text, marker))
    rects = []
    for symbol in parse_placed_symbols(text):
        box = boxes.get(symbol.lib_id)
        if box is None:
            continue
        rects.append((symbol.x + box[0], symbol.y - box[3],
                      symbol.x + box[2], symbol.y - box[1]))
    return rects


def _rects_overlap(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _continuation_blocks(
    text: str,
    leaf_nets: list[EmitNet],
    continuation_names: set[str],
) -> tuple[list[str], dict[str, int]]:
    """DD-14 clause 2: a `global_label` per cross-sheet net that has none yet.

    Returns (blocks, report). `report` separates "already carried a label" from
    "added one" from "could not anchor", because a single count would let a net
    that was silently never labelled look like a net that never needed one.

    ANCHOR CHOICE (round 46 fix). A label must sit ON one of its own pins or the
    cross-sheet join breaks, so the free choice is WHICH pin and which of the two
    text directions. Taking the first resolvable pin at angle 0 was measured to put
    the battery page's `BAT_EXT` text directly across the NTC wire run, from which a
    reviewer correctly read a short that does not exist electrically. Every
    (pin, angle) pair is now scored against the wire runs and symbol bodies already
    on the page, and the first clear pair wins. `crowded` counts the nets for which
    no clear pair existed, so a label placed on top of something is reported rather
    than looking identical to one placed in free space.
    """
    if not continuation_names:
        return [], {"already_labelled": 0, "added": 0, "unanchorable": 0,
                    "crowded": 0}
    existing = {m.group(1) for m in _EXISTING_GLOBAL_RE.finditer(text)}
    existing_locals = {
        (round(float(m.group(2)), 2), round(float(m.group(3)), 2)): m.group(1)
        for m in re.finditer(r'\(label\s+"([^"]+)"[^(]*\(at\s+(-?[\d.]+)\s+(-?[\d.]+)', text)
    }
    positions = _leaf_pin_positions(text)
    segments = _wire_segments(text)
    bodies = _body_rects(text)
    blocks: list[str] = []
    already = 0
    crowded = 0
    unanchorable: list[str] = []
    claimed: list[tuple[float, float, float, float]] = []
    for net in leaf_nets:
        if net.name not in continuation_names:
            continue
        if net.name in existing:
            already += 1
            continue
        candidates = [positions[(ref, pin)] for ref, pin in net.nodes
                      if (ref, pin) in positions]
        if not candidates:
            unanchorable.append(net.name)
            continue
        best = None
        best_cost = None
        for point in candidates:
            has_local = (round(point[0], 2), round(point[1], 2)) in existing_locals
            for angle in (0, 180):
                rect = _label_rect(net.name, point[0], point[1], angle)
                cost = sum(1 for seg in segments if _segment_hits_rect(seg, rect))
                cost += sum(1 for body in bodies if _rects_overlap(rect, body))
                cost += sum(1 for taken in claimed if _rects_overlap(rect, taken))
                if has_local:
                    cost += 50
                if best_cost is None or cost < best_cost:
                    best, best_cost = (point, angle, rect), cost
                if cost == 0:
                    break
            if best_cost == 0:
                break
        point, angle, rect = best
        if best_cost:
            crowded += 1
        claimed.append(rect)
        blocks.append(
            _continuation_label_block(net.name, point[0], point[1], angle))
        existing.add(net.name)
    if unanchorable:
        raise HierarchicalEmitError(
            "E_CONTINUATION_NOT_ANCHORABLE",
            f"cross-sheet net(s) {sorted(unanchorable)} have no resolvable pin on "
            f"this leaf, so no continuation label could be anchored. Emitting "
            f"without them would drop the cross-file join while every file still "
            f"existed.",
            nets=sorted(unanchorable),
        )
    return blocks, {
        "already_labelled": already,
        "added": len(blocks),
        "unanchorable": 0,
        "crowded": crowded,
    }


def _lib_local_boxes(lib_source: str) -> dict[str, tuple[float, float, float, float]]:
    """lib_id -> local drawn bbox, from every coordinate in its definition."""
    boxes: dict[str, tuple[float, float, float, float]] = {}
    for match in re.finditer(r'\(symbol "([^"]+)"', lib_source):
        lib_id = match.group(1)
        if ":" not in lib_id:
            continue  # a unit sub-symbol ("Device_R_0_1"), folded into its parent
        block = _balanced_sexpr(lib_source, lib_source.index("(", match.start()))
        points = [(float(a), float(b)) for a, b in _XY_RE.findall(block)]
        points += [(float(a), float(b)) for a, b in _AT_RE.findall(block)]
        if not points:
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        boxes[lib_id] = (min(xs), min(ys), max(xs), max(ys))
    return boxes


def _drawn_extent(text: str) -> tuple[float, float, float, float] | None:
    """The drawn bbox of a leaf, in absolute mm, or None when nothing parsed.

    Symbol ORIGINS are not the extent -- round 45 measured origins inside the page
    while the render overflowed by 31.44 mm, because a symbol's body and pin stubs
    reach past its origin. So each placed symbol contributes its library body box
    transformed into sheet coordinates, alongside every wire and label coordinate.
    """
    marker = text.find("(lib_symbols")
    if marker < 0:
        return None
    lib_source = _balanced_sexpr(text, marker)
    body = text[marker + len(lib_source):]
    boxes = _lib_local_boxes(lib_source)

    points: list[tuple[float, float]] = [
        (float(a), float(b)) for a, b in _XY_RE.findall(body)]
    points += [(float(a), float(b)) for a, b in _AT_RE.findall(body)]
    for lib_id, sx, sy in _PLACED_AT_RE.findall(body):
        box = boxes.get(lib_id)
        if box is None:
            continue
        ox, oy = float(sx), float(sy)
        # KiCad symbol-local y grows upward; sheet y grows downward.
        points.append((ox + box[0], oy - box[3]))
        points.append((ox + box[2], oy - box[1]))
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _translate_placed(text: str, dx: float, dy: float) -> str:
    """Shift every PLACED coordinate by (dx, dy), leaving lib definitions alone."""
    marker = text.find("(lib_symbols")
    lib_source = _balanced_sexpr(text, marker)
    head_end = marker + len(lib_source)
    head, body = text[:head_end], text[head_end:]

    def shift_at(match: re.Match) -> str:
        return (f"(at {round(float(match.group(1)) + dx, 4)} "
                f"{round(float(match.group(2)) + dy, 4)}")

    def shift_xy(match: re.Match) -> str:
        return (f"(xy {round(float(match.group(1)) + dx, 4)} "
                f"{round(float(match.group(2)) + dy, 4)})")

    body = _AT_RE.sub(shift_at, body)
    body = _XY_RE.sub(shift_xy, body)
    return head + body


def fit_page(text: str, paper: str) -> tuple[str, str, dict]:
    """DD-14 clause 3: translate, and escalate the sheet, until the content fits.

    A no-op when the content already sits inside the margin on the current paper,
    so a page that never overflowed keeps its exact bytes.
    """
    extent = _drawn_extent(text)
    if extent is None:
        return text, paper, {"status": "no_geometry_parsed"}
    min_x, min_y, max_x, max_y = extent
    dx = max(0.0, _PAGE_MARGIN_MM - min_x)
    dy = max(0.0, _PAGE_MARGIN_MM - min_y)
    need_w = max_x + dx + _PAGE_MARGIN_MM
    need_h = max_y + dy + _PAGE_MARGIN_MM

    # Both orientations of each sheet, smallest area first, landscape preferred at
    # equal area. Landscape-only was measured to waste a whole sheet size: the
    # mcu_swd page needs 243 x 270 mm, which A3 landscape (369 x 246 usable)
    # misses by 24 mm on height alone, so it escalated to A2 and rendered 41 %
    # covered. A3 PORTRAIT (246 x 369 usable) holds the same content.
    start = _PAPER_LADDER.index(paper) if paper in _PAPER_LADDER else 0
    candidates = []
    for candidate in _PAPER_LADDER[start:]:
        width, height = _PAPER_DIMS_MM[candidate]
        candidates.append((width * height, 0, candidate, "", width, height))
        candidates.append((width * height, 1, candidate, "portrait", height, width))
    chosen = None
    orientation = ""
    _tb_w, _tb_h = 120.0, 45.0
    for _area, _rank, candidate, orient, width, height in sorted(candidates):
        if need_w <= width and need_h <= height:
            _shifted_max_x = max_x + dx
            _shifted_max_y = max_y + dy
            if _shifted_max_x > width - _tb_w and _shifted_max_y > height - _tb_h:
                _shift_up_needed = math.ceil((_shifted_max_y - (height - _tb_h)) / 1.27) * 1.27
                _avail_headroom = (min_y + dy) - _PAGE_MARGIN_MM
                if _shift_up_needed <= _avail_headroom:
                    dy -= _shift_up_needed
                    chosen, orientation = candidate, orient
                    break
                continue
            chosen, orientation = candidate, orient
            break
    if chosen is None:
        raise HierarchicalEmitError(
            "E_PAGE_FIT_IMPOSSIBLE",
            f"drawn content needs {need_w:.2f} x {need_h:.2f} mm, larger than the "
            f"largest sheet in the ladder ({_PAPER_LADDER[-1]}). Refusing to emit a "
            f"page whose content is known to be clipped.",
            needed_mm=[round(need_w, 2), round(need_h, 2)], paper=paper,
        )
    # Quantize translation to KiCad 1.27 mm grid so every placed endpoint stays on-grid
    dx = round(dx / 1.27) * 1.27
    dy = round(dy / 1.27) * 1.27
    report = {
        "status": "measured",
        "extent_mm": [round(v, 2) for v in extent],
        "dx_mm": round(dx, 4), "dy_mm": round(dy, 4),
        "paper_in": paper, "paper_out": chosen,
    }
    report["orientation_out"] = orientation or "landscape"
    if abs(dx) < 1e-4 and abs(dy) < 1e-4 and chosen == paper and not orientation:
        report["status"] = "already_fits"
        return text, paper, report
    if abs(dx) > 1e-4 or abs(dy) > 1e-4:
        text = _translate_placed(text, dx, dy)
    if chosen != paper or orientation:
        replacement = (f'(paper "{chosen}" {orientation})' if orientation
                       else f'(paper "{chosen}")')
        text = text.replace(f'(paper "{paper}")', replacement, 1)
    return text, chosen, report


def replica_nodes_for_view(
    ref: str,
    view: ReplicaView,
    nets: list[EmitNet],
) -> list[EmitNet]:
    """The leaf-net fragments a replica view must draw, or raise.

    A requested net that assigns NO pin of `ref` raises instead of producing an
    empty fragment: an empty fragment draws nothing, which is exactly the F-3
    violation this contract exists to make impossible to ship quietly.
    """
    by_name = {net.name: net for net in nets}
    fragments: list[EmitNet] = []
    for name in view.nets:
        canonical = by_name.get(name)
        nodes = [] if canonical is None else [
            (node_ref, pin) for node_ref, pin in canonical.nodes if node_ref == ref]
        if not nodes:
            why = ("net absent entirely" if canonical is None
                   else "net exists but assigns other refs only")
            raise HierarchicalEmitError(
                "E_REPLICA_NET_NOT_CANONICAL",
                f"{ref}: replica view on {view.sheet!r} requests net {name!r}, but "
                f"the canonical design assigns no pin of {ref} to it ({why}). "
                f"Drawing it would invent a connection the netlist cannot "
                f"contradict.",
                ref=ref, sheet=view.sheet, net=name,
                net_exists=canonical is not None,
            )
        fragments.append(EmitNet(name=name, nodes=nodes))
    return fragments


def _sheet_block(
    name: str,
    filename: str,
    sheet_uuid: str,
    root_uuid: str,
    project_name: str,
    page: int,
    pos_x: float,
    pos_y: float,
) -> str:
    """One root `(sheet ...)` block. Six required fields per data-schema."""
    return (
        f"  (sheet (at {pos_x} {pos_y}) (size {_BLOCK_W_MM} {_BLOCK_H_MM})\n"
        f"    (stroke (width 0.1524) (type solid))\n"
        f"    (fill (color 0 0 0 0.0000))\n"
        f'    (uuid "{sheet_uuid}")\n'
        f'    (property "Sheetname" "{name}" (at {pos_x} {pos_y - 0.7} 0)\n'
        f"      (effects (font (size 1.27 1.27)) (justify left bottom)))\n"
        f'    (property "Sheetfile" "{filename}" '
        f"(at {pos_x} {pos_y + _BLOCK_H_MM + 0.7} 0)\n"
        f"      (effects (font (size 1.27 1.27)) (justify left top)))\n"
        f'    (instances (project "{project_name}" '
        f'(path "/{root_uuid}" (page "{page}"))))\n'
        f"  )"
    )


def _root_document(
    root_uuid: str,
    sheet_names: list[str],
    sheet_uuids: dict[str, str],
    project_name: str,
    paper: str,
) -> str:
    blocks = []
    for index, name in enumerate(sheet_names):
        pos_x = _BLOCK_X0_MM + (index % _BLOCKS_PER_ROW) * _BLOCK_DX_MM
        pos_y = _BLOCK_Y0_MM + (index // _BLOCKS_PER_ROW) * _BLOCK_DY_MM
        blocks.append(_sheet_block(
            name, f"{name}.kicad_sch", sheet_uuids[name], root_uuid,
            project_name, _FIRST_LEAF_PAGE + index, pos_x, pos_y))
    pages = "".join(
        f'\n    (path "/{sheet_uuids[name]}" (page "{_FIRST_LEAF_PAGE + i}"))'
        for i, name in enumerate(sheet_names))
    from datetime import date as _dt_date
    _date_str = _dt_date.today().isoformat()
    _title_block = (
        "  (title_block\n"
        f'    (title "{project_name}")\n'
        f'    (date "{_date_str}")\n'
        f'    (rev "v1.0")\n'
        f'    (company "bodesign")\n'
        "  )\n"
    )
    return (
        "(kicad_sch\n"
        f"  (version {SCHEMATIC_VERSION})\n"
        '  (generator "bodesign")\n'
        '  (generator_version "9.0")\n'
        f'  (uuid "{root_uuid}")\n'
        f'  (paper "{paper}")\n'
        f"{_title_block}"
        "  (lib_symbols\n  )\n"
        + "\n".join(blocks) + "\n"
        f'  (sheet_instances\n    (path "/" (page "1")){pages}\n  )\n'
        ")\n"
    )


_LEAF_ROOT_UUID_RE = re.compile(r'^(\s*\(uuid ")([0-9a-fA-F-]{36})("\)\s*)$', re.M)


def _rewrite_leaf_instance_paths(text: str, root_uuid: str, sheet_uuid: str, page_num: int = 2) -> str:
    """Re-anchor a leaf's symbol instance paths under the root and update sheet_instances."""
    text = re.sub(
        r'\(path "/[0-9a-fA-F-]{36}" \(reference ',
        f'(path "/{root_uuid}/{sheet_uuid}" (reference ',
        text,
    )
    text = re.sub(
        r'\(sheet_instances\s+\(path\s+"/"\s+\(page\s+"[^"]+"\)\)\)',
        f'(sheet_instances (path "/{sheet_uuid}" (page "{page_num}")))',
        text,
    )
    return text


def emit_hierarchical_schematic(
    project_dir: str | Path,
    project_name: str,
    components: list[EmitComponent],
    nets: list[EmitNet],
    sheet_map: SheetMap,
    per_sheet_nc: dict[str, list[str]] | None = None,
    subsystem_views: dict[str, list[str]] | None = None,
    view_local_max_nodes: int = VIEW_LOCAL_MAX_NODES,
    auto_layout: bool = False,
    trim_small_replicas: bool = False,
    layout_engine: str | None = None,
    engine_orientation_sets: dict | None = None,
    engine_placement_models: list | tuple | None = None,
    engine_outline_refs: list | tuple | None = None,
    engine_spacing_overrides: dict | None = None,
    **emit_kwargs,
) -> HierarchicalEmitResult:
    """Emit root + N leaves, or delegate to the flat path when nothing was declared.

    layout_engine (DD-13/DD-15 presentation authority): `None` keeps the legacy
    path byte-for-byte (`auto_layout` grid + legacy router). `"elk-layered"`
    replaces ONLY the per-leaf placement + routing with one validated
    `elk_layout` presentation solution per leaf; engine failure raises
    `HierarchicalEmitError(E_ENGINE_*)` and never falls back to the legacy router.

    `sheet_map` comes from `partition_components`, which has ALREADY validated names,
    rejected duplicates and (given `project_name`) checked the leaf-vs-root collision.
    This function re-checks that the collision check actually RAN, because a SheetMap
    built without `project_name` carries `collision_checked=False` and emitting from it
    would write a leaf over the root.
    """
    root_dir = Path(project_dir)
    root_dir.mkdir(parents=True, exist_ok=True)

    if not sheet_map.is_multi_sheet:
        flat = emit_kicad_schematic(
            root_dir, project_name, components, nets, **emit_kwargs)
        return HierarchicalEmitResult(
            project_dir=flat.project_dir,
            schematic_path=flat.schematic_path,
            project_path=flat.project_path,
            emit_mode=EMIT_MODE_LEGACY,
            files=[flat.schematic_path, flat.project_path],
            leaf_paths={},
            created_paths=[flat.schematic_path, flat.project_path],
            cross_sheet_nets=[],
            warnings=list(flat.warnings),
            leaf_results={},
        )

    if not sheet_map.collision_checked:
        raise HierarchicalEmitError(
            "E_COLLISION_CHECK_NOT_RUN",
            "the SheetMap was built without `project_name`, so the leaf-vs-root "
            "collision check never ran. Emitting from it could write a leaf over "
            "the root while `files` still listed a complete set. Re-run "
            "partition_components(spec, project_name=...).",
            project_name=project_name,
        )

    sheet_names = list(sheet_map.sheets)
    by_ref = {ref: sheet for sheet, refs in sheet_map.sheets.items() for ref in refs}
    per_sheet_nets, cross_nets, orphans = nets_by_sheet(nets, by_ref)
    assert_no_endpoint_lost(nets, per_sheet_nets, orphans)

    warnings: list[str] = []
    if orphans:
        warnings.append(
            f"{len(orphans)} net node(s) reference refs absent from the component "
            f"list and were not placed on any sheet: {sorted(orphans)[:12]}")

    cross_set = set(cross_nets)
    # DD-14: sheet -> the SUBSYSTEM's own nets, which are the only ones a view may
    # draw locally. Scoping to the declared nets is load-bearing, not tidiness: with
    # every cross-sheet net un-forced, the GND/+3V3/SYS/BATT rails were routed as
    # drawn trunks across a dense page and their stub endpoints landed on foreign
    # wires, FUSING 7 measured node classes into 2. The ruling revises the label-only
    # rule for the selected subsystem, not for every high-fanout rail.
    view_nets_by_sheet: dict[str, set[str]] = {
        sheet: {str(net) for net in nets_declared}
        for sheet, nets_declared in (subsystem_views or {}).items()
    }
    view_sheets = set(view_nets_by_sheet)
    unknown_views = sorted(view_sheets - set(sheet_names))
    if unknown_views:
        raise HierarchicalEmitError(
            "E_SUBSYSTEM_VIEW_UNKNOWN_SHEET",
            f"subsystem view(s) {unknown_views} name sheets that no component was "
            f"assigned to. A view of a sheet that does not exist would be silently "
            f"ignored, so it is refused instead.",
            sheets=unknown_views, declared=sorted(sheet_names),
        )
    empty_views = sorted(s for s, n in view_nets_by_sheet.items() if not n)
    if empty_views:
        raise HierarchicalEmitError(
            "E_SUBSYSTEM_VIEW_NO_NETS",
            f"subsystem view(s) {empty_views} declare no nets. A view with no nets "
            f"would draw no local connection while still reporting as a view.",
            sheets=empty_views,
        )
    ledger = _CreationLedger()
    root_uuid = _uid()
    sheet_uuids = {name: _uid() for name in sheet_names}
    paper = emit_kwargs.get("paper", "A4")

    root_path = ledger.claim(root_dir / f"{project_name}.kicad_sch")
    project_path = ledger.claim(root_dir / f"{project_name}.kicad_pro")
    leaf_targets = {
        name: ledger.claim(root_dir / f"{name}.kicad_sch") for name in sheet_names
    }

    component_by_ref = {c.ref: c for c in components}
    leaf_results: dict[str, SchematicEmitResult] = {}
    leaf_paths: dict[str, str] = {}
    replica_marked: dict[str, int] = {}
    continuation_reports: dict[str, dict] = {}
    page_fit: dict[str, dict] = {}
    view_label_only: dict[str, dict] = {}
    symbol_boxes: dict[str, dict] = {}
    engine_reports: dict[str, dict] = {}
    try:
        for leaf_idx, name in enumerate(sheet_names, start=2):
            members = set(sheet_map.sheets[name])
            leaf_components = [c for c in components if c.ref in members]
            leaf_nets = per_sheet_nets.get(name, [])

            # --- DD-13 clause 4c: replica views drawn on THIS leaf ------------
            # The replica symbol and its requested net fragments are appended to the
            # SAME emitter call as the canonical members, so a replica's geometry is
            # produced by the same code path and stays comparable. Only the two
            # neutrality flags are flipped afterwards, on the landed bytes.
            replica_here = sheet_map.replicas_on(name)
            replica_refs_here: set[str] = set()
            trimmed_replicas_here: list[tuple[str, str, str, str]] = []  # (ref, pin, net, home_sheet)
            for replica_ref, view in replica_here:
                source = component_by_ref.get(replica_ref)
                if source is None:
                    raise HierarchicalEmitError(
                        "E_REPLICA_UNKNOWN_REF",
                        f"replica of {replica_ref!r} requested on {name!r}, but no "
                        f"placed component carries that ref.",
                        ref=replica_ref, sheet=name,
                    )
                frag_nodes = replica_nodes_for_view(replica_ref, view, nets)
                contributed_pins = {
                    (pin, frag.name) for frag in frag_nodes
                    for r, pin in frag.nodes if r == replica_ref
                }
                home_sheet = next((s for s, refs in sheet_map.sheets.items() if replica_ref in refs), "power_rail")
                if trim_small_replicas and len(contributed_pins) <= 2:
                    for pin, net_name in sorted(contributed_pins):
                        trimmed_replicas_here.append((replica_ref, pin, net_name, home_sheet))
                    continue

                position = len(leaf_components)
                pos_x, pos_y = _auto_place_local(position)
                leaf_components.append(EmitComponent(
                    ref=source.ref, lib_id=source.lib_id, value=source.value,
                    footprint=source.footprint, x=pos_x, y=pos_y, unit=source.unit))
                replica_refs_here.add(replica_ref)
                # Fragments carry ONLY this ref's pins on the requested nets, so the
                # view depicts the declared subset and nothing else.
                leaf_nets = leaf_nets + frag_nodes

            # DD-14: on a declared SUBSYSTEM VIEW the cross-sheet nets are drawn as
            # ordinary local wires and a `global_label` is appended afterwards, so
            # the page explains the circuit while the label still carries the join
            # (clause 2, measured). Every other sheet keeps DD-2's label-only rule.
            view_nets = view_nets_by_sheet.get(name, set())
            replica_view_nets = {
                net for _ref, view in replica_here for net in view.nets}
            leaf_cross = {net.name for net in leaf_nets if net.name in cross_set}
            forced = set(emit_kwargs.get("label_nets") or ())
            # Locally drawn == on a SUBSYSTEM VIEW sheet, any cross-sheet net whose
            # LOCAL SLICE is small enough for the emitter's guarded route -- not
            # only the subsystem's own named nets. Narrowing it to the named nets
            # was measured to cost the whole page: on `usbc`, VBUS has a 2-node
            # local slice and is well inside the bound, yet naming only
            # VBUS_CON/CC1/CC2 forced it to a label, and that single extra forced
            # label took the page from 4 drawn wires to 0 (controls: no label_nets
            # -> 4, {GND} -> 4, {GND,VBUS} -> 0). The SLICE BOUND is the anti-fusion
            # mechanism; the name filter was a second, cruder one that mostly
            # removed legible connections. Non-view sheets keep DD-2's label-only
            # rule unchanged -- and that gate is load-bearing, not decorative:
            # dropping `view_nets` from the expression entirely (rather than only
            # from the net-name filter) let the non-view `io` sheet draw its
            # cross-sheet nets too, and the netlist then FUSED GND with the
            # C12.1/R12.2/SW3.1/U2.24 net -- a real short, caught by comparing the
            # export against the DECLARED spec rather than against a previous run.
            candidates = (leaf_cross | replica_view_nets) if view_nets else set()
            # AGGREGATED across fragments: a replica view appends a SECOND EmitNet
            # carrying the same name, so a per-name overwrite would read the 9-node
            # SYS rail as its 1-node replica fragment and let it under the bound.
            slice_size: dict[str, int] = {}
            for fragment in leaf_nets:
                slice_size[fragment.name] = (
                    slice_size.get(fragment.name, 0) + len(fragment.nodes))
            drawn_locally = {
                net for net in candidates
                if slice_size.get(net, 0) <= view_local_max_nodes}
            # Reported for the SUBSYSTEM's own nets: those are what the page was
            # asked to show, so a reader needs to know which of them stayed on a
            # label. A cross-sheet net that is merely present on the sheet is not
            # part of that promise and is not reported as a shortfall.
            oversized = {
                net: slice_size.get(net, 0)
                for net in (candidates & view_nets) - drawn_locally}
            if oversized:
                view_label_only[name] = oversized
            forced |= (leaf_cross | replica_view_nets) - drawn_locally
            continuation_names = drawn_locally
            leaf_kwargs = dict(emit_kwargs)
            leaf_kwargs["label_nets"] = forced
            # `nc` is per-leaf: the emitter raises on an entry it cannot resolve,
            # so the whole-design list would fail every sheet but the owning one.
            if per_sheet_nc is not None:
                leaf_kwargs["nc"] = per_sheet_nc.get(name) or None

            # Round 46 clipping/overlap fix: re-place the WHOLE leaf (canonical
            # members and replicas together) on a grid whose cells are as large as
            # the symbols that occupy them. Done here rather than at spec-parse
            # time because this is the first point where a sheet's full draw list
            # is known, and before emission because wires are routed from these
            # coordinates -- moving symbols afterwards would leave the wires behind.
            engine_solution = None
            if layout_engine is not None and layout_engine != LAYOUT_ENGINE_ELK:
                raise HierarchicalEmitError(
                    "E_ENGINE_UNKNOWN",
                    f"layout_engine={layout_engine!r} is not a known engine "
                    f"(supported: {LAYOUT_ENGINE_ELK!r}); refused rather than "
                    f"silently using the legacy router.",
                    layout_engine=layout_engine)
            if layout_engine == LAYOUT_ENGINE_ELK and leaf_components:
                # DD-15 seam: final rendered symbol geometry is resolved INSIDE
                # elk_layout with the emitter's own scale stacking, so the engine's
                # ports are the emitter's pin tips. Policy of WHICH nets are drawn
                # is this function's (DD-14 slice bound + forced labels + gnd);
                # the engine only routes what it is handed.
                from .elk_layout import (LAYOUT_VARIANTS, PLACEMENT_MODELS, ElkLayoutError,
                                         solve_sheet)
                _forced_here = set(forced)
                # Round 3: ONE predeclared orientation set, applied only on the sheet
                # that owns the ref; other sheets run identity.
                # Round 4: predeclared placement models, selected BY NAME from
                # elk_layout.PLACEMENT_MODELS (unknown name = refusal, not a guess).
                _known_pm = {m["name"]: m for m in PLACEMENT_MODELS}
                _bad_pm = [n for n in (engine_placement_models or ()) if n not in _known_pm]
                if _bad_pm:
                    raise HierarchicalEmitError(
                        "E_ENGINE_PLACEMENT_UNKNOWN",
                        f"unknown placement model(s) {_bad_pm}; known {sorted(_known_pm)}",
                        models=_bad_pm)
                _sheet_pmodels = tuple(_known_pm[n] for n in engine_placement_models) \
                    if engine_placement_models else None
                _sheet_osets = {r: tuple(ids) for r, ids in (engine_orientation_sets or {}).items()
                                if any(c.ref == r for c in leaf_components)} or None

                def _drawn_filter(net, _forced=_forced_here):
                    if net.name in _forced:
                        return False, "forced label continuation (DD-14 slice bound / policy)"
                    if _GND_RE.match(net.name):
                        return False, "ground: power/label continuation, never a page-wide chain"
                    return True, ""
                try:
                    engine_solution = solve_sheet(
                        leaf_components, leaf_nets,
                        symbol_dir=emit_kwargs.get("symbol_dir"),
                        page_scale=float(emit_kwargs.get("page_scale", 1.0)),
                        drawn_filter=_drawn_filter,
                        motif_geometries=emit_kwargs.get("motif_geometries"),
                        cross_sheet_nets=set(cross_set),
                        orientation_sets=_sheet_osets,
                        placement_models=_sheet_pmodels,
                        outline_refs={r for r in (engine_outline_refs or ())
                                      if any(c.ref == r for c in leaf_components)} or None,
                        spacing_overrides=dict(engine_spacing_overrides or {}) or None,
                        **({"variants": tuple(v for v in LAYOUT_VARIANTS
                                              if v["name"] == "model-order")}
                           if (_sheet_osets or _sheet_pmodels or engine_outline_refs
                               or engine_spacing_overrides) else {}))
                except ElkLayoutError as error:
                    raise HierarchicalEmitError(
                        "E_ENGINE_REFUSED",
                        f"{name}: the layered engine refused this sheet "
                        f"({error.code}: {error.message}). No legacy fallback.",
                        sheet=name, engine_code=error.code,
                        engine_details=error.details) from error
                leaf_components = [
                    replace(c, x=engine_solution.poses[c.ref][0],
                            y=engine_solution.poses[c.ref][1])
                    for c in leaf_components]
                symbol_boxes[name] = {
                    "engine": LAYOUT_ENGINE_ELK,
                    "elkjs": engine_solution.receipt.elkjs_version,
                    "node": engine_solution.receipt.node_version,
                    "wall_s": engine_solution.receipt.wall_s,
                    "graph_sha256": engine_solution.receipt.graph_sha256,
                    "solution_sha256": engine_solution.receipt.solution_sha256,
                    "verification": engine_solution.verification,
                    "variant": engine_solution.variant,
                    "variant_log": engine_solution.variant_log,
                    "orientations": dict(engine_solution.orientations),
                    "orientation_sweep": engine_solution.orientation_sweep,
                    "placement_model": engine_solution.placement_model,
                    "outlines": engine_solution.outlines,
                    "spacing_overrides": engine_solution.spacing_overrides,
                    "foreign_crossings": engine_solution.foreign_crossings,
                    "ink": {
                        "props": {r: {"candidate": p.candidate, "ref_at": list(p.ref_at),
                                      "val_at": list(p.val_at)}
                                  for r, p in engine_solution.props.items()},
                        "flags": {n: {"at": list(f.at), "edge": list(f.edge), "pin": f.pin,
                                      "box": list(f.box)}
                                  for n, f in engine_solution.flags.items()},
                        "local_labels": {n: {"at": list(f.at), "box": list(f.box)}
                                         for n, f in engine_solution.local_labels.items()},
                        "fixed_flag_boxes": engine_solution.fixed_flag_boxes,
                    },
                }
                engine_reports[name] = symbol_boxes[name]
                leaf_kwargs["presentation_solution"] = engine_solution
            elif auto_layout and leaf_components:
                boxes, box_report = _library_symbol_boxes(
                    emit_kwargs.get("symbol_dir"),
                    {c.lib_id for c in leaf_components})
                # Round 47: size the cell from what will be DRAWN, not from what the
                # library stores. The emitter lifts a stored symbol's geometry so its
                # rendered pin pitch reaches the page floor (_vendor_sym_scale), and
                # the library box does not carry that factor. Measured on the btdongle
                # power_rail leaf: local:ETA6003 stores a 38.10 x 33.02 mm box and
                # landed at 114.30 x 99.06 mm -- exactly 3.0x -- so U1 received a cell
                # a third of its drawn size and the other five symbols were placed
                # INSIDE its body, with 17 of 24 wire runs crossing it.
                boxes, drawn_report = _drawn_symbol_boxes(
                    boxes, leaf_components, emit_kwargs.get("symbol_dir"),
                    float(emit_kwargs.get("page_scale", 1.0)))
                box_report = dict(box_report)
                box_report.update(drawn_report)
                symbol_boxes[name] = box_report
                grid = layout_sheet(
                    [(c.ref, c.lib_id) for c in leaf_components], boxes)
                leaf_components = [
                    replace(c, x=grid[c.ref][0], y=grid[c.ref][1])
                    if c.ref in grid else c
                    for c in leaf_components
                ]

            leaf_kwargs["title"] = f"{project_name} - {name}"
            leaf_kwargs["cross_sheet_nets"] = cross_set
            leaf_result = emit_kicad_schematic(
                root_dir, name, leaf_components, leaf_nets, **leaf_kwargs)
            leaf_path = Path(leaf_result.schematic_path)
            ledger.record(leaf_path)
            # emit_kicad_schematic also writes `<name>.kicad_pro` believing it is a
            # standalone project. In a hierarchy only the root owns a project file.
            stray_project = Path(leaf_result.project_path)
            if stray_project != project_path and stray_project.exists():
                stray_project.unlink()

            leaf_text = _rewrite_leaf_instance_paths(
                leaf_path.read_text(encoding="utf-8"), root_uuid, sheet_uuids[name], page_num=leaf_idx)
            leaf_text, marked = _mark_replica_symbols(leaf_text, replica_refs_here)
            if marked != len(replica_refs_here):
                raise HierarchicalEmitError(
                    "E_REPLICA_FLAGS_NOT_APPLIED",
                    f"{name}: expected to mark {len(replica_refs_here)} replica "
                    f"symbol(s) netlist-neutral, marked {marked}. An unmarked "
                    f"replica would contribute real nodes to the netlist and a "
                    f"second BOM row while the file set still looked complete.",
                    sheet=name, expected=len(replica_refs_here), marked=marked,
                    refs=sorted(replica_refs_here),
                )
            replica_marked[name] = marked

            # DD-14 clauses 2 and 4, applied to the LANDED bytes so the annotation
            # and the continuation labels are read back from the same text a
            # reviewer and the fidelity checker will read.
            extra_blocks = _replica_annotation_blocks(
                leaf_text, replica_refs_here, by_ref)
            continuation, continuation_report = _continuation_blocks(
                leaf_text, leaf_nets, continuation_names)
            extra_blocks.extend(continuation)
            search_text = leaf_text + "\n" + "\n".join(continuation)
            for ref, pin, net_name, home in trimmed_replicas_here:
                m = re.search(
                    rf'\(global_label\s+"{re.escape(net_name)}"[^()]*\(at\s+([-\d.]+)\s+([-\d.]+)',
                    search_text,
                )
                if not m:
                    m = re.search(
                        rf'\(label\s+"{re.escape(net_name)}"[^()]*\(at\s+([-\d.]+)\s+([-\d.]+)',
                        search_text,
                    )
                if m:
                    lx, ly = float(m.group(1)), float(m.group(2))
                    ax = round(lx + 2.54, 4)
                    ay = round(ly - 2.54, 4)
                else:
                    lx, ly = 35.56, 35.56
                    extra_blocks.append(
                        f'  (global_label "{net_name}" (shape bidirectional) (at {lx} {ly} 0)\n'
                        f'    (effects (font (size 1.27 1.27)) (justify left)) (uuid "{_uid()}"))'
                    )
                    ax, ay = round(lx + 2.54, 4), round(ly - 2.54, 4)
                annotation_text = f"→ {ref}.{pin} {net_name} — home: {home}"
                extra_blocks.append(
                    f'  (text "{annotation_text}"\n'
                    f'    (at {ax} {ay} 0)\n'
                    f'    (effects (font (size 1.27 1.27) (italic yes)) (justify left))\n'
                    f'  )'
                )
            leaf_text = _insert_blocks(leaf_text, extra_blocks)
            if continuation_names:
                continuation_reports[name] = continuation_report

            leaf_text, leaf_paper, fit_report = fit_page(leaf_text, paper)
            page_fit[name] = fit_report
            if leaf_paper != paper:
                warnings.append(
                    f"{name}: drawn content did not fit {paper}; the sheet was "
                    f"escalated to {leaf_paper} (extent "
                    f"{fit_report.get('extent_mm')} mm).")

            leaf_path.write_text(leaf_text, encoding="utf-8")
            leaf_results[name] = leaf_result
            leaf_paths[name] = str(leaf_path)
            warnings.extend(leaf_result.warnings)

        root_path.write_text(
            _root_document(root_uuid, sheet_names, sheet_uuids, project_name, paper),
            encoding="utf-8")
        ledger.record(root_path)
        project_path.write_text(_project_document(), encoding="utf-8")
        ledger.record(project_path)
    except Exception as exc:
        removed = ledger.rollback()
        if isinstance(exc, HierarchicalEmitError):
            raise
        raise HierarchicalEmitError(
            "E_LEAF_WRITE_FAILED",
            f"emission failed ({type(exc).__name__}: {exc}); removed only the "
            f"{len(removed)} path(s) this call created, leaving pre-existing files "
            f"untouched.",
            removed=removed, cause=repr(exc),
        ) from exc

    files = [str(root_path)] + [leaf_paths[name] for name in sheet_names]
    files.append(str(project_path))
    missing = [path for path in files if not Path(path).exists()]
    if missing:
        raise HierarchicalEmitError(
            "E_FILES_MANIFEST_PHANTOM",
            f"`files` would have listed {missing}, which are not on disk.",
            missing=missing,
        )

    return HierarchicalEmitResult(
        project_dir=str(root_dir),
        schematic_path=str(root_path),
        project_path=str(project_path),
        emit_mode=EMIT_MODE_HIERARCHICAL,
        files=files,
        leaf_paths=leaf_paths,
        created_paths=[str(path) for path in ledger.paths],
        cross_sheet_nets=sorted(cross_set),
        warnings=warnings,
        leaf_results=leaf_results,
        replica_marked=replica_marked,
        replica_views_requested=sum(
            len(views) for views in sheet_map.replica_map.values()),
        continuation_labels=continuation_reports,
        page_fit=page_fit,
        view_nets_label_only=view_label_only,
        symbol_boxes=symbol_boxes,
        engine_reports=engine_reports,
    )


def emit_from_spec(
    project_dir: str | Path,
    project_name: str,
    spec_components: list[dict],
    components: list[EmitComponent],
    nets: list[EmitNet],
    **emit_kwargs,
) -> HierarchicalEmitResult:
    """Convenience entry: partition the spec, then emit on the route it selects.

    `spec_components` carries the `sheet` / `group` declarations; `components` carries
    the placed geometry. They are separate arguments because placement is the caller's
    job and this module never invents coordinates.
    """
    sheet_map = partition_components(
        {"components": spec_components}, project_name=project_name)
    return emit_hierarchical_schematic(
        project_dir, project_name, components, nets, sheet_map, **emit_kwargs)


# ── Spec-level entry (the MCP wiring surface calls THIS) ────────────────────
#
# OUTCOME CODOMAIN of `emit_multisheet` (errors.md §Outcome Codomain):
#   ok            -> HierarchicalEmitResult, emit_mode hierarchical|single-legacy
#   failed        -> PartitionError (declaration defects) or HierarchicalEmitError
#                    (E_SPEC_NETS_MALFORMED / E_NET_NODE_MALFORMED / E_NC_UNKNOWN_REF
#                     / E_OUTPUT_PATH_OCCUPIED / E_LEAF_WRITE_FAILED / ...)
#   not-run       -> SPEC_ENTRY_COUNTERS["calls_entered"] == 0. A caller that never
#                    reached this function is distinguishable from one that ran and
#                    produced a single legacy file.
#   empty         -> n/a: a spec with zero components raises E_SPEC_NO_COMPONENTS.
#                    "nothing to draw" is a caller defect here, never a quiet success.
#   indeterminate -> n/a: every branch either writes real files or raises.

#: Deterministic per-sheet placement grid. Matches composer's netlist-path constants
#: (columns 4, 45 mm pitch, 35 mm origin) so a leaf reads like the flat output.
_PLACE_COLUMNS = 4
_PLACE_DX_MM = 45.0
_PLACE_DY_MM = 45.0
_PLACE_X0_MM = 35.0
_PLACE_Y0_MM = 35.0

#: Branch-ENTRY counters, same discipline as partition.COUNTERS.
SPEC_ENTRY_COUNTERS: dict[str, int] = {
    "calls_entered": 0,
    "raised_no_components": 0,
    "raised_nets_malformed": 0,
    "raised_node_malformed": 0,
    "raised_nc_unknown_ref": 0,
}


def _auto_place_local(index: int) -> tuple[float, float]:
    """Grid position for the `index`-th component ON ITS OWN SHEET.

    The index is per-sheet, not global: a global index would scatter a four-part
    leaf across the coordinates its refs happened to occupy in the whole design.
    """
    return (
        _PLACE_X0_MM + (index % _PLACE_COLUMNS) * _PLACE_DX_MM,
        _PLACE_Y0_MM + (index // _PLACE_COLUMNS) * _PLACE_DY_MM,
    )


def parse_spec_nets(raw_nets) -> list[EmitNet]:
    """Turn `spec["nets"]` into EmitNet, rejecting malformed entries.

    Deliberately STRICTER than the composer's parse, which filters nodes with
    `if "." in str(n)` and therefore drops a malformed node silently. A dropped node
    is a deleted endpoint: the emitted schematic would be missing a connection while
    every count still looked plausible.
    """
    if raw_nets is None:
        return []
    if not isinstance(raw_nets, (list, tuple)):
        SPEC_ENTRY_COUNTERS["raised_nets_malformed"] += 1
        raise HierarchicalEmitError(
            "E_SPEC_NETS_MALFORMED",
            f"`nets` must be a list, received {type(raw_nets).__name__}.",
            received_type=type(raw_nets).__name__,
        )
    out: list[EmitNet] = []
    for index, net in enumerate(raw_nets):
        if not isinstance(net, dict):
            SPEC_ENTRY_COUNTERS["raised_nets_malformed"] += 1
            raise HierarchicalEmitError(
                "E_SPEC_NETS_MALFORMED",
                f"net #{index} is {type(net).__name__}; expected a mapping with "
                f"`name` and `nodes`.",
                index=index,
            )
        name = str(net.get("name", "")).strip()
        if not name:
            SPEC_ENTRY_COUNTERS["raised_nets_malformed"] += 1
            raise HierarchicalEmitError(
                "E_SPEC_NETS_MALFORMED",
                f"net #{index} has a blank `name`.", index=index,
            )
        raw_nodes = net.get("nodes")
        if not isinstance(raw_nodes, (list, tuple)) or not raw_nodes:
            SPEC_ENTRY_COUNTERS["raised_nets_malformed"] += 1
            raise HierarchicalEmitError(
                "E_SPEC_NETS_MALFORMED",
                f"net {name!r} has no `nodes` list. A net with no endpoints is not "
                f"an empty net, it is an incomplete declaration.",
                net=name,
            )
        nodes: list[tuple[str, str]] = []
        for node in raw_nodes:
            text = str(node).strip()
            ref, sep, pin = text.partition(".")
            if not sep or not ref.strip() or not pin.strip():
                SPEC_ENTRY_COUNTERS["raised_node_malformed"] += 1
                raise HierarchicalEmitError(
                    "E_NET_NODE_MALFORMED",
                    f"net {name!r} node {text!r} is not REF.PIN. It is REJECTED "
                    f"rather than filtered out: dropping it would delete an endpoint "
                    f"the caller declared while the net still looked complete.",
                    net=name, node=text,
                )
            nodes.append((ref.strip(), pin.strip()))
        out.append(EmitNet(name=name, nodes=nodes))
    return out


def split_nc_by_sheet(
    nc: list[str] | None,
    ref_to_sheet: dict[str, str],
) -> dict[str, list[str]]:
    """Route each `REF.PIN` no-connect declaration to the leaf holding REF.

    A leaf raises on an `nc` entry it cannot resolve, so passing the whole list to
    every leaf would fail every sheet but the one that owns the ref. An entry whose
    ref is on NO sheet raises here instead of surfacing as an emitter error that
    names a pin rather than the real defect.
    """
    routed: dict[str, list[str]] = {}
    if not nc:
        return routed
    unknown: list[str] = []
    for entry in nc:
        text = str(entry).strip()
        ref = text.partition(".")[0].strip()
        sheet = ref_to_sheet.get(ref)
        if sheet is None:
            unknown.append(text)
            continue
        routed.setdefault(sheet, []).append(text)
    if unknown:
        SPEC_ENTRY_COUNTERS["raised_nc_unknown_ref"] += 1
        raise HierarchicalEmitError(
            "E_NC_UNKNOWN_REF",
            f"{len(unknown)} no-connect entr(ies) name a ref absent from the "
            f"component list: {sorted(unknown)[:12]}.",
            unknown=sorted(unknown),
        )
    return routed


def emit_multisheet(
    project_dir: str | Path,
    project_name: str,
    spec: dict,
    **emit_kwargs,
) -> HierarchicalEmitResult:
    """Partition a raw spec, place each leaf, and emit root + N leaves.

    This is the whole path from a declarative spec to files on disk, and it is what
    the MCP handler calls. `spec` is the compose_schematic shape plus the `sheet`
    field: {"components": [{ref, symbol, value?, footprint?, group?, sheet?, x?, y?}],
    "nets": [{name, nodes: ["REF.PIN", ...]}], "nc": ["REF.PIN", ...]}.

    Placement: a component carrying BOTH `x` and `y` keeps them; otherwise it gets a
    deterministic per-sheet grid slot. Partial coordinates are not completed --
    inventing the missing half would be a fabricated placement.
    """
    SPEC_ENTRY_COUNTERS["calls_entered"] += 1
    if not isinstance(spec, dict):
        raise HierarchicalEmitError(
            "E_SPEC_MALFORMED_SHAPE",
            f"spec must be a dict, received {type(spec).__name__}.",
            received_type=type(spec).__name__,
        )
    raw_components = spec.get("components")
    if not raw_components:
        SPEC_ENTRY_COUNTERS["raised_no_components"] += 1
        raise HierarchicalEmitError(
            "E_SPEC_NO_COMPONENTS",
            "spec declares no components. An empty draw is refused rather than "
            "returning a valid-looking file set with nothing in it.",
        )

    sheet_map = partition_components(spec, project_name=project_name)
    nets = parse_spec_nets(spec.get("nets"))

    by_ref = {ref: sheet for sheet, refs in sheet_map.sheets.items() for ref in refs}
    routed_nc = split_nc_by_sheet(spec.get("nc"), by_ref)

    comp_by_ref = {}
    for comp in raw_components:
        ref = str(comp.get("ref", "")).strip()
        if ref:
            comp_by_ref[ref] = comp

    placed: list[EmitComponent] = []
    for sheet_name, refs in sheet_map.sheets.items():
        for position, ref in enumerate(refs):
            source = comp_by_ref[ref]
            declared_x, declared_y = source.get("x"), source.get("y")
            if declared_x is not None and declared_y is not None:
                pos_x, pos_y = float(declared_x), float(declared_y)
            else:
                pos_x, pos_y = _auto_place_local(position)
            placed.append(EmitComponent(
                ref=ref,
                lib_id=str(source.get("symbol", "")).strip(),
                value=str(source.get("value", "")),
                footprint=str(source.get("footprint", "")),
                x=pos_x, y=pos_y,
            ))

    # DD-14: a spec may name which sheets are subsystem VIEWS (local wires drawn,
    # continuation carried by an appended global_label). Declared in the spec so the
    # MCP surface can express it; a kwarg of the same name is merged rather than
    # silently overridden, because a caller setting both means both.
    declared_views = spec.get("subsystem_views")
    if declared_views is not None and not isinstance(declared_views, dict):
        raise HierarchicalEmitError(
            "E_SPEC_SUBSYSTEM_VIEWS_SHAPE",
            f"spec['subsystem_views'] must be a mapping of sheet name -> list of "
            f"that subsystem's net names, received "
            f"{type(declared_views).__name__}. A bare list of sheet names is "
            f"refused because it does not say WHICH nets the view may draw "
            f"locally, and un-scoped local drawing fuses the shared rails.",
            received_type=type(declared_views).__name__,
        )
    views: dict[str, set[str]] = {}
    for source in (emit_kwargs.pop("subsystem_views", None) or {}, declared_views or {}):
        for sheet, sheet_nets in source.items():
            views.setdefault(str(sheet), set()).update(str(n) for n in sheet_nets)

    # Size-aware layout is enabled ONLY when the spec left placement to us. A spec
    # that declared coordinates gets them honoured exactly as before -- re-placing a
    # caller's explicit geometry would be a silent override, and the legacy
    # byte-stability regression depends on that path being untouched.
    any_declared = any(
        c.get("x") is not None and c.get("y") is not None
        for c in raw_components if isinstance(c, dict))
    emit_kwargs.setdefault("auto_layout", not any_declared)
    # DD-15: `layout_engine` may be declared in the spec or passed as a kwarg;
    # both set and different is a contradiction, refused rather than resolved.
    spec_engine = spec.get("layout_engine")
    kw_engine = emit_kwargs.get("layout_engine")
    if spec_engine is not None and kw_engine is not None and spec_engine != kw_engine:
        raise HierarchicalEmitError(
            "E_ENGINE_CONFLICT",
            f"spec['layout_engine']={spec_engine!r} and kwarg layout_engine="
            f"{kw_engine!r} disagree.", spec=spec_engine, kwarg=kw_engine)
    if spec_engine is not None:
        emit_kwargs["layout_engine"] = str(spec_engine)
    if spec.get("engine_placement_models") is not None:
        emit_kwargs["engine_placement_models"] = tuple(str(n) for n in spec["engine_placement_models"])
    if spec.get("engine_outline_refs") is not None:
        emit_kwargs["engine_outline_refs"] = tuple(str(r) for r in spec["engine_outline_refs"])
    if spec.get("engine_spacing_overrides") is not None:
        emit_kwargs["engine_spacing_overrides"] = {
            str(k): str(v) for k, v in dict(spec["engine_spacing_overrides"]).items()}
    if spec.get("engine_orientation_sets") is not None:
        emit_kwargs["engine_orientation_sets"] = {
            str(r): tuple(ids) for r, ids in dict(spec["engine_orientation_sets"]).items()}
    if views or emit_kwargs.get("trim_small_replicas"):
        emit_kwargs.setdefault("trim_small_replicas", True)

    return emit_hierarchical_schematic(
        project_dir, project_name, placed, nets, sheet_map,
        per_sheet_nc=routed_nc if spec.get("nc") else None,
        subsystem_views={k: sorted(v) for k, v in views.items()} or None,
        **emit_kwargs)


__all__ = [
    "EMIT_MODE_HIERARCHICAL",
    "replica_nodes_for_view",
    "EMIT_MODE_LEGACY",
    "SPEC_ENTRY_COUNTERS",
    "HierarchicalEmitError",
    "HierarchicalEmitResult",
    "PartitionError",
    "assert_no_endpoint_lost",
    "emit_from_spec",
    "emit_hierarchical_schematic",
    "emit_multisheet",
    "nets_by_sheet",
    "parse_spec_nets",
    "split_nc_by_sheet",
]
