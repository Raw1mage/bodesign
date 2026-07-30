"""C03→C04 stage-entry readiness gate (BR_20260707).

Deterministic machine check that C03 (EE) delivery is complete BEFORE C04 layout
may start. The pre-existing bodesign lifecycle only had a C04 *output* gate
(check_c04: copper/unconnected/SI); there was no C04 *entry* gate on C03
deliverable completeness — so an incomplete BOM (draft/blocked rows, BOM↔SSOT
conflicts, unfrozen pad counts) leaked into C04 and was only found by downstream
collisions. This module is that entry gate.

Design (matches prd_bom_crosscheck): pure function, no LLM, no fallback. Missing
inputs raise (typed); blocking findings return normally as gate="FAIL". Gate
thresholds are NEVER relaxed to pass (check_c04 floating-PSRAM false-pass lesson,
AGENTS.md §3).

Hard-fail conditions (BR acceptance criteria R1–R4):
  R1 BOM schema lint   — inconsistent column count (quoting breakage) / bad status
                         enum / duplicate (board, ref)
  R2 BOM readiness     — any draft/blocked row; a finalized row whose mpn carries
                         TBC/TBD/UNDECIDED
  R3 drawability       — every row needs a symbol-source marker
                         (official | vendor+LCSC id | manual | N-A)
  R4 SSOT crosscheck   — active BOM parts vs Pin_Allocation.csv agree (no
                         wireless/interface-scheme conflict); J_* pad counts match
                         a frozen tally when provided. Ref-level matching requires a
                         ref-bearing column in the pinmap; a ball/peripheral-oriented
                         pinmap (the shape the deliverable table specifies) reports
                         ssot_crosscheck.status="not_run" instead of flagging every
                         active part.
  R5 BOM<->netlist     — every BOM row that should exist as a schematic symbol is
                         present in the supplied netlist(s). Requires netlist_path;
                         when absent the report says netlist_crosscheck.status=
                         "not_run" rather than letting PASS imply it was checked.
                         NOTE R3 vs R5: R3 checks the row CLAIMS a symbol source;
                         R5 checks the symbol was actually DRAWN. R3 alone passing
                         never means the part exists in the schematic.
  R6 pin-spec polarity — a BOM row's parenthesised pin spec, e.g. "FPC 4P(R/G/B/GND)",
                         must not contradict the netlist on ground-vs-supply. Such a
                         mismatch is electrically LEGAL (a connector pin on GND is a
                         valid net), so ERC/DRC pass while the board cannot work.
                         Requires netlist_path; reports not_run otherwise.
Warn (non-blocking): stock=0, mechanical MPN TBC — procurement notes.

Error codes:
  BOM_MISSING          bom csv absent
  BOM_EMPTY            zero data rows
  PIN_ALLOC_MISSING    pin-allocation csv named but absent
  NETLIST_MISSING      netlist path named but absent
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPORT_SCHEMA = "bodesign.c03.stage_entry_gate.v1"
REPORT_FILENAME = "check_c03.report.json"

# Allowed BOM row lifecycle states.
# BR_20260730 F3: "design-ready" is ADMITTED as a first-class state. It was already
# in production use (21 rows of the aiguard C03 BOM) and a consumer-side gate
# treated it as passing, while this gate rejected it as an unknown status — the two
# gates returned opposite verdicts on the same file with neither reporting a
# conflict. Admitting it (rather than forcing a rename) is the honest resolution:
# the state has a real, distinct meaning below `finalized` — see _READY_STATUS.
_STATUS_ENUM = {"finalized", "design-ready", "draft", "blocked", "proposed", "alternate"}
# States that clear the C04-entry readiness bar.
#   finalized    — part fully specified, mpn committed, ready to order
#   design-ready — electrically/mechanically decided and drawable, mpn may still be
#                  generic (owner-decided interface, vendor selection deferred).
#                  Sufficient for LAYOUT entry; NOT sufficient for procurement.
_READY_STATUS = {"finalized", "design-ready"}
# States that block C04 entry outright.
_BLOCKING_STATUS = {"draft", "blocked"}
# Placeholder tokens forbidden in a finalized part's mpn (case-insensitive).
_FORBIDDEN_MPN = ("tbc", "tbd", "undecided", "todo", "xxx", "???")
# Recognised symbol-source markers (R3 drawability).
_SYMBOL_SOURCES = ("official", "vendor", "lcsc", "manual", "n-a", "n/a")
# A bare LCSC part number is itself vendor-fetchable symbol evidence, and is
# STRICTER than the bare literal "lcsc" already accepted above (an id can be
# resolved; the word cannot). Accepting it is therefore not a relaxation — it
# closes a third vocabulary divergence with the consumer-side gate, which has
# always accepted this form (check_bom.py R4). Requires >=5 digits so a value
# like "C1" is not mistaken for a part number.
_LCSC_ID = re.compile(r"\bC\d{5,}\b", re.I)
# Column aliases carrying the R3 symbol-source evidence. `deck_status` is the name
# actually used by the c03-ee GUIDE and by every product BOM; omitting it meant
# _col_index returned None -> symbol_name None -> EVERY row failed R3. A gate that
# fails all rows has the same discriminating power as one that passes all rows:
# none. "I could not find the column" was being reported as "the column is empty"
# (BR_20260730; same shape as the mcpctl busy-probe UNKNOWN lesson).
_SYMBOL_COLUMNS = ("symbol_source", "symbol", "sym_source", "drawability", "deck_status")
# Reference prefixes considered "active" for the SSOT crosscheck (drive interfaces).
_ACTIVE_PREFIXES = ("U", "J", "Y", "SW")

# ── R5 (BOM <-> netlist) scope machinery ────────────────────────────────────
# A netlist covers ONE schematic sheet-set; a product BOM covers the whole product
# across several boards and several modules. A naive set-difference between the two
# is therefore NOT a defect detector — measured on the real aiguard inputs it
# yields 33 findings of which 2 are genuine. R5 must state the basis of its own
# verdict rather than pretend the two sets are comparable (V5/V6 discipline).
#
# Refs legitimately absent from an EE netlist:
_NONELECTRICAL_PREFIXES = ("LENS", "ANT")   # optics / passive radiator: no symbol
# Aggregate BOM rows (e.g. "C*/R*") stand for a class, not one placed part.
_AGGREGATE_MARKERS = ("*", "?")

# ── R6 (pin-spec polarity) ──────────────────────────────────────────────────
# BOM rows for connectors carry a parenthesised pin spec, e.g.
#   "FPC 4P 1.0mm(R/G/B/GND)".
# That text READS like a comment but is used downstream as the wiring spec: a
# schematic-capture agent wires pin N to whatever token N says. When the spec is
# wrong the resulting netlist is *electrically legal* — a connector pin tied to GND
# is a perfectly valid net — so ERC/DRC pass and the defect is functional only
# (BR_20260730 round=2: J_LED specced "(R/G/B/GND)" against a common-ANODE LED;
# pin 4 was wired to GND, the anodes lost their supply, the LED could never light,
# and every connectivity check was green).
#
# R6 checks only the one class of mismatch that is unambiguous and cannot be a
# naming-style difference: a GROUND/SUPPLY polarity inversion. Exact token-to-net
# matching was tried and rejected — the corrected spec "+3V3 common-anode" does not
# string-equal its net "+3V3_PB", so exact matching would flag the *right* answer.
# A check that flags correct work is worse than no check.
_GND_TOKENS = ("gnd", "vss", "agnd", "dgnd", "ground", "0v", "vee")
_PWR_PREFIXES = ("+", "vdd", "vcc", "vbat", "vbus", "vin", "vout", "vsys", "vdda")
_PWR_PATTERN = re.compile(r"^\+|\b\d+v\d*\b|\bv(dd|cc|bat|bus|in|out|sys)\b")


@dataclass
class RowFinding:
    board: str
    ref: str
    code: str            # R1_SCHEMA | R2_READINESS | R3_DRAWABILITY | R4_SSOT
    detail: str


@dataclass
class CheckC03Result:
    schema: str = REPORT_SCHEMA
    gate: str = "PASS"                       # 'PASS' | 'FAIL'
    blocking: list[RowFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    bom_rows: int = 0
    active_parts: int = 0
    ssot_checked: bool = False
    # BR_20260730 F2: always present. {"status": "not_run", ...} when no netlist was
    # supplied, so a caller can never mistake "never checked" for "checked, clean".
    netlist_crosscheck: dict = field(default_factory=lambda: {"status": "not_run"})
    # BR_20260730 R6: same not_run discipline — a caller must never read a clean
    # gate as "the pin specs were checked" when no netlist was supplied.
    pin_polarity: dict = field(default_factory=lambda: {"status": "not_run"})
    # BR_20260730: `ssot_checked` alone could not distinguish "crosschecked, clean"
    # from "could not crosscheck at all". This carries the basis of that verdict.
    ssot_crosscheck: dict = field(default_factory=lambda: {"status": "not_run"})


# ── CSV loading (quoting-破損 surfaces as a schema finding, not a crash) ─────

def _read_csv_rows(path: str) -> tuple[list[str], list[list[str]]]:
    """Return (header, raw_rows) with each raw row kept as a list so a row whose
    physical column count differs from the header (quoting breakage) is detectable.
    Uses csv so quoted commas are honoured; a genuinely malformed quote still yields
    a mismatched-length row rather than an exception."""
    text = Path(path).read_text(encoding="utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if r and any(c.strip() for c in r)]
    # BR_20260730: '#' section banners are a documented BOM convention (every
    # product BOM groups rows by module with them). Keeping them made each one
    # surface as R1_SCHEMA "likely CSV quoting breakage" — 28 findings on the real
    # aiguard BOM, every one a misdiagnosis pointing the caller at a quoting bug
    # that does not exist. Drop them BEFORE the column-count check so R1 reports
    # only genuine schema damage.
    rows = [r for r in rows if not r[0].lstrip().startswith("#")]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _col_index(header: list[str], *names: str) -> int | None:
    low = [_norm(h) for h in header]
    for n in names:
        if n in low:
            return low.index(n)
    return None


# ── individual checks (pure) ────────────────────────────────────────────────

def _check_schema(header: list[str], raw_rows: list[list[str]],
                  status_i: int | None, board_i: int | None, ref_i: int | None) -> list[RowFinding]:
    findings: list[RowFinding] = []
    ncol = len(header)
    seen: set[tuple[str, str]] = set()
    for n, row in enumerate(raw_rows, start=2):  # line 1 = header
        board = row[board_i].strip() if (board_i is not None and board_i < len(row)) else ""
        ref = row[ref_i].strip() if (ref_i is not None and ref_i < len(row)) else ""
        if len(row) != ncol:
            findings.append(RowFinding(board, ref or f"line{n}", "R1_SCHEMA",
                                       f"column count {len(row)} != header {ncol} "
                                       "(likely CSV quoting breakage)"))
            continue
        if status_i is not None:
            st = _norm(row[status_i])
            if st and st not in _STATUS_ENUM:
                findings.append(RowFinding(board, ref or f"line{n}", "R1_SCHEMA",
                                           f"unknown status {row[status_i]!r} "
                                           f"(allowed: {sorted(_STATUS_ENUM)})"))
        if ref:
            key = (board, ref)
            if key in seen:
                findings.append(RowFinding(board, ref, "R1_SCHEMA",
                                           "duplicate (board, ref)"))
            seen.add(key)
    return findings


def _check_readiness(rows: list[dict], status_i_name: str, mpn_i_name: str) -> list[RowFinding]:
    findings: list[RowFinding] = []
    for r in rows:
        st = _norm(r.get(status_i_name, ""))
        board, ref = r.get("_board", ""), r.get("_ref", "")
        if st in _BLOCKING_STATUS:
            findings.append(RowFinding(board, ref, "R2_READINESS",
                                       f"row status={st or 'unset'} blocks C04 entry"))
        if st == "finalized":
            mpn = _norm(r.get(mpn_i_name, ""))
            if any(tok in mpn for tok in _FORBIDDEN_MPN):
                findings.append(RowFinding(board, ref, "R2_READINESS",
                                           f"finalized row mpn carries placeholder ({r.get(mpn_i_name)!r})"))
        # BR_20260730 F3: a `design-ready` row is allowed a generic/deferred mpn
        # (that is precisely what distinguishes it from `finalized`), so the
        # placeholder check above deliberately does NOT apply to it. It is
        # sufficient for C04 layout entry and insufficient for procurement; the
        # procurement gate is a separate check, not this one.
    return findings


def _check_drawability(rows: list[dict], symbol_i_name: str | None) -> list[RowFinding]:
    """R3 — every row must CLAIM a symbol source.

    Scope (BR_20260730 F5): this asserts the BOM row carries symbol-source
    *evidence*, i.e. it claims to be drawable. It does NOT verify the symbol was
    actually placed in the schematic — that is R5's job (BOM<->netlist). Do not
    read a passing R3 as "the part is drawn"; it means "the row says where its
    symbol comes from".
    """
    findings: list[RowFinding] = []
    if symbol_i_name is None:
        # BR_20260730: NO symbol column at all. Report this ONCE as a schema-level
        # blocker instead of blaming all N rows for an empty value we never read.
        # "I could not find the column" is not "the column is empty" — the former
        # is a gate-input defect, the latter a BOM-content defect, and conflating
        # them made the gate fail every row of a BOM whose evidence column simply
        # had a different (documented) name.
        return [RowFinding("", "<schema>", "R3_DRAWABILITY",
                           "no symbol-source column found in BOM header "
                           f"(looked for: {', '.join(_SYMBOL_COLUMNS)}) — "
                           "cannot assess drawability for any row")]
    for r in rows:
        board, ref = r.get("_board", ""), r.get("_ref", "")
        raw = (r.get(symbol_i_name) or "").strip()
        marker = _norm(raw)
        if any(s in marker for s in _SYMBOL_SOURCES) or _LCSC_ID.search(raw):
            continue
        # Distinguish "declared nothing" from "declared, but the origin class is not
        # one we recognise". Both stay BLOCKING — the vocabulary is deliberately not
        # widened to make a row pass — but the caller needs to know which edit fixes
        # it: add a declaration, versus name the origin class of an existing one.
        # (Reporting both as "no symbol source marker" sent a caller looking for a
        # missing field that was in fact present.)
        if "symbol=" in marker:
            declared = raw.split("symbol=", 1)[1][:60]
            detail = ("symbol source declared but its origin class is unrecognised "
                      f"(found: {declared!r}); name one of "
                      "official | vendor+LCSC | manual | N-A")
        else:
            detail = ("no symbol source marker "
                      "(official | vendor+LCSC | manual | N-A)")
        findings.append(RowFinding(board, ref, "R3_DRAWABILITY", detail))
    return findings


# ── R5: BOM <-> netlist ref consistency (BR_20260730 F2) ────────────────────

def _netlist_refs(path: str) -> set[str]:
    """Component refs declared in a KiCad netlist: `(comp (ref "U1")`."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return {m.group(1).strip()
            for m in re.finditer(r'\(\s*comp\s+\(\s*ref\s+"?([^\s")]+)"?', text)}


