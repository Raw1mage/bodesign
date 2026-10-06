"""Display-fidelity check for replica views (design.md DD-13 clause 4c, F-1/F-2/F-3).

WHY THIS IS A SEPARATE MODULE FROM `fidelity.py`
-------------------------------------------------
`fidelity.py` compares a spec partition against an EXPORTED NETLIST. This check
exists precisely because the exported netlist has ZERO discriminating power here: a
replica symbol carries `(on_board no)`, so its pins are absent from the export by
construction, and the netlist of a CORRECT replica is identical to that of a
miswired one (measured, DD-13 clause 3). The instrument must read the leaf
`.kicad_sch` itself. Two instruments whose input sources are opposites do not belong
in one module -- a reader reaching for "the fidelity check" must not find the one
that cannot see the defect.

WHAT IS CHECKED (the three frozen obligations)
-----------------------------------------------
F-1  every drawn attachment maps to a canonical `ref.pin` -> net
F-2  no invented or contradictory local connection
F-3  every requested net is actually expanded

UNSUPPORTED INPUT IS `indeterminate`, NEVER `ok`
-------------------------------------------------
The drawn map is built from geometry this engine emits: symbols at rotation 0, with
`global_label` anchors coinciding with pin endpoints. Anything outside that -- a
rotated symbol, a wire endpoint on a replica pin, a symbol whose library definition
is not embedded -- is reported as INDETERMINATE with the reason named. It is never
silently treated as "no violation found", because "the drawing is right" and "the
parser could not read the drawing" would otherwise share one output.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .kicad_emit import _extract_symbol_block, _pin_endpoints

#: Coordinate tolerance (mm) when matching a label anchor to a pin endpoint. The
#: emitter rounds to 4 decimals and snaps to a 1.27 mm grid, so anything this close
#: is the same point; anything further apart is a different point on the grid.
_COORD_EPS_MM = 0.01

#: Status codomain (errors.md §Outcome Codomain). Five values, none collapsible.
STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_NOT_RUN = "not-run"
STATUS_EMPTY = "empty"
STATUS_INDETERMINATE = "indeterminate"

_SYMBOL_BLOCK_RE = re.compile(r"^  \(symbol\n", re.M)
_AT_RE = re.compile(r"\(at\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)")
_LIB_ID_RE = re.compile(r'\(lib_id "([^"]+)"\)')
_REF_RE = re.compile(r'\(property "Reference" "([^"]+)"')
_FLAGS_RE = re.compile(r"\(in_bom (yes|no)\) \(on_board (yes|no)\)")
_GLOBAL_LABEL_RE = re.compile(
    r'\(global_label "([^"]+)"[^\n]*?\(at\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)')
_LOCAL_LABEL_RE = re.compile(
    r'^  \(label "([^"]+)" \(at\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)', re.M)
_WIRE_RE = re.compile(
    r"\(wire \(pts \(xy\s+(-?[0-9.]+)\s+(-?[0-9.]+)\) "
    r"\(xy\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)\)")


class ReplicaFidelityError(ValueError):
    """A display-fidelity violation. Carries `code` for machine branching."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


@dataclass
class DrawnSymbol:
    """One placed symbol read back out of a landed leaf file."""

    ref: str
    lib_id: str
    x: float
    y: float
    rotation: float
    in_bom: str
    on_board: str

    @property
    def is_replica(self) -> bool:
        """The two neutrality flags together. Either alone is NOT a replica.

        `on_board no` alone still leaves a BOM row; `in_bom no` alone still puts the
        pins in the netlist. Requiring both is what makes this predicate mean what
        DD-13 clause 2 measured.
        """
        return self.in_bom == "no" and self.on_board == "no"


