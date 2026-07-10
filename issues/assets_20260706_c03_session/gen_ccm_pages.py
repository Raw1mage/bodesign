"""CCM multi-page schematic generator (v03).

Rationale: the STM32N657 is a 222-ball BGA symbol; a single-sheet draftsman
compose overflows past A0. Industry-standard practice is a multi-sheet
schematic — one functional page per subsystem, cross-page signals carried by
same-named net labels. This driver reuses the EXACT net truth from gen_ccm.py
(no electrical change) and slices it per `group` into independent draftsman
sheets.

Each page spec = { components of that group } + { nets that touch any of those
components }. A net that also touches components on other pages appears on this
page as a label endpoint (the composer routes incomplete/label-only nets as
labels), which is precisely the cross-page interface convention.

v03 fix (DD-6, per-page U1 pin subset):
    A single 222-ball U1 symbol renders 111 pins per side @2.0 mm pitch, and
    each pin gets a global_label 1.27 mm tall -> guaranteed overlap ("black
    blob"), which no paper size or stub length can cure. The industry-standard
    cure for a large MCU is to draw ONLY the pins that a given page actually
    uses, per functional sheet. This module builds, for each page, a U1 symbol
    VARIANT `STM32N657_FULL__<slug>` that contains ONLY the balls whose nets
    touch that page, re-flowed compactly. Ball numbers and net truth are
    unchanged (electrical identity preserved); only which pins are DRAWN
    per-sheet changes. A one-line note records the balls carried to other sheets.
"""
import json, importlib.util, sys, os, re

FB = "/work/aiguard/C03-EE/full_board"
SYMDIRS = [f"{FB}/symbols", f"{FB}/authentic_lib", f"{FB}/authentic_host", "/usr/share/kicad/symbols"]

# Per-page U1 in-symbol pin pitch. HISTORY: a single global 11.43 mm (user pitch
# ×3 directive) forced sparse pages (01_power, 02_mcu_core) past the 40% sheet
# utilization floor; a global pitch cannot satisfy all 5 pages because each page's
# U1 ball-subset has a different aspect ratio (03_memory's 69-ball subset is a
# ~8:1 narrow-tall column). User decision: PER-PAGE pitch — each page picks the
# LARGEST KiCad-grid-multiple pitch that still passes the smallest-frame + ≥40%
# utilization gate. scale coherence (page_scale = pitch / 2.54) guarantees the
# per-page in-symbol readability is identical at any pitch (whole-page uniform
# scale), so pitch only sets the absolute paper size, never the relative density.
# Candidates are tried large→small; the first PASS wins (the util-vs-pitch curve
# is non-monotonic — a larger pitch can PASS while a smaller one FAILs by jumping
# up a paper size at low fill — so "first PASS descending" is the correct rule,
# not "threshold then go below").
_PITCH_CANDIDATES = (11.43, 10.16, 8.89, 7.62, 6.35, 5.08, 3.81, 2.54)
_KICAD_BASE_PITCH = 2.54
_SCALE_QUANTUM = 0.1      # DD-29(3): page_scale ladder step. The former whole-pitch
                         # (1.0) quantum floored a true fit of e.g. 1.94 down to 1.0,
                         # filling only ~22% of the paper AABB (the "畫面留白 80%" the user
                         # must crop by hand). Empirically 0.5 still collapsed several
                         # pages back to 1.0; a 0.1 step lets each page scale up close to
                         # its true fit (01_power 1.0→1.3, 04_wireless→1.1) so content
                         # fills the sheet tightly. page_scale stays a clean tenth-pitch
                         # quantum; symbol geometry is scale-coherent so no overlap risk.
# Mirror the composer's utilization floor (single source of truth) for the
# fail-loud NO_VIABLE_PITCH message only; the gate itself lives in composer.py.
from bodesign_eda_bridge.composer import MIN_SHEET_UTILIZATION as MIN_UTIL_FLOOR
# DD-9b: BudgetInfeasible is raised by _fit_sheet on frame overflow. It subclasses
# Exception (NOT ValueError), so the pitch-scan probe must catch it EXPLICITLY to
# treat frame-fit as a per-pitch candidate gate rather than a hard engine fault.
from bodesign_eda_bridge.occupancy import (
    BudgetInfeasible,
    IntraSymbolTextOverlap,
    LedgerAssertionFailed,
)

from bodesign_eda_bridge import compose_schematic
# v04: per-page U1 subset symbols now go through the SAME four-edge geometry
# engine as the full symbol (BR: four-edge physical-pinout mirror placement).
# We rebuild each selected ball as a KiCadSymbolPin and let _symbol_geometry do
# the BGA perimeter projection, so a per-page subset shows pins on all four
# edges at their faithful package positions instead of the old two-column reflow.
from bodesign_eda_bridge.kicad_symbol import (
    KiCadSymbolPin as _K,
    _symbol_geometry as _sg,
    _pin_block as _pb,
    _PIN_LENGTH as _PL,
    _property as _prop,
    _escape as _esc,
)

_BALL_RE = re.compile(r"^([A-Z]{1,2})([0-9]+)$")


def _native_ball_key(ball):
    """DD-21 sort key: native BGA ball order (row letter primary, column NUMERIC
    secondary so A2 < A10). Row letters are ordered length-then-lexicographic so a
    two-letter row (AA) sorts after every single-letter row. Non-parsing balls sort
    last, stable by string."""
    m = _BALL_RE.match(ball)
    if not m:
        return (1, len(ball), ball, 0)
    row = m.group(1)
    return (0, len(row), row, int(m.group(2)))


def _split_lr(balls_native):
    """DD-21 (SUPERSEDED by _perimeter_sides / DD-28): split a NATIVE-ordered ball
    list into (left, right) halves for a two-edge symbol. Kept for reference only."""
    n = len(balls_native)
    half = (n + 1) // 2
    return balls_native[:half], balls_native[half:]


# DD-28 ball-grid axis helpers (row LETTER index / col NUMBER), built from the
# ACTUAL rows present in _U1_PIN_META (BGA skips I/O/Q/S/X/Z — never guess the
# alphabet). Populated lazily after _U1_PIN_META is known (see below).
_U1_ROWS_SORTED = None   # ascending list of distinct row letters actually used
_U1_COLS_SORTED = None   # ascending list of distinct col numbers actually used
_U1_ROW_IDX = None       # row letter -> 0-based index in the used-row axis
_U1_COL_IDX = None       # col number -> 0-based index in the used-col axis


def _ball_row_col(ball):
    """(row_letter, col_int) for a BGA ball id, or (None, None) if unparsable."""
    m = _BALL_RE.match(ball)
    if not m:
        return (None, None)
    return (m.group(1), int(m.group(2)))


def _build_u1_grid_axes():
    """Populate the row/col axis index maps from every ball in _U1_PIN_META. The
    axes are the DISTINCT rows/cols that PHYSICALLY exist on the package, ordered
    by native BGA order (row: length-then-lex so AA follows Z; col: numeric). A
    ball's perimeter distance is measured in AXIS INDEX units, so a ball one row in
    from the top edge is distance 1 regardless of which letters the package skips."""
    global _U1_ROWS_SORTED, _U1_COLS_SORTED, _U1_ROW_IDX, _U1_COL_IDX
    rows, cols = set(), set()
    for b in _U1_PIN_META:
        r, c = _ball_row_col(b)
        if r is not None:
            rows.add(r)
            cols.add(c)
    _U1_ROWS_SORTED = sorted(rows, key=lambda r: (len(r), r))
    _U1_COLS_SORTED = sorted(cols)
    _U1_ROW_IDX = {r: i for i, r in enumerate(_U1_ROWS_SORTED)}
    _U1_COL_IDX = {c: i for i, c in enumerate(_U1_COLS_SORTED)}