def _netlist_scope(path: str) -> str:
    """The schematic this netlist was exported from (its own `(source ...)`)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    m = re.search(r'\(\s*source\s+"([^"]+)"', text)
    return os.path.basename(m.group(1)) if m else "unknown"


def _is_aggregate_ref(ref: str) -> bool:
    return any(mk in ref for mk in _AGGREGATE_MARKERS)


def _netlist_part_text(path: str) -> dict[str, str]:
    """{ref: searchable text} per netlist component (value + footprint + fields).

    Used to answer "is this BOM part drawn under a DIFFERENT refdes?" — see
    _check_netlist's refdes-divergence classification. Matching on part identity
    (mpn) rather than refdes is the only way to tell "never drawn" apart from
    "drawn, but the schematic and the BOM disagree on what to call it".
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    out: dict[str, str] = {}
    for m in re.finditer(r'\(\s*comp\s+\(\s*ref\s+"?([^\s")]+)"?\)(.{0,800}?)'
                         r'(?=\(\s*comp\s+\(\s*ref\s|\Z)', text, re.S):
        out[m.group(1).strip()] = m.group(2)
    return out


#: An mpn fragment shorter than this is too generic to identify a part by
#: (e.g. "C", "10uF"), so a match on it would be coincidence, not evidence.
_MPN_MIN_MATCH = 5


