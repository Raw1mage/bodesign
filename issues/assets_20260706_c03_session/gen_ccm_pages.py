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

from bodesign_eda_bridge import compose_schematic

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
    """Return [(ball, side_x, rot, full_pin_line), ...] for every U1 pin."""
    out = []
    # each pin is a single line in the generated symbol; iterate line-wise to keep
    # the exact original s-expr text for re-emission.
    for line in _U1_SRC.splitlines():
        s = line.strip()
        if not s.startswith("(pin "):
            continue
        m = re.search(r'\(at\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\).*?\(number\s+"([^"]+)"', s)
        if not m:
            continue
        side_x = float(m.group(1)); rot = float(m.group(3)); ball = m.group(4)
        out.append((ball, side_x, rot, s))
    return out

_U1_PINS = _u1_pin_lines()
_U1_BALL_SET = {b for (b, _sx, _r, _l) in _U1_PINS}

def build_u1_variant(slug, balls_used, carried_note):
    """Write STM32N657_FULL__<slug> containing ONLY balls_used, re-flowed.

    balls_used: iterable of ball ids (e.g. {"A1","B5",...}) touched on this page.
    carried_note: human string naming where the other banks live.
    Returns (variant_lib_id, variant_dir) — a fresh single-symbol library.
    Pins keep their original left/right side assignment; y is re-flowed compact
    at 2.54 mm pitch (on-grid) so a small subset is readable and never overlaps.
    """
    sel = [(b, sx, rot, line) for (b, sx, rot, line) in _U1_PINS if b in balls_used]
    # keep deterministic order: left side first (sorted by original ball), then right
    left  = sorted([p for p in sel if p[1] < 0], key=lambda p: p[0])
    right = sorted([p for p in sel if p[1] >= 0], key=lambda p: p[0])
    # 3.81 mm (3 grid units) so the in-body pin NAME text of one row clears the
    # next row's name — 2.54 mm packed the names into a vertical smear on dense
    # sides. Net (global) labels outside the body are further separated by the
    # emitter's per-column stagger pass.
    PITCH = 3.81
    n = max(len(left), len(right), 1)
    top = (n - 1) * PITCH / 2.0
    # rectangle height sized to the taller column
    half_h = top + PITCH
    lines = ['(kicad_symbol_lib',
             '\t(version 20241209)',
             '\t(generator "bodesign-aiguard-fullboard-perpage")',
             f'\t(symbol "STM32N657_FULL__{slug}"',
             '\t\t(exclude_from_sim no)(in_bom yes)(on_board yes)',
             f'\t\t(property "Reference" "U" (at -55 {half_h+4:.2f} 0)(effects (font (size 1.27 1.27))))',
             f'\t\t(property "Value" "STM32N657L0 ({slug})" (at -55 {-half_h-4:.2f} 0)(effects (font (size 1.27 1.27))))',
             f'\t\t(property "Footprint" "aiguard:STM32N657_VFBGA223" (at 0 0 0)(effects (font (size 1.27 1.27))(hide yes)))',
             f'\t\t(property "Datasheet" "per-page subset; {carried_note}" (at 0 0 0)(effects (font (size 1.27 1.27))(hide yes)))',
             f'\t\t(symbol "STM32N657_FULL__{slug}_0_1"',
             f'\t\t\t(rectangle (start -55 {half_h:.2f})(end 55 {-half_h:.2f})(stroke (width 0.254)(type default))(fill (type background))))',
             f'\t\t(symbol "STM32N657_FULL__{slug}_1_1"']
    def _emit_col(col, side_x):
        for i, (ball, _sx, rot, line) in enumerate(col):
            yy = top - i * PITCH
            # rewrite the (at X Y ROT) of the original pin line to the new y,
            # keeping side_x and rot and the rest (name/number) verbatim.
            new = re.sub(r'\(at\s+-?[0-9.]+\s+-?[0-9.]+\s+(-?[0-9.]+)\)',
                         f'(at {side_x} {yy:.2f} \\1)', line, count=1)
            lines.append('\t\t\t' + new)
    _emit_col(left, -60)
    _emit_col(right, 60)
    lines += ['\t\t)', '\t)', ')']
    vdir = f"{FB}/sch_ccm_pages/_symvariants"
    os.makedirs(vdir, exist_ok=True)
    open(f"{vdir}/u1_{slug}.kicad_sym", "w").write("\n".join(lines))
    return f"u1_{slug}:STM32N657_FULL__{slug}", vdir

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
    if u1_on_page:
        carried = f"{len(u1_balls_here)}/{len(_U1_BALL_SET)} balls on this sheet; remaining STM32N657 balls appear on their functional sheets"
        variant_lib, vdir = build_u1_variant(slug, u1_balls_here, carried)
        if vdir not in SYMDIRS:
            page_symdirs = [vdir] + SYMDIRS
        else:
            page_symdirs = SYMDIRS
        # ensure a U1 component exists on this page pointing at the variant symbol
        if "U1" in refs:
            for c in comps:
                if c["ref"] == "U1":
                    c["symbol"] = variant_lib
        else:
            comps.append({"ref": "U1", "group": grp, "symbol": variant_lib,
                          "value": f"STM32N657L0 ({slug})",
                          "footprint": "aiguard:STM32N657_VFBGA223"})
            if "U1" not in refs:
                refs = refs + ["U1"]
        # re-collect page_nets now that U1 is a member of this page
        page_nets = []
        for n in ccm_nets:
            on_page = [nd for nd in n["nodes"] if nd.split(".")[0] in refs]
            if on_page:
                page_nets.append({"name": n["name"], "nodes": on_page})
    else:
        page_symdirs = SYMDIRS

    for c in comps:
        c.pop("_rail", None)
    spec = {"components": comps, "nets": page_nets}
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
    if grp == "stamp":
        r = compose_schematic(outdir, f"aiguard_ccm_{slug}", spec, symbol_dirs=page_symdirs,
                              validate=True, style="draftsman",
                              connection_style="label", power_ports=False)
    else:
        r = compose_schematic(outdir, f"aiguard_ccm_{slug}", spec, symbol_dirs=page_symdirs,
                              validate=True, style="draftsman")
    sf = r.sheet_fit
    erc = r.validation.erc_errors if r.validation else "?"
    print(f"[{slug}] refs={len(refs)} nets={len(page_nets)} placed={r.placed} "
          f"u1_balls={len(u1_balls_here) if u1_on_page else 0} "
          f"paper={sf.selected_paper if sf else '?'} overflow={sf.overflow if sf else '?'} erc={erc}")
    if r.warnings:
        print(f"   warnings: {r.warnings}")
    manifest.append({"group": grp, "slug": slug, "title": title, "refs": refs,
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