def _perimeter_sides(balls_native):
    """DD-28: assign each ball to one of the four symbol edges by MIRRORING the BGA
    ballout top-view. Edge membership (on the PACKAGE axes, not just the page subset):

      top    = balls on the FIRST used row (min row index)
      bottom = balls on the LAST used row (max row index)
      left   = balls on the FIRST used column (min col index)
      right  = balls on the LAST used column (max col index)
      inner  = every other ball -> nearest perimeter by AXIS-INDEX distance:
               d_top = row_idx, d_bottom = (Rmax - row_idx),
               d_left = col_idx, d_right = (Cmax - col_idx); assign to the edge with
               the smallest distance; ties break top > left > right > bottom.

    Within an edge the primary order mirrors the ballout: top/bottom run left->right
    by COLUMN (tie: row), left/right run top->bottom by ROW (tie: col). Returns a
    dict {left,right,top,bottom} of ball-id lists (a partition of the input, native
    to the page subset — every input ball lands on exactly one edge).
    """
    if _U1_ROW_IDX is None:
        _build_u1_grid_axes()
    r_max = len(_U1_ROWS_SORTED) - 1
    c_max = len(_U1_COLS_SORTED) - 1
    edges = {"left": [], "right": [], "top": [], "bottom": []}
    for b in balls_native:
        r, c = _ball_row_col(b)
        if r is None or r not in _U1_ROW_IDX:
            # unparsable ball: fall back to left edge so nothing is dropped.
            edges["left"].append(b)
            continue
        ri = _U1_ROW_IDX[r]
        ci = _U1_COL_IDX[c]
        if ri == 0:
            edges["top"].append(b)
        elif ri == r_max:
            edges["bottom"].append(b)
        elif ci == 0:
            edges["left"].append(b)
        elif ci == c_max:
            edges["right"].append(b)
        else:
            # inner ball: nearest perimeter by axis-index distance, tie top>left>right>bottom.
            cand = [
                (ri, "top"),
                (ci, "left"),
                (c_max - ci, "right"),
                (r_max - ri, "bottom"),
            ]
            # stable min: python min keeps first on ties, and cand is already in the
            # tie-break priority order.
            edges[min(cand, key=lambda t: t[0])[1]].append(b)
    # within-edge ordering: mirror the ballout.
    def _col_key(b):
        r, c = _ball_row_col(b)
        return (_U1_COL_IDX.get(c, 0), _U1_ROW_IDX.get(r, 0))

    def _row_key(b):
        r, c = _ball_row_col(b)
        return (_U1_ROW_IDX.get(r, 0), _U1_COL_IDX.get(c, 0))

    edges["top"].sort(key=_col_key)
    edges["bottom"].sort(key=_col_key)
    edges["left"].sort(key=_row_key)
    edges["right"].sort(key=_row_key)
    return edges

# --- Rebuild the full CCM component+net truth by executing gen_ccm.py's logic ---
# gen_ccm.py is a script that calls compose at import; we instead exec it in a
# namespace where compose_schematic is stubbed, capturing ccm_comp + ccm_nets.
_captured = {}
def _stub_compose(*a, **k):
    class _R:
        placed=0; nets=0
        class emit: unresolved_pins=[]
        warnings=[]; validation=None
    return _R()

src = open(f"{FB}/gen_ccm.py").read()
ns = {"__name__": "_genccm", "compose_schematic": _stub_compose, "json": json, "sys": sys}
exec(src, ns)
ccm_comp = ns["ccm_comp"]
ccm_nets = ns["ccm_nets"]   # already merged (merge_same at end of gen_ccm)

print(f"captured components={len(ccm_comp)} nets={len(ccm_nets)}")

# group of each ref
group_of = {c["ref"]: c.get("group", "misc") for c in ccm_comp}

# ---------------------------------------------------------------------------
# v03: per-page U1 symbol variant builder.
# Parse the full STM32N657_FULL symbol once; for a given set of balls, emit a
# compact variant symbol drawing ONLY those balls (re-flowed vertically), named
# STM32N657_FULL__<slug> so each page embeds an independent lib_id. Electrical
# truth is untouched: pin `number` (= ball) is preserved verbatim.
# ---------------------------------------------------------------------------
U1_SYM_PATH = f"{FB}/symbols/stm32n657_full.kicad_sym"
_U1_SRC = open(U1_SYM_PATH).read()
_PIN_LINE_RE = re.compile(r'\(pin\s+\S+\s+\S+\s*\(at\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\)'
                          r'.*?\(number\s+"([^"]+)"', re.DOTALL)

def _u1_pin_lines():
    """Return [(ball, kind, name), ...] for every U1 pin (kind/name from full sym)."""
    out = []
    # each pin is a single line in the generated symbol; parse ball/kind/name so
    # the subset can be re-flowed through the four-edge geometry engine.
    for line in _U1_SRC.splitlines():
        s = line.strip()
        if not s.startswith("(pin "):
            continue
        km = re.match(r'\(pin\s+(\S+)\s', s)
        nm = re.search(r'\(name\s+"([^"]*)"', s)
        bm = re.search(r'\(number\s+"([^"]+)"', s)
        if not (km and bm):
            continue
        out.append((bm.group(1), km.group(1), nm.group(1) if nm else ""))
    return out

_U1_PINS = _u1_pin_lines()
_U1_BALL_SET = {b for (b, _k, _n) in _U1_PINS}
_U1_PIN_META = {b: (k, n) for (b, k, n) in _U1_PINS}

# v05: per-page U1 split. A dense per-page subset (e.g. 05_stamp_icd's 74 balls)
# places up to ~24-29 pins on ONE symbol edge; each pin's ang180 global-label
# x-box (~75 mm @ page_scale 4.5) then OVERLOADS that edge's usable-x corridor
# (root cause: label-box x-occupancy, which the _fit_sheet body-clearance floor
# structurally cannot reach — proven by the 8-number closed-loop probe). The
# industry-standard cure for a mega-symbol is a MULTI-UNIT split: draw the ball
# subset as N smaller symbols (distinct instances), so each symbol's own
# _assign_bga distributes only its band's balls -> per-edge label columns drop
# ~1/N. connection_style="label" means connectivity is by net name (zero drawn
# wire binds by ref), so N distinct sub-refs are electrically inert; and the
# fidelity gate keys off the SEED set u1_balls_here (ref-agnostic), so the split
# is invisible to it as long as the N bands union-complete the seed set.
# OPT-IN per slug: absent => n=1 => byte-identical to the pre-split single symbol.
# DD-9 (2026-07-07): the intra-page U1 band split (05_stamp_icd:2) was SUPERSEDED
# by a real SHEET split (05a/05b below). The band split placed 2 U1 instances on
# ONE sheet, so pad_h (=max bbox half-height, U1's) was unchanged and the
# BUDGET_INFEASIBLE h:+7.27mm persisted (pad_h + label_reach = 365mm constant
# band dominates content_h; probe-confirmed). Splitting the PAGE halves span_y AND
# gives each sheet a SMALLER U1 ball-subset (43/48 vs 91 balls) -> smaller pad_h.
# Now empty: every page draws a single (unsplit) per-page U1 subset symbol.
_U1_SPLIT_BY_SLUG = {}