def _find_by_mpn(row: dict, mpn_name: str | None,
                 part_text: dict[str, str]) -> tuple[str, str] | None:
    """Is this BOM row's part drawn under some OTHER refdes? -> (that_ref, basis).

    Answers the question that separates "never drawn" from "drawn under a name the
    BOM does not use". Matching is on the mpn, because that is what identifies a
    physical part independently of what either document calls it.

    Conservative by construction — a FALSE divergence claim is worse than missing
    one, because it tells the caller a part exists when it may not:
      - needs an mpn of at least _MPN_MIN_MATCH chars (a 1-2 char mpn matches
        everything), and the mpn must not be a placeholder token;
      - the mpn must appear in the netlist component's own text (value / footprint
        / fields), not merely share a prefix;
      - the longest mpn stem is tried first so "nRF7002-QFAA-R" prefers the exact
        part over a family-wide "nRF7002" hit;
      - returns None on ambiguity (2+ candidate refs), because a guess between two
        parts is exactly the kind of confident-but-wrong output this repo lints for.
    """
    if not mpn_name:
        return None
    mpn = _norm(row.get(mpn_name, ""))
    if len(mpn) < _MPN_MIN_MATCH or any(tok in mpn for tok in _FORBIDDEN_MPN):
        return None
    # Progressively shorter stems: full mpn first, then drop trailing -SUFFIXes.
    stems = [mpn]
    parts = mpn.split("-")
    for cut in range(len(parts) - 1, 0, -1):
        stem = "-".join(parts[:cut])
        if len(stem) >= _MPN_MIN_MATCH:
            stems.append(stem)
    for stem in stems:
        hits = [ref for ref, text in part_text.items() if stem in _norm(text)]
        if len(hits) == 1:
            return hits[0], f"mpn {stem!r}"
        if len(hits) > 1:
            return None  # ambiguous: refuse to name one
    return None


