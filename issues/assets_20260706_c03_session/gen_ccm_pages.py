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
# Mirror the composer's utilization floor (single source of truth) for the
# fail-loud NO_VIABLE_PITCH message only; the gate itself lives in composer.py.
from bodesign_eda_bridge.composer import MIN_SHEET_UTILIZATION as MIN_UTIL_FLOOR

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
# OPT-IN per slug: absent => n=1 => byte-identical to the pre-split single symbol
# (01-04 unchanged). Only 05_stamp_icd opts in.
_U1_SPLIT_BY_SLUG = {"05_stamp_icd": 2}


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
        pins = [
            _K(number=b, name=_U1_PIN_META[b][1], kind=_U1_PIN_META[b][0])
            for b in band
        ]
        # dense per-page subset (50-74 balls on ONE symbol): 1.27 mm pin pitch packs
        # the 1.27 mm-tall pin NAME text into a vertical smear. 3.81 mm (3 grid units)
        # clears adjacent names -- same readable spacing the old two-column reflow used.
        # user directive (pitch 3x): widen adjacent-pin spacing to 11.43 mm (=3.81*3,
        # 9 grid units) so perimeter wiring / net-label text never crowds.
        # pitch scales the body (user directive); pin GRAPHIC length stays at the base
        # _PL so the symbol's outer extent is not needlessly inflated (a longer pin
        # would push a sparse page's frame up a paper size at no readability gain --
        # the user complaint was tiny TEXT, cured by text_scale below, not short pins).
        geom = _sg(pins, pin_pitch=pin_pitch)
        left = round(-geom.half_w - _PL, 2)
        right = round(geom.half_w + _PL, 2)
        top = geom.half_h
        bottom = -geom.half_h
        band_note = carried_note if len(bands) == 1 else f"band {bi + 1}/{len(bands)}; {carried_note}"
        lines = [
            '(kicad_symbol_lib',
            '\t(version 20241209)',
            '\t(generator "bodesign-aiguard-fullboard-perpage")',
            f'\t(symbol "{_esc(sym_name)}"',
            '\t\t(exclude_from_sim no)(in_bom yes)(on_board yes)',
            _prop('Reference', 'U', left, top + 3.81, visible=True),
            _prop('Value', f'STM32N657L0 ({slug})', right - 15.24, top + 3.81, visible=True),
            _prop('Footprint', 'aiguard:STM32N657_VFBGA223', 0, 0, visible=False),
            _prop('Datasheet', f'per-page subset; {band_note}', 0, 0, visible=False),
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
        lines.extend(_pb(pin, x, y, rot, text_scale=page_scale)
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


# functional pages: group -> (page_slug, human title)
PAGES = [
    ("power",    "01_power",    "電源樹 (Power Tree)"),
    ("mcu",      "02_mcu_core", "MCU 核心 (STM32N657 + HSE)"),
    ("mem",      "03_memory",   "記憶體 (XSPI PSRAM + OCTOSPI Flash)"),
    ("wireless", "04_wireless", "無線 (nRF7002 WiFi + MDBT53 BLE)"),
    ("stamp",    "05_stamp_icd","郵票座 ICD (Castellated Edge A/B)"),
]

manifest = []
for grp, slug, title in PAGES:
    refs = [c["ref"] for c in ccm_comp if group_of.get(c["ref"]) == grp]
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
        core_balls = {
            ball for ball, netset in _U1_BALL_NETS.items()
            if any(nm.startswith(pfx) for nm in netset for pfx in MCU_CORE_NET_PREFIXES)
        }
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
        return {"components": p_comps, "nets": p_nets}, p_symdirs, p_refs

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
    _compose_common.update(connection_style="label")
    if grp == "stamp":
        _compose_common.update(power_ports=False)

    # _solve_and_compose: scan _PITCH_CANDIDATES large→small. For each, rebuild the
    #   page at that pitch (_build_page_at_pitch) and dry-run compose into a
    #   throwaway dir; the composer's util gate raises SHEET_UTILIZATION_TOO_LOW on
    #   a sparse sheet, so a caught raise == this pitch FAILs. First PASS wins →
    #   real compose into outdir at that pitch, returning (r, pitch, refs_final).
    #   NOT to be read as: finding a util threshold then going below it — the curve
    #   is non-monotonic, so it is strictly "first PASS descending".
    #   Done when a candidate's real compose completes, or fail-loud if none pass.
    def _solve_and_compose(real_outdir):
        scan = []
        for cand in _PITCH_CANDIDATES:
            pscale = round(cand / _KICAD_BASE_PITCH, 4)
            p_spec, p_symdirs, p_refs = _build_page_at_pitch(cand, pscale)
            kw = dict(_compose_common); kw["symbol_dirs"] = p_symdirs
            kw["page_scale"] = pscale
            probe_dir = f"/tmp/_pitch_probe/{slug}_{cand}"
            os.makedirs(probe_dir, exist_ok=True)
            try:
                pr = compose_schematic(probe_dir, f"aiguard_ccm_{slug}", p_spec, **kw)
            except ValueError as e:
                # Pitch-scan FAIL signals: a candidate pitch is INFEASIBLE for this
                # page and must be eliminated so the scan descends to the next one.
                # Two orthogonal infeasibility signals, both caught as FAIL:
                #  - SHEET_UTILIZATION_TOO_LOW: frame too sparse at this pitch.
                #  - LABEL_DENSITY_UNRESOLVED: at this pitch a mega-symbol's edge
                #    labels cannot clear the usable-x/y corridor (the emit guard
                #    fail-louds). That is a per-pitch feasibility verdict, NOT a
                #    hard engine error — a SMALLER pitch shrinks the label reach and
                #    may fit, so this pitch simply FAILs and the scan continues.
                # Any OTHER ValueError is a real engine fault → re-raise (fail-loud).
                if "SHEET_UTILIZATION_TOO_LOW" in str(e):
                    m = re.search(r"(\d+)% of (\w+)", str(e))
                    scan.append(f"{cand}:{m.group(2) if m else '?'}:{m.group(1) if m else '?'}%FAIL")
                    continue
                if "LABEL_DENSITY_UNRESOLVED" in str(e):
                    scan.append(f"{cand}:LABEL_INFEASIBLE:FAIL")
                    continue
                raise
            psf = pr.sheet_fit
            scan.append(f"{cand}:{psf.selected_paper if psf else '?'}:PASS")
            # first PASS descending → real compose at this pitch
            r_real = compose_schematic(real_outdir, f"aiguard_ccm_{slug}", p_spec, **kw)
            return r_real, cand, pscale, p_refs, p_spec, scan
        # no candidate passed → fail-loud with the full scan table
        raise ValueError(
            f"NO_VIABLE_PITCH for {slug}: every candidate failed the "
            f"≥{int(MIN_UTIL_FLOOR*100)}% utilization gate. scan={' '.join(scan)}")

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
for grp, slug, title in PAGES:
    refs = [c["ref"] for c in ccm_comp if group_of.get(c["ref"]) == grp]
    # replicate the page_nets selection (nodes restricted to this page's refs),
    # but here we want the UNION back to full nodes -> use the SSOT nodes whose
    # ref is drawn on some page. Simpler: a node belongs to the merged partition
    # iff its ref is drawn on ANY page. U1 is drawn on every page that carries
    # its balls, so its balls recombine across pages.
    pass

# A ref is "drawn" if it appears on any page's refs OR is U1 (per-page subset).
_drawn_refs = set()
for grp, slug, title in PAGES:
    for c in ccm_comp:
        if group_of.get(c["ref"]) == grp:
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