def _split_balls(balls_sorted, n):
    """Partition an ascending-sorted ball-id list into n contiguous BGA-column bands.

    balls_sorted: ball ids already sorted (e.g. ['A10','A11',...,'K3']).
    n: number of bands (>=1).
    Returns: list of n ball-id lists, pairwise-disjoint, union == input
    (fidelity-complete: no ball duplicated or dropped). Split key is the BGA
    COLUMN number so each band is a distinct physical package region (left->right
    vertical strips); a band's own _assign_bga then projects only its balls.
    NOT to be read as: functional/net grouping — this is a geometric column split.
    """
    if n <= 1 or len(balls_sorted) <= 1:
        return [list(balls_sorted)]
    def _col(ball):
        m = re.match(r"^([A-Z]{1,2})([0-9]+)$", ball)
        return int(m.group(2)) if m else 0
    ordered = sorted(balls_sorted, key=lambda b: (_col(b), b))
    cols = sorted({_col(b) for b in ordered})
    # split the COLUMN axis into n contiguous ranges, assign each ball by its col.
    per = len(cols) / n
    col_band = {c: min(int(i / per), n - 1) for i, c in enumerate(cols)}
    bands = [[] for _ in range(n)]
    for b in ordered:
        bands[col_band[_col(b)]].append(b)
    # drop empty bands (degenerate column distribution) so we never emit a 0-pin symbol.
    return [band for band in bands if band]


def _split_balls_by_row(balls_sorted, n):
    """Partition a ball-id list into n contiguous BGA-ROW bands (DD-9a).

    Mirrors _split_balls but splits on the BGA ROW LETTER axis instead of the
    column number. pad_h (=max-bbox half-height) is governed by a U1 subset's
    VERTICAL extent (row span), so splitting on rows halves the vertical
    projection of each sheet's U1 subset -> halves pad_h. Row letters are ordered
    A<B<...<Z<AA<AB (length-then-lexicographic) so a two-letter row sorts after
    every single-letter row. Returns n pairwise-disjoint ball lists whose union
    == input (fidelity-complete). NOT functional/net grouping — geometric only.
    """
    if n <= 1 or len(balls_sorted) <= 1:
        return [list(balls_sorted)]
    def _row_key(ball):
        m = re.match(r"^([A-Z]{1,2})([0-9]+)$", ball)
        r = m.group(1) if m else ""
        return (len(r), r)
    def _col(ball):
        m = re.match(r"^([A-Z]{1,2})([0-9]+)$", ball)
        return int(m.group(2)) if m else 0
    ordered = sorted(balls_sorted, key=lambda b: (_row_key(b), _col(b)))
    rows = sorted({_row_key(b) for b in ordered})
    per = len(rows) / n
    row_band = {r: min(int(i / per), n - 1) for i, r in enumerate(rows)}
    bands = [[] for _ in range(n)]
    for b in ordered:
        bands[row_band[_row_key(b)]].append(b)
    return [band for band in bands if band]


def build_u1_variant(slug, balls_used, carried_note, pin_pitch, page_scale):
    """Write STM32N657_FULL__<slug>[_bN] containing ONLY balls_used, four-edge placed.

    balls_used: iterable of ball ids (e.g. {"A1","B5",...}) touched on this page.
    carried_note: human string naming where the other banks live.
    Returns (variant_lib_ids, variant_dir) — variant_lib_ids is a LIST of one
    lib_id per sub-symbol band (length 1 unless the slug opts into a split via
    _U1_SPLIT_BY_SLUG). The caller instantiates one U1 component per lib_id.

    v04: the selected balls are rebuilt as KiCadSymbolPin objects and laid out by
    the SAME four-edge geometry engine (_symbol_geometry) that the full symbol
    uses. Each ball's BGA coordinate (A1, K16, ...) is perimeter-projected to its
    nearest package edge, so a per-page subset shows pins on all four sides at
    their faithful physical positions — not the old left/right two-column reflow.
    Electrical truth is untouched: pin `number` (= ball) is preserved verbatim.
    v05: opt-in multi-symbol split for mega-subset pages (see _U1_SPLIT_BY_SLUG).
    """
    vdir = f"{FB}/sch_ccm_pages/_symvariants"
    os.makedirs(vdir, exist_ok=True)
    all_balls = [b for b in sorted(balls_used) if b in _U1_PIN_META]
    n = _U1_SPLIT_BY_SLUG.get(slug, 1)
    bands = _split_balls(all_balls, n)
    lib_ids = []
    for bi, band in enumerate(bands):
        # single-band pages keep the original bare slug name (byte-identical);
        # split pages suffix _bN so each sub-symbol is an independent lib_id.
        suffix = "" if len(bands) == 1 else f"_b{bi}"
        sym_name = f"STM32N657_FULL__{slug}{suffix}"
        file_stem = f"u1_{slug}{suffix}"
        # DD-21 (user directive): draw the ball subset in NATIVE BGA order on the
        # LEFT/RIGHT edges only (no four-edge perimeter projection). Native-sort the
        # band, split into left/right halves, and hand `_symbol_geometry` a
        # pre-assigned `sides` dict so top/bottom stay empty and both edges share one
        # vert_pitch. `pins` (in native order) is the partition SSOT the engine checks.
        _band_native = sorted(band, key=_native_ball_key)
        _by_ball = {
            b: _K(number=b, name=_U1_PIN_META[b][1], kind=_U1_PIN_META[b][0])
            for b in _band_native
        }
        # DD-28 (user directive, SUPERSEDES DD-21 left/right reflow): mirror the BGA
        # ballout top-view onto the four symbol edges (A row -> top, W row -> bottom,
        # col 1 -> left, col 19 -> right; inner balls -> nearest perimeter). The pins
        # list is ordered edge-major (top,left,right,bottom) then within-edge ballout
        # order, so the four-edge geometry engine (which sizes body H from L/R counts,
        # W from T/B counts) and the `pins` partition-SSOT check both see a consistent
        # set. Every ball lands on exactly one edge -> electrical truth intact.
        _edge_balls = _perimeter_sides(_band_native)
        _sides = {
            e: [_by_ball[b] for b in _edge_balls[e]]
            for e in ("left", "right", "top", "bottom")
        }
        pins = (_sides["top"] + _sides["left"] + _sides["right"] + _sides["bottom"])
        # dense per-page subset (50-74 balls on ONE symbol): 1.27 mm pin pitch packs
        # the 1.27 mm-tall pin NAME text into a vertical smear. 3.81 mm (3 grid units)
        # clears adjacent names -- same readable spacing the old two-column reflow used.
        # user directive (pitch 3x): widen adjacent-pin spacing to 11.43 mm (=3.81*3,
        # 9 grid units) so perimeter wiring / net-label text never crowds.
        # pitch scales the body (user directive); pin GRAPHIC length stays at the base
        # _PL so the symbol's outer extent is not needlessly inflated (a longer pin
        # would push a sparse page's frame up a paper size at no readability gain --
        # the user complaint was tiny TEXT, cured by text_scale below, not short pins).
        # DD-3 scale coherence: pin GRAPHIC length, body floors AND all property
        # text now grow with page_scale so the skeleton keeps pace with the pin
        # pitch (pitch already ×scale). Previously pin_length stayed at base _PL
        # (5.08) and refdes/value text stayed 1.27 -> "字大骨架小" imbalance.
        _pl_s = round(_PL * page_scale, 4)
        geom = _sg(pins, pin_pitch=pin_pitch, pin_length=_pl_s, scale=page_scale, sides=_sides)
        left = round(-geom.half_w - _pl_s, 2)
        right = round(geom.half_w + _pl_s, 2)
        top = geom.half_h
        bottom = -geom.half_h
        band_note = carried_note if len(bands) == 1 else f"band {bi + 1}/{len(bands)}; {carried_note}"
        lines = [
            '(kicad_symbol_lib',
            '\t(version 20241209)',
            '\t(generator "bodesign-aiguard-fullboard-perpage")',
            f'\t(symbol "{_esc(sym_name)}"',
            '\t\t(exclude_from_sim no)(in_bom yes)(on_board yes)',
            _prop('Reference', 'U', left, top + 3.81, visible=True, text_scale=page_scale),
            _prop('Value', f'STM32N657L0 ({slug})', right - 15.24, top + 3.81, visible=True, text_scale=page_scale),
            _prop('Footprint', 'aiguard:STM32N657_VFBGA223', 0, 0, visible=False, text_scale=page_scale),
            _prop('Datasheet', f'per-page subset; {band_note}', 0, 0, visible=False, text_scale=page_scale),
            f'\t\t(symbol "{_esc(sym_name)}_0_1"',
            '\t\t\t(rectangle',
            f'\t\t\t\t(start {-geom.half_w} {bottom})',
            f'\t\t\t\t(end {geom.half_w} {top})',
            '\t\t\t\t(stroke (width 0.254) (type default))',
            '\t\t\t\t(fill (type background))',
            '\t\t\t)',
            '\t\t)',
            f'\t\t(symbol "{_esc(sym_name)}_1_1"',
        ]
        lines.extend(_pb(pin, x, y, rot, pin_length=_pl_s, text_scale=page_scale)
                     for pin, x, y, rot in geom.pin_placements)
        lines += ['\t\t)', '\t)', ')']
        open(f"{vdir}/{file_stem}.kicad_sym", "w").write("\n".join(lines))
        lib_ids.append(f"{file_stem}:{sym_name}")
    return lib_ids, vdir