def _check_netlist(rows: list[dict], netlist_paths: list[str],
                   mpn_name: str | None = None,
                   covers_boards: list[str] | None = None) -> tuple[list[RowFinding], dict]:
    """Every BOM row that should exist as a schematic symbol must appear in one of
    the supplied netlists.

    Deliberately ONE-directional, against the original proposal. A netlist covers
    one schematic sheet-set; a product BOM covers a whole product across boards and
    modules, and legitimately rolls passives up into aggregate rows ("C*/R*").
    Measured on the real aiguard inputs, a symmetric set-difference reports 33
    findings of which 2 are real — a gate that cries wolf 31 times gets ignored,
    which is worse than no gate. The reverse direction (netlist ref with no BOM
    row) is reported as a WARNING with its count, never as a blocker, so the
    information is available without drowning the real signal.

    Exemptions are explicit, never silent:
      - qty == 0            -> a functional alternate, not placed
      - aggregate ref       -> stands for a class ("C*/R*"), not one part
      - non-electrical      -> LENS / ANT: no schematic symbol by nature
    """
    covered: set[str] = set()
    scopes: list[str] = []
    part_text: dict[str, str] = {}
    for np_ in netlist_paths:
        covered |= _netlist_refs(np_)
        scopes.append(_netlist_scope(np_))
        if mpn_name:
            part_text.update(_netlist_part_text(np_))

    def _assessable(r: dict) -> bool:
        ref = r.get("_ref", "")
        if not ref or _is_aggregate_ref(ref):
            return False
        if ref.upper().startswith(_NONELECTRICAL_PREFIXES):
            return False
        return _norm(r.get("qty", "")) not in ("0", "0.0")

    # Per-board coverage is computed FIRST, because whether a missing row is
    # actionable depends on whether its board was captured at all.
    #
    # Alias hits are resolved in this SAME pass and cached for the row loop below.
    # Computing them twice would be the duplicate-fact shape (V4-c): two copies of
    # "is this part drawn?" that drift apart under edits — which is precisely how
    # board-level and row-level evidence came to disagree in the first place.
    per_board: dict[str, dict] = {}
    alias_by_ref: dict[str, tuple] = {}
    for r in rows:
        if not _assessable(r):
            continue
        ref = r.get("_ref", "")
        board = r.get("_board", "") or "<unset>"
        b = per_board.setdefault(board, {"rows": 0, "drawn": 0,
                                         "drawn_as_other_refdes": 0, "missing": []})
        b["rows"] += 1
        if ref in covered:
            b["drawn"] += 1
            continue
        # Drawn under a DIFFERENT refdes still means this board was captured. The
        # real CORE board is exactly this case: all four of its parts are drawn as
        # JSA/JSB/UW1/UB1, so a refdes-literal count reports drawn=0 and the board
        # looks untouched while being fully captured in fact.
        alias = _find_by_mpn(r, mpn_name, part_text) if mpn_name else None
        if alias:
            alias_by_ref[ref] = alias
            b["drawn_as_other_refdes"] += 1
        else:
            b["missing"].append(ref)
    uncaptured = sorted(b for b, v in per_board.items()
                        if v["rows"] and not v["drawn"] and not v["drawn_as_other_refdes"])

    # Which boards do the supplied netlists actually cover? This decides whether a
    # missing row is an actionable gap or has no baseline to be judged against, so
    # HOW it was decided is reported alongside the verdict (the `basis` discipline
    # from BR_20260729 §C).
    #
    # `drawn > 0` is only an INFERENCE, and a genuinely ambiguous one: a board with
    # zero drawn refs is indistinguishable from a board whose every row is undrawn.
    # A 6-board product BOM checked against 2 netlists has 5 boards with no possible
    # baseline (fix = capture those boards, not this BOM), while a single-row BOM
    # whose one row is missing looks structurally identical and IS a real gap. That
    # ambiguity lives in the inputs, so no cleverness here resolves it — only the
    # caller knows. `covers_boards` lets them say, and the report always states
    # which mechanism was used so an inferred exemption can never be mistaken for a
    # declared one.
    # A board counts as OBSERVED when its parts appear in the netlists at all —
    # under their own refdes OR under a diverged one. Counting only refdes-literal
    # hits would call the real CORE board "never captured" while all four of its
    # parts sit in the netlist as JSA/JSB/UW1/UB1.
    observed = {b for b, v in per_board.items()
                if v["drawn"] or v["drawn_as_other_refdes"]}
    coverage_conflicts: list[dict] = []
    if covers_boards is not None:
        declared = {b.strip() for b in covers_boards if b.strip()}
        unknown = sorted(declared - set(per_board))
        # BR_20260730b §Q: a DECLARED scope may never exempt a board the netlists
        # were OBSERVED to draw. Trusting the declaration alone hands the caller a
        # mute button: on the real inputs, narrowing covers_boards to ['PRODUCT']
        # moved every undrawn CORE row into rows_unassessable and flipped the gate
        # to PASS — while CORE was sitting right there in the netlist at drawn=2.
        # That inverts the ordering rule this function already follows one level
        # down (mpn match before board exemption, see (1) below): POSITIVE evidence
        # outranks ABSENCE of evidence, and `drawn > 0` is positive evidence.
        #
        # Declaration and observation disagreeing is itself a fact worth a human,
        # not something to silently resolve either way — so the board is withheld
        # from the exemption set AND the contradiction is reported.
        for b in sorted(observed - declared):
            v = per_board[b]
            seen = v["drawn"] + v["drawn_as_other_refdes"]
            coverage_conflicts.append({
                "board": b,
                "declared_covered": False,
                "observed_drawn": v["drawn"],
                "observed_drawn_as_other_refdes": v["drawn_as_other_refdes"],
                "rows": v["rows"],
                "detail": f"covers_boards omits {b!r}, but the supplied netlist(s) "
                          f"draw {seen} of its {v['rows']} rows "
                          f"({v['drawn']} by refdes, {v['drawn_as_other_refdes']} under "
                          f"a diverged refdes) — its undrawn rows are NOT exempt. Either "
                          f"the declaration is stale or these refs belong to another "
                          f"board; reconcile before trusting this gate.",
            })
        captured = declared | observed
        coverage_basis = "declared" if not coverage_conflicts else "declared_with_observed_conflict"
    else:
        unknown = []
        captured = observed
        coverage_basis = "inferred_from_drawn_refs"

    # An exemption is only granted when SOME board was actually matched. If the
    # netlists resolve nothing in this BOM, the comparison itself is broken — wrong
    # file, wrong project, or nothing captured yet — and every row must stay a
    # finding. Without this, passing an unrelated netlist would exempt the entire
    # BOM and turn the gate green: a demotion rule that can silence itself is a
    # false-green generator, the exact shape this gate exists to prevent.
    #
    # It is also what separates the two structurally identical cases: a 1-row BOM
    # whose only row is undrawn (nothing covered → real gap) from a 6-board BOM
    # where 2 boards are covered and 5 have no baseline (→ unassessable).
    grant_exemptions = bool(captured)

    findings: list[RowFinding] = []
    exempt: dict[str, list[str]] = {"qty_zero": [], "aggregate": [], "non_electrical": []}
    unassessable: dict[str, list[str]] = {}
    divergent: list[dict] = []
    checked = 0
    for r in rows:
        ref = r.get("_ref", "")
        board = r.get("_board", "")
        if not ref:
            continue
        if _is_aggregate_ref(ref):
            exempt["aggregate"].append(ref)
            continue
        if ref.upper().startswith(_NONELECTRICAL_PREFIXES):
            exempt["non_electrical"].append(ref)
            continue
        if _norm(r.get("qty", "")) in ("0", "0.0"):
            exempt["qty_zero"].append(ref)
            continue
        checked += 1
        if ref in covered:
            continue

        # (1) Is this part drawn under a DIFFERENT refdes? Checked FIRST, because an
        # mpn match is POSITIVE evidence that the part exists in the schematic, while
        # board-coverage is only the ABSENCE of evidence. Ordering the exemption
        # first would swallow every divergence on a board whose refdes all diverge
        # (exactly the CORE case: J_X1/J_X2/U4A/U4B are drawn as JSA/JSB/UW1/UB1, so
        # CORE looks "uncaptured" by refdes while being fully captured in fact).
        alias = alias_by_ref.get(ref)
        if not alias and grant_exemptions and (board or "<unset>") not in captured:
            # (2) Nothing matched, and no netlist covers this board -> no baseline.
            unassessable.setdefault(board or "<unset>", []).append(ref)
            continue

        if alias:
            divergent.append({"board": board, "bom_ref": ref,
                              "netlist_ref": alias[0], "matched_on": alias[1]})
            findings.append(RowFinding(
                board, ref, "R5_REFDES_DIVERGENCE",
                f"drawn in the schematic as {alias[0]!r} (matched on {alias[1]}), "
                f"not as {ref!r} — the part EXISTS; the BOM and the schematic "
                f"disagree on its refdes. Fix by reconciling the two names, NOT by "
                f"drawing it again. {alias[0]!r} appears in no BOM row."))
            continue

        # (3) Board captured, no part-identity match anywhere: genuinely undrawn.
        findings.append(RowFinding(board, ref, "R5_NETLIST",
                                   "BOM row has no matching component in the "
                                   f"supplied netlist(s) [{', '.join(scopes)}] — "
                                   "its board IS captured, so this part is "
                                   "declared in the BOM but never drawn"))

    report = {
        "status": "run",
        "netlists": [os.path.basename(x) for x in netlist_paths],
        "netlist_scopes": scopes,
        "netlist_refs": len(covered),
        "bom_rows_checked": checked,
        "exempted": {k: sorted(v) for k, v in exempt.items() if v},
        "netlist_refs_without_bom_row": sorted(covered - {r.get("_ref", "") for r in rows}),
        "per_board": {b: {"rows": v["rows"], "drawn": v["drawn"],
                          "drawn_as_other_refdes": v["drawn_as_other_refdes"],
                          "missing": sorted(v["missing"])}
                      for b, v in sorted(per_board.items())},
        # Boards with zero drawn refs: their schematic was never captured at all.
        # Distinct from a per-part omission and fixed differently.
        "boards_not_captured": uncaptured,
        # BR_20260730 round=8: rows on a board NO supplied netlist covers. There is
        # no baseline to compare them against, so they are NOT findings — same rule
        # as consumer_fork_drift's forks_unassessable: a gap in the REFERENCE is not
        # a defect in the thing being checked. Reported (never dropped) so "not
        # assessed" can never be read as "assessed, clean".
        "rows_unassessable_board_not_captured":
            {b: sorted(v) for b, v in sorted(unassessable.items())},
        # HOW the covered-board set was decided. "inferred_from_drawn_refs" cannot
        # tell "no netlist covers this board" from "every row on it is undrawn";
        # pass covers_boards= to make it authoritative.
        "board_coverage_basis": coverage_basis,
        "boards_covered": sorted(captured),
        # False when the netlists matched NO board here: no row is exempt, because a
        # comparison that resolves nothing is broken rather than out of scope.
        "exemptions_granted": grant_exemptions,
        # Declared board names matching no BOM row: a typo in covers_boards would
        # otherwise silently exempt nothing while looking accepted.
        "boards_declared_not_in_bom": unknown,
        # BR_20260730b §Q: boards the caller declared as NOT covered which the
        # netlists nevertheless draw. Their rows stay assessable (observation beats
        # declaration); the contradiction is surfaced for a human to reconcile
        # rather than silently resolved in either direction.
        "board_coverage_conflicts": coverage_conflicts,
        # Parts that ARE drawn, under a refdes the BOM does not use.
        "refdes_divergences": divergent,
    }
    return findings, report