@dataclass
class ReplicaFidelityReport:
    """Result of checking ONE leaf's replica views.

    `status` is five-valued on purpose. `ok` and `empty` are different questions
    ("nothing was wrong" vs "there was nothing to check"), and `indeterminate` is
    what a parser that could not read the geometry returns instead of a clean pass.
    """

    status: str
    sheet: str
    leaf_path: str
    #: (ref, pin) -> net name, as DRAWN in the leaf file.
    drawn: dict[tuple[str, str], str] = field(default_factory=dict)
    #: (ref, pin) -> net name, from the canonical netlist export.
    canonical: dict[tuple[str, str], str] = field(default_factory=dict)
    violations: list[dict] = field(default_factory=list)
    #: Why the result is indeterminate. Empty on every other status.
    indeterminate_reasons: list[str] = field(default_factory=list)
    #: How many replica symbols were found in this leaf. 0 with status `empty`
    #: means the leaf legitimately has none; 0 with a non-empty request list is a
    #: violation, not an absence.
    replica_symbols_found: int = 0
    replica_views_requested: int = 0

    @property
    def ok(self) -> bool:
        return self.status == STATUS_OK

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "sheet": self.sheet,
            "leaf_path": self.leaf_path,
            "drawn": {f"{ref}.{pin}": net for (ref, pin), net in self.drawn.items()},
            "canonical": {f"{ref}.{pin}": net
                          for (ref, pin), net in self.canonical.items()},
            "violations": list(self.violations),
            "indeterminate_reasons": list(self.indeterminate_reasons),
            "replica_symbols_found": self.replica_symbols_found,
            "replica_views_requested": self.replica_views_requested,
        }


def _balanced(text: str, start: int) -> str:
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
    raise ReplicaFidelityError(
        "E_LEAF_SEXPR_UNBALANCED",
        "an s-expression in the leaf never closes; refusing to guess its extent.",
        offset=start,
    )


def parse_placed_symbols(text: str) -> list[DrawnSymbol]:
    """Every top-level placed symbol in a leaf, with its flags and transform."""
    out: list[DrawnSymbol] = []
    for match in _SYMBOL_BLOCK_RE.finditer(text):
        block = _balanced(text, text.index("(", match.start()))
        lib_match = _LIB_ID_RE.search(block)
        ref_match = _REF_RE.search(block)
        at_match = _AT_RE.search(block)
        flags_match = _FLAGS_RE.search(block)
        if not (lib_match and ref_match and at_match and flags_match):
            continue
        out.append(DrawnSymbol(
            ref=ref_match.group(1),
            lib_id=lib_match.group(1),
            x=float(at_match.group(1)),
            y=float(at_match.group(2)),
            rotation=float(at_match.group(3)),
            in_bom=flags_match.group(1),
            on_board=flags_match.group(2),
        ))
    return out


def _lib_symbols_source(text: str) -> str:
    marker = text.find("(lib_symbols")
    if marker < 0:
        return ""
    return _balanced(text, marker)


def pin_endpoints_absolute(
    symbol: DrawnSymbol,
    lib_source: str,
) -> tuple[dict[str, tuple[float, float]], list[str]]:
    """Absolute (x, y) of every pin of one placed symbol, plus refusal reasons.

    Only rotation 0 is supported, because that is the only transform this engine
    emits. A rotated symbol returns NO endpoints and a reason -- guessing the
    rotated coordinates would produce a drawn map that looks complete and is wrong.
    """
    reasons: list[str] = []
    if abs(symbol.rotation) > _COORD_EPS_MM:
        reasons.append(
            f"{symbol.ref}: symbol placed at rotation {symbol.rotation}; this "
            f"parser resolves pin endpoints for rotation 0 only, so its drawn "
            f"attachments are UNREAD rather than assumed correct")
        return {}, reasons
    block = _extract_symbol_block(lib_source, symbol.lib_id)
    if block is None:
        reasons.append(
            f"{symbol.ref}: lib_id {symbol.lib_id!r} has no definition embedded in "
            f"this leaf's lib_symbols, so its pin geometry is unknown")
        return {}, reasons
    endpoints: dict[str, tuple[float, float]] = {}
    for pin, (px, py, _rot) in _pin_endpoints(block).items():
        endpoints[pin] = (round(symbol.x + px, 4), round(symbol.y - py, 4))
    if not endpoints:
        reasons.append(
            f"{symbol.ref}: the embedded definition of {symbol.lib_id!r} declares "
            f"no pins, so no attachment can be resolved")
    return endpoints, reasons