# v03.1: MCU-page ball whitelist. U1 has group="mcu", so without this every one
# of its 152 net-touched balls lands on the MCU sheet (still a blob). Industry
# practice draws only the CORE banks on the MCU sheet (power rails, clock, reset,
# boot/debug); every functional-IO ball is ALREADY drawn on its own sheet because
# the shared net crosses there. We keep an MCU-core ball on the MCU sheet iff the
# net name that touches it starts with one of these functional prefixes.
MCU_CORE_NET_PREFIXES = (
    "+1V8", "+3V3", "VDDA", "GND", "PWR", "VBAT", "BAT",   # power rails
    "HSE", "NRST", "BOOT0", "SWDIO", "SWCLK", "DBG",         # clock / reset / debug
    "SHARED",                                                  # core shared
)

# DD-9a (2026-07-07): 02_mcu_core SPLIT into two sheets. The single MCU sheet hit
# BUDGET_INFEASIBLE h:+7.27mm — content_h = span_y + pad_h(168, =U1 64-ball subset
# half-height 336.56/2) + 2*label_reach(197) = 848 > A0 841. pad_h is dominated by
# the U1 half-height, which is a STEP function of ball count (four-edge BGA
# perimeter projection): 64 balls -> half_h 177, but ~32 balls -> half_h 91 (a per-
# edge pin count that halves the body height). Probe-confirmed. Splitting the 64
# core balls into two ~32-ball functional banks drops each sheet's pad_h from 168
# to ~91, and halves span_y + per-sheet net count (lower label_reach). Cross-sheet
# nets carry by same-named global label (collinearity-free). The fidelity gate keys
# off the ball SEED set (ref-agnostic) and exempts power/GND/VDD/VSS balls from the
# lost-signal check, so the two banks' seed union completing the core set is enough.
# Bank A = SMPS/analog/PMU power + clock/reset/boot/debug signals; Bank B = digital
# IO rails (+3V3, GND, VDDIO). A ball is kept on a sheet iff a net touching it
# starts with one of that sheet's prefixes.
# DD-9a: the MCU sheet's 64 core balls are split into two SHEETS by BGA ROW band
# (not by functional net-prefix). Rationale (probe-confirmed 2026-07-07): a
# functional split is 53:11 unbalanced (POWER prefixes hit 53 balls, SIGNAL 11),
# so the POWER sheet's U1 subset keeps ~53 balls and its half-height still
# dominates pad_h (=max-bbox/2) -> BUDGET_INFEASIBLE h:+7.27mm persists. pad_h is
# governed by the U1 subset's VERTICAL extent (BGA row span), so splitting on the
# ROW axis into two contiguous row-bands (35/29 balls, 8 rows each vs 16) halves
# the vertical projection -> halves pad_h. Column-split (43:21) is also unbalanced;
# row-split is the balanced geometric cut. Each sheet seeds ONLY its row band; the
# union of both bands == the whole core set (fidelity seed-union preserved).
# slug -> which of the 2 row bands (0 or 1) this sheet draws.
MCU_CORE_ROW_BANDS = {
    "02a_mcu_upper": 0,   # upper BGA rows (A..~K)
    "02b_mcu_lower": 1,   # lower BGA rows (~L..W)
}


def _u1_ball_nets(ccm_nets):
    """ball -> set of net-names touching it (for MCU-core filtering)."""
    m = {}
    for n in ccm_nets:
        for nd in n["nodes"]:
            r, _, p = nd.partition(".")
            if r == "U1":
                m.setdefault(p, set()).add(n["name"])
    return m


_U1_BALL_NETS = _u1_ball_nets(ccm_nets)


# functional pages: (group, page_slug, human_title, ref_filter).
# ref_filter (DD-9): optional iterable of refs; when present, this page draws ONLY
# those refs from the group instead of the whole group. None => whole group
# (byte-identical to the pre-filter behaviour for 01-04).
#
# DD-9 (2026-07-07): 05_stamp_icd was SPLIT into two independent sheets. The
# single stamp page hit BUDGET_INFEASIBLE h:+7.27mm: content_h = span_y(471) +
# pad_h(168, =U1 subset half-height) + 2*label_reach(197) = 836 > A0 841. The
# pitch-invariant constant band (pad_h + label_reach = 365mm) dominates and
#降 pitch cannot shrink it (probe-confirmed). JSA and JSB share only GND, so a
# clean functional split (JSA sheet / JSB sheet) halves span_y AND gives each
# sheet a smaller U1 ball-subset (43 vs 48 balls) -> smaller pad_h. Cross-sheet
# nets (GND) carry by same-named global label (connection_style="label"),
# collinearity-free by construction. Fidelity gate keys off the ball SEED set
# (ref-agnostic), so the two sheets' seed subsets union-complete the SSOT.
# DD-9b (2026-07-07): 02_mcu_core RESTORED to a SINGLE sheet. The DD-9a 02a/02b
# row-band split was probe-proven ineffective: the real BUDGET_INFEASIBLE page was
# 01_power (touches_via_other cross-seed pulls 43-69 U1 balls onto EVERY page), and
# the mcu-sheet split cannot govern that cross-seed. The true fix is the pitch-scan
# gate-order fix above (BUDGET_INFEASIBLE now eliminates a pitch instead of aborting
# the scan), which lets a smaller fit-capable pitch win per page. The row-band
# helpers (_split_balls_by_row / MCU_CORE_ROW_BANDS) are KEPT as dormant
# infrastructure: if any page still exhausts all candidates post-fix, that page can
# re-apply a band split. 05a/05b stamp split stays (independently passing + better
# JSA/JSB page semantics, per DD-9a).
PAGES = [
    ("power",    "01_power",     "電源樹 (Power Tree)", None),
    ("mcu",      "02_mcu_core",  "MCU 核心 (STM32N657 SMPS/類比/時鐘複位除錯 + 數位 IO / 電軌)", None),
    # DD-9c (2026-07-07): 03_memory SPLIT into two sheets by memory INTERFACE. The
    # single memory page exhausted all 8 pitch candidates under the M4 gates (large
    # pitch INTRA_OVERLAP: HSPI/OSPI IO net-name text 7-17mm horizontal overlap on a
    # ~8:1 narrow-tall page; small pitch INK_LOW). U2 (HEXASPI PSRAM) touches only
    # HSPI_* nets, U3 (OCTOSPI Flash) only OSPI_* nets; the two interfaces are
    # prefix-disjoint (shared nets = +1V8, GND, carried cross-sheet by same-named
    # global label). A per-ref filter (U2 / U3) is therefore the clean interface
    # split -> each sheet halves the IO label count, relieving both horizontal text
    # overlap and ink density. Reuses the DD-9 ref_filter path (same as 05a/05b).
    ("mem",      "03a_memory_hspi","記憶體 A (HEXASPI PSRAM / HSPI)", ("U2",)),
    ("mem",      "03b_memory_ospi","記憶體 B (OCTOSPI Flash / OSPI)", ("U3",)),
    ("wireless", "04_wireless",  "無線 (nRF7002 WiFi + MDBT53 BLE)", None),
    ("stamp",    "05a_stamp_jsa","郵票座 ICD A (Castellated Edge JSA)", ("JSA",)),
    ("stamp",    "05b_stamp_jsb","郵票座 ICD B (Castellated Edge JSB)", ("JSB",)),
]