def _netlist_pin_nets(paths: list[str]) -> dict[str, dict[str, str]]:
    """{ref: {pin: net_name}} across all supplied netlists."""
    out: dict[str, dict[str, str]] = {}
    net_re = re.compile(r'\(\s*net\s+\(\s*code\s+"[^"]*"\s*\)\s*\(\s*name\s+"([^"]+)"')
    node_re = re.compile(r'\(\s*node\s+\(\s*ref\s+"([^"]+)"\s*\)\s*\(\s*pin\s+"([^"]+)"')
    for path in paths:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        # Walk sequentially: every node belongs to the most recent net header.
        pos, current = 0, None
        for m in re.finditer(r'\(\s*net\s+\(\s*code|\(\s*node\s+\(\s*ref', text):
            chunk = text[m.start():m.start() + 400]
            nm = net_re.match(chunk)
            if nm:
                current = nm.group(1)
                continue
            nd = node_re.match(chunk)
            if nd and current:
                out.setdefault(nd.group(1), {})[nd.group(2)] = current
    return out


def _pin_spec_tokens(value: str) -> list[str] | None:
    """Positional pin tokens from a BOM value's trailing "(a/b/c)" spec."""
    m = re.search(r"\(([^()]*/[^()]*)\)\s*$", value.strip())
    if not m:
        return None
    toks = [t.strip() for t in m.group(1).split("/")]
    return toks if all(toks) else None