def _near(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= _COORD_EPS_MM and abs(a[1] - b[1]) <= _COORD_EPS_MM


def drawn_map_for_refs(
    text: str,
    refs: set[str],
) -> tuple[dict[tuple[str, str], list[str]], list[str]]:
    """(ref, pin) -> the net names DRAWN on that pin, for the given refs only.

    A pin carrying two different label names yields two entries; F-2 is what turns
    that into a violation, so this function reports rather than resolves it.

    Wire endpoints landing on a tracked pin are NOT traced. They are returned as
    refusal reasons: resolving a wire to a net name needs a full wire-graph walk
    with junction semantics, and inventing an answer for it would be exactly the
    "guessed correct" this contract forbids.
    """
    reasons: list[str] = []
    lib_source = _lib_symbols_source(text)
    if not lib_source:
        return {}, ["the leaf carries no (lib_symbols) block; no pin geometry"]

    endpoints: dict[tuple[str, str], tuple[float, float]] = {}
    for symbol in parse_placed_symbols(text):
        if symbol.ref not in refs:
            continue
        pins, why = pin_endpoints_absolute(symbol, lib_source)
        reasons.extend(why)
        for pin, position in pins.items():
            endpoints[(symbol.ref, pin)] = position

    labels: list[tuple[str, tuple[float, float]]] = [
        (m.group(1), (float(m.group(2)), float(m.group(3))))
        for m in _GLOBAL_LABEL_RE.finditer(text)
    ]
    labels.extend(
        (m.group(1), (float(m.group(2)), float(m.group(3))))
        for m in _LOCAL_LABEL_RE.finditer(text)
    )

    wire_ends: list[tuple[float, float]] = []
    for match in _WIRE_RE.finditer(text):
        wire_ends.append((float(match.group(1)), float(match.group(2))))
        wire_ends.append((float(match.group(3)), float(match.group(4))))

    drawn: dict[tuple[str, str], list[str]] = {}
    for key, position in endpoints.items():
        for name, anchor in labels:
            if _near(position, anchor):
                drawn.setdefault(key, []).append(name)
        for end in wire_ends:
            if _near(position, end):
                reasons.append(
                    f"{key[0]}.{key[1]}: a wire endpoint lands on this pin; this "
                    f"parser does not trace wire graphs, so the net it carries is "
                    f"UNREAD rather than assumed to match")
                break
    return drawn, reasons


def canonical_pin_net_map(netlist_path: str | Path) -> dict[tuple[str, str], str]:
    """(ref, pin) -> net name, from an exported KiCad netlist.

    This is the CANONICAL side. It comes from the home design's export, where the
    replica's own pins are absent by construction -- which is the whole reason the
    drawn side has to be parsed from the leaf instead.
    """
    text = Path(netlist_path).read_text(encoding="utf-8", errors="replace")
    out: dict[tuple[str, str], str] = {}
    for block_match in re.finditer(r'\(net \(code "[^"]*"\) \(name "([^"]*)"\)',
                                   text):
        name = block_match.group(1)
        block = _balanced(text, text.rindex("(", 0, block_match.end()) if False
                          else block_match.start())
        for node in re.finditer(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', block):
            out[(node.group(1), node.group(2))] = name
    return out


def export_netlist(sch_path: str | Path, out_path: str | Path) -> tuple[int, str]:
    """Run kicad-cli. Returns (returncode, combined output) -- never raises on rc."""
    result = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "-o", str(out_path),
         str(sch_path)],
        capture_output=True, text=True,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def check_replica_display_fidelity(
    leaf_path: str | Path,
    sheet: str,
    views: list[tuple[str, object]],
    canonical: dict[tuple[str, str], str],
) -> ReplicaFidelityReport:
    """F-1/F-2/F-3 for one leaf.

    leaf_path: the LANDED `.kicad_sch` -- the drawn map is read from these bytes,
               never from an emitter's intended-connection list.
    views:     (ref, ReplicaView) pairs this leaf was asked to draw.
    canonical: (ref, pin) -> net, from the home design's netlist export.
    """
    path = Path(leaf_path)
    report = ReplicaFidelityReport(
        status=STATUS_NOT_RUN, sheet=sheet, leaf_path=str(path),
        canonical=dict(canonical), replica_views_requested=len(views),
    )
    if not path.exists():
        report.status = STATUS_FAILED
        report.violations.append({
            "code": "E_REPLICA_LEAF_MISSING",
            "detail": f"{path} does not exist; no drawing could be read.",
        })
        return report

    text = path.read_text(encoding="utf-8")
    symbols = parse_placed_symbols(text)
    replica_symbols = [s for s in symbols if s.is_replica]
    report.replica_symbols_found = len(replica_symbols)

    if not views:
        # Nothing was REQUESTED. That is `empty`, not `ok`: no obligation was
        # examined, so this result carries no evidence about drawing correctness.
        report.status = STATUS_EMPTY
        return report

    requested_refs = {ref for ref, _view in views}
    drawn_refs = {s.ref for s in replica_symbols}
    missing_symbols = sorted(requested_refs - drawn_refs)
    if missing_symbols:
        report.violations.append({
            "code": "E_REPLICA_SYMBOL_NOT_DRAWN",
            "refs": missing_symbols,
            "detail": f"{missing_symbols} were requested as replica views on "
                      f"{sheet!r} but no symbol carrying BOTH (in_bom no) and "
                      f"(on_board no) was found in the landed file.",
        })

    drawn, reasons = drawn_map_for_refs(text, requested_refs)
    report.drawn = {key: names[0] for key, names in drawn.items() if names}
    report.indeterminate_reasons = reasons

    for (ref, pin), names in sorted(drawn.items()):
        # --- F-2: two different nets on one pin --------------------------------
        distinct = sorted(set(names))
        if len(distinct) > 1:
            report.violations.append({
                "code": "E_REPLICA_WIRE_CONTRADICTS_HOME",
                "obligation": "F-2",
                "ref": ref, "pin": pin, "drawn_nets": distinct,
                "detail": f"{ref}.{pin} is drawn attached to {distinct}; one pin "
                          f"cannot depict two nets.",
            })
            continue
        drawn_net = distinct[0]
        canonical_net = canonical.get((ref, pin))
        # --- F-2: an attachment on a pin with no canonical net -----------------
        if canonical_net is None:
            report.violations.append({
                "code": "E_REPLICA_WIRE_CONTRADICTS_HOME",
                "obligation": "F-2",
                "ref": ref, "pin": pin, "drawn_net": drawn_net,
                "detail": f"{ref}.{pin} is drawn on {drawn_net!r} but the canonical "
                          f"design assigns this pin to no net at all; the drawing "
                          f"invents a connection the netlist cannot contradict.",
            })
            continue
        # --- F-1: the attachment names a DIFFERENT canonical net ---------------
        if drawn_net != canonical_net:
            report.violations.append({
                "code": "E_REPLICA_WIRE_NOT_CANONICAL",
                "obligation": "F-1",
                "ref": ref, "pin": pin,
                "drawn_net": drawn_net, "canonical_net": canonical_net,
                "detail": f"{ref}.{pin} is drawn on {drawn_net!r}; the canonical "
                          f"design puts it on {canonical_net!r}. The exported "
                          f"netlist is IDENTICAL either way, which is why this "
                          f"check reads the leaf file.",
            })

    # --- F-3: every requested net actually expanded ----------------------------
    for ref, view in views:
        drawn_here = {name
                      for (drawn_ref, _pin), names in drawn.items()
                      if drawn_ref == ref
                      for name in names}
        for net in getattr(view, "nets", ()):
            if net not in drawn_here:
                report.violations.append({
                    "code": "E_REPLICA_NET_NOT_EXPANDED",
                    "obligation": "F-3",
                    "ref": ref, "net": net, "sheet": sheet,
                    "drawn_nets": sorted(drawn_here),
                    "detail": f"{ref}: view on {sheet!r} requested net {net!r}, "
                              f"which appears on NO drawn attachment. Requesting a "
                              f"net and drawing nothing is the failure that looks "
                              f"like success in every other check.",
                })

    if report.violations:
        report.status = STATUS_FAILED
    elif reasons:
        # Nothing was found wrong, but part of the drawing could not be read. That
        # is NOT a pass: the unread part is exactly where a defect could hide.
        report.status = STATUS_INDETERMINATE
    else:
        report.status = STATUS_OK
    return report


__all__ = [
    "STATUS_EMPTY",
    "STATUS_FAILED",
    "STATUS_INDETERMINATE",
    "STATUS_NOT_RUN",
    "STATUS_OK",
    "DrawnSymbol",
    "ReplicaFidelityError",
    "ReplicaFidelityReport",
    "canonical_pin_net_map",
    "check_replica_display_fidelity",
    "drawn_map_for_refs",
    "export_netlist",
    "parse_placed_symbols",
    "pin_endpoints_absolute",
]