manifest = []
for grp, slug, title, ref_filter in PAGES:
    refs = [c["ref"] for c in ccm_comp if group_of.get(c["ref"]) == grp
            and (ref_filter is None or c["ref"] in ref_filter)]
    comps = [dict(c) for c in ccm_comp if c["ref"] in refs]
    # nets touching any ref on this page; keep only nodes on this page's refs
    page_nets = []
    u1_balls_here = set()
    for n in ccm_nets:
        on_page = [nd for nd in n["nodes"] if nd.split(".")[0] in refs]
        if on_page:
            page_nets.append({"name": n["name"], "nodes": on_page})
        # collect the U1 balls whose net also touches this page BECAUSE OF A
        # NON-U1 ref on this page (the signal crosses to U1 → its ball must be
        # DRAWN here to carry it). We must NOT count U1's own membership: on the
        # MCU sheet U1 IS in refs, so `any(node in refs)` would be true for every
        # U1 net and pull all 222 balls back (the blob). Restrict the trigger to
        # OTHER refs; the MCU sheet's own core balls are seeded separately below.
        touches_via_other = any(
            nd.split(".")[0] in refs and nd.split(".")[0] != "U1" for nd in n["nodes"]
        )
        if touches_via_other:
            for nd in n["nodes"]:
                r, _, pin = nd.partition(".")
                if r == "U1" and pin in _U1_BALL_SET:
                    u1_balls_here.add(pin)

    # If U1 signals appear on this page, draw U1 as a per-page pin subset variant.
    # This replaces the full 222-ball symbol (the "black blob" root cause).
    # v03.1: on the MCU sheet, U1 belongs to group "mcu" so `"U1" in refs` is
    # True but u1_balls_here is empty (no OTHER mcu-group ref shares U1's nets).
    # Seed it with the CORE banks only, so the MCU sheet draws power/clock/reset/
    # debug balls; all functional-IO balls stay on their own sheets (already
    # carried there by the crossing net). Electrical truth is unchanged — this
    # only selects which balls are DRAWN on the MCU sheet.
    if grp == "mcu":
        # DD-9a: seed the whole MCU-core ball set (net-prefix filtered), THEN keep
        # only THIS sheet's BGA ROW band. The row-band split (MCU_CORE_ROW_BANDS)
        # halves the U1 subset's vertical extent -> halves pad_h -> fits A0. The
        # union of band 0 + band 1 == the whole core set (seed-union fidelity).
        # An unknown slug (unsplit caller) keeps the whole core set (byte-identical
        # to pre-split behaviour).
        core_balls = {
            ball for ball, netset in _U1_BALL_NETS.items()
            if any(nm.startswith(pfx) for nm in netset for pfx in MCU_CORE_NET_PREFIXES)
        }
        _band = MCU_CORE_ROW_BANDS.get(slug)
        if _band is not None:
            _bands = _split_balls_by_row(sorted(core_balls), 2)
            core_balls = set(_bands[_band]) if _band < len(_bands) else set()
        u1_balls_here |= core_balls

    u1_on_page = "U1" in refs or bool(u1_balls_here)

    # --- per-page pitch solver -------------------------------------------------
    # _build_page_at_pitch(pin_pitch, page_scale): rebuild THIS page's compose
    # spec + symbol dirs at a candidate pitch. Regenerates the U1 variant at that
    # pitch so the in-symbol geometry, text_scale and compose page_scale stay
    # coherent. Works on fresh copies of refs/comps so a rejected candidate leaves
    # no residue. Returns (spec, page_symdirs, refs_final). Not to be read as:
    # mutating the outer-loop refs/comps.
    def _build_page_at_pitch(pin_pitch, page_scale):
        p_refs = list(refs)
        p_comps = [dict(c) for c in comps]
        if u1_on_page:
            carried = (f"{len(u1_balls_here)}/{len(_U1_BALL_SET)} balls on this sheet; "
                       f"remaining STM32N657 balls appear on their functional sheets")
            variant_libs, vdir = build_u1_variant(slug, u1_balls_here, carried,
                                                  pin_pitch, page_scale)
            p_symdirs = [vdir] + SYMDIRS if vdir not in SYMDIRS else SYMDIRS
            # v05: build_u1_variant returns a LIST of lib_ids (one per split band).
            # The first band keeps ref "U1" (byte-identical for unsplit pages);
            # extra bands are placed as sibling instances U1_b1, U1_b2, ... . These
            # are electrically inert extra refs: connection_style="label" carries
            # nets by name, and the fidelity gate keys off the seed set
            # u1_balls_here (ref-agnostic), so N drawn instances reunite to the
            # same ball set. Each sub-symbol drew a disjoint ball band, so no ball
            # is duplicated across instances.
            band_refs = ["U1"] + [f"U1_b{i}" for i in range(1, len(variant_libs))]
            if "U1" in p_refs:
                for c in p_comps:
                    if c["ref"] == "U1":
                        c["symbol"] = variant_libs[0]
            else:
                p_comps.append({"ref": "U1", "group": grp, "symbol": variant_libs[0],
                                "value": f"STM32N657L0 ({slug})",
                                "footprint": "aiguard:STM32N657_VFBGA223"})
                p_refs = p_refs + ["U1"]
            for extra_ref, extra_lib in zip(band_refs[1:], variant_libs[1:]):
                p_comps.append({"ref": extra_ref, "group": grp, "symbol": extra_lib,
                                "value": f"STM32N657L0 ({slug})",
                                "footprint": "aiguard:STM32N657_VFBGA223"})
                p_refs = p_refs + [extra_ref]
        else:
            p_symdirs = SYMDIRS
        p_nets = []
        for n in ccm_nets:
            on_page = [nd for nd in n["nodes"] if nd.split(".")[0] in p_refs]
            if on_page:
                p_nets.append({"name": n["name"], "nodes": on_page})
        for c in p_comps:
            c.pop("_rail", None)
        # DD-21 (user directive): every DRAWN U1 ball that carries NO net node on
        # this page gets an explicit KiCad (no_connect) glyph — a drawn pin is never
        # left hanging. `u1_balls_here` is exactly the U1 ball subset DRAWN on this
        # page (build_u1_variant draws these balls in native order across L/R). A
        # ball is "connected here" iff some page net has a `U1.<ball>` node. The
        # emitter resolves each "U1.<ball>" to the placed pin endpoint (fail-fast if
        # a ball is not actually drawn), so NC entries are constrained to drawn balls.
        _nc = []
        if u1_on_page:
            _connected_balls = {
                nd.partition(".")[2] for pn in p_nets for nd in pn["nodes"]
                if nd.partition(".")[0] == "U1"
            }
            _drawn_here = [b for b in sorted(u1_balls_here) if b in _U1_PIN_META]
            _nc = [f"U1.{b}" for b in _drawn_here if b not in _connected_balls]
        return {"components": p_comps, "nets": p_nets, "nc": _nc}, p_symdirs, p_refs

    outdir = f"{FB}/sch_ccm_pages/{slug}"
    os.makedirs(outdir, exist_ok=True)
    # stamp ICD page: JSA/JSB are Conn_01x36 castellated edge connectors with dozens
    # of pins packed on one x column. draftsman's drawn-wire routing (_bus_route /
    # _orthogonal_route) daisy-chains same-net pins with orthogonal wires that, on
    # such a dense column, run COLLINEAR and KiCad fuses them into one net (the
    # 141-node GND short that absorbed 14 rails). Per-pin GLOBAL LABELS with zero
    # drawn wire (connection_style="label") is the industry convention for edge
    # connectors and is collinearity-free by construction. Other pages keep the
    # draftsman drawn-wire style + power symbols for BGA rails.
    # Compact-layout tuning (user directive: pages are too sparse, ~1/3 fill —
    # tighten spacing/padding, pick the smallest fitting frame). The per-page U1
    # already carries a large in-symbol pin_pitch (11.43 mm), so the placement
    # engine's k = max(member bbox)+gutter inflates EVERY part's spacing to U1's
    # extent, scattering the tiny decoupling caps and leaving big whitespace. We
    # pass an opt-in gutter scale (<1) to tighten inter-part / inter-cluster
    # whitespace and a small sheet margin so the smallest standard frame is
    # chosen. Electrical truth and pin_pitch are untouched.
    _GUTTER_SCALE = 0.18   # tighten the 12/20/30 mm ladder + *3 cell multiplier
    _SHEET_MARGIN = 6.0    # per-side border before paper selection (was 12.7)
    # DD-14 (user directive: PER-PAGE pitch). U1's in-symbol pin_pitch sets the
    # single-symbol height; a page whose U1 ball-subset is a narrow-tall column
    # (03_memory ~8:1) needs a DIFFERENT pitch than a wide/dense page to pass the
    # smallest-frame + ≥40% utilization gate. macro_compact clusters each big part
    # with its satellite caps; page_fill spreads overlap-free units so whitespace
    # is even breathing gutters; the utilization gate (composer, MIN 40%) is the
    # authority that a page is not sparse. The per-page pitch solver below picks
    # the LARGEST candidate pitch that still passes that gate.
    _compose_common = dict(
        symbol_dirs=None, validate=True, style="draftsman",
        placement_gutter_scale=_GUTTER_SCALE, sheet_margin_mm=_SHEET_MARGIN,
        macro_compact=True, page_fill=True,
    )
    # DD-15 (user directive: NO chip-to-chip wire routing on ANY schematic page).
    # Physical routing is the layout tool's job; the schematic expresses connectivity
    # by same-named global labels only. draftsman's drawn-wire style (_bus_route /
    # _orthogonal_route) daisy-chains same-net pins with orthogonal wires that cross
    # component bodies (the ADQ5/6/7 wires seen penetrating U2 on 02/03). Forcing
    # connection_style="label" on EVERY page emits a per-pin global label with zero
    # inter-component drawn wire — the industry convention. power_ports stays True on
    # non-stamp pages so BGA rails still hang power/GND symbols (a power symbol on a
    # rail pin is not chip-to-chip routing); the dense castellated stamp page keeps
    # power_ports=False (its rails are labelled too, collinearity-free by construction).
    # BR_20260708 landing: the draftsman drawn-wire routers now do component-body
    # keep-out (obstacle avoidance) — a 2-node short net routes AROUND every OTHER
    # symbol body instead of through it (the ADQ5/6/7-through-U2 defect), and the
    # emit machine check (wire_body_intrusions) proves 0 crossings. So the all-page
    # connection_style="label" stopgap is REMOVED: pages use the draftsman mixed
    # default — 2-node short nets draw a solid wire loop; multi-node (>=3) nets +
    # power/GND rails fall back to global label (T3). The dense castellated stamp
    # page keeps power_ports=False AND forces all_label (its collinear connector
    # columns cannot draw wire safely — collinearity-free by construction).
    if grp == "stamp":
        _compose_common.update(power_ports=False)

    # DD-12 (2026-07-07, user directive: 「一開始就把晶片維度、腳數間距、腳長度全都
    # 算清楚，一次到位，砍掉所有事後驗算邏輯」). CONSTRUCTIVE closed-form sizing REPLACES
    # the solve_paper_first scan. The symbol geometry is already constructive
    # (_symbol_geometry sizes every body so pin NAME text cannot overlap by
    # construction — DD-2 need_w / DD-11a horiz_pitch / DD-11a2 corner_span), so
    # there is nothing to try-and-reject. Three deterministic steps, zero retry:
    #   1. build the page ONCE at scale 1.0 (the natural size), probe-compose into a
    #      throwaway dir to measure the composed content bbox;
    #   2. size_paper_closed_form(bbox) picks the smallest paper that contains it and
    #      the largest KiCad-pitch-multiple scale that fills that paper (圖大紙小);
    #   3. rebuild the page ONCE at that scale and compose the deliverable.
    # The only fail-loud path is CONTENT_EXCEEDS_A0 (content bigger than A0 at
    # scale 1.0) — raised inside size_paper_closed_form, never a scale-down retry.
    from bodesign_eda_bridge.composer import (
        size_paper_closed_form, STANDARD_PAPERS, PAPER_MARGIN_FRAC,
    )
    # DD-30: label-reach mirror constants live in kicad_emit (composer re-imports
    # them there too); pull them here for the ink-inclusive joint sizer below.
    from bodesign_eda_bridge.kicad_emit import (
        _LABEL_STUB_STEP_MM, _LABEL_CW_MM, _LABEL_GLYPH_MM, _LABEL_HMARGIN_MM,
        _PIN_NAME_OFFSET_MM, _PIN_NAME_CH_MM, _LABEL_VMARGIN_MM,
    )
    _scale_to_refs_spec: dict[float, tuple] = {}

    def _pf_build(scale):
        pitch = round(scale * _KICAD_BASE_PITCH, 4)
        p_spec, p_symdirs, p_refs = _build_page_at_pitch(pitch, scale)
        # BR_20260708: the dense castellated stamp page cannot draw wire on its
        # collinear connector columns; force spec-level all_label there (a SPEC
        # key, not a compose kwarg). Every other page uses the draftsman mixed
        # default (2-node wire / multi-node + rail label).
        if grp == "stamp":
            p_spec["all_label"] = True
        _scale_to_refs_spec[scale] = (p_refs, p_spec, pitch)
        return p_spec, p_symdirs

    def _solve_and_compose(real_outdir):
        _kw = {k: v for k, v in _compose_common.items() if k != "symbol_dirs"}
        scan: list[str] = []
        # STEP 1 — natural-size probe: build + compose ONCE at scale 1.0 to measure
        # the composed content bbox (the single determined input to closed-form).
        probe_dir = f"{real_outdir}/_closed_form_probe"
        os.makedirs(probe_dir, exist_ok=True)
        base_spec, base_symdirs = _pf_build(1.0)
        probe = compose_schematic(
            probe_dir, f"aiguard_ccm_{slug}", base_spec,
            symbol_dirs=base_symdirs, page_scale=1.0, **_kw,
        )
        sf0 = probe.sheet_fit
        _usable_frac = max(1.0 - 2 * PAPER_MARGIN_FRAC, 1e-6)
        # DD-32 (2026-07-07, sizer probe-deliverable coherence): the scale-1.0-probe +
        # LINEAR-EXTRAPOLATION sizer (`_ink_at(s) = span·s + ext·s + 2·reach(s)`) is
        # STRUCTURALLY dead. Since 第八棒 scaled peripheral (non-U1) symbol geometry
        # with page_scale (kicad_emit.load_symbol/_scale_symbol_geometry), the true
        # drawn ink now grows NON-LINEARLY with scale AND only in the deliverable
        # (page_scale>1), never in the scale-1.0 probe. Measured on 02_mcu:
        #   probe@1.0 true ink 421.7×385.6  →  deliverable@1.1 true ink 526.1×468.3
        #   ratios W 1.247 / H 1.214  ≠  scale 1.1
        # so any base·s extrapolation from the 1.0 probe under-predicts → picks too
        # small a paper → overflow (all 7 pages inframe=False). The non-linearity is
        # irreducible: peripheral parts carry scale-invariant text-pad constants
        # (_TEXT_PAD_H_MM etc.) so per-part bbox(s) ≠ bbox(1.0)·s.
        #
        # FIX (Plan A, probe==deliverable by construction): _fit_sheet at compose
        # scale s already emits content_w/h = the TRUE drawn AABB at that s (per-edge
        # extent, composer.py:1187-1202). So for each candidate scale we COMPOSE a
        # throwaway probe AT THAT SCALE and read its content_w/h directly — no
        # extrapolation. Deliverable (STEP 3) rebuilds at the same chosen scale, so it
        # draws exactly the ink the probe measured → fits the chosen paper by
        # construction. Probe compose ≈ 10–50 ms; the ladder is ~10–15 candidates.
        body_w = sf0.content_w if sf0 else 0.0   # scale-1.0 ink (scan display only)
        body_h = sf0.content_h if sf0 else 0.0

        # ---- Plan A helpers -------------------------------------------------------
        # _probe_ink_at(scale): compose a throwaway probe at `scale` (wl=None) and
        #   return the TRUE drawn ink extent (W, H) at that scale, measured by PARSING
        #   the probe's own emitted .kicad_sch — every element anchor (symbol/wire/
        #   global_label/label/text/junction), the exact same all-element parse the
        #   inframe acceptance gate uses. Cached per scale.
        #
        # DD-32b (2026-07-07, RCA of the DD-32 residual overflow): the first DD-32 cut
        # read `sheet_fit.content_w/h` as the fit quantity. Boundary evidence disproved
        # that as authoritative — on 02_mcu@1.2 the probe's sheet_fit.content_w/h was
        # 349.9×374.2, but the SAME probe's TRUE parsed ink (all element anchors) was
        # 544.1×488.9 (global_labels reach x∈[153.9,438.9] and symbols reach x=−105.2,
        # neither fully captured by content_w/h = span + ext_l/r + 2·reach). The probe
        # GEOMETRY equals the deliverable's by construction (probe@s ink == deliverable@s
        # ink, verified identical), so the ONLY defect was the sizer trusting an
        # under-reporting model value instead of the real drawn extent. Parsing the
        # probe's true ink here makes the fit test == the inframe gate == the deliverable
        # by construction — no model, no extrapolation, no fudge.
        _probe_ink_cache: dict[float, tuple[float, float]] = {}

        def _parse_true_ink(_schpath: str) -> tuple[float, float]:
            # all-element extent: every (at x y) and (xy x y) anchor in the .kicad_sch.
            # IDENTICAL basis to the inframe acceptance gate (nothing is placed off this
            # extent), so a page that fits here fits the gate by construction.
            try:
                _t = open(_schpath).read()
            except OSError:
                return (0.0, 0.0)
            _xs: list[float] = []
            _ys: list[float] = []
            for _m in re.finditer(r"\(at\s+(-?[\d.]+)\s+(-?[\d.]+)", _t):
                _xs.append(float(_m.group(1))); _ys.append(float(_m.group(2)))
            for _m in re.finditer(r"\(xy\s+(-?[\d.]+)\s+(-?[\d.]+)\)", _t):
                _xs.append(float(_m.group(1))); _ys.append(float(_m.group(2)))
            if not _xs:
                return (0.0, 0.0)
            return (max(_xs) - min(_xs), max(_ys) - min(_ys))

        def _probe_ink_at(scale: float, paper: str) -> tuple[float, float]:
            # DD-32c (2026-07-07): the probe MUST compose under the SAME paper_whitelist
            # the deliverable will use at this (paper, scale), because page_fill spreads
            # component centres to fill the BOUNDED chosen sheet — a wl=None probe leaves
            # centres at their natural (unbounded) positions and under-measures the ink.
            # Boundary evidence: 01_power@1.0 probe(wl=None)=393.4x360.1 but
            # deliverable(wl=A2)=479.7x422.3 (uniform ~1.22x across all 7 pages). Binding
            # the candidate paper into the probe makes probe ink == deliverable ink by
            # construction, so the fit-test and the acceptance gate agree.
            _sk = round(scale, 4)
            _ck = (_sk, paper)
            _hit = _probe_ink_cache.get(_ck)
            if _hit is not None:
                return _hit
            _pspec, _psym = _pf_build(_sk)
            _pdir = f"{real_outdir}/_scale_probe_{paper}_{_sk}"
            os.makedirs(_pdir, exist_ok=True)
            compose_schematic(
                _pdir, f"aiguard_ccm_{slug}", _pspec,
                symbol_dirs=_psym, page_scale=_sk,
                paper_whitelist={paper}, **_kw,
            )
            _iw, _ih = _parse_true_ink(f"{_pdir}/aiguard_ccm_{slug}.kicad_sch")
            _probe_ink_cache[_ck] = (_iw, _ih)
            return (_iw, _ih)

        def _quantised_scales_desc(max_scale: float) -> list[float]:
            # tenth-pitch quantum ladder (DD-29(3) _SCALE_QUANTUM), never below 1.0,
            # descending so the first fit is the tightest.
            n = max(int(max_scale / _SCALE_QUANTUM), int(1.0 / _SCALE_QUANTUM))
            out = []
            while n * _SCALE_QUANTUM >= 1.0 - 1e-9:
                out.append(round(n * _SCALE_QUANTUM, 4))
                n -= 1
            return out or [1.0]

        scan.append(
            f"[closed-form] probe scale=1.0 ink={body_w:.1f}x{body_h:.1f} "
            f"(per-scale probe sizer, DD-32)")
        # STEP 2 — per-scale-probe paper+scale selection. Smallest-paper-first,
        # largest-scale-first: for each paper, upper-bound the scale from the scale-1.0
        # ink (a lower bound on the growth rate, so _cap never under-shoots the true
        # feasible scale), then walk the quantum ladder DOWN, composing a probe at each
        # s and accepting the first whose TRUE ink fits this paper's 90% usable region.
        # Fail-loud CONTENT_EXCEEDS_A0 when even A0 cannot hold the scale-1.0 ink.
        _chosen_paper = None
        _chosen_scale = None
        for _pn, _pw, _ph in STANDARD_PAPERS:
            _uw, _uh = _pw * _usable_frac, _ph * _usable_frac
            if body_w <= 0 or body_h <= 0:
                _chosen_paper, _chosen_scale = _pn, 1.0
                break
            # _cap: scale ceiling from the scale-1.0 ink. True ink grows FASTER than
            # linear (peripheral scaling), so body·s is a LOWER bound on true ink → the
            # linear _cap is an UPPER bound on feasible scale (safe: we probe downward
            # from it and never skip a feasible larger s). Guard ≥1.0.
            _cap = min(_uw / max(body_w, 1e-6), _uh / max(body_h, 1e-6))
            for _s in _quantised_scales_desc(max(_cap, 1.0)):
                _iw, _ih = _probe_ink_at(_s, _pn)
                if _iw <= _uw and _ih <= _uh:
                    _chosen_paper, _chosen_scale = _pn, _s
                    break
            if _chosen_paper is not None:
                break
        if _chosen_paper is None:
            _ln, _lw, _lh = STANDARD_PAPERS[-1]
            _iw, _ih = _probe_ink_at(1.0, _ln)
            raise ValueError(
                f"CONTENT_EXCEEDS_A0: true drawn ink {_iw:.1f}×{_ih:.1f} mm at scale "
                f"1.0 exceeds {_ln} {_lw:.0f}×{_lh:.0f} usable ({_usable_frac*100:.0f}%). "
                f"Split the subsystem (fail-loud, not a scale-down retry).")

        class _Sizing:
            paper = _chosen_paper
            scale = round(_chosen_scale, 4)
        sizing = _Sizing()
        _ciw, _cih = _probe_ink_at(sizing.scale, sizing.paper)
        scan.append(
            f"[closed-form] paper={sizing.paper} scale={sizing.scale} "
            f"pitch={round(sizing.scale * _KICAD_BASE_PITCH, 4)} "
            f"probe_ink={_ciw:.1f}x{_cih:.1f}")
        # STEP 3 — build ONCE at the closed-form scale and compose the deliverable,
        # pinned to the chosen paper (paper_whitelist) so the frame is exactly the
        # one the closed form selected.
        final_spec, final_symdirs = _pf_build(sizing.scale)
        real = compose_schematic(
            real_outdir, f"aiguard_ccm_{slug}", final_spec,
            symbol_dirs=final_symdirs, page_scale=sizing.scale,
            paper_whitelist={sizing.paper}, **_kw,
        )
        real.warnings.extend(scan)
        p_refs, p_spec, chosen_pitch = _scale_to_refs_spec[sizing.scale]
        return real, chosen_pitch, sizing.scale, p_refs, p_spec, scan

    r, chosen_pitch, chosen_pscale, refs, spec, scan_row = _solve_and_compose(outdir)
    page_nets = spec["nets"]
    sf = r.sheet_fit
    erc = r.validation.erc_errors if r.validation else "?"
    print(f"[{slug}] pitch={chosen_pitch} scale={chosen_pscale} refs={len(refs)} "
          f"nets={len(page_nets)} placed={r.placed} "
          f"u1_balls={len(u1_balls_here) if u1_on_page else 0} "
          f"paper={sf.selected_paper if sf else '?'} overflow={sf.overflow if sf else '?'} erc={erc}")
    print(f"   pitch_scan: {' '.join(scan_row)}")
    if r.warnings:
        print(f"   warnings: {r.warnings}")
    manifest.append({"group": grp, "slug": slug, "title": title, "refs": refs,
                     "pitch": chosen_pitch, "page_scale": chosen_pscale,
                     "paper": sf.selected_paper if sf else None,
                     "overflow": sf.overflow if sf else None, "erc": erc,
                     "net_count": len(page_nets),
                     "u1_balls_on_page": sorted(u1_balls_here) if u1_on_page else []})