def _polarity_of(name: str) -> str | None:
    """'gnd' | 'power' | None for a token or net name."""
    n = _norm(name)
    if not n:
        return None
    head = re.split(r"[\s,;]", n)[0]
    if any(head == g or head.startswith(g + "_") or head.endswith("_" + g)
           for g in _GND_TOKENS) or head in _GND_TOKENS:
        return "gnd"
    if _PWR_PATTERN.search(head) or head.startswith(_PWR_PREFIXES):
        return "power"
    return None


def _check_pin_polarity(rows: list[dict], netlist_paths: list[str],
                        value_col: str | None) -> tuple[list[RowFinding], dict]:
    """R6 — a BOM pin spec must not contradict the netlist on ground vs supply.

    Positional alignment (token N == pin N) is the same assumption a capture agent
    makes when reading the spec, so it is the assumption worth checking. When the
    token count does not match the ref's pin count in the netlist the alignment is
    unknown: report `unaligned` and check nothing, rather than guess an offset and
    emit findings from a wrong premise.
    """
    if value_col is None:
        return [], {"status": "not_run", "reason": "no value/description column in BOM header"}
    pin_nets = _netlist_pin_nets(netlist_paths)
    findings: list[RowFinding] = []
    checked: list[str] = []
    unaligned: list[dict] = []
    no_spec = 0
    for r in rows:
        ref = r.get("_ref", "")
        board = r.get("_board", "")
        if not ref or ref not in pin_nets:
            continue                      # absence is R5's finding, not R6's
        toks = _pin_spec_tokens(r.get(value_col, "") or "")
        if toks is None:
            no_spec += 1
            continue
        nets = pin_nets[ref]
        if len(toks) != len(nets):
            unaligned.append({"ref": ref, "spec_tokens": len(toks), "netlist_pins": len(nets)})
            continue
        checked.append(ref)
        for i, tok in enumerate(toks, start=1):
            net = nets.get(str(i))
            if net is None:
                continue
            want, got = _polarity_of(tok), _polarity_of(net)
            if want and got and want != got:
                findings.append(RowFinding(
                    board, ref, "R6_PIN_POLARITY",
                    f"pin {i}: BOM spec says {tok!r} ({want}) but netlist wires it to "
                    f"{net!r} ({got}) — electrically legal, so ERC/DRC cannot catch "
                    "this; one of the two is wrong"))
    report = {
        "status": "run",
        "refs_checked": sorted(checked),
        "rows_without_pin_spec": no_spec,
        # Reported, never silently dropped: an unaligned row was NOT checked.
        "unaligned": unaligned,
    }
    return findings, report