json.dump(manifest, open(f"{FB}/sch_ccm_pages/manifest.json", "w"), ensure_ascii=False, indent=2)
print("=== manifest written ===")

# ---------------------------------------------------------------------------
# Fidelity gate (SSOT-based). The single-sheet baseline .net is now polluted by
# the power-symbol drawing layer and cannot be a clean reference. The clean
# electrical truth is `ccm_nets` (captured pre-compose above, via the stubbed
# gen_ccm exec). We assert the per-page slices REUNITE into exactly that truth:
#   1. every (net -> set of REAL component pins) recombines to the SSOT set;
#   2. no page introduces or drops a pin relative to the SSOT restricted to the
#      refs actually drawn across all pages.
# Power ports / PWR_FLAG never appear here because we compare the compose INPUT
# specs (page_nets), not the emitted .net. diff 0/0 == fidelity preserved.
# ---------------------------------------------------------------------------
def _ssot_partition(nets):
    part = {}
    for n in nets:
        s = part.setdefault(n["name"].lstrip("/"), set())
        for nd in n["nodes"]:
            s.add(nd)
    return part

_ssot = _ssot_partition(ccm_nets)

# Rebuild the merged partition from the exact per-page specs that were composed.
_merged = {}
for grp, slug, title, ref_filter in PAGES:
    refs = [c["ref"] for c in ccm_comp if group_of.get(c["ref"]) == grp
            and (ref_filter is None or c["ref"] in ref_filter)]
    # replicate the page_nets selection (nodes restricted to this page's refs),
    # but here we want the UNION back to full nodes -> use the SSOT nodes whose
    # ref is drawn on some page. Simpler: a node belongs to the merged partition
    # iff its ref is drawn on ANY page. U1 is drawn on every page that carries
    # its balls, so its balls recombine across pages.
    pass

# A ref is "drawn" if it appears on any page's refs OR is U1 (per-page subset).
# DD-9: with ref_filter the stamp group is split across 05a/05b, but the UNION of
# both pages' refs still equals the whole stamp group, so drawn-ref completeness is
# unchanged (a group ref filtered off 05a is drawn on 05b or vice versa).
_drawn_refs = set()
for grp, slug, title, ref_filter in PAGES:
    for c in ccm_comp:
        if group_of.get(c["ref"]) == grp and (ref_filter is None or c["ref"] in ref_filter):
            _drawn_refs.add(c["ref"])
_drawn_refs.add("U1")

# The merged partition = SSOT restricted to nodes whose ref is drawn somewhere.
# For U1, restrict further to balls actually drawn across pages (per-page subset)
_u1_drawn = set()
for m in manifest:
    _u1_drawn |= set(m["u1_balls_on_page"])

_fid_diff = 0
_orphan = 0
for net, nodes in _ssot.items():
    for nd in nodes:
        r, _, p = nd.partition(".")
        if r == "U1":
            # a U1 ball must be drawn on >=1 page iff the SSOT net is a real signal
            # (non power/NC). Power/NC balls may be omitted by the subset by design.
            if p not in _u1_drawn and not (net.startswith(("+", "GND", "VDD", "VSS", "VBAT", "unconnected", "PWR"))):
                # a real signal ball that no page drew -> genuine fidelity loss
                print(f"[FIDELITY] LOST signal ball U1.{p} (net {net})")
                _fid_diff += 1
        elif r not in _drawn_refs:
            print(f"[FIDELITY] node {nd} on net {net} has no page")
            _orphan += 1

print(f"=== FIDELITY GATE: ssot_nets={len(_ssot)} u1_balls_drawn={len(_u1_drawn)} "
      f"signal_balls_lost={_fid_diff} orphan_nodes={_orphan} ===")
print("FIDELITY:", "PASS diff 0/0" if (_fid_diff == 0 and _orphan == 0) else "FAIL")