def _load_pin_alloc_refs(path: str) -> tuple[set[str] | None, list[str]]:
    """Refs in the Pin_Allocation SSOT, plus its header.

    Returns (None, header) when the file carries NO ref-bearing column. That is a
    distinct outcome from "a ref column exists and is empty", and the caller MUST
    keep them apart: returning an empty set for both made every active BOM part
    look absent from the SSOT (26/26 on the real aiguard inputs, each reported as
    "BOM<->SSOT conflict — owner must reconcile"). "I could not find the column"
    is not "these parts are missing" (BR_20260730; same shape as R3's missing
    symbol column and the mcpctl busy-probe UNKNOWN rule).

    Note the artifact contract: the c03-ee GUIDE deliverable table (:43, :340, :374
    — the last marked `exported`, "ball->GPIO->function") defines Pin_Allocation.csv
    as a ball/peripheral-oriented pinmap, which has no ref column by design. Only
    the §3c prose (:230, :243) assumes a ref list. All four Pin_Allocation.csv files
    in the fleet follow the deliverable table. So a missing ref column is the NORMAL
    case for a conforming file, not a schema violation — hence not_run rather than
    a blocking finding.
    """
    header, raw = _read_csv_rows(path)
    ci = _col_index(header, "ref", "refdes", "component", "reference")
    if ci is None:
        return None, header
    refs: set[str] = set()
    for row in raw:
        if ci < len(row) and row[ci].strip():
            refs.add(row[ci].strip())
    return refs, header


def _check_ssot(active_rows: list[dict], pin_alloc_refs: set[str]) -> list[RowFinding]:
    """Every active BOM part (drive interface: U/J/Y/SW) must appear in the
    Pin_Allocation SSOT. A BOM-only active ref means the BOM proposes a part the
    pin allocation never accounted for (the U4 wireless-scheme conflict class)."""
    findings: list[RowFinding] = []
    for r in active_rows:
        ref = r.get("_ref", "")
        if ref and ref not in pin_alloc_refs:
            findings.append(RowFinding(r.get("_board", ""), ref, "R4_SSOT",
                                       "active part not in Pin_Allocation.csv SSOT "
                                       "(BOM↔SSOT conflict — owner must reconcile)"))
    return findings


# ── top level ───────────────────────────────────────────────────────────────

def check_c03(bom_csv: str, *, pin_allocation_csv: str | None = None,
              netlist_path: str | list[str] | None = None,
              covers_boards: list[str] | None = None,
              frozen_pad_counts: dict | None = None,
              out_dir: str | None = None) -> CheckC03Result:
    """C03→C04 stage-entry gate. Deterministic; missing inputs raise, blocking
    findings return normally as gate=FAIL. Never relaxes a threshold to pass.

    frozen_pad_counts: optional {ref: expected_pad_count}; when a BOM row for that
    ref carries a pad-count column, a mismatch is a R4_SSOT blocker (J_* freeze).

    netlist_path: one path, or a list of paths, to KiCad `.net` exports covering
    the schematic(s) this BOM is drawn in. Enables R5 (BOM<->netlist). When it is
    NOT supplied the result carries netlist_crosscheck={"status": "not_run", ...}
    and gate=PASS must NOT be read as "every BOM row is drawn" — the gate simply
    never looked (BR_20260730; a verdict must carry the scope that produced it).

    covers_boards: which `board` values the supplied netlists actually cover, e.g.
    ["PRODUCT", "CORE"]. A product BOM spans every board while one netlist covers
    one schematic, so rows on a board with no netlist have NO baseline to be judged
    against and are reported under netlist_crosscheck.
    rows_unassessable_board_not_captured instead of as findings. Omit it and
    coverage is INFERRED from which refs resolved — an inference that cannot tell
    "no netlist covers this board" from "every row on it is undrawn", so the report
    always states which mechanism was used (board_coverage_basis). Declaring it
    makes the scope authoritative (BR_20260730 round=8).
    """
    if not os.path.isfile(bom_csv):
        raise ValueError(f"BOM_MISSING: {bom_csv} not found — run C03 BOM export first.")
    header, raw_rows = _read_csv_rows(bom_csv)
    if not raw_rows:
        raise ValueError(f"BOM_EMPTY: {bom_csv} has a header but zero data rows.")

    board_i = _col_index(header, "board", "board_id")
    ref_i = _col_index(header, "ref", "refdes", "reference")
    status_i = _col_index(header, "status", "state")
    mpn_i = _col_index(header, "mpn", "manufacturer_part_number", "part_number")
    symbol_i = _col_index(header, *_SYMBOL_COLUMNS)
    pad_i = _col_index(header, "pad_count", "pads", "pad_qty")
    stock_i = _col_index(header, "stock", "in_stock")
    value_i = _col_index(header, "value", "description", "desc", "part_value")

    findings: list[RowFinding] = []
    # R1 schema (uses raw rows for column-count breakage)
    findings += _check_schema(header, raw_rows, status_i, board_i, ref_i)

    # Build dict rows only from well-formed rows for R2–R4.
    ncol = len(header)
    dict_rows: list[dict] = []
    for row in raw_rows:
        if len(row) != ncol:
            continue
        d = {header[i]: row[i] for i in range(ncol)}
        d["_board"] = row[board_i].strip() if board_i is not None else ""
        d["_ref"] = row[ref_i].strip() if ref_i is not None else ""
        dict_rows.append(d)

    status_name = header[status_i] if status_i is not None else "status"
    mpn_name = header[mpn_i] if mpn_i is not None else "mpn"
    symbol_name = header[symbol_i] if symbol_i is not None else None
    value_name = header[value_i] if value_i is not None else None

    findings += _check_readiness(dict_rows, status_name, mpn_name)
    findings += _check_drawability(dict_rows, symbol_name)

    active_rows = [r for r in dict_rows
                   if r.get("_ref", "").upper().startswith(_ACTIVE_PREFIXES)]

    ssot_checked = False
    ssot_report: dict = {
        "status": "not_run",
        "reason": "pin_allocation_csv not supplied — active BOM parts were NOT "
                  "checked against the pin allocation",
    }
    if pin_allocation_csv:
        if not os.path.isfile(pin_allocation_csv):
            raise ValueError(f"PIN_ALLOC_MISSING: {pin_allocation_csv} not found.")
        pin_refs, pin_header = _load_pin_alloc_refs(pin_allocation_csv)
        if pin_refs is None:
            # Ref-level crosscheck is not applicable to this (contract-conforming)
            # pinmap schema. Say so; do NOT convert inapplicability into 26 findings.
            ssot_report = {
                "status": "not_run",
                "reason": "Pin_Allocation.csv has no ref-bearing column "
                          f"(header: {pin_header}) — it is a ball/peripheral pinmap "
                          "per the c03-ee deliverable table, so ref-level BOM<->SSOT "
                          "crosscheck does not apply; NO active part was verified "
                          "against the pin allocation",
                "pin_alloc_header": pin_header,
                "active_parts_unverified": sorted(r.get("_ref", "") for r in active_rows),
            }
        else:
            findings += _check_ssot(active_rows, pin_refs)
            ssot_report = {
                "status": "run",
                "pin_alloc_refs": len(pin_refs),
                "active_parts_checked": len(active_rows),
            }
            ssot_checked = True

    # R5 BOM<->netlist (BR_20260730 F2). Absence of netlist_path is reported as
    # not_run, never silently folded into a PASS.
    if netlist_path is None:
        netlist_report: dict = {
            "status": "not_run",
            "reason": "netlist_path not supplied — BOM rows were NOT checked against "
                      "any schematic; a PASS here does not mean every part is drawn",
        }
        polarity_report: dict = {
            "status": "not_run",
            "reason": "netlist_path not supplied — BOM pin specs were NOT checked "
                      "against the wiring; a PASS here does not mean they agree",
        }
    else:
        paths = [netlist_path] if isinstance(netlist_path, str) else list(netlist_path)
        missing = [x for x in paths if not os.path.isfile(x)]
        if missing:
            raise ValueError(f"NETLIST_MISSING: {', '.join(missing)} not found.")
        nl_findings, netlist_report = _check_netlist(dict_rows, paths, mpn_name,
                                                     covers_boards)
        findings += nl_findings
        pol_findings, polarity_report = _check_pin_polarity(dict_rows, paths, value_name)
        findings += pol_findings

    # frozen pad-count crosscheck (J_* freeze)
    if frozen_pad_counts and pad_i is not None:
        for r in dict_rows:
            ref = r.get("_ref", "")
            if ref in frozen_pad_counts:
                raw_pad = r.get(header[pad_i], "").strip()
                try:
                    actual = int(float(raw_pad)) if raw_pad else None
                except ValueError:
                    actual = None
                expect = frozen_pad_counts[ref]
                if actual is None or actual != expect:
                    findings.append(RowFinding(r.get("_board", ""), ref, "R4_SSOT",
                                               f"pad_count {raw_pad!r} != frozen {expect}"))

    # Warnings (non-blocking): stock=0.
    warnings: list[str] = []
    if stock_i is not None:
        for r in dict_rows:
            sv = _norm(r.get(header[stock_i], ""))
            if sv in ("0", "0.0", "out", "oos"):
                warnings.append(f"{r.get('_ref','?')}: stock=0 (procurement warn)")

    # Reverse direction (netlist ref with no BOM row) is information, not a verdict:
    # a netlist covering more than this BOM's scope is normal. Surfaced as a counted
    # warning so it is visible without swamping the real R5 signal.
    orphan = netlist_report.get("netlist_refs_without_bom_row") or []
    if orphan:
        warnings.append(
            f"{len(orphan)} netlist component(s) have no BOM row "
            f"(informational; netlist scope may exceed this BOM): "
            + ", ".join(orphan[:12]) + (" …" if len(orphan) > 12 else "")
        )

    result = CheckC03Result(
        schema=REPORT_SCHEMA,
        gate="FAIL" if findings else "PASS",
        blocking=findings,
        warnings=warnings,
        bom_rows=len(dict_rows),
        active_parts=len(active_rows),
        ssot_checked=ssot_checked,
        netlist_crosscheck=netlist_report,
        pin_polarity=polarity_report,
        ssot_crosscheck=ssot_report,
    )

    if out_dir is not None:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, REPORT_FILENAME), "w", encoding="utf-8") as fp:
            json.dump(asdict(result), fp, sort_keys=True, indent=2, ensure_ascii=False)
            fp.write("\n")
    return result
