"""Generalized subsystem composer (G3 / N10): design spec → schematic IR → emit.

Turns a declarative design spec (components + named-net interconnect) into the
EmitComponent/EmitNet IR and emits a `kicad-cli`-validatable schematic. This is
the generic, spec-driven generalization of the OpenMV-specific subsystem
emitter: parses `"REF.PIN"` node strings, resolves symbols across multiple
sources (stdlib + project-local generated libraries), and reuses
`emit_kicad_schematic` for the actual S-expr + connectivity.

Two placement/connection styles (DD-3 — opt-in, default preserves old behaviour):
  - "netlist" (DEFAULT): naive `index % columns` grid + global-label connectivity.
    Byte-equivalent to the pre-upgrade composer. Existing callers see no change.
  - "draftsman" (opt-in): subsystem-clustered, deterministic force-directed
    placement + drawn-wire connectivity (connection_style="wire") + sheet-fit.
    Produces an engineer-readable schematic. No RNG anywhere (deterministic rail).

Spec shape:
    {
      "components": [{"ref": "U5", "symbol": "Device:R", "value": "10k", "group": "power", "x": ..., "y": ...}],
      "nets": [{"name": "VCC_3.3V", "nodes": ["U5.1", "C1.1"], "kind": "power"}],
    }
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .kicad_emit import (
    DEFAULT_SYMBOL_DIR,
    EmitComponent,
    EmitNet,
    SchematicEmitResult,
    emit_kicad_schematic,
    load_symbol,
    resolve_symbol_library,
    validate_kicad_schematic,
    _vendor_sym_scale,
    _native_pitch_and_count,
    _page_pitch_floor,
    _snap_grid,
    _LABEL_STUB_STEP_MM,
    _LABEL_CW_MM,
    _LABEL_GLYPH_MM,
    _LABEL_HMARGIN_MM,
    _PIN_NAME_OFFSET_MM,
    _PIN_NAME_CH_MM,
    _LABEL_VMARGIN_MM,
)
from .occupancy import BudgetInfeasible, IntraSymbolTextOverlap, LedgerAssertionFailed, LedgerRect, OccupancyLedger

# Standard ISO-216 portrait sheet sizes (mm), smallest → largest (DD-5).
STANDARD_PAPERS: list[tuple[str, float, float]] = [
    ("A4", 297.0, 210.0),
    ("A3", 420.0, 297.0),
    ("A2", 594.0, 420.0),
    ("A1", 841.0, 594.0),
    ("A0", 1189.0, 841.0),
]

# Deterministic force-directed parameters (fixed → regression-stable, DD-2/DD-7).
PLACEMENT_ITERATIONS = 60
SPRING_K = 0.05
REPULSE_K = 2200.0
GRAVITY_K = 0.25  # centroid pull per iteration (contains all-pairs repulsion spread)
# Upper bound of the cluster gutter (T4): the actual gutter scales with design
# size via _cluster_gutter_mm() so a 16-part board is not inflated to A2.
CLUSTER_GUTTER_MM = 30.0
BBOX_MARGIN_MM = 2.54
SHEET_MARGIN_MM = 12.7
# Minimum content-bbox / usable-area ratio for a page_fill page. Below this the
# sheet is too empty (frame-fit over-padded or page_fill under-spread) — the
# engine fail-lounds rather than shipping the sparse A0 user rejected 4×.
MIN_SHEET_UTILIZATION = 0.40
# M4-2 (scale-coherence DD-6b): TRUE-INK density floor. The old MIN_SHEET_UTILIZATION
# measured the enclosing content AABB (gameable by a long-label chain / one tall
# part). The ink floor measures the SUM of real drawn box areas (component bboxes +
# net-label boxes) ⊆ AABB, so it is strictly smaller and its floor must be lower or
# every page false-fails. 0.18 re-expresses the 0.40-AABB intent for the tighter
# ink measure (a well-packed CCM page inks 25-45% of usable; the rejected sparse-A0
# case inks < 10%). page_fill-only; non-CCM callers never reach this gate.
MIN_INK_DENSITY = 0.18
# Legacy unscaled pin-name/number/property text height (KiCad default 1.27 mm);
# ×page_scale gives the rendered label text height for the true-ink term.
_BASE_TEXT_HEIGHT_MM = 1.27
# Half-extent margin added to every part's bbox ONLY for _page_fill_distribute's
# edge-to-edge gap math. A part's symbol bbox does not include its emitted power-
# port zone (stub + PWR_FLAG glyph reaching OUTSIDE the body). page-fill spreads
# by body edges only, so a neighbour with body gap>0 could still sweep its port
# zone into an adjacent body (guard C: POWER_PORT_INSIDE_SYMBOL_BODY). Reserving
# this clearance on each side keeps the port zone out of every neighbour.
# v11 review bug 3 (「主圖和副圖中間仍保持不合理的超大空間」): the former 63.5 mm
# reserved "2.54 stub + 8×7.62 stagger" — but the staggered power-port lane was
# ABOLISHED by DD-22/23 全直線化 (ports now run a SINGLE straight stub, no tier /
# jog). The real outward reach is _STUB_MM(2.54) + one PWR_FLAG hop _STUB_MM(2.54)
# = 5.08 mm graphic; the 63.5 mm floor is a dead-lane zombie that ballooned the
# main↔peripheral gutter to ~68 mm (measured 02_mcu U1↔crystal). Closed-form
# clearance = 2×_STUB_MM (both parts' straight ports facing) + one grid clear gap.
# label-name reach is handled by the label-aware gap math elsewhere, not here.
PORT_CLEARANCE_MM = 12.7  # DD-22/23 straight-port: 2×2.54 stub + 7.62 clear gap


# ---------------------------------------------------------------------------
# DD-10 (A7): page density budget. Text-overlap's治本 layer is placement density —
# per-page net count / component count / per-symbol pin count decide the text
# space available; the emit-layer anti-overlap has no solution past a critical
# density (same engine: aiguard 04_wireless page v=3 vs product single-page
# v=231, the sole difference being density). compose_schematic front-lints these
# and fail-fasts (DENSITY_BUDGET_EXCEEDED, suggest splitting pages) before
# placement.
#
# Thresholds calibrated on aiguard CCM实測 (BR_20260706_schematic_text_render_qa_gap):
#   - 04_wireless page (PASS, qa v=3):   ~12 nets / 8 components / typical symbol pins
#   - 03_memory page (FAIL, qa v=18):    ~24 nets / 10 components / one 60+ pin symbol
# The defaults sit in the PASS/FAIL midband (not fitted to either endpoint, R5)
# and are per-key overridable (explicit, never silent).
DENSITY_BUDGET_DEFAULTS: dict[str, int] = {
    "max_nets_per_page": 20,        # 04_wireless≈12 PASS … 03_memory≈24 FAIL → 20 midband
    "max_components_per_page": 15,  # 04_wireless≈8 PASS … 03_memory≈10 FAIL → 15 headroom
    "max_pins_per_symbol": 64,      # 03_memory FAIL page carried a single 60+ pin symbol
}


def _lint_density_budget(
    budget: dict | None,
    parsed: list[dict],
    nets: list,
    symbol_dirs,
    bbox_cache: dict,
) -> None:
    """DD-10 fail-fast density lint (runs BEFORE placement).

    budget is None  → lint disabled (zero-break default).
    budget is {}    → use DENSITY_BUDGET_DEFAULTS verbatim.
    budget is dict  → per-key override on top of the defaults.

    Raises ValueError("DENSITY_BUDGET_EXCEEDED: ...") enumerating every exceeded
    metric (measured vs threshold) plus the remedy (split pages / raise budget via
    explicit override). Per-symbol pin count is derived from load_symbol pins;
    a symbol that fails to load is skipped for the pin metric (fail-visible via
    the existing bbox warnings path — the lint never fabricates a pin count).
    """
    if budget is None:
        return
    thresholds = dict(DENSITY_BUDGET_DEFAULTS)
    thresholds.update(budget)

    n_nets = len(nets)
    n_components = len(parsed)

    # Per-symbol pin count: reuse load_symbol; count endpoints. Cache is shared
    # with _estimate_bbox so a symbol is parsed once.
    worst_pin_ref = None
    worst_pin_count = 0
    for c in parsed:
        try:
            _definition, pins = load_symbol(c["symbol"], symbol_dirs)
        except (FileNotFoundError, KeyError):
            continue
        pin_count = len(pins)
        if pin_count > worst_pin_count:
            worst_pin_count = pin_count
            worst_pin_ref = c["ref"]

    violations: list[str] = []
    if n_nets > thresholds["max_nets_per_page"]:
        violations.append(
            f"nets/page: {n_nets} > {thresholds['max_nets_per_page']}")
    if n_components > thresholds["max_components_per_page"]:
        violations.append(
            f"components/page: {n_components} > {thresholds['max_components_per_page']}")
    if worst_pin_count > thresholds["max_pins_per_symbol"]:
        violations.append(
            f"pins/symbol: {worst_pin_count} ({worst_pin_ref}) > "
            f"{thresholds['max_pins_per_symbol']}")

    if violations:
        raise ValueError(
            "DENSITY_BUDGET_EXCEEDED: page density exceeds the budget "
            "(text-overlap is unsolvable at the emit layer past this density — "
            "DD-10). Exceeded: " + "; ".join(violations) + ". Remedy: split the "
            "subsystem across multiple sheets/pages, OR raise the budget with an "
            "explicit density_budget override (e.g. density_budget="
            "{\"max_nets_per_page\": <higher>}).")


def _cluster_gutter_mm(component_count: int, scale: float = 1.0) -> float:
    """Deterministic gutter ladder (T4): small designs get a tight gutter so
    sheet-fit stays readable; CLUSTER_GUTTER_MM remains the >50-part ceiling.

    scale (opt-in, default 1.0 → byte-identical): multiplies the ladder value so
    a caller that already spreads pins via a large in-symbol pin_pitch (CCM
    per-page U1 @11.43 mm) can compact the inter-part gutter without touching the
    global constants that every other board depends on."""
    if component_count <= 20:
        return 12.0 * scale
    if component_count <= 50:
        return 20.0 * scale
    return CLUSTER_GUTTER_MM * scale


@dataclass(slots=True)
class Cluster:
    cluster_id: str
    source: str  # "declared" | "net-degree"
    members: list[str]
    center_x: float = 0.0
    center_y: float = 0.0

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "source": self.source,
            "members": list(self.members),
            "center_mm": {"x": round(self.center_x, 4), "y": round(self.center_y, 4)},
        }


@dataclass(slots=True)
class RouteStats:
    wired_nets: int = 0
    labelled_nets: int = 0
    junctions: int = 0
    label_fallback_reasons: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "wired_nets": self.wired_nets,
            "labelled_nets": self.labelled_nets,
            "junctions": self.junctions,
            "label_fallback_reasons": list(self.label_fallback_reasons),
        }


@dataclass(slots=True)
class SheetFit:
    selected_paper: str = "A4"
    content_w: float = 0.0
    content_h: float = 0.0
    overflow: bool = False
    # DD-30 pad-semantics: the RAW extent terms the ink-inclusive formula is built
    # from, exposed so an upstream sizer rebuilds extent with the SAME formula
    # instead of re-scaling the baked content_w/h blob (the double-count defect).
    #   span_w/h  = centre-to-centre AABB (max_centre − min_centre) at this compose
    #               scale — contains NO pad/label/prop; it is pure centre span.
    #   pad_w/h   = HALF the largest component bbox (max_bbox/2) at this compose
    #               scale — ONE edge's centre→edge reach. The full extent needs it
    #               on BOTH opposing edges → add 2×pad, never 1×.
    span_w: float = 0.0
    span_h: float = 0.0
    pad_w: float = 0.0
    pad_h: float = 0.0
    # DD-31 per-edge true-extent: ink overhang past the centre-span on each edge
    #   ext_l/r = how far the leftmost/rightmost part's OWN half-bbox hangs past
    #             min_centre / max_centre (NOT the global max-bbox/2). content_w =
    #             span_w + ext_l + ext_r + 2*reach reproduces the true drawn AABB.
    #   ext_t/b = same on the H axis. These supersede pad_w/h for content sizing and
    #             block-origin centring; pad_w/h retained for legacy diagnostics only.
    ext_l: float = 0.0
    ext_r: float = 0.0
    ext_t: float = 0.0
    ext_b: float = 0.0

    def to_dict(self) -> dict:
        return {
            "selected_paper": self.selected_paper,
            "content_bbox_mm": {"w": round(self.content_w, 4), "h": round(self.content_h, 4)},
            "overflow": self.overflow,
        }


@dataclass(slots=True)
class ComposeResult:  # noqa: D101 — fidelity field appended for BR1 (2026-07-06)
    emit: SchematicEmitResult
    validation: object | None = None
    placed: int = 0
    nets: int = 0
    warnings: list[str] = field(default_factory=list)
    style: str = "netlist"
    clusters: list[Cluster] = field(default_factory=list)
    route_stats: RouteStats | None = None
    sheet_fit: SheetFit | None = None
    ink_metrics: dict | None = None
    ledger: "OccupancyLedger | None" = None  # M4-5 (TV-8): shared occupancy ledger (draftsman only) for geometry single-truth对帐
    fidelity: object | None = None  # BR1: FidelityReport when fidelity=True
    # BR_20260708: drawn wire segments crossing a NON-host symbol body (keep-out).
    # Empty == every drawn wire clears all symbol bodies (the BR geometry check).
    wire_body_intrusions: list[dict] = field(default_factory=list)
    # BR_20260723d: active-IC symbols that failed to load (fail-visible). Empty ==
    # every active IC resolved its symbol. Non-empty is a blocking defect (compose
    # raises SymbolLoadError before returning a "looks complete" result) — never a
    # silent empty-box on a missing multi-pin IC symbol.
    symbol_load_failures: list[dict] = field(default_factory=list)
    # BR_20260802: WHICH bytes produced these numbers. Without it, "composed the
    # file you just wrote" and "composed a copy you replaced two minutes ago"
    # return the same success shape, and a measurement cannot be attributed to a
    # version after the fact — which is how an erc_errors count had to be thrown
    # away entirely rather than merely re-checked. Always populated.
    inputs: dict = field(default_factory=dict)


class SymbolLoadError(RuntimeError):
    """BR_20260723d: an ACTIVE IC's symbol failed to load — fail-loud.

    A missing/mismatched symbol library for a multi-pin active IC (e.g. lib name
    `stm32n657_full` when the file on disk is `stm32_pruned.kicad_sym`) previously
    degraded to a silent empty-box: the IC rendered pinless, every net on its pins
    lost its route, and compose still returned a "looks complete" schematic. That
    is a No-silent-fallback 天條 violation. This error carries the full failure
    list so the caller sees exactly which active IC symbols could not be resolved.
    Passive (<=2-pin R/C/L) symbol misses are NOT this error — they legitimately
    degrade to a small placeholder box (BR NOT-bug boundary).
    """

    def __init__(self, failures: list[dict]):
        self.failures = failures
        refs = ", ".join(f"{f['ref']}({f['symbol']})" for f in failures)
        super().__init__(
            f"active IC symbol(s) failed to load: {refs}. "
            f"compose refuses to emit a schematic with pinless active-IC empty boxes "
            f"(No-silent-fallback). See symbol_load_failures for per-ref reason + "
            f"the symbol libraries actually present on the search path."
        )


class InputProvenanceMismatch(RuntimeError):
    """BR_20260802: a declared expect_sha did not match the bytes on disk.

    The optional half of the provenance fix, and the load-bearing one: reporting
    which bytes were read still leaves the CHECK to the caller's discipline, and
    a check that depends on someone remembering is one that eventually is not
    made. Declaring the expected digest moves it into the tool, where a stale
    file becomes a refusal instead of a plausible-looking success.
    """

    def __init__(self, mismatches: list[dict]):
        self.mismatches = mismatches
        lines = "; ".join(
            f"{m['path']}: expected {m['expected'][:12]}… but read {m['actual'][:12]}…"
            f" ({m['bytes']} bytes, mtime {m['mtime']})"
            for m in mismatches)
        super().__init__(
            f"COMPOSE_INPUT_SHA_MISMATCH: {len(mismatches)} declared input(s) do not "
            f"match the bytes on disk: {lines}. Refusing to compose — the result "
            f"would be structurally valid and describe a version you did not mean, "
            f"which is indistinguishable after the fact from one you did.")


def _file_provenance(path) -> dict:
    """path + sha256 + mtime + size for one file actually opened.

    Reads the bytes rather than trusting mtime: on a network/FUSE mount an mtime
    can be served from a write-back cache while the content differs, which is the
    exact failure mode (a stale container copy) this record exists to expose.
    """
    p = Path(path)
    try:
        data = p.read_bytes()
        st = p.stat()
        return {"path": str(p), "sha256": hashlib.sha256(data).hexdigest(),
                "mtime": int(st.st_mtime), "bytes": st.st_size}
    except OSError as exc:
        # Never silently omit a file we could not measure: an absent entry would
        # read as "this input was not used", conflating unread with unreadable.
        return {"path": str(p), "sha256": None, "mtime": None, "bytes": None,
                "error": f"{type(exc).__name__}: {exc}"}


# BR_20260802 (round 2, one level up): WHICH ENGINE produced the numbers.
# `inputs` answers "which bytes were read"; it does not answer "which bytes did
# the reading". Those are different questions and the second one bit harder:
# this package is bind-mounted into the server container from a host working
# tree, so the running engine tracks uncommitted edits, not any commit. Results
# measured against such an engine stop being reproducible the moment anyone runs
# `git checkout` / `reset --hard` on that tree -- and nothing in the response
# lets you find out afterwards which engine you had. Recording the module's own
# bytes costs one hash of a path Python already resolved into `__file__`.
#
# Deliberately NOT shelling out to git for a commit id: the container has no
# repository, so `git describe` would fail there and succeed on a host, making
# the field's presence depend on where it ran. A content hash is available
# everywhere and is what actually identifies the code.
#
# The comparison command matters and is easy to get wrong: `git hash-object` is
# NOT this digest. It is SHA-1 over `blob <len>\0<content>`, so it can never
# equal a sha256 of the same bytes -- an instruction to compare them would fail
# every time and read as "the engine is wrong" rather than "the recipe is".
# The digest that does compare is `git show <rev>:<path> | sha256sum`.
_ENGINE_MODULE_FILES = ("composer.py", "kicad_emit.py")


def _engine_provenance() -> dict:
    """Provenance of the modules doing the composing, not of what they read."""
    here = Path(__file__).resolve().parent
    mods = [_file_provenance(here / name) for name in _ENGINE_MODULE_FILES]
    unreadable = [m["path"] for m in mods if m.get("sha256") is None]
    return {
        "modules": mods,
        # An engine we could not hash must not read as an engine we verified.
        "status": "measured" if not unreadable else "incomplete",
        "unreadable": unreadable,
        "note": ("sha256 of the running engine's own source. To learn whether "
                 "this run used committed code, compare against "
                 "`git show <rev>:<path> | sha256sum` -- NOT `git hash-object`, "
                 "which is SHA-1 over a blob header and never matches. No commit "
                 "id is reported: the container has no repository, and a field "
                 "present only on some hosts is worse than no field."),
    }


class EmptySpecError(ValueError):
    """BR_20260730b N2: the spec declares no components — refuse the empty deliverable.

    A spec whose `components` key is missing or empty produced a 213-byte
    schematic with zero symbols, which FOUR gates then independently blessed:
    the draftsman gate PASSed (rects=0 — nothing cannot overlap), ERC reported 0
    violations (nothing cannot be miswired), validation said "validated", and the
    call returned ok:true. Each gate was internally correct and collectively they
    certified nothing, because they all answered questions about a drawing that
    does not exist.

    The recorded trigger was `{"__spec_file__": "/path/spec.json"}` — a caller
    reasonably guessing that `spec` accepts a file reference, since the MCP
    schema declares only {"type": "object"}. So this error prints the keys it
    RECEIVED beside the keys compose actually reads: the fault is always a
    key-name mismatch, and showing both sides answers it in one line rather
    than sending the caller into composer source.
    """

    #: spec keys compose_schematic actually consumes. This tuple is a hand-copy of
    #: the real spec.get()/spec[...] call sites, so an AST-derived test asserts it
    #: both ways (nothing read-but-unadvertised, nothing advertised-but-ignored).
    #: It earned that test immediately: the first version of this tuple omitted
    #: l6_avoidance, because the grep used to enumerate the keys was written
    #: [a-z_]* and silently skipped the one key containing a digit — the same
    #: duplicate-fact drift (V4-c) that this list represents.
    KNOWN_KEYS = ("components", "nets", "nc", "all_label", "l6_avoidance")

    def __init__(self, spec: dict):
        got = sorted(spec) if isinstance(spec, dict) else []
        self.spec_keys = got
        unknown = [k for k in got if k not in self.KNOWN_KEYS]
        detail = "spec is empty (no keys at all)" if not got else f"spec keys received: {got}"
        hint = (
            f" None of {unknown} is a key compose reads — pass the spec CONTENT "
            f"inline, not a reference to it." if unknown else ""
        )
        super().__init__(
            "COMPOSE_EMPTY_SPEC: spec declares no components, so the schematic "
            f"would be empty. {detail}; compose reads "
            f"{list(self.KNOWN_KEYS)}.{hint} Refusing rather than emitting a "
            "symbol-less sheet: an empty drawing passes EVERY downstream gate "
            "(0 overlaps, 0 ERC violations, status=validated, ok:true) because "
            "each one is asking about a drawing that is not there — four green "
            "lights over nothing."
        )


class SymbolDirsEncodingError(TypeError):
    """BR_20260730b N1: `symbol_dirs` arrived as a JSON-ENCODED list, not a path.

    An MCP client filling an argument whose inputSchema declares NO type may
    serialise an array to text, so `["/work/symbols"]` reaches compose as the
    string '["/work/symbols"]'. Nothing downstream can tell that apart from a
    directory name: the str branch of the symbol_dirs merge wraps it in a list,
    every custom library fails to resolve, and only the KiCad stdlib still
    loads. The result LOOKS mostly healthy (stock passives place, nets count),
    which is why a whole compose run can be read as "my symbols are broken"
    when the real fault is one argument's type at the facade boundary.

    Raised instead of silently decoding: auto-decoding would be a fallback that
    repairs the caller's bug invisibly and would hide the schema defect that
    produced it (No-silent-fallback 天條). The message carries BOTH the raw
    string and the decoded list so the caller can see exactly what to pass.
    """

    def __init__(self, raw: str, decoded: list):
        self.raw = raw
        self.decoded = decoded
        super().__init__(
            f"symbol_dirs is a JSON-encoded list, not a directory: {raw!r}. "
            f"It decodes to {decoded!r} — pass THAT as a real array (or a single "
            f"bare string for one dir), not as text. A JSON-text 'path' can never "
            f"exist, so every custom symbol library would fail to resolve while "
            f"the KiCad stdlib still loaded, making the run look partly healthy. "
            f"If you are calling through the MCP facade, this usually means the "
            f"tool's inputSchema did not declare symbol_dirs as an array."
        )


def _auto_place(index: int, columns: int = 4, dx: float = 45.0, dy: float = 45.0, x0: float = 35.0, y0: float = 35.0) -> tuple[float, float]:
    return (round(x0 + (index % columns) * dx, 3), round(y0 + (index // columns) * dy, 3))


def _parse_node(node: str) -> tuple[str, str]:
    ref, _, pin = node.partition(".")
    return ref.strip(), pin.strip()


# ---------------------------------------------------------------------------
# DD-4: symbol bbox estimation (pin-extent proxy + margin). Load failure is
# fail-visible (returns None) — the caller drops the component from the
# force-directed model instead of injecting a default size (errors.md E-DRAFT-001).
# ---------------------------------------------------------------------------
_TEXT_CH_MM = 1.27          # rendered ref/value/label text height (matches emit)
# A ref+value stack ("C1" / "100nF") sits at component.y ± 1.27 and each string
# is ~1.27 mm tall; its widest string (value like "100nF") runs several chars.
# The placement bbox used to be pin-extent only, so a 2-pin cap's ~2.5 mm pin
# box ignored its wider "C1 100nF" text — caps packed pin-to-pin visually
# collided their text. Pad every bbox by the text envelope so placement/packing
# reserves room for the labels too (治本 for the C1~C5 text-overlap symptom).
_TEXT_PAD_W_MM = 10.16      # 8 chars × ~1.27 mm — ref/value string width reserve
_TEXT_PAD_H_MM = 2 * _TEXT_CH_MM + 2.54  # ref above + value below + gap


def _is_per_page_symbol(lib_id: str) -> bool:
    """True for a symbol ALREADY emitted at page_scale by build_u1_variant.

    v11 bug 2: the per-page U1 variant carries a lib_id `u1_<slug>[_bN]:...`
    (gen_ccm_pages.build_u1_variant file_stem = f"u1_{slug}..."). Its in-symbol
    pin pitch is ALREADY ×page_scale (measured y-pitch 6.35 mm @ scale 2.5), so
    scaling it again in load_symbol would DOUBLE it. Stored/system peripherals
    (Device:*, power_*, Conn_*, PWR_FLAG, ldo_*/buck_*/psram, aiguard_U*) carry
    no `u1_` library prefix and DO need scaling to match the main density.
    """
    library = lib_id.partition(":")[0]
    return library.startswith("u1_")


def _estimate_bbox(lib_id: str, symbol_dir, _cache: dict, page_scale: float = 1.0,
                   page_floor: float = 0.0, _npitch_cache: dict | None = None) -> tuple[float, float] | None:
    """Estimate (width, height) in mm — pin endpoints ∪ ref/value text envelope.

    Effective bbox = pin graphic extent + margin, then widened/heightened by the
    ref/value text envelope (BR: text-overlap 治本 — placement must reserve room
    for the labels, not just the pin graphics). Returns None when the symbol
    cannot be loaded — caller treats as fail-visible (warning + skip from
    refinement), never substitutes a default.

    page_scale (v11 bug 2): a stored peripheral symbol's pin geometry is scaled
    so its bbox reflects the SAME per-page density as the main symbol. The U1
    variant is exempt (already ×page_scale). The cache key includes the scale so
    two pages at different scales never collide.

    page_floor (DD-29/30/31): when >0, a stored ≥4-pin symbol's scale is lifted to
    max(page_scale, page_floor / native_pitch) via the SAME _vendor_sym_scale helper
    the emitter uses — so the placement bbox and the emitted geometry stay
    same-source (a bbox computed at page_scale while the symbol emits larger would
    under-reserve and collide). page_floor==0.0 keeps the legacy page_scale bbox.
    """
    if _is_per_page_symbol(lib_id):
        _sym_scale = 1.0
    elif page_floor > 0.0:
        _npitch, _ncount = _native_pitch_and_count(lib_id, symbol_dir, _npitch_cache)
        _sym_scale = _vendor_sym_scale(page_scale, _npitch, page_floor, _ncount)
    else:
        _sym_scale = page_scale
    _key = (lib_id, _sym_scale)
    if _key in _cache:
        return _cache[_key]
    try:
        _definition, pins = load_symbol(lib_id, symbol_dir, page_scale=_sym_scale)
    except (FileNotFoundError, KeyError):
        _cache[_key] = None
        return None
    if not pins:
        # A symbol with no parsable pins gives no extent proxy; treat as a small
        # square (still text-padded so its ref/value has room) so two such
        # symbols still repel, deterministically.
        side = 2 * BBOX_MARGIN_MM
        bbox = (max(side, _TEXT_PAD_W_MM), max(side, _TEXT_PAD_H_MM))
        _cache[lib_id] = bbox
        return bbox
    xs = [p[0] for p in pins.values()]
    ys = [p[1] for p in pins.values()]
    w = (max(xs) - min(xs)) + 2 * BBOX_MARGIN_MM
    h = (max(ys) - min(ys)) + 2 * BBOX_MARGIN_MM
    # Reserve the ref/value text envelope as a MAX (not additive): a small symbol
    # (a 2-pin cap ~2.5 mm wide) must still fit "C1"/"100nF", so its bbox grows to
    # the text envelope; a large symbol (U1/UB1) whose graphic extent already
    # dwarfs the label is left EXACTLY as-is (byte-identical to the pin-extent
    # bbox). An additive pad (h += const) perturbed EVERY part including big ones,
    # shifting neighbours' power ports into a large body (guard C regression) — the
    # max form confines the change to parts that actually need label room.
    w = max(w, _TEXT_PAD_W_MM)
    h = max(h, _TEXT_PAD_H_MM)
    bbox = (max(w, 2 * BBOX_MARGIN_MM), max(h, 2 * BBOX_MARGIN_MM))
    _cache[lib_id] = bbox
    return bbox


# ---------------------------------------------------------------------------
# DD-2 stage A: clustering. Declared `group` wins; otherwise net-degree
# connected-components with deterministic hub degree-capping (R4 / E-DRAFT-003).
# ---------------------------------------------------------------------------
def _cluster(refs: list[str], groups: dict[str, str], adjacency: dict[str, set[str]], warnings: list[str]) -> list[Cluster]:
    """Partition component refs into clusters (deterministic, no RNG).

    refs:      ordered component refs (spec order; ties broken by this order).
    groups:    ref → declared group label (absent ref ⇒ no declared group).
    adjacency: ref → set of refs sharing at least one net.
    """
    declared = {ref: groups[ref] for ref in refs if ref in groups and groups[ref]}
    if declared:
        # Declared-group clustering (explicit wins). Refs without a declared
        # group form their own singleton auto cluster so nothing is dropped.
        by_group: dict[str, list[str]] = {}
        order: list[str] = []
        for ref in refs:
            label = declared.get(ref)
            if label is None:
                label = f"auto-{ref}"
            if label not in by_group:
                by_group[label] = []
                order.append(label)
            by_group[label].append(ref)
        return [
            Cluster(cluster_id=label, source="declared", members=by_group[label])
            for label in order
        ]

    # net-degree clustering: connected components over the net adjacency graph.
    # Hub degree-capping (R4): if one node connects (almost) everything, the
    # naive connected-component would collapse to a single cluster — split the
    # hub's neighbours into per-neighbour buckets so we still get structure.
    ref_index = {ref: i for i, ref in enumerate(refs)}
    visited: set[str] = set()
    components: list[list[str]] = []
    for ref in refs:
        if ref in visited:
            continue
        stack = [ref]
        comp: list[str] = []
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            comp.append(node)
            for nb in sorted(adjacency.get(node, ()), key=lambda r: ref_index.get(r, 1 << 30)):
                if nb in ref_index and nb not in visited:
                    stack.append(nb)
        comp.sort(key=lambda r: ref_index[r])
        components.append(comp)

    # Degenerate hub detection (E-DRAFT-003): single component containing all
    # refs AND a hub whose degree ≥ (n-1) (connects everything else).
    if len(components) == 1 and len(refs) >= 3:
        degrees = {ref: len(adjacency.get(ref, ())) for ref in refs}
        hub = max(refs, key=lambda r: (degrees[r], -ref_index[r]))
        if degrees[hub] >= len(refs) - 1:
            warnings.append(
                f"net-degree clustering produced a single dominant cluster "
                f"(hub degree={degrees[hub]}); consider declaring groups"
            )
            # degree-cap split: hub gets its own cluster; each remaining ref is
            # bucketed deterministically into pairs around the hub.
            others = [r for r in refs if r != hub]
            clusters = [Cluster(cluster_id="auto-hub", source="net-degree", members=[hub])]
            bucket_size = max(2, (len(others) + 2) // 3)
            for i in range(0, len(others), bucket_size):
                members = others[i : i + bucket_size]
                clusters.append(Cluster(cluster_id=f"auto-{len(clusters)}", source="net-degree", members=members))
            return clusters

    return [
        Cluster(cluster_id=f"auto-{i}", source="net-degree", members=comp)
        for i, comp in enumerate(components)
    ]


# ---------------------------------------------------------------------------
# DD-2 stage B: deterministic force-directed refinement within a cluster.
# No RNG: initial layout is a ref-sorted grid; fixed iterations/step.
# ---------------------------------------------------------------------------
def _refine(members: list[str], adjacency: dict[str, set[str]], bboxes: dict[str, tuple[float, float] | None], gutter_scale: float = 1.0) -> dict[str, tuple[float, float]]:
    """Return deterministic local (x, y) offsets per member around (0, 0).

    Spring (shared-net attraction) + repulsion (overlap avoidance). Members
    whose bbox is None (symbol load failed) are excluded from the model
    (fail-visible) but still placed on the deterministic grid.

    gutter_scale (opt-in, default 1.0 → byte-identical): scales the neighbour
    separation `k`. `k` is (largest member bbox + gutter); when one member is a
    huge symbol (CCM per-page U1 at pin_pitch=11.43), `k` inflates every part's
    spacing to that symbol's extent, scattering tiny decoupling caps. A caller
    that wants a compact page passes gutter_scale<1 to tighten the layout while
    the global engine defaults stay untouched for every other board.
    """
    if not members:
        return {}
    # Deterministic initial grid: ref-sorted, square-ish. Spacing = the target
    # separation `k` (largest member bbox + gutter) so the layout starts roughly
    # to scale instead of at a fixed 1-inch pitch that the forces must undo.
    ordered = sorted(members)
    dims = [max(bboxes[r]) for r in ordered if bboxes.get(r) is not None]
    k = ((max(dims) if dims else 2 * BBOX_MARGIN_MM) + _cluster_gutter_mm(len(ordered))) * gutter_scale  # desired neighbour spacing
    cols = max(1, int(len(ordered) ** 0.5 + 0.9999))
    pos: dict[str, list[float]] = {}
    for i, ref in enumerate(ordered):
        pos[ref] = [float((i % cols) * k), float((i // cols) * k)]

    active = [r for r in ordered if bboxes.get(r) is not None]
    if len(active) < 2:
        return {r: (pos[r][0], pos[r][1]) for r in ordered}

    # Fruchterman-Reingold with a cooling schedule + per-iteration step clamp. The
    # previous loop had no cooling/clamp + a large absolute repulsion constant, so
    # small parts flew apart to a ~1m span (→ oversized sheet, sparse fill). FR with
    # k-scaled forces and a decaying max-step converges to ~k spacing. Deterministic
    # (fixed init grid + fixed schedule; no RNG) so it stays regression-stable.
    member_set = set(active)
    temp = k * 2.0               # initial max displacement per iteration
    cool = (k * 2.0 - k * 0.05) / max(1, PLACEMENT_ITERATIONS)
    k2 = k * k
    for _ in range(PLACEMENT_ITERATIONS):
        disp: dict[str, list[float]] = {r: [0.0, 0.0] for r in active}
        # Repulsion fr = k^2 / d between every active pair (along the unit vector).
        for i, a in enumerate(active):
            for b in active[i + 1 :]:
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                dist = (dx * dx + dy * dy) ** 0.5
                if dist < 1e-6:
                    dx = (1.0 if a < b else -1.0)
                    dy = 0.0
                    dist = 1.0
                force = k2 / dist
                ux, uy = dx / dist, dy / dist
                disp[a][0] += ux * force
                disp[a][1] += uy * force
                disp[b][0] -= ux * force
                disp[b][1] -= uy * force
        # Attraction fa = d^2 / k along shared-net edges (within this cluster).
        for a in active:
            for b in sorted(adjacency.get(a, ())):
                if b in member_set and a < b:
                    dx = pos[b][0] - pos[a][0]
                    dy = pos[b][1] - pos[a][1]
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist < 1e-6:
                        continue
                    force = (dist * dist) / k
                    ux, uy = dx / dist, dy / dist
                    disp[a][0] += ux * force
                    disp[a][1] += uy * force
                    disp[b][0] -= ux * force
                    disp[b][1] -= uy * force
        # Gravity toward the cluster centroid. Without it, all-pairs repulsion has
        # nothing to contain it and sparsely-connected nodes escape to the periphery
        # (a ~1m span for a handful of small parts). Pulling each node toward the
        # barycenter bounds the layout so the sheet-fit picks a sane paper.
        cx = sum(pos[r][0] for r in active) / len(active)
        cy = sum(pos[r][1] for r in active) / len(active)
        for r in active:
            disp[r][0] += (cx - pos[r][0]) * GRAVITY_K
            disp[r][1] += (cy - pos[r][1]) * GRAVITY_K
        # Clamp each displacement to the current temperature, then cool.
        for r in active:
            dlen = (disp[r][0] ** 2 + disp[r][1] ** 2) ** 0.5
            if dlen > 1e-9:
                scale = min(dlen, temp) / dlen
                pos[r][0] += disp[r][0] * scale
                pos[r][1] += disp[r][1] * scale
        temp = max(temp - cool, k * 0.05)

    # Satellite snap (A2): a 2-terminal decoupling/oscillator part that shares a
    # net with exactly ONE cluster peer is a "satellite" of that peer. Force-
    # directed placement pulls it toward the cluster centroid (gravity), so it
    # drifts away from the device it decouples and reads as scattered. After FR
    # converges, snap each satellite to a fixed offset beside its host so it sits
    # visually adjacent. Deterministic (ref-sorted, fixed offset); hosts are not
    # themselves satellites, so this never chains.
    host_of: dict[str, str] = {}
    for r in ordered:
        peers = [n for n in adjacency.get(r, ()) if n in member_set and n != r]
        bb = bboxes.get(r)
        is_small = bb is not None and max(bb) <= (2 * BBOX_MARGIN_MM + 5.0)
        if len(peers) == 1 and is_small and peers[0] in pos:
            host_of[r] = peers[0]
    # break any accidental mutual pairing: a host that is itself a satellite of
    # its own satellite must not be snapped (keep the larger/earlier ref as host).
    for sat in sorted(host_of):
        host = host_of[sat]
        if host in host_of and host_of[host] == sat:
            # deterministic tie-break: the ref sorting first stays the host.
            if sat < host:
                host_of.pop(host, None)
            else:
                host_of.pop(sat, None)
    SAT_DX = k * 0.6
    for sat in sorted(host_of):
        host = host_of[sat]
        if host in pos and sat in pos:
            pos[sat] = [pos[host][0] + SAT_DX, pos[host][1]]

    # Deterministic power-port de-overlap (guard C治本). FR converges to ~k body
    # spacing, but k is derived from the symbol bbox ONLY — it does NOT model the
    # emitted power-port zone (stub + stagger tiers reaching PORT_CLEARANCE_MM
    # OUTSIDE the body). With a tight gutter_scale two big parts can settle body-
    # to-body close enough that one part's top/bottom power-port row lands inside
    # the other's body (POWER_PORT_INSIDE_SYMBOL_BODY). After FR + satellite snap,
    # push apart any pair whose PORT_CLEARANCE-inflated AABBs still overlap, along
    # the axis of least penetration, splitting the push so the layout stays centred.
    # Only ever INCREASES separation of already-too-close parts; deterministic
    # (ref-sorted pairs, fixed arithmetic, no RNG); satellites ride their host by
    # keeping their post-snap offset. Runs a few sweeps to settle chained pushes.
    big_active = [r for r in ordered if bboxes.get(r) is not None
                  and max(bboxes[r]) > (2 * BBOX_MARGIN_MM + 5.0)]
    if len(big_active) >= 2:
        pad = PORT_CLEARANCE_MM
        for _sweep in range(8):
            moved = False
            for i, a in enumerate(big_active):
                aw, ah = bboxes[a]
                for b in big_active[i + 1:]:
                    bw, bh = bboxes[b]
                    dx = pos[b][0] - pos[a][0]
                    dy = pos[b][1] - pos[a][1]
                    # required centre separation so neither body enters the other's
                    # port zone: half-widths + one PORT_CLEARANCE border (once; the
                    # zone belongs to whichever part owns the ports on that edge).
                    need_x = (aw + bw) / 2.0 + pad
                    need_y = (ah + bh) / 2.0 + pad
                    overlap_x = need_x - abs(dx)
                    overlap_y = need_y - abs(dy)
                    if overlap_x <= 0 or overlap_y <= 0:
                        continue  # clear on at least one axis → no port intrusion
                    # push along the axis of LEAST penetration (smallest displacement).
                    if overlap_x <= overlap_y:
                        sgn = 1.0 if dx >= 0 else -1.0
                        pos[a][0] -= sgn * overlap_x / 2.0
                        pos[b][0] += sgn * overlap_x / 2.0
                    else:
                        sgn = 1.0 if dy >= 0 else -1.0
                        pos[a][1] -= sgn * overlap_y / 2.0
                        pos[b][1] += sgn * overlap_y / 2.0
                    moved = True
            if not moved:
                break

    return {r: (pos[r][0], pos[r][1]) for r in ordered}


def _aabb_overlaps(a_pos: tuple[float, float], a_box: tuple[float, float], b_pos: tuple[float, float], b_box: tuple[float, float]) -> bool:
    ax, ay = a_pos
    bx, by = b_pos
    aw, ah = a_box
    bw, bh = b_box
    return (
        abs(ax - bx) * 2 < (aw + bw)
        and abs(ay - by) * 2 < (ah + bh)
    )


def _resolve_overlaps(
    abs_pos: dict[str, tuple[float, float]],
    bboxes: dict[str, tuple[float, float] | None],
    warnings: list[str],
    gutter_scale: float = 1.0,
) -> dict[str, tuple[float, float]]:
    """Deterministic AABB de-overlap fallback (R1 / E-DRAFT-004).

    After force-directed convergence, if any two components still overlap, lay
    the whole set out on a deterministic gutter grid sized to per-row/column
    extents. Non-random; identical input ⇒ identical output.

    gutter_scale (opt-in, default 1.0 → byte-identical): scales ONLY the gutter
    added on top of the overlap-safety cell size. This is what makes the fallback
    honour a caller's compact request — previously the fallback re-gridded EVERY
    part at the largest-bbox cell (a huge per-page U1) and silently discarded the
    force-directed compaction, so tiny decoupling caps ended up spaced by U1's
    ~90 mm extent. The cell floor still uses per-axis max bbox so no two parts
    overlap; only the inter-cell whitespace shrinks.
    """
    refs = sorted(abs_pos)
    overlap_pairs = 0
    for i, a in enumerate(refs):
        ab = bboxes.get(a)
        if ab is None:
            continue
        for b in refs[i + 1 :]:
            bb = bboxes.get(b)
            if bb is None:
                continue
            if _aabb_overlaps(abs_pos[a], ab, abs_pos[b], bb):
                overlap_pairs += 1
    if overlap_pairs == 0:
        return abs_pos
    warnings.append(
        f"{overlap_pairs} component pairs still overlap after refinement; "
        f"applied deterministic gutter re-spacing"
    )
    sized = [r for r in refs if bboxes.get(r) is not None]
    unsized = [r for r in refs if bboxes.get(r) is None]
    gutter = _cluster_gutter_mm(len(refs)) * gutter_scale

    # Oversized-part isolation (the real whitespace治本). Gridding a huge part (a
    # per-page U1 whose body is ~90 mm tall at pin_pitch 11.43) together with tiny
    # parts forces the WHOLE grid onto U1's row/column extent — the tiny parts end
    # up scattered ~100 mm apart with 60%+ whitespace. Instead: pull every part
    # whose bbox is far larger than the median into its OWN column on the right,
    # stacked vertically; pack the remaining small parts in a dense square grid on
    # the left. Each side is overlap-safe (cells sized to that side's real max
    # bbox + gutter). Deterministic (ref-sorted, fixed threshold).
    def _area(r: str) -> float:
        bb = bboxes.get(r) or (2 * BBOX_MARGIN_MM, 2 * BBOX_MARGIN_MM)
        return bb[0] * bb[1]
    areas = sorted(_area(r) for r in sized)
    median_area = areas[len(areas) // 2] if areas else 4 * BBOX_MARGIN_MM * BBOX_MARGIN_MM
    big = [r for r in sized if _area(r) >= max(median_area * 6.0, 1.0)]
    small = [r for r in sized if r not in set(big)] + unsized

    out: dict[str, tuple[float, float]] = {}

    # left block: dense square grid of the small parts, per-column/row sized.
    cols = max(1, int(len(small) ** 0.5 + 0.9999)) if small else 1
    col_w: dict[int, float] = {}
    row_h: dict[int, float] = {}
    for i, ref in enumerate(small):
        bb = bboxes.get(ref) or (2 * BBOX_MARGIN_MM, 2 * BBOX_MARGIN_MM)
        c, r = i % cols, i // cols
        col_w[c] = max(col_w.get(c, 0.0), bb[0])
        row_h[r] = max(row_h.get(r, 0.0), bb[1])
    col_x: dict[int, float] = {}
    acc = 0.0
    for c in range(cols):
        col_x[c] = acc
        acc += col_w.get(c, 2 * BBOX_MARGIN_MM) + gutter
    left_w = acc
    row_y: dict[int, float] = {}
    acc = 0.0
    nrows = (len(small) + cols - 1) // cols if small else 0
    for r in range(nrows):
        row_y[r] = acc
        acc += row_h.get(r, 2 * BBOX_MARGIN_MM) + gutter
    left_h = acc
    for i, ref in enumerate(small):
        c, r = i % cols, i // cols
        out[ref] = (col_x[c], row_y[r])

    # right column: big parts stacked vertically beside the small-part block.
    big_x = left_w + gutter
    acc = 0.0
    for ref in sorted(big):
        bb = bboxes[ref]
        out[ref] = (big_x, acc)
        acc += bb[1] + gutter
    return out


# ---------------------------------------------------------------------------
# DD-12 (user directive: pages ~1/3 filled — "整頁縮到 50% 都不為過"). The
# force-directed field + overlap-gated de-overlap leave a topology of "a few big
# parts + their satellite small parts" SPARSE by construction: `_refine`'s
# neighbour spacing k is (largest-member bbox + gutter), so a per-page U1 (~90 mm
# body at pin_pitch 11.43) inflates EVERY cap's spacing to U1's extent, and
# `_resolve_overlaps`'s big/small isolation only fires WHEN parts already overlap
# (they don't after FR converges), so the compaction is silently skipped.
#
# `_macro_compact` is an opt-in, UNCONDITIONAL post-placement pass (not gated on
# overlap). It groups each "big" part (area ≥ median×BIG_AREA_RATIO) with its
# net-adjacent small "satellite" parts into ONE composite unit (the big body plus
# a satellite column to its right), then 2D shelf-packs those units + any leftover
# small parts into a near-square envelope. Shelf-packing (NOT single-column
# stacking) is the fix for the sparse "few big + satellites" topology: stacking
# macros vertically only lengthens one axis (a per-page U1 + 3 regulators became a
# tall strip → A2 grew to A1/A0), whereas shelf-packing fills both axes so the
# content bbox stays near-square and _fit_sheet picks a SMALLER paper.
# Deterministic (ref-sorted, height-descending shelves; no RNG). Electrical truth
# is untouched — only (x, y) change.
# ---------------------------------------------------------------------------
MACRO_BIG_AREA_RATIO = 6.0     # a part is "big" (macro anchor) if area ≥ median×this
MACRO_SAT_GUTTER_MM = 3.81     # gap between a big part and its satellite column
MACRO_INTER_GUTTER_MM = 10.16  # gap between packed units (both axes)


def _shelf_pack(
    items: list[tuple[str, float, float]],
    max_shelf_w: float,
    gutter: float,
) -> tuple[dict[str, tuple[float, float]], float, float]:
    """Deterministic height-descending shelf bin-packing (2D).

    items:       [(unit_id, w, h), ...] — each unit's bounding box (already
                 includes any satellite column width/height for a macro unit).
    max_shelf_w: a shelf wraps to a new row once adding the next unit would
                 exceed this width (the near-square target width).
    gutter:      inter-unit gap on both axes.
    Returns ({unit_id: (top_left_x, top_left_y)}, total_w, total_h). Coordinates
    are the unit's TOP-LEFT corner (caller converts to per-part centres).

    Deterministic: items are packed in the given order (caller sorts by height
    descending, ref-tiebroken); a shelf's height is its tallest member. No RNG.
    Overlap-free by construction (each unit occupies a disjoint [x,x+w]×[y,y+h]).
    """
    placed: dict[str, tuple[float, float]] = {}
    x = 0.0
    y = 0.0
    shelf_h = 0.0
    total_w = 0.0
    for uid, w, h in items:
        if x > 0.0 and x + w > max_shelf_w:
            # wrap to a new shelf.
            y += shelf_h + gutter
            x = 0.0
            shelf_h = 0.0
        placed[uid] = (x, y)
        x += w + gutter
        shelf_h = max(shelf_h, h)
        total_w = max(total_w, x - gutter)
    total_h = y + shelf_h
    return placed, total_w, total_h


def _macro_compact(
    abs_pos: dict[str, tuple[float, float]],
    bboxes: dict[str, tuple[float, float] | None],
    adjacency: dict[str, set[str]],
    warnings: list[str],
    gutter_scale: float = 1.0,
) -> dict[str, tuple[float, float]]:
    """Deterministic macro + 2D shelf bin-packing (DD-12 — opt-in whitespace治本).

    abs_pos:   post-refine absolute centres (ref → (x, y)).
    bboxes:    ref → (w, h) or None (symbol load failed — packed as a small square).
    adjacency: ref → set of net-sharing refs.
    Returns a NEW ref → (x, y) map (part CENTRES) that is tightly packed. Unsized
    parts (bbox None) get a small default square so nothing is dropped.

    NOT a de-overlap fallback: it always runs (when the caller opts in) and
    re-lays EVERY non-explicit part, discarding the sparse force-directed spread.
    Overlap-safety holds by construction (shelf-packed disjoint boxes).
    """
    refs = sorted(abs_pos)
    if not refs:
        return abs_pos

    def _bb(r: str) -> tuple[float, float]:
        return bboxes.get(r) or (2 * BBOX_MARGIN_MM, 2 * BBOX_MARGIN_MM)

    def _area(r: str) -> float:
        w, h = _bb(r)
        return w * h

    sat_gutter = MACRO_SAT_GUTTER_MM * gutter_scale
    inter_gutter = MACRO_INTER_GUTTER_MM * gutter_scale

    areas = sorted(_area(r) for r in refs)
    median_area = areas[len(areas) // 2] if areas else 4 * BBOX_MARGIN_MM * BBOX_MARGIN_MM
    big = [r for r in refs if _area(r) >= max(median_area * MACRO_BIG_AREA_RATIO, 1.0)]
    big_set = set(big)
    small = [r for r in refs if r not in big_set]

    # satellite assignment (RELAXED vs the first design): a small part is a
    # satellite of the LARGEST big part it shares a net with (≥1 big neighbour,
    # not exactly-one). Power nets (VSYS/GND) make a cap touch several big parts;
    # the exactly-one rule dropped every such cap to a separate grid. Picking the
    # largest-area big host is deterministic (area then ref tiebreak) and keeps a
    # decoupling cap beside the device it actually decouples.
    sat_of: dict[str, str] = {}
    for r in small:
        big_neighbours = [nb for nb in adjacency.get(r, ()) if nb in big_set]
        if big_neighbours:
            sat_of[r] = max(big_neighbours, key=lambda b: (_area(b), b))
    sats_by_host: dict[str, list[str]] = {b: [] for b in big}
    for s in sorted(sat_of):
        sats_by_host[sat_of[s]].append(s)

    # Build composite "units": each big part + its satellite column (to the right).
    # A unit's bbox is (big_w + sat_col_w, max(big_h, sat_col_h)). Leftover small
    # parts (no big host) are singleton units. Then 2D shelf-pack all units.
    # local_offsets[unit_id] = {ref: (dx, dy)} centre offsets from unit top-left.
    unit_bbox: dict[str, tuple[float, float]] = {}
    local_offsets: dict[str, dict[str, tuple[float, float]]] = {}

    # PORT_CLEARANCE_MM is reserved as a symmetric border around EVERY unit so a
    # part's emitted power-port zone (stub + stagger tiers reaching outside the
    # body bbox, which _bb does NOT model) cannot land inside a neighbouring unit's
    # body after shelf-packing (guard C: POWER_PORT_INSIDE_SYMBOL_BODY). The border
    # widens the unit's packing footprint on all four sides and shifts the per-part
    # centres inward by the same amount, so inter-unit gaps always clear the port
    # zone. Part sizes / electrical truth are untouched; only (x, y) change.
    _pad = PORT_CLEARANCE_MM
    # Intra-unit clearance (fix: guard C intrusion inside a unit). `sat_gutter` is a
    # cosmetic hairline (~0.7 mm at CCM gutter_scale) fine for a tiny decoupling cap
    # hugging a big body, but a "satellite" can itself be a large multi-pin part (a
    # 48×86 mm BLE module shares GND/+3V3 with U1 → assigned as its satellite). The
    # big body emits power-port stubs/stagger reaching PORT_CLEARANCE_MM OUTSIDE its
    # body bbox (which _bb does NOT model); at a 0.7 mm gutter that outward zone lands
    # inside the satellite body (guard C: POWER_PORT_INSIDE_SYMBOL_BODY). The `_pad`
    # border only clears BETWEEN units, not big↔satellite WITHIN a unit. So the
    # big↔column gap AND the inter-satellite gap must clear the port zone whenever the
    # neighbouring part is large enough to be a body a port could fall into. Tiny caps
    # (bbox ≤ the small-part threshold) keep the tight cosmetic gutter — they have no
    # body a stub could intrude, so their spacing is unchanged (compactness preserved).
    _SAT_BODY_MM = 2 * BBOX_MARGIN_MM + 5.0  # a "part with a real body" (same test as _refine)
    def _sat_gap(part_a_big: bool, other_bb: tuple[float, float]) -> float:
        # Clear the port zone if the OTHER side is a real body (not a hairline cap).
        if max(other_bb) > _SAT_BODY_MM:
            return max(sat_gutter, PORT_CLEARANCE_MM)
        return sat_gutter
    for b in big:
        bw, bh = _bb(b)
        sats = sats_by_host[b]
        sat_w1 = max((_bb(s)[0] for s in sats), default=0.0)
        sat_h1 = max((_bb(s)[1] for s in sats), default=0.0)
        # big↔satellite-block horizontal gap: clear the port zone when the widest
        # satellite is a real body (a port on the big's right edge could fall in).
        big_sat_gap = _sat_gap(True, (sat_w1, sat_h1)) if sats else 0.0
        # Satellite GRID (M6-6 fix): a big IC with a full power rail draws 20+
        # decoupling caps as its satellites; a single vertical column縱疊 them into
        # one x-line spanning the whole sheet (the '超大畫布超小重點' relapse — the
        # column height dwarfs the big body, the sheet grows to A1 and every part
        # is a tiny speck on one line). Pack the satellites into a near-square grid
        # (~√N columns) beside the big body instead of one tall column, so the unit
        # stays compact on BOTH axes. Cell = per-axis max satellite bbox + the same
        # port-clearance gap the column used. Deterministic (sats already sorted).
        n_sat = len(sats)
        sat_cols = max(1, int(n_sat ** 0.5 + 0.9999)) if n_sat else 1
        sat_cell_gap = max(sat_gutter, PORT_CLEARANCE_MM) if sat_h1 > _SAT_BODY_MM or sat_w1 > _SAT_BODY_MM else sat_gutter
        sat_cell_w = sat_w1 + sat_cell_gap
        sat_cell_h = sat_h1 + sat_cell_gap
        sat_nrows = (n_sat + sat_cols - 1) // sat_cols if n_sat else 0
        sat_block_w = sat_cols * sat_cell_w - (sat_cell_gap if sat_cols else 0.0)
        sat_block_h = sat_nrows * sat_cell_h - (sat_cell_gap if sat_nrows else 0.0)
        core_w = bw + (big_sat_gap + sat_block_w if sats else 0.0)
        core_h = max(bh, sat_block_h)
        unit_bbox[b] = (core_w + 2 * _pad, core_h + 2 * _pad)
        offs: dict[str, tuple[float, float]] = {}
        # big body centre: left region, vertically centred in the core (offset by pad).
        offs[b] = (_pad + bw / 2.0, _pad + core_h / 2.0)
        # satellite grid: to the big body's right, vertically centred block.
        sat_x0 = _pad + bw + big_sat_gap
        sat_y0 = _pad + (core_h - sat_block_h) / 2.0
        for i, s in enumerate(sats):
            sw, sh = _bb(s)
            c, r = i % sat_cols, i // sat_cols
            cx = sat_x0 + c * sat_cell_w + sat_w1 / 2.0
            cy = sat_y0 + r * sat_cell_h + sat_h1 / 2.0
            offs[s] = (cx, cy)
        local_offsets[b] = offs

    leftover = [s for s in small if s not in sat_of]
    for s in leftover:
        sw, sh = _bb(s)
        unit_bbox[s] = (sw + 2 * _pad, sh + 2 * _pad)
        local_offsets[s] = {s: (_pad + sw / 2.0, _pad + sh / 2.0)}

    # Near-square target shelf width: sqrt(total unit area) × 1.4 so the packed
    # envelope trends toward a landscape-ish rectangle rather than a tall strip.
    total_unit_area = sum(w * h for (w, h) in unit_bbox.values())
    max_unit_w = max((w for (w, h) in unit_bbox.values()), default=0.0)
    target_w = max(max_unit_w, (total_unit_area ** 0.5) * 1.4)

    # Pack units height-descending (tallest first → tight shelves), ref-tiebroken.
    unit_ids = sorted(unit_bbox, key=lambda u: (-unit_bbox[u][1], u))
    items = [(u, unit_bbox[u][0], unit_bbox[u][1]) for u in unit_ids]
    unit_tl, _tw, _th = _shelf_pack(items, target_w, inter_gutter)

    # Expand each unit's placement into per-part centres.
    out: dict[str, tuple[float, float]] = {}
    for uid, (ux, uy) in unit_tl.items():
        for ref, (dx, dy) in local_offsets[uid].items():
            out[ref] = (ux + dx, uy + dy)
    return out


# ---------------------------------------------------------------------------
# DD-13 (user directive: "紙面空間那麼大，內容不准擠成一堆"). The objective flips
# from _macro_compact's minimize-bbox to DISTRIBUTE-across-the-chosen-frame: once
# a paper is picked for the (large) content, spread the packed units so the
# whitespace is shared as breathing gutters between groups instead of pooling as
# one big empty corner. This is the OPPOSITE of macro_compact (which packs tight);
# they are two ends of one axis and the caller picks one. Deterministic: units
# are the same shelf-packed macro units, only their inter-unit gaps grow to fill
# the content region uniformly. Electrical truth untouched — only (x, y) change.
#
# Overlap-safety: distribution only ever INCREASES gaps between the already
# overlap-free packed units (each unit keeps its internal part offsets), so no
# new overlap can appear. Text bbox is honoured because the unit sizes already
# include the text envelope (_estimate_bbox pads for ref/value text).
# ---------------------------------------------------------------------------
def _page_fill_distribute(
    centres: dict[str, tuple[float, float]],
    bboxes: dict[str, tuple[float, float] | None],
    fill_ratio: float = 0.82,
    avail: tuple[float, float] | None = None,
) -> dict[str, tuple[float, float]]:
    """Spread packed centres so the content fills a near-square envelope evenly.

    centres:    ref → (x, y) part CENTRES (post macro-pack; overlap-free).
    bboxes:     ref → (w, h) or None (text-padded extents; None → small square).
    fill_ratio: the packed content bbox is scaled up so its span becomes
                span/fill_ratio (i.e. gaps grow to leave fill_ratio of the area
                to content). 0.82 ≈ tasteful breathing room, not a sparse field.
    avail:      (avail_w, avail_h) — the usable region of the ALREADY-CHOSEN paper
                (frame minus margins), i.e. the hard upper bound the spread must
                NOT exceed. When given, the per-axis growth is clamped so the
                distributed span never exceeds the available region: distribution
                fills the chosen frame but NEVER drives a larger frame (that was
                the sparse-page A0 regression — a few units × a 63.5 mm gap floor
                ballooned the span, then _fit_sheet re-measured it and jumped to
                A0). When None, legacy behaviour (unbounded grow, capped ×2).

    The scale is applied to each part's centre RELATIVE to the content centroid,
    so inter-part gaps grow uniformly while every part keeps its own size (bboxes
    are NOT scaled). Because parts only move apart, the layout stays overlap-free.
    Deterministic (pure arithmetic on sorted refs; no RNG).
    """
    refs = sorted(centres)
    if len(refs) < 2:
        return centres

    def _bb(r: str) -> tuple[float, float]:
        return bboxes.get(r) or (2 * BBOX_MARGIN_MM, 2 * BBOX_MARGIN_MM)

    # Content AABB of the packed layout (part centre ± half-bbox).
    min_x = min(centres[r][0] - _bb(r)[0] / 2 for r in refs)
    max_x = max(centres[r][0] + _bb(r)[0] / 2 for r in refs)
    min_y = min(centres[r][1] - _bb(r)[1] / 2 for r in refs)
    max_y = max(centres[r][1] + _bb(r)[1] / 2 for r in refs)
    span_x = max_x - min_x
    span_y = max_y - min_y
    if span_x <= 1e-6 and span_y <= 1e-6:
        return centres

    # How much slack exists → how much to grow. Grow the layout so the occupied
    # fraction lands at fill_ratio, capped so a dense page is not blown apart.
    occupied = sum(_bb(r)[0] * _bb(r)[1] for r in refs)
    packed_area = max(span_x * span_y, 1e-6)
    current_ratio = min(1.0, occupied / packed_area)
    if current_ratio <= fill_ratio:
        # already at/under target density — no spreading needed.
        return centres
    grow = (current_ratio / fill_ratio) ** 0.5
    grow = min(grow, 2.0)  # never more than double (avoid runaway sheets)

    # GAP-BASED (edge-to-edge) spread, NOT a centroid scale. A pure centroid
    # scale only grows CENTRE distances, so a wide body (a multi-pin part with
    # ~40 mm half-extent) can still sweep its edge across a neighbour's outward
    # power-port zone (guard C: POWER_PORT_INSIDE_SYMBOL_BODY). Instead, per axis,
    # sort parts by coordinate and grow only the GAP between consecutive part
    # EDGES by an axis-local factor; each part's half-extent is preserved
    # verbatim. Edge gaps only increase, so no body can overlap a neighbour (or
    # its ports) that it did not already touch. Deterministic (sorted; no RNG).
    #
    # The gap floor (PORT_CLEARANCE_MM) guarantees a part's unmodelled power-port
    # outward zone can never land inside a neighbour body (guard C). BUT on a
    # sparse page (few units) a per-gap 63.5 mm floor summed across an axis used
    # to balloon the span far past the packed extent, and _fit_sheet then jumped
    # the frame to A0. To keep the frame fixed, the floor is applied FIRST to get
    # the minimum feasible span, then the remaining slack up to `avail` (if given)
    # is what actually gets distributed — the span is CLAMPED to the chosen frame.
    def _spread_axis(coord_of, half_of, avail_len) -> dict[str, float]:
        order = sorted(refs, key=lambda r: (coord_of(r), r))
        origin = coord_of(order[0]) - half_of(order[0])
        # Fixed cost of this axis: sum of part extents + floored inter-part gaps.
        gaps: list[float] = []  # packed inter-edge gap between consecutive parts
        prev_edge = coord_of(order[0]) + half_of(order[0])
        extent_sum = 2 * half_of(order[0])
        for r in order[1:]:
            gaps.append(max((coord_of(r) - half_of(r)) - prev_edge, 0.0))
            extent_sum += 2 * half_of(r)
            prev_edge = coord_of(r) + half_of(r)
        floored = [max(g, PORT_CLEARANCE_MM) for g in gaps]
        floor_span = extent_sum + sum(floored)
        # Target span: grow the packed gaps by `grow`, but never below the floor
        # span and never above the available region (when a frame is fixed).
        grown = [g * grow for g in gaps]
        grown_span = extent_sum + sum(grown)
        target_span = max(grown_span, floor_span)
        if avail_len is not None:
            target_span = min(target_span, max(avail_len, floor_span))
        # Distribute the slack (target_span − extent_sum) across the floored gaps
        # proportionally to each floored gap's share (uniform-ish breathing).
        slack = target_span - extent_sum
        floor_total = sum(floored)
        new_coord: dict[str, float] = {}
        cursor = origin
        idx = 0
        prev_r = None
        for r in order:
            h = half_of(r)
            if prev_r is None:
                lead = cursor
            else:
                base = floored[idx]
                share = (base / floor_total) if floor_total > 1e-9 else (1.0 / max(len(floored), 1))
                gap = max(slack * share, base if slack >= floor_total else base)
                # keep the floor as a hard minimum regardless of slack rounding
                gap = max(gap, base)
                lead = prev_edge_val + gap
                idx += 1
            new_coord[r] = lead + h
            prev_edge_val = lead + 2 * h
            prev_r = r
        return new_coord

    aw = ah = None
    if avail is not None:
        aw, ah = avail
    nx = _spread_axis(lambda r: centres[r][0], lambda r: _bb(r)[0] / 2, aw)
    ny = _spread_axis(lambda r: centres[r][1], lambda r: _bb(r)[1] / 2, ah)
    return {r: (nx[r], ny[r]) for r in refs}


def _compact_frame_avail(
    centres: dict[str, tuple[float, float]],
    bboxes: dict[str, tuple[float, float] | None],
    sheet_margin_mm: float | None,
    label_reach_mm: float = 0.0,
    prop_reach_mm: float = 0.0,
) -> tuple[float, float] | None:
    """Pick the smallest standard paper for the COMPACT (pre-fill) layout and
    return its usable region (paper span − content pad − 2×margin) per axis.

    This locks the frame to the packed content BEFORE page-fill spreads it, so
    distribution fills WITHIN the chosen frame instead of ballooning the span and
    driving _fit_sheet to a larger paper (the sparse-page A0 regression). Returns
    None when there is nothing to bound (caller falls back to legacy unbounded
    grow). Mirrors _fit_sheet's needed_w/needed_h math (content AABB + max-bbox
    pad + 2×margin) so the frame chosen here is the one _fit_sheet re-derives.
    """
    refs = sorted(centres)
    if not refs:
        return None
    margin = SHEET_MARGIN_MM if sheet_margin_mm is None else sheet_margin_mm

    def _bb(r: str) -> tuple[float, float]:
        return bboxes.get(r) or (2 * BBOX_MARGIN_MM, 2 * BBOX_MARGIN_MM)

    min_x = min(centres[r][0] - _bb(r)[0] / 2 for r in refs)
    max_x = max(centres[r][0] + _bb(r)[0] / 2 for r in refs)
    min_y = min(centres[r][1] - _bb(r)[1] / 2 for r in refs)
    max_y = max(centres[r][1] + _bb(r)[1] / 2 for r in refs)
    # BUGFIX (double-count): the AABB span (max−min) is ALREADY measured on
    # centre±half-bbox, so it fully contains every part's extent. Adding a whole
    # max-bbox pad on top counted the widest/tallest part twice — for a huge U1
    # (~550 mm tall) that inflated content_h by ~275 mm and jumped a sparse page
    # to A0. Edge-clip protection only needs HALF the max bbox (outermost part's
    # centre-to-edge), applied once. Must mirror _fit_sheet exactly.
    # DD-31 per-edge true-extent (mirror _fit_sheet exactly): min_x/max_x are
    # already the per-edge AABB (centre ± OWN half-bbox), so the extent past the
    # centre-span on each edge is ext_lo/hi below. This supersedes the symmetric
    # max-bbox/2 pad, which over-reserved H (U1's full half-height on both edges)
    # and under-reserved W. content = centre-span + ext_lo + ext_hi + 2*reach.
    _cminx = min(centres[r][0] for r in refs)
    _cmaxx = max(centres[r][0] for r in refs)
    _cminy = min(centres[r][1] for r in refs)
    _cmaxy = max(centres[r][1] for r in refs)
    ext_l = max(_cminx - min_x, 0.0)
    ext_r = max(max_x - _cmaxx, 0.0)
    ext_t = max(_cminy - min_y, 0.0)
    ext_b = max(max_y - _cmaxy, 0.0)
    # label_reach_mm: mirror _fit_sheet exactly (labels hang outside the AABB).
    # prop_reach_mm (DD-30): the Reference/Value property text of the LARGEST body
    # part (U1) is anchored by _place_symbol_props at centre ± (half_body + _clear)
    # — one clear row PAST the body edge — so its text row hangs `prop_reach` mm
    # OUTSIDE the body AABB. Mirror _fit_sheet.
    content_w = (_cmaxx - _cminx) + ext_l + ext_r + 2 * label_reach_mm + 2 * prop_reach_mm
    content_h = (_cmaxy - _cminy) + ext_t + ext_b + 2 * label_reach_mm + 2 * prop_reach_mm
    needed_w = content_w + 2 * margin
    needed_h = content_h + 2 * margin
    for _name, pw, ph in STANDARD_PAPERS:
        if needed_w <= pw and needed_h <= ph:
            # usable span for the CENTRE-span on this paper: paper − per-edge ext
            # (edge clipping guard) − 2×margin − label/prop reach, so page_fill spreads
            # the CENTRES WITHIN the ink-inclusive frame. Hard upper bound.
            return (max(pw - ext_l - ext_r - 2 * margin - 2 * label_reach_mm - 2 * prop_reach_mm, 1.0),
                    max(ph - ext_t - ext_b - 2 * margin - 2 * label_reach_mm - 2 * prop_reach_mm, 1.0))
    return None  # overflow even largest paper → let legacy grow handle it


# ---------------------------------------------------------------------------
# DD-5: sheet-fit. Compute content AABB, pick the smallest standard paper that
# fits (with margin), and translate content to the margin origin.
# ---------------------------------------------------------------------------
def _fit_sheet(components: list[EmitComponent], bboxes: dict[str, tuple[float, float] | None], warnings: list[str], sheet_margin_mm: float | None = None, label_reach_mm: float = 0.0, prop_reach_mm: float = 0.0, fail_on_overflow: bool = False, paper_whitelist: set[str] | None = None) -> SheetFit:
    if not components:
        return SheetFit(selected_paper="A4", content_w=0.0, content_h=0.0, overflow=False)
    # sheet_margin_mm (opt-in, default None → SHEET_MARGIN_MM=12.7 unchanged): the
    # per-side white border added around the content AABB before paper selection.
    # A caller that wants a tighter frame (CCM compact pages) passes a smaller
    # value; every other board keeps the global default.
    margin = SHEET_MARGIN_MM if sheet_margin_mm is None else sheet_margin_mm
    min_x = min(c.x for c in components)
    min_y = min(c.y for c in components)
    max_x = max(c.x for c in components)
    max_y = max(c.y for c in components)
    # Pad by HALF the largest bbox so symbol bodies/pins are not clipped at
    # edges. BUGFIX (double-count): min_x/max_x already span centre±half-bbox, so
    # the AABB fully contains every part; a full max-bbox pad counted the widest
    # part twice and ballooned a sparse page to A0. Half = outermost centre→edge,
    # applied once. Must mirror _compact_frame_avail exactly.
    pad_w = max((bb[0] for bb in bboxes.values() if bb is not None), default=2 * BBOX_MARGIN_MM) / 2
    pad_h = max((bb[1] for bb in bboxes.values() if bb is not None), default=2 * BBOX_MARGIN_MM) / 2
    # label_reach_mm (CCM label-only sheet-coherence): global labels hang a stub +
    # scaled net-name text OUTSIDE the component AABB on every edge. A frame chosen
    # on the component AABB alone clips them (the OUT_OF_FRAME defect). Inflate the
    # AABB symmetrically by the measured label reach so BOTH frame selection and the
    # utilization denominator see the real ink. 0.0 (default) == legacy byte-stable.
    # prop_reach_mm (DD-30): _place_symbol_props anchors the largest body part's
    # Reference/Value text one clear row PAST its body edge (centre ± (half_body +
    # _clear)); that text row hangs `prop_reach` mm OUTSIDE the pad-based AABB (which
    # spans only the body). Inflate symmetrically so frame selection sees it, exactly
    # like label_reach. 0.0 (default) == legacy byte-stable.
    # DD-31 per-edge true-extent (supersedes the symmetric span+2*pad model): the
    # pre-fix formula reserved HALF the single WIDEST/TALLEST bbox on BOTH opposing
    # edges. That is axis-asymmetric wrong: on the H axis it double-reserved U1's
    # full half-height (over-count → false CONTENT_EXCEEDS_A0), while on W it missed
    # the actual outermost-part hang (under-count). The true drawn extent is the
    # per-edge AABB: each opposing edge's outermost part contributes ITS OWN
    # half-bbox, not the global max. Measure ext_{l,r,t,b} = how far ink hangs past
    # the centre-span on that specific edge; content = span + ext_lo + ext_hi + 2*reach.
    # (When one part dominates every edge, ext == max-bbox/2 and this reduces to the
    # old symmetric term — so non-U1 pages are unaffected in the limit.)
    span_w = max_x - min_x
    span_h = max_y - min_y

    def _cbb(c: EmitComponent) -> tuple[float, float]:
        return bboxes.get(c.ref) or (2 * BBOX_MARGIN_MM, 2 * BBOX_MARGIN_MM)

    ext_l = max((min_x - (c.x - _cbb(c)[0] / 2) for c in components), default=0.0)
    ext_r = max(((c.x + _cbb(c)[0] / 2) - max_x for c in components), default=0.0)
    ext_t = max((min_y - (c.y - _cbb(c)[1] / 2) for c in components), default=0.0)
    ext_b = max(((c.y + _cbb(c)[1] / 2) - max_y for c in components), default=0.0)
    ext_l = max(ext_l, 0.0)
    ext_r = max(ext_r, 0.0)
    ext_t = max(ext_t, 0.0)
    ext_b = max(ext_b, 0.0)
    content_w = span_w + ext_l + ext_r + 2 * label_reach_mm + 2 * prop_reach_mm
    content_h = span_h + ext_t + ext_b + 2 * label_reach_mm + 2 * prop_reach_mm

    needed_w = content_w + 2 * margin
    needed_h = content_h + 2 * margin
    # M4-2 (occupancy-ledger, DD-3): budget-first frame scan. Walk the standard
    # papers smallest→largest; the FIRST whose usable region contains the
    # label-inclusive content AABB is the budget-feasible frame. Record each
    # rejected candidate's per-axis overload so BUDGET_INFEASIBLE carries an
    # actionable缺項清單 (errors.md) instead of a silent oversize warning.
    # DD-11c (paper-first): a caller may constrain the frame scan to a single-paper
    # whitelist so the OUTER paper loop (A4→A0) owns paper selection and _fit_sheet
    # only answers "does this content fit THIS paper?". None (default) => the full
    # STANDARD_PAPERS scan, byte-identical to every pre-DD-11c caller (TV-2 rail).
    _papers = (
        [p for p in STANDARD_PAPERS if p[0] in paper_whitelist]
        if paper_whitelist is not None else STANDARD_PAPERS
    )
    if not _papers:
        # An empty whitelist is a caller contract error, not a per-scale verdict.
        raise ValueError(
            f"PAPER_WHITELIST_EMPTY: no STANDARD_PAPERS match {sorted(paper_whitelist or ())}")
    selected = _papers[-1]
    overflow = True
    candidates_tried: list[dict] = []
    for name, pw, ph in _papers:
        fits_w = needed_w <= pw
        fits_h = needed_h <= ph
        if fits_w and fits_h:
            selected = (name, pw, ph)
            overflow = False
            break
        candidates_tried.append({
            "paper": name,
            "needed_w": round(needed_w, 2), "avail_w": pw,
            "needed_h": round(needed_h, 2), "avail_h": ph,
            "reason": "width" if not fits_w and fits_h else
                      "height" if fits_w and not fits_h else "both",
        })
    paper_name, paper_w, paper_h = selected
    if overflow:
        # DD-2 / errors.md BUDGET_INFEASIBLE: every standard frame was rejected.
        # overloaded_edges = the axes that exceeded even the largest paper. This
        # is fail-loud by design (no silent up-frame loop, no scale drop); human
        # adjudication splits/reduces content (DD-7). Gated opt-in so non-CCM
        # callers keep the legacy warn-and-grow behaviour (byte-identical).
        if fail_on_overflow:
            _lp_name, _lp_w, _lp_h = _papers[-1]
            overloaded_edges = []
            if needed_w > _lp_w:
                overloaded_edges.append({"axis": "w", "needed": round(needed_w, 2), "avail": _lp_w, "over": round(needed_w - _lp_w, 2)})
            if needed_h > _lp_h:
                overloaded_edges.append({"axis": "h", "needed": round(needed_h, 2), "avail": _lp_h, "over": round(needed_h - _lp_h, 2)})
            warnings.append(f"[budget] INFEASIBLE page={paper_name} edges={overloaded_edges}")
            raise BudgetInfeasible(overloaded_edges, candidates_tried)
        warnings.append("content exceeds largest standard sheet; consider splitting into multiple sheets")

    # Centre the content block on the chosen paper. DD-31 per-edge extent: content_w
    # now spans span + ext_l + ext_r + 2*reach, so the block's leftmost INK edge is
    # (ext_l + reach) LEFT of the leftmost centre. Components translate by
    # (c-min_centre)+block_origin, so the leftmost CENTRE lands at block_origin_x; for
    # the leftmost ink edge to land at the centred margin (paper-content)/2, the
    # inward offset must be the SAME per-edge overhang the content was built from
    # (ext_l + reach), NOT the symmetric max-bbox pad. (Using pad_w here while content
    # shrank to the true per-edge extent mis-centred the block and pushed ink off the
    # far edge — the DD-31 false-fail's twin failure mode on the H axis.)
    _reach = label_reach_mm + prop_reach_mm
    block_origin_x = (paper_w - content_w) / 2.0 + ext_l + _reach
    block_origin_y = (paper_h - content_h) / 2.0 + ext_t + _reach
    # PER-EDGE LABEL-REACH GUTTER (frame-first x/y floor). Symmetric paper
    # inflation (+2*label_reach in content_w/h) reserves the SPACE but centring
    # alone does not guarantee the outermost part's pin clears its outward label
    # reach: a left-edge (ang180) label's text runs `label_reach` mm LEFT of its
    # pin, so the leftmost pin's x must be >= margin + label_reach or the emit
    # layer's x-corridor guard fail-louds (LABEL_DENSITY_UNRESOLVED). The
    # translation below maps each part's centre by (c-min)+block_origin, so the
    # leftmost part's CENTRE lands at block_origin_x. Its outward label edge sits
    # a further (half-bbox + label_reach) LEFT of that centre. To keep that edge
    # inside the usable region the block origin must satisfy:
    #     block_origin_x >= margin + label_reach + half_bbox_leftmost
    # pad_w == max-bbox/2 is the conservative outermost centre->edge guard already
    # used for edge-clip protection, so it is the correct (upper-bound) half-bbox
    # term for the outermost part on any edge. Enforce the HARD per-edge floor on
    # both axes. reach==0 (every non-CCM caller) => the max() is a no-op and the
    # centring is byte-identical.
    # SNAP SLACK (_snap_grid uses grid=1.27 in kicad_emit): the floor must clear
    # the reach EXACTLY, but the per-component translate below snaps to the 1.27mm
    # grid, so a floor set to the exact minimum can round DOWN 0.27mm and land the
    # pin below the reach (the emit x-corridor guard then fail-louds by a fraction
    # of a grid). Add one deterministic grid step so the snapped origin still
    # clears the floor. Not a fallback: a fixed quantum matched to the snap grid.
    _SNAP_SLACK_MM = 1.27
    if label_reach_mm > 0.0 or prop_reach_mm > 0.0:
        block_origin_x = max(block_origin_x, margin + label_reach_mm + prop_reach_mm + ext_l + _SNAP_SLACK_MM)
        block_origin_y = max(block_origin_y, margin + label_reach_mm + prop_reach_mm + ext_t + _SNAP_SLACK_MM)
    for c in components:
        c.x = _snap_grid((c.x - min_x) + block_origin_x)
        c.y = _snap_grid((c.y - min_y) + block_origin_y)

    return SheetFit(selected_paper=paper_name, content_w=content_w, content_h=content_h, overflow=overflow,
                    span_w=span_w, span_h=span_h, pad_w=pad_w, pad_h=pad_h,
                    ext_l=ext_l, ext_r=ext_r, ext_t=ext_t, ext_b=ext_b)


# ---------------------------------------------------------------------------
# DD-12 (user directive: 「一開始就把晶片維度、腳數間距、腳長度全都算清楚，一次到位，
# 砍掉所有事後驗算邏輯」). CONSTRUCTIVE closed-form paper sizing — the paradigm
# REVERSAL of solve_paper_first's scan-eliminate-retry. Geometry is fully
# determined up front: symbol bodies are built by _symbol_geometry so pin NAME
# text can never overlap (DD-2 need_w / DD-11a horiz_pitch / DD-11a2 corner_span
# are constructive INPUTS, not post-hoc floors), so there is nothing to try-and-
# reject. Given the composed content bbox at scale 1.0, this closes the form:
#   1. paper = smallest STANDARD_PAPER whose usable region contains (bbox × 1.0);
#   2. scale = the largest multiple that still fits that paper's usable region
#      (fit-to-frame × a target fill so the circuit fills the sheet — 「圖大紙小」).
# One pass, one answer. The ONLY failure mode is bbox × 1.0 exceeding even A0 —
# that is fail-loud (CONTENT_EXCEEDS_A0), never a retry at a smaller scale.
#
# DD-16 (user directive: 外框 spacing 留 5%): the frame-to-content border is a
# fraction of the PAPER size (per side), not a fixed mm. The usable region is thus
# paper × (1 - 2×margin_frac) on each axis (5% → 90%×90% usable), and that same
# region is both the paper-fit test AND the scale denominator:
#   scale = min((pw×(1-2f))/bbox_w, (ph×(1-2f))/bbox_h).
# ---------------------------------------------------------------------------
# DD-16: per-side frame border as a fraction of the paper dimension (5%).
PAPER_MARGIN_FRAC = 0.05


@dataclass(slots=True)
class PaperSizing:
    paper: str
    scale: float
    content_w: float
    content_h: float


def size_paper_closed_form(
    content_w: float,
    content_h: float,
    *,
    margin_frac: float = PAPER_MARGIN_FRAC,
    scale_quantum: float | None = None,
    papers: list[tuple[str, float, float]] | None = None,
    sheet_margin_mm: float | None = None,  # accepted+ignored (DD-16 supersedes); kept for caller compat
) -> PaperSizing:
    """DD-12/DD-16 constructive paper sizing: closed-form paper + scale, zero retry.

    content_w / content_h: the composed content bbox (frame-inclusive width /
        height in mm) measured at page_scale == 1.0. Because the symbol geometry
        is constructive (text cannot overlap by construction), this bbox is the
        single determined input — no per-scale probing.
    margin_frac: DD-16 per-side frame border as a FRACTION of the paper dimension
        (default 0.05 → 90%×90% usable region). This is the sole margin parameter;
        the usable region = paper × (1 - 2×margin_frac) per axis, used for BOTH the
        paper-fit test and the scale denominator.
    scale_quantum: if given, the returned scale is floored to a multiple of this
        (e.g. KiCad's 2.54 base-pitch ladder → whole-pitch scales). None → the
        exact fit-to-usable real value.
    sheet_margin_mm: accepted for caller signature compatibility but IGNORED — DD-16
        replaced the fixed-mm border with the paper-fraction margin above.

    Returns PaperSizing(paper, scale, content_w, content_h). Raises ValueError
    (CONTENT_EXCEEDS_A0) when the scale==1.0 content does not fit even the
    largest paper's usable region — the sole fail-loud path (never a scale-down retry).
    """
    _papers = papers if papers is not None else STANDARD_PAPERS
    _usable_frac = max(1.0 - 2 * margin_frac, 1e-6)
    if content_w <= 0.0 or content_h <= 0.0:
        return PaperSizing(paper=_papers[0][0], scale=1.0, content_w=content_w, content_h=content_h)
    # 1. smallest paper whose USABLE region (paper × 90%) contains the scale==1.0
    #    content. (DD-16: the border is a paper fraction, so the usable box scales
    #    with the paper, not a fixed mm.)
    chosen: tuple[str, float, float] | None = None
    for name, pw, ph in _papers:
        if content_w <= pw * _usable_frac and content_h <= ph * _usable_frac:
            chosen = (name, pw, ph)
            break
    if chosen is None:
        _ln, _lw, _lh = _papers[-1]
        raise ValueError(
            f"CONTENT_EXCEEDS_A0: content bbox {content_w:.1f}×{content_h:.1f} mm "
            f"exceeds the largest standard paper {_ln} {_lw:.0f}×{_lh:.0f} mm usable "
            f"region ({_usable_frac * 100:.0f}%) at scale 1.0. Reduce content per page "
            f"(split the subsystem); this is fail-loud, not a scale-down retry.")
    name, pw, ph = chosen
    # 2. largest scale whose content fills the paper's usable region (DD-16):
    #    scale = min((pw×90%)/bbox_w, (ph×90%)/bbox_h). No separate fill_target —
    #    the 90% usable region IS the fill envelope.
    usable_w = max(pw * _usable_frac, 1.0)
    usable_h = max(ph * _usable_frac, 1.0)
    fit = min(usable_w / content_w, usable_h / content_h)
    scale = max(fit, 1.0)  # never shrink below the natural size
    if scale_quantum is not None and scale_quantum > 0:
        floored = (int(scale / scale_quantum)) * scale_quantum
        scale = floored if floored >= 1.0 else 1.0
    return PaperSizing(paper=name, scale=round(scale, 4), content_w=content_w, content_h=content_h)


# ---------------------------------------------------------------------------
# DD-11c (SUPERSEDED by DD-12 size_paper_closed_form): paper-first solver. The
# pre-DD-11c pitch-scan (gen_ccm_pages.py
# _solve_and_compose) scanned scale LARGE→small with the paper picked passively
# by _fit_sheet — so overflow/overlap eliminated big scales, every page bottomed
# out at scale 1.0 (smallest symbols), yet _fit_sheet still spread page_fill onto
# a big paper → "canvas bigger, circuit finer" (v2 user rejection). This reverses
# the search: OUTER loop over papers A4→A0 (small→large), INNER loop over scale
# large→small; the FIRST paper that admits ANY scale wins → the smallest paper
# carrying the largest circuit ("圖大紙小"). All the per-(paper,scale) PASS/FAIL
# machinery already lives in compose_schematic (overflow/BUDGET_INFEASIBLE, intra
# overlap, dual-criterion ink); this solver only owns the iteration order +
# single-paper constraint (paper_whitelist), so no new gate is introduced.
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class PaperFirstSolution:
    paper: str
    scale: float
    result: ComposeResult
    scan: list[str] = field(default_factory=list)


# The infeasibility signals that mean "this (paper,scale) is not viable, try the
# next scale / paper" (per-scale verdict), NOT a hard engine fault. Mirrors the
# DD-9b/DD-10 classifier the gen script uses; any OTHER exception re-raises.
_PAPER_FIRST_VERDICT_MARKERS = (
    "SHEET_UTILIZATION_TOO_LOW",
    "LABEL_DENSITY_UNRESOLVED",
    "BUDGET_INFEASIBLE",
    "TEXT_OVERLAP_INTRA_SYMBOL",
    "INK_DENSITY_LOW",
    "LEDGER_ASSERTION_FAILED",
)


def _paper_first_verdict_reason(exc: Exception) -> str | None:
    """Return a short FAIL reason if exc is a per-(paper,scale) feasibility
    verdict, else None (caller re-raises → real engine fault, fail-loud)."""
    msg = str(exc)
    for marker in _PAPER_FIRST_VERDICT_MARKERS:
        if marker in msg:
            return marker
    return None


def solve_paper_first(
    scale_candidates,
    build_fn,
    compose_kwargs: dict,
    out_dir: str | Path,
    project_name: str,
    papers: list[tuple[str, float, float]] | None = None,
) -> PaperFirstSolution:
    """DD-11c paper-first solve: smallest paper → largest scale that fits it.

    scale_candidates: iterable of candidate page_scale values (any order — sorted
        descending internally so the INNER loop always tries the largest first).
    build_fn(scale) -> (spec, symbol_dirs): rebuild THIS page's compose spec +
        symbol dirs at a candidate scale (regenerates scaled symbol geometry).
        Called fresh per scale so a rejected candidate leaves no residue.
    compose_kwargs: kwargs forwarded to compose_schematic (page_fill, style,
        connection_style, sheet_margin_mm, …). page_scale and paper_whitelist are
        injected by the solver and MUST NOT be pre-set by the caller.
    out_dir / project_name: real output target; the winning (paper,scale) composes
        into out_dir. Probes use a throwaway sibling dir so a losing candidate
        never writes the deliverable.

    Returns PaperFirstSolution(paper, scale, result, scan). Raises ValueError
    (NO_VIABLE_PAPER_SCALE) with the full per-(paper,scale) scan table when no
    combination is viable — fail-loud, never a silent fallback to pitch-first.
    """
    import os as _os

    if "page_scale" in compose_kwargs or "paper_whitelist" in compose_kwargs:
        raise ValueError(
            "solve_paper_first owns page_scale and paper_whitelist; "
            "remove them from compose_kwargs")
    _papers = papers if papers is not None else STANDARD_PAPERS
    _scales = sorted({float(s) for s in scale_candidates}, reverse=True)
    if not _scales:
        raise ValueError("solve_paper_first: scale_candidates is empty")
    scan: list[str] = []
    probe_root = f"{out_dir}/_paper_first_probe"
    for paper_name, _pw, _ph in _papers:
        # INNER: largest scale first on THIS single paper. First PASS wins the page
        # (smallest paper × largest circuit) — descend to a smaller scale only when
        # the larger one overflows/overlaps this paper.
        for scale in _scales:
            spec, symbol_dirs = build_fn(scale)
            kw = dict(compose_kwargs)
            kw["page_scale"] = scale
            kw["paper_whitelist"] = {paper_name}
            kw["symbol_dirs"] = symbol_dirs
            probe_dir = f"{probe_root}/{paper_name}_{scale}"
            _os.makedirs(probe_dir, exist_ok=True)
            try:
                compose_schematic(probe_dir, project_name, spec, **kw)
            except Exception as exc:  # noqa: BLE001 — classified below, else re-raised
                reason = _paper_first_verdict_reason(exc)
                if reason is None:
                    raise
                scan.append(f"[solve] paper={paper_name} scale={scale} verdict=FAIL:{reason}")
                continue
            scan.append(f"[solve] paper={paper_name} scale={scale} verdict=PASS")
            scan.append(f"[solve] WON paper={paper_name} scale={scale}")
            real = compose_schematic(out_dir, project_name, spec, **kw)
            real.warnings.extend(scan)
            return PaperFirstSolution(paper=paper_name, scale=scale, result=real, scan=scan)
    raise ValueError(
        f"NO_VIABLE_PAPER_SCALE for {project_name}: no (paper,scale) combination "
        f"passed every gate (overflow/BUDGET_INFEASIBLE, intra overlap, ink). "
        f"scan={' | '.join(scan)}")


# BR_20260905 (multi-node draw policy). The blanket `len(nodes) >= 3 => label`
# switch this replaces made `_bus_route` and every `(junction ...)` emit path 100%
# dead code on the default draftsman route, so the deliverable carried 0 pin-to-pin
# wires and 0 junctions (BR §2.1-§2.3: 124 wires, 124 of them 5.08 mm label stubs).
#
# The replacement mirrors the user-supplied reference schematic (BR §3.1): net
# labels are reserved for the GLOBAL POWER rails whose fan-out is large, and every
# other multi-node net is DRAWN as an orthogonal daisy-chain with junction dots at
# its interior pins. A net is labelled iff it is >=3-node AND one of:
#   - the spec declares kind power/bus, or
#   - its NAME is power/ground shaped (`_power_net_kind`), or
#   - its endpoint count exceeds MULTI_NODE_DRAW_MAX_FANOUT.
# 2-node behaviour is untouched (byte-stable).
#
# 6 is the fan-out line: a decoupling / pull-up star (3-5 endpoints) is exactly the
# RC/RL/LC structure the user says must be visible as drawn copper, while a 7+
# endpoint rail (BR §2.7: BATT=7, SYS=9, GND~50) is the "扇出極多的全域電源節點"
# the reference figure itself keeps on labels.
MULTI_NODE_DRAW_MAX_FANOUT = 6


def _net_power_kind_names(nets: list[EmitNet], net_kinds: dict[str, str]) -> set[str]:
    """Net names that are GLOBAL POWER/BUS rails, by declaration or by name shape.

    Taxonomy:
      - input nets      : the parsed EmitNet list.
      - input net_kinds : {net name -> spec-declared `kind`} (may be partial).
      - output          : the subset of net NAMES that are power/ground/bus rails.
      - rule: a net qualifies iff spec `kind` is "power"/"bus", OR its name matches
              the emitter's own `_power_net_kind` classifier (GND/VCC/+3V3/...).
              The name test is DELEGATED to kicad_emit so composer and emitter
              cannot disagree about what "a power net" is -- a second local regex
              here is exactly the drift BR_20260905 was caused by.
      - NOT: a signal net that merely has many endpoints (that is the separate
             MULTI_NODE_DRAW_MAX_FANOUT test at the call site).
    """
    from .kicad_emit import _power_net_kind
    out: set[str] = set()
    for net in nets:
        if net_kinds.get(net.name, "") in ("power", "bus"):
            out.add(net.name)
        elif _power_net_kind(net.name) is not None:
            out.add(net.name)
    return out


def _build_route_stats(nets: list[EmitNet], net_kinds: dict[str, str], placements: dict[str, EmitComponent], pin_resolvable, emit: SchematicEmitResult, label_nets: set[str] | frozenset | None = None, label_reasons: dict[str, str] | None = None) -> RouteStats:
    """Derive route statistics deterministically from the resolved IR.

    A net is wired iff: not power/bus kind, all nodes resolve, >=2 distinct
    resolvable endpoints, and it is not in `label_nets`. Otherwise it is labelled
    (with an explicit reason).

    label_nets / label_reasons (BR_20260905, replaces the old `multi_node_to_label`
    boolean): the EXACT set the emitter was handed, plus the per-net reason the
    composer chose it. Passing the set itself (rather than re-deriving a rule here)
    is what keeps stats and emission from drifting -- the old boolean re-derived
    ">=3 nodes" locally and would have silently disagreed the moment the policy
    stopped being a pure node-count test, which is precisely what it now is.
    """
    label_nets = set(label_nets) if label_nets else set()
    label_reasons = label_reasons or {}
    stats = RouteStats()
    unresolved_set = set(emit.unresolved_pins)
    for net in nets:
        kind = net_kinds.get(net.name, "")
        resolvable = [(r, p) for (r, p) in net.nodes if f"{r}.{p}" not in unresolved_set and pin_resolvable(r, p)]
        if kind in ("power", "bus"):
            stats.labelled_nets += 1
            stats.label_fallback_reasons.append({"net": net.name, "reason": kind})
            continue
        if len(net.nodes) != len(resolvable):
            stats.labelled_nets += 1
            stats.label_fallback_reasons.append({"net": net.name, "reason": "unresolved"})
            continue
        if len(resolvable) < 2:
            stats.labelled_nets += 1
            stats.label_fallback_reasons.append({"net": net.name, "reason": "single-pin"})
            continue
        if net.name in label_nets:
            stats.labelled_nets += 1
            stats.label_fallback_reasons.append(
                {"net": net.name, "reason": label_reasons.get(net.name, "forced-label")})
            continue
        stats.wired_nets += 1
        if len(resolvable) >= 3:
            stats.junctions += max(0, len(resolvable) - 2)
    return stats


def compose_schematic(
    out_dir: str | Path,
    project_name: str,
    spec: dict,
    symbol_dirs: str | Path | list = DEFAULT_SYMBOL_DIR,
    columns: int = 4,
    validate: bool = False,
    connection_style: str | None = None,
    style: str = "netlist",
    measure_ink: bool = False,
    power_ports: bool = True,
    fidelity: bool = False,
    density_budget: dict | None = None,
    placement_gutter_scale: float = 1.0,
    sheet_margin_mm: float | None = None,
    macro_compact: bool = False,
    page_fill: bool = False,
    page_scale: float = 1.0,
    paper_whitelist: set[str] | None = None,
    power_port_gate: str = "error",
    ink_gate: bool = True,
    expect_sha: dict | None = None,
) -> ComposeResult:
    """Compose a schematic from a declarative spec.

    expect_sha (BR_20260802, optional): {path: sha256}. Every declared path is
    hashed before any work happens and a mismatch raises InputProvenanceMismatch.
    Without it the result still reports `inputs` (what was actually read), but
    checking that record stays the caller's job -- and the recorded failure was
    precisely a caller who had no way to notice it was composing a container copy
    that a host-side edit had already superseded.

    style (DD-3, opt-in — default preserves pre-upgrade behaviour):
      - "netlist" (DEFAULT): naive grid + global-label. Byte-equivalent to the
        old composer. Existing callers are unaffected (no-silent-change rail).
      - "draftsman": subsystem-clustered deterministic force-directed placement
        + drawn-wire connectivity + sheet-fit.

    connection_style: if the caller passes this explicitly it is honoured and
    `style` does NOT override it. When None, it is derived from `style`
    (netlist→"label", draftsman→"wire" for 2-node nets; multi-node (>=3 node)
    nets go to labels per-net — T3 — because drawn multi-node routing is
    unreliable, and the label decision is passed to the emitter so stats and
    emission cannot drift).

    spec["nc"] (T1): optional list of "REF.PIN" strings declared intentionally
    unconnected; forwarded to the emitter which places `(no_connect ...)` glyphs
    and fail-fasts on unresolvable entries.

    density_budget (DD-10, A7 — opt-in fail-fast page density lint):
      - None (DEFAULT): lint disabled (zero break; existing callers unaffected).
      - {}: use DENSITY_BUDGET_DEFAULTS (aiguard-calibrated).
      - dict: per-key override on top of the defaults.
    When enabled, a page whose net count / component count / per-symbol pin count
    exceeds the budget raises ValueError("DENSITY_BUDGET_EXCEEDED: ...") BEFORE
    placement (fail-fast), suggesting a page split or an explicit budget override.
    """
    if style not in ("netlist", "draftsman"):
        raise ValueError(f"style must be 'netlist' or 'draftsman', got {style!r}")

    # symbol_dirs resolution (BR_20260723_compose_symbol_dirs_stdlib_merge):
    # a caller that supplies a custom symbol dir (e.g. a staged token path holding
    # a pruned STM32 symbol) still needs the KiCad standard library for R/C/L and
    # other stock passives (Device.kicad_sym etc.). The historical `.get(default)`
    # / default-parameter semantics treated user dir and stdlib as MUTUALLY
    # EXCLUSIVE — passing any custom dir silently dropped the stdlib, so every
    # stock passive failed to resolve and placement collapsed to placed:0. Merge
    # instead of override: user dirs first (caller precedence for symbol
    # shadowing), DEFAULT_SYMBOL_DIR always appended as a fallback, order-preserving
    # dedup. This is the single caller chokepoint (MCP facade + direct-Python +
    # worker callers all pass through here), so the merge lives ONLY here.
    #
    # BR_20260730b N1: a str that is really a JSON-ENCODED LIST is NOT a directory.
    # An MCP client filling an argument whose inputSchema declares no type (the
    # facade had `"symbol_dirs": {}`) may serialise the array to text, so
    # ["/work/symbols"] arrives as the 17-char string '["/work/symbols"]'. That
    # string is not a path, will never exist, and the isinstance(str) branch below
    # would happily wrap it in a list — every custom symbol then fails to resolve
    # while stdlib parts still load, so compose looks 90% healthy. Detect the
    # encoding here (the one chokepoint every caller passes through) and fail loud
    # with the decoded value, instead of reporting it downstream as "library not
    # found in ['[\"/work/symbols\"]']" — an error that blames the callee's disk
    # for the caller's arg type. Deliberately narrow: only a string whose FIRST
    # non-space char is '[' is treated as encoded, so a real directory named
    # "[weird]" is not hijacked (it would have to be valid JSON yielding a list).
    if isinstance(symbol_dirs, str) and symbol_dirs.lstrip()[:1] == "[":
        try:
            _decoded = json.loads(symbol_dirs)
        except (ValueError, TypeError):
            _decoded = None
        if isinstance(_decoded, list):
            raise SymbolDirsEncodingError(symbol_dirs, _decoded)
    if isinstance(symbol_dirs, (str, Path)):
        _user_dirs = [symbol_dirs]
    elif symbol_dirs is None:
        _user_dirs = []
    else:
        _user_dirs = list(symbol_dirs)
    _merged_dirs: list = []
    for _d in [*_user_dirs, DEFAULT_SYMBOL_DIR]:
        if _d and str(_d) not in {str(x) for x in _merged_dirs}:
            _merged_dirs.append(_d)
    symbol_dirs = _merged_dirs

    # BR_20260802: the declared-digest gate runs FIRST, before any work, so a
    # stale input costs a refusal rather than a full compose whose numbers cannot
    # afterwards be attributed to a version.
    if expect_sha:
        _mismatch: list[dict] = []
        for _path, _want in expect_sha.items():
            _prov = _file_provenance(_path)
            if _prov.get("sha256") != _want:
                _mismatch.append({"path": str(_path), "expected": str(_want),
                                  "actual": str(_prov.get("sha256")),
                                  "bytes": _prov.get("bytes"),
                                  "mtime": _prov.get("mtime"),
                                  "error": _prov.get("error")})
        if _mismatch:
            raise InputProvenanceMismatch(_mismatch)

    # BR_20260730b N2: a spec carrying NO components is refused here, before any
    # gate can bless it.
    #
    # The sibling guard further down catches "declared components, but every one
    # was skipped". This is the OTHER half: components never declared at all. It
    # was missing, so `spec.get("components", [])` returned [] and compose emitted
    # a 213-byte schematic holding zero symbols — and then FOUR independent gates
    # each truthfully reported success on it: the draftsman gate PASSed
    # (intra_overlap=0 label_overlap=0 rects=0 — nothing cannot overlap), ERC found
    # 0 violations (nothing cannot be miswired), validation status="validated",
    # and the call returned ok:true placed:0 nets:0. Four green lights over an
    # empty deliverable, because every gate answered a question about a drawing
    # that does not exist.
    #
    # The observed trigger was a caller passing {"__spec_file__": "/path/spec.json"}
    # — reasonably expecting `spec` to accept a file reference, since its schema
    # says only {"type": "object"}. No key matched, so the spec was silently an
    # empty design. Hence the error names the keys actually RECEIVED next to the
    # ones this function reads: the whole failure is a key-name mismatch, and
    # printing both sides makes that visible in one line instead of sending the
    # caller to read composer source (which is what actually happened).
    #
    # No legitimate caller composes an empty schematic: with nothing to place,
    # every downstream artefact (netlist, ERC report, PDF) is vacuous. Callers
    # that legitimately hold an empty component list (the analyzer/detector
    # scripts that build {"components": []} as an accumulator) never reach
    # compose with it — they populate it first.
    if not spec.get("components"):
        raise EmptySpecError(spec)

    raw_components = spec.get("components", [])
    raw_nets = spec.get("nets", [])
    warnings: list[str] = []
    _ink_gate_verdict = None  # M6-5: observe-only true-ink gate verdict, attached to result post-emit (None on non-page_fill / A4-exempt path)

    # Effective connection style: explicit caller value wins; else derive from style.
    # T3: in the derived draftsman default, multi-node nets are labelled per-net
    # (explicit_conn=False marks that the per-net override applies).
    explicit_conn = connection_style is not None
    if explicit_conn:
        effective_conn = connection_style
    else:
        effective_conn = "wire" if style == "draftsman" else "label"

    # Parse components into a working list preserving spec order/index.
    parsed: list[dict] = []
    skips: list[str] = []
    for index, comp in enumerate(raw_components):
        ref = str(comp.get("ref", "")).strip()
        symbol = str(comp.get("symbol", "")).strip()
        if not ref or not symbol:
            missing = " and ".join(
                f for f, present in (("ref", ref), ("symbol", symbol)) if not present)
            reason = (f"component #{index} missing {missing}; skipped "
                      f'(each component needs ref + symbol: "Lib:Part", e.g. '
                      f'{{"ref": "R1", "symbol": "Device:R"}})')
            skips.append(reason)
            warnings.append(reason)
            continue
        parsed.append({
            "index": index,
            "ref": ref,
            "symbol": symbol,
            "value": str(comp.get("value", "")),
            "footprint": str(comp.get("footprint", "")),
            "group": str(comp.get("group", "")).strip() or None,
            "x": comp.get("x"),
            "y": comp.get("y"),
        })

    # Parse nets (shared by both styles).
    nets: list[EmitNet] = []
    net_kinds: dict[str, str] = {}
    for net in raw_nets:
        name = str(net.get("name", "")).strip()
        nodes = [_parse_node(str(n)) for n in net.get("nodes", []) if "." in str(n)]
        if name and nodes:
            nets.append(EmitNet(name=name, nodes=nodes))
            kind = str(net.get("kind", "")).strip()
            if kind:
                net_kinds[name] = kind

    # BR_20260723d: active-IC symbol-load gate (fail-loud, No-silent-fallback). An
    # active IC whose symbol library cannot be resolved used to degrade silently to
    # a pinless empty box (every net on its pins lost its route, compose still
    # returned a "looks complete" schematic). Detect the failure HERE — before the
    # bbox/pin-count/placement sites that swallow it — and raise SymbolLoadError so
    # the caller sees exactly which active IC symbols are missing.
    #
    # "active IC" criterion (honest, no fabrication):
    #   - spec declares comp["type"] == "ic" (explicit), OR
    #   - the ref appears with >2 DISTINCT pins across nets (used-as-an-IC proxy:
    #     a part wired on >2 pins is an active multi-pin device, not a 2-pin
    #     R/C/L passive).
    # Passive (<=2-pin, type != ic) symbol misses are NOT this gate — they keep the
    # legitimate small-placeholder degrade (BR NOT-bug boundary).
    _raw_type_by_ref: dict[str, str] = {}
    for _comp in raw_components:
        _r = str(_comp.get("ref", "")).strip()
        if _r:
            _raw_type_by_ref[_r] = str(_comp.get("type", "")).strip().lower()
    _distinct_pins_by_ref: dict[str, set[str]] = {}
    for _net in raw_nets:
        for _node in _net.get("nodes", []):
            _ns = str(_node)
            if "." in _ns:
                _r, _, _p = _ns.partition(".")
                _r = _r.strip()
                _p = _p.strip()
                if _r and _p:
                    _distinct_pins_by_ref.setdefault(_r, set()).add(_p)

    def _is_active_ic(ref: str) -> bool:
        if _raw_type_by_ref.get(ref) == "ic":
            return True
        return len(_distinct_pins_by_ref.get(ref, ())) > 2

    _symload_failures: list[dict] = []
    for _c in parsed:
        if not _is_active_ic(_c["ref"]):
            continue
        try:
            load_symbol(_c["symbol"], symbol_dirs)
        except (FileNotFoundError, KeyError) as _exc:
            _lib = _c["symbol"].partition(":")[0]
            _available = sorted({
                _p.name
                for _d in symbol_dirs
                if _d and Path(_d).is_dir()
                for _p in Path(_d).glob("*.kicad_sym")
            })
            _symload_failures.append({
                "ref": _c["ref"],
                "symbol": _c["symbol"],
                "reason": f"{type(_exc).__name__}: {_exc}",
                "expected_library": f"{_lib}.kicad_sym",
                "available_libraries": _available,
            })
    if _symload_failures:
        raise SymbolLoadError(_symload_failures)

    # BR_20260802: record WHICH library files backed this compose. Resolution goes
    # through the same helper load_symbol uses, so the reported path cannot drift
    # from the loaded one -- a provenance record that may disagree with the bytes
    # it describes is worse than none, because it gets trusted.
    _libs_used: dict[str, dict] = {}
    for _c in parsed:
        try:
            _lp = resolve_symbol_library(_c["symbol"], symbol_dirs)
        except (FileNotFoundError, KeyError):
            continue  # passives legitimately fall back to a placeholder box
        if str(_lp) not in _libs_used:
            _libs_used[str(_lp)] = _file_provenance(_lp)

    # T1: declared no-connect pins (forwarded verbatim; emitter fail-fasts on
    # unresolvable entries).
    nc_list = [str(n) for n in spec.get("nc", [])]

    # T3: per-net label override — only in the derived (non-explicit) draftsman
    # default. HISTORY (do not restore): this used to send EVERY >=3-node net to a
    # label with reason "multi-node"; BR_20260905 removed that. See the block below.
    #
    # T3b (all_label): connector-dense boards (product board) pack dozens of pins
    # on tight x columns; the 2-node drawn-wire route runs COLLINEAR on such
    # columns and KiCad fuses collinear wire runs into one net (short). Callers may
    # set spec["all_label"]=True to force EVERY net (2-node included) onto global
    # labels — zero drawn wire, collinearity-free by construction. Electrical
    # definition is untouched; only the drawn-vs-label rendering decision changes.
    label_nets: set[str] | None = None
    label_reasons: dict[str, str] = {}
    all_label = bool(spec.get("all_label", False))
    if all_label:
        label_nets = {net.name for net in nets}
        label_reasons = {net.name: "all-label" for net in nets}
    elif style == "draftsman" and not explicit_conn:
        # BR_20260905: was `{n for n in nets if len(n.nodes) >= 3}` -- a blanket
        # node-count switch that labelled EVERY multi-node net, which made
        # kicad_emit._bus_route and the whole `(junction ...)` emit path dead code
        # and reduced the deliverable to pin-label stubs. Now only the
        # high-fan-out GLOBAL POWER rails go to labels (the reference schematic's
        # own convention, BR §3.1); a 3..MULTI_NODE_DRAW_MAX_FANOUT signal star --
        # decoupling, pull-up, divider, RC/RL/LC -- is DRAWN with junctions.
        _power_like = _net_power_kind_names(nets, net_kinds)
        label_nets = set()
        for net in nets:
            if len(net.nodes) < 3:
                continue
            if net.name in _power_like:
                label_nets.add(net.name)
                label_reasons[net.name] = "power-rail"
            elif len(net.nodes) > MULTI_NODE_DRAW_MAX_FANOUT:
                label_nets.add(net.name)
                label_reasons[net.name] = "high-fanout"
        # M6-8d (user 03a ruling): cross-IC bus policy. When >=2 signals cross the
        # SAME pair of ICs, every cross-IC signal between them is forced to a global
        # label (all-label for that IC pair) — this kills the 12+ unordered wire
        # crossings a drawn cross-IC bus produced. A drawn wire is retained ONLY for
        # short IC<->satellite-passive and intra-cluster links. Style stays uniform
        # per bus: once an IC pair is label-ized, ALL its signals are labels (never a
        # mix of drawn + label on one bus). ICs are pin-count>2 parts (passives are
        # <=2-pin R/C/L); a net's "IC endpoints" are its multi-pin member refs.
        _pin_ct: dict[str, int] = {}
        for _c in parsed:
            try:
                _def, _pins = load_symbol(_c["symbol"], symbol_dirs)
                _pin_ct[_c["ref"]] = len(_pins)
            except Exception:
                _pin_ct[_c["ref"]] = 0
        def _is_ic(ref: str) -> bool:
            return _pin_ct.get(ref, 0) > 2
        # Count signals per unordered IC pair; a signal "crosses" an IC pair when its
        # nodes touch >=2 distinct ICs.
        _pair_sig: dict[frozenset, list[str]] = {}
        for net in nets:
            ic_refs = sorted({r for (r, _p) in net.nodes if _is_ic(r)})
            if len(ic_refs) < 2:
                continue
            for _i in range(len(ic_refs)):
                for _j in range(_i + 1, len(ic_refs)):
                    _pair_sig.setdefault(frozenset((ic_refs[_i], ic_refs[_j])), []).append(net.name)
        _crossic_label = {
            n for names in _pair_sig.values() if len(names) >= 2 for n in names
        }
        if _crossic_label:
            label_nets |= _crossic_label

    clusters: list[Cluster] = []
    sheet_fit: SheetFit | None = None
    bboxes: dict[str, tuple[float, float] | None] = {}
    bbox_cache: dict = {}

    # DD-10 (A7): page density lint runs BEFORE placement (fail-fast). Disabled
    # by default (density_budget is None). Applies to both styles — an over-dense
    # page is unreadable regardless of connectivity rendering.
    _lint_density_budget(density_budget, parsed, nets, symbol_dirs, bbox_cache)

    if style == "netlist":
        # ---- BYTE-EQUIVALENT legacy path (TV9). Do not change. ----
        components: list[EmitComponent] = []
        for c in parsed:
            if c["x"] is not None and c["y"] is not None:
                x, y = float(c["x"]), float(c["y"])
            else:
                x, y = _auto_place(c["index"], columns)
            components.append(EmitComponent(
                ref=c["ref"], lib_id=c["symbol"], value=c["value"],
                footprint=c["footprint"], x=x, y=y,
            ))
        paper = "A4"
    else:
        # ---- draftsman path: cluster → refine → de-overlap → sheet-fit ----
        # DD-29/30/31: the page pitch floor (main-chip rendered pitch, or 7.62 mm on
        # a chip-less page) so a dense vendor symbol's placement bbox reflects the
        # SAME lifted density the emitter will draw (same-source via _vendor_sym_scale).
        _floor_comps = [
            EmitComponent(ref=c["ref"], lib_id=c["symbol"], value=c["value"],
                          footprint=c["footprint"], x=0.0, y=0.0)
            for c in parsed
        ]
        _page_floor = _page_pitch_floor(_floor_comps, symbol_dirs)
        _npitch_cache: dict = {}
        for c in parsed:
            bboxes[c["ref"]] = _estimate_bbox(
                c["symbol"], symbol_dirs, bbox_cache, page_scale=page_scale,
                page_floor=_page_floor, _npitch_cache=_npitch_cache)
            if bboxes[c["ref"]] is None:
                warnings.append(f"{c['ref']}: symbol '{c['symbol']}' bbox unavailable; excluded from force-directed placement")

        # Build net adjacency (ref ↔ ref sharing a net).
        adjacency: dict[str, set[str]] = {c["ref"]: set() for c in parsed}
        for net in nets:
            members = [r for (r, _p) in net.nodes if r in adjacency]
            for i, a in enumerate(members):
                for b in members[i + 1 :]:
                    if a != b:
                        adjacency[a].add(b)
                        adjacency[b].add(a)

        groups = {c["ref"]: c["group"] for c in parsed if c["group"]}
        refs = [c["ref"] for c in parsed]
        clusters = _cluster(refs, groups, adjacency, warnings)

        # Stage B per cluster, then lay clusters on a deterministic grid.
        abs_pos: dict[str, tuple[float, float]] = {}
        explicit: dict[str, tuple[float, float]] = {}
        for c in parsed:
            if c["x"] is not None and c["y"] is not None:
                explicit[c["ref"]] = (float(c["x"]), float(c["y"]))

        n_clusters = len(clusters)
        ccols = max(1, int(n_clusters ** 0.5 + 0.9999))
        # Estimate a uniform cluster cell size from worst-case bbox + gutter.
        max_w = max((bb[0] for bb in bboxes.values() if bb is not None), default=2 * BBOX_MARGIN_MM)
        max_h = max((bb[1] for bb in bboxes.values() if bb is not None), default=2 * BBOX_MARGIN_MM)
        # placement_gutter_scale (opt-in, default 1.0): a caller whose symbols
        # already carry a large in-symbol pin_pitch (CCM per-page U1 @11.43 mm)
        # tightens the inter-part / inter-cluster whitespace by scaling the
        # cell + gutter WITHOUT touching the global constants other boards use.
        # The `*3` bbox multiplier is likewise scaled so a huge U1 does not blow
        # the inter-cluster grid apart.
        cell = (max(max_w, max_h) * 3 + _cluster_gutter_mm(len(parsed))) * placement_gutter_scale
        for ci, cluster in enumerate(clusters):
            cx = (ci % ccols) * cell
            cy = (ci // ccols) * cell
            cluster.center_x = cx
            cluster.center_y = cy
            local = _refine(cluster.members, adjacency, bboxes, gutter_scale=placement_gutter_scale)
            for ref, (lx, ly) in local.items():
                if ref in explicit:
                    abs_pos[ref] = explicit[ref]
                else:
                    abs_pos[ref] = (cx + lx, cy + ly)

        # De-overlap / compaction for non-explicit components.
        non_explicit_pos = {r: p for r, p in abs_pos.items() if r not in explicit}
        if macro_compact:
            # DD-12 (opt-in): unconditional macro bin-pack replaces the sparse
            # force-directed spread (big part + satellite small parts packed tight,
            # macros stacked). Guarantees overlap-safety by construction, so the
            # overlap-gated _resolve_overlaps is not needed on this path.
            resolved = _macro_compact(
                non_explicit_pos, bboxes, adjacency, warnings,
                gutter_scale=placement_gutter_scale,
            )
        else:
            resolved = _resolve_overlaps(non_explicit_pos, bboxes, warnings, gutter_scale=placement_gutter_scale)
        # DD-13 (opt-in): after packing, DISTRIBUTE the units across the frame so
        # whitespace is shared as breathing gutters rather than pooling in one
        # empty corner (user directive: "紙面空間那麼大，內容不准擠成一堆"). Runs on the
        # packed (overlap-free) centres; only grows inter-unit gaps, never sizes,
        # so overlap-safety is preserved. Explicit-position parts are left alone.
        # Label reach (CCM label-only sheet-coherence): every label-routed net hangs
        # a global label a stub + scaled net-name text OUTSIDE the component AABB.
        # Frame selection on the component AABB alone clips them (OUT_OF_FRAME). The
        # reach = scaled stub length + scaled longest-name text run; feed it to BOTH
        # the compact-frame chooser and _fit_sheet so the frame contains the labels
        # and page_fill spreads within a label-inclusive region. page_scale==1.0 =>
        # reach 0 (legacy byte-stable; only CCM scaled pages inflate).
        _label_reach = 0.0
        if page_scale > 1.0 and (label_nets or effective_conn == "label"):
            _lbl_names = [n.name for n in nets] if effective_conn == "label" else list(label_nets or ())
            _max_name = max((len(s) for s in _lbl_names), default=0)
            _stub = _LABEL_STUB_STEP_MM * page_scale
            # Mirror emit's _label_bbox width EXACTLY: len*CW*scale + GLYPH*scale +
            # HMARGIN (an UNSCALED +0.4 mm the emit box always adds). Omitting the
            # HMARGIN under-reserved the gutter by 0.4 mm, so the longest 14-char
            # labels' emit box (need=98.41) exceeded the reserved reach (98.01) and
            # the emit x-corridor guard fail-louded. The reserved reach MUST be the
            # exact box the guard measures, not an approximation.
            _text = (_max_name * _LABEL_CW_MM + _LABEL_GLYPH_MM) * page_scale + _LABEL_HMARGIN_MM
            _label_reach = _stub + _text
        # prop_reach (DD-30): _place_symbol_props anchors the largest body part's
        # Reference/Value text one clear row PAST its body edge (centre ± (half_body +
        # _clear)). pad_h/pad_w in _fit_sheet cover only half_body; the text row hangs
        # `_clear` mm further out plus half its own box height. Mirror the emit constant
        # EXACTLY (kicad_emit._place_symbol_props) so the reserved gutter equals the
        # drawn text row. page_scale==1.0 keeps it small (byte-stable framing intent).
        _prop_h = _PIN_NAME_CH_MM * page_scale + _LABEL_VMARGIN_MM
        _prop_clear = _PIN_NAME_OFFSET_MM * page_scale + _prop_h
        _prop_reach = _prop_clear + _prop_h / 2.0
        if page_fill:
            avail = _compact_frame_avail(resolved, bboxes, sheet_margin_mm, label_reach_mm=_label_reach, prop_reach_mm=_prop_reach)
            resolved = _page_fill_distribute(resolved, bboxes, avail=avail)
        abs_pos.update(resolved)

        components = []
        by_ref = {c["ref"]: c for c in parsed}
        for ref in refs:
            x, y = abs_pos[ref]
            c = by_ref[ref]
            components.append(EmitComponent(
                ref=ref, lib_id=c["symbol"], value=c["value"],
                footprint=c["footprint"], x=_snap_grid(x), y=_snap_grid(y),
            ))

        # DD-12: overflow is an OBSERVATION, not a driving gate. The constructive
        # closed-form sizer (size_paper_closed_form) picks the smallest paper that
        # contains the scale==1.0 content and only THEN scales up to fill it, so an
        # overflowing frame cannot be produced by construction — the sole real
        # overflow (content bigger than A0) fail-louds inside size_paper_closed_form
        # (CONTENT_EXCEEDS_A0). Here _fit_sheet stays fail_on_overflow=False so it
        # records overflow as a warning rather than raising a per-scale verdict that
        # would drive a retry (there is no scan to feed). paper_whitelist is honoured
        # so a caller that already closed the form pins the frame to the chosen paper.
        sheet_fit = _fit_sheet(components, bboxes, warnings, sheet_margin_mm=sheet_margin_mm, label_reach_mm=_label_reach, prop_reach_mm=_prop_reach, fail_on_overflow=False, paper_whitelist=paper_whitelist)
        paper = sheet_fit.selected_paper

        # M4-2 (scale-coherence DD-6b): TRUE-INK density gate REPLACES the AABB
        # utilization ratio. The old gate measured content_w×content_h (the AABB)
        # against usable area — but a long label chain / one tall part inflates the
        # AABB so a genuinely-sparse page (few small parts flung to the corners)
        # passes at a fake-high ratio (TV-7). The real question the user's 「紙面空曠」
        # rejection asks is: how much of the paper is ACTUAL INK? Sum the real drawn
        # boxes — each component's bbox area + each net-label's box area (stub + scaled
        # name text) — and divide by usable area. This cannot be gamed by AABB
        # stretch: an empty corridor contributes zero ink. Same fail-loud contract,
        # same A4 exemption (a few tiny parts cannot ink-fill A4). page_fill-only so
        # non-CCM callers stay byte-identical.
        smallest_paper = STANDARD_PAPERS[0][0]
        if page_fill and not sheet_fit.overflow and components and paper != smallest_paper:
            pw, ph = next((w, h) for name, w, h in STANDARD_PAPERS if name == paper)
            usable = max((pw - 2 * SHEET_MARGIN_MM) * (ph - 2 * SHEET_MARGIN_MM), 1.0)
            # TRUE ink = sum of each drawn element's box area (NOT the enclosing AABB).
            ink_area = 0.0
            for c in components:
                _bb = bboxes.get(c.ref)
                if _bb is not None and _bb[0] > 0 and _bb[1] > 0:
                    ink_area += _bb[0] * _bb[1]
            # Net-label ink: each label-routed net hangs one box of stub + scaled
            # name text per endpoint. Approximate one label box per label-routed net
            # (the dominant ink term on a label-only CCM page); box = reach × scaled
            # text height. reach already == stub + scaled text width (_label_reach).
            if _label_reach > 0.0:
                _lbl_names = [n.name for n in nets] if effective_conn == "label" else list(label_nets or ())
                _lbl_h = _BASE_TEXT_HEIGHT_MM * page_scale
                ink_area += len(_lbl_names) * _label_reach * _lbl_h
            ink_density = ink_area / usable
            aabb_util = (sheet_fit.content_w * sheet_fit.content_h) / usable
            # M6-3 (DD-12 revision, 2026-07-10 使用者「超大畫布超小重點」裁決):
            # SINGLE-criterion TRUE-INK gate. The DD-6b DUAL (aabb_util OR ink_density)
            # criterion is REMOVED — it is exactly what let a hollow-large U1 pass: a
            # 223-ball BGA drawn as an empty rectangle inflates the content AABB so
            # aabb_util is HIGH while the REAL ink (frame outline + pins + text) is a
            # thin shell → ink_density LOW. The OR let criterion (1) rubber-stamp that
            # hollow page. Now ONLY true-ink counts: a page PASSES iff
            #   ink_density >= MIN_INK_DENSITY.
            # ink_area sums per-component bbox area — but a hollow body's ink is its
            # OUTLINE + pin/text, NOT the empty interior. We therefore charge the
            # hollow interior of a large body as ZERO ink by capping each component's
            # counted ink at a shell model: min(full bbox, outline+pins). For the
            # closed-form CCM path the bbox IS the drawn ink for compact parts, so
            # small parts are unaffected; only a large mostly-empty body is discounted.
            _INK_SHELL_FRAC = 0.35   # a hollow BGA body inks ~its frame+pins ≈ 35% of bbox
            ink_area = 0.0
            for c in components:
                _bb = bboxes.get(c.ref)
                if _bb is not None and _bb[0] > 0 and _bb[1] > 0:
                    _area = _bb[0] * _bb[1]
                    # large body (> ~1 A5 worth) is treated as a shell, not a solid.
                    if _area > 40000.0:   # mm² ; ~200×200, i.e. a page-dominating IC
                        _area *= _INK_SHELL_FRAC
                    ink_area += _area
            if _label_reach > 0.0:
                _lbl_names = [n.name for n in nets] if effective_conn == "label" else list(label_nets or ())
                _lbl_h = _BASE_TEXT_HEIGHT_MM * page_scale
                ink_area += len(_lbl_names) * _label_reach * _lbl_h
            ink_density = ink_area / usable
            _ink_pass = ink_density >= MIN_INK_DENSITY
            warnings.append(
                f"[gate] page={project_name} paper={paper} "
                f"ink_density={ink_density * 100:.1f}% aabb_util={aabb_util * 100:.1f}% "
                f"floor={MIN_INK_DENSITY * 100:.0f}% verdict={'PASS' if _ink_pass else 'INK_DENSITY_LOW'}"
            )
            # M6-5 (DD-12 companion, observe-only probe): the sizer's STEP-1/STEP-2
            # probe composes UNBOUNDED at candidate (paper,scale) purely to MEASURE the
            # emitted true-ink extent. On a sparse candidate the gate would raise BEFORE
            # emit (composer.py emit is below), so the probe's .kicad_sch is never
            # written → the sizer parses 0.0×0.0 → CONTENT_EXCEEDS_A0 false fault. With
            # ink_gate=False the gate becomes OBSERVE-ONLY: it records the measured
            # ink_density into ink_metrics (read by the sizer to reject sub-floor
            # candidates) and lets emit run so the probe file exists. The DELIVERABLE
            # path keeps the default ink_gate=True → still fail-loud on a hollow frame.
            _ink_gate_verdict = {
                "ink_density": ink_density,
                "aabb_util": aabb_util,
                "floor": MIN_INK_DENSITY,
                "ink_ok": _ink_pass,
                "paper": paper,
            }
            if not _ink_pass and ink_gate:
                # fail-loud per-(paper,scale) verdict (INK_DENSITY_LOW is in
                # _PAPER_FIRST_VERDICT_MARKERS): solve_paper_first / the closed-form
                # caller reads this to reject the hollow page and pick a SMALLER
                # paper / pitch, never to ship the sparse frame the user rejected.
                raise ValueError(
                    f"INK_DENSITY_LOW: page={project_name} paper={paper} "
                    f"ink_density={ink_density * 100:.1f}% < floor {MIN_INK_DENSITY * 100:.0f}% "
                    f"(hollow/sparse frame — pick smaller paper or higher fill)"
                )

        # M6-5 (observe-only contract, 續棒 fix): the gate block above only runs on the
        # page_fill / non-overflow / non-A4 path. But the sizer's probe (ink_gate=False)
        # MUST get a density verdict for EVERY candidate (paper,scale) it tries, else a
        # candidate whose paper is A4 / overflowing / whatever leaves _ink_gate_verdict
        # None → the ladder reads ink_ok defaulting True → it wrongly ACCEPTS a page the
        # deliverable (ink_gate=True) then rejects at STEP 3 (INK_DENSITY_LOW), and the
        # chosen paper is non-deterministic. So when ink_gate=False and the gate block
        # did NOT run, compute the SAME true-ink density here as an OBSERVATION. The A4 /
        # overflow / non-page_fill exemptions mean "do not REJECT for density" → ink_ok
        # is forced True on the exempt path (density is still reported for the ladder /
        # calibration), matching the deliverable's own A4 exemption.
        if not ink_gate and _ink_gate_verdict is None and components:
            _pw, _ph = next((w, h) for name, w, h in STANDARD_PAPERS if name == paper)
            _usable = max((_pw - 2 * SHEET_MARGIN_MM) * (_ph - 2 * SHEET_MARGIN_MM), 1.0)
            _ink_area = 0.0
            for c in components:
                _bb = bboxes.get(c.ref)
                if _bb is not None and _bb[0] > 0 and _bb[1] > 0:
                    _a = _bb[0] * _bb[1]
                    if _a > 40000.0:
                        _a *= 0.35   # _INK_SHELL_FRAC: hollow large body inks ~its frame+pins
                    _ink_area += _a
            if _label_reach > 0.0:
                _ln = [n.name for n in nets] if effective_conn == "label" else list(label_nets or ())
                _ink_area += len(_ln) * _label_reach * (_BASE_TEXT_HEIGHT_MM * page_scale)
            _obs_density = _ink_area / _usable
            _obs_aabb = (sheet_fit.content_w * sheet_fit.content_h) / _usable
            # Exempt path: never REJECT for density (ink_ok=True). Only a page that both
            # ran through the gate's own conditions AND failed would be ink_ok=False, and
            # that path is handled by the gate block above — here we are on the exempt
            # branch, so ink_ok is True by definition of "exempt".
            _smallest = STANDARD_PAPERS[0][0]
            _exempt = (not page_fill) or sheet_fit.overflow or paper == _smallest
            _obs_ok = True if _exempt else (_obs_density >= MIN_INK_DENSITY)
            _ink_gate_verdict = {
                "ink_density": _obs_density,
                "aabb_util": _obs_aabb,
                "floor": MIN_INK_DENSITY,
                "ink_ok": _obs_ok,
                "paper": paper,
                "exempt": _exempt,
            }

    # Fail-fast: if the caller declared components but EVERY one was skipped, the
    # emitted schematic would be empty and ERC would report 0 violations — a false
    # green. Refuse to ship it and list each skip reason (BR: silent-skip → assert).
    if raw_components and not parsed:
        raise ValueError(
            "COMPOSE_ALL_COMPONENTS_SKIPPED: every declared component was skipped, "
            "the schematic would be empty (0 violations is a false green). Reasons: "
            + "; ".join(skips))

    # M3-2 (occupancy-ledger): build the ONE ledger instance here and reserve the
    # placed component bodies (pin-inclusive extent) up front, then pass it into
    # emit so placement and emit share ONE space account (DD-1 「同一實例」).
    # Non-draftsman / legacy callers leave ledger=None so emit self-builds exactly
    # as before (byte-identical). The reserve is a MIRROR of already-decided
    # placement (try_reserve, non-blocking) — it changes no geometry, it only lets
    # emit's label solver SEE the real bodies (M3-3 will make emit consult them).
    _ledger: "OccupancyLedger | None" = None
    if style == "draftsman":
        _ledger = OccupancyLedger(paper=paper)
        for comp in components:
            _bb = bboxes.get(comp.ref)
            if _bb is None:
                continue
            _hw, _hh = _bb[0] / 2.0, _bb[1] / 2.0
            if _hw <= 0 or _hh <= 0:
                continue
            _ledger.try_reserve(LedgerRect(
                comp.x - _hw, comp.y - _hh, comp.x + _hw, comp.y + _hh,
                comp.ref, "body", source_layer="L1",
            ))

    emit = emit_kicad_schematic(
        out_dir, project_name, components, nets,
        symbol_dir=symbol_dirs, connection_style=effective_conn, paper=paper,
        nc=nc_list or None, label_nets=label_nets, power_ports=power_ports,
        page_scale=page_scale, ledger=_ledger, power_port_gate=power_port_gate,
        clusters=clusters,
        l6_avoidance=bool(spec.get("l6_avoidance", False)),
    )
    warnings.extend(emit.warnings)

    # M4-3b (occupancy-ledger, DD-5 / DD-11): A5 post-emit assertion gate. After
    # emit has reserved every label into the SHARED ledger, assert label↔label
    # owner-aware overlap == 0. This is an ASSERTION over the final state, NOT a
    # blocking reserve during placement (DD-11: blocking would false-positive on
    # the 449 legitimate cross-owner adjacencies — *|power rail ports, body|label
    # anchors — and kill all 5 pages). The emit label solver already achieves zero
    # label overlap by construction; the gate is a correctness detector for the
    # ledger/placement, not a quality tuner. Draftsman-only (netlist path has no
    # shared ledger). Failure => LedgerAssertionFailed (errors.md
    # LEDGER_ASSERTION_FAILED); snapshot dumped for RCA.
    if _ledger is not None:
        # M4-1 (scale-coherence DD-6a): intra-symbol text-overlap gate FIRST. The
        # blind spot the user rejected 4× (「綠字互疊」/滿頁疊字) is SAME-owner text
        # boxes overlapping — the A5 label gate below is owner-aware and EXEMPTS same
        # owner, so it structurally cannot see it. This gate uses the real page_scale
        # text boxes (kind="pin_extent") and flags same-owner geometric overlap.
        # assert-only fail-loud: no auto-avoid, no tolerance drop.
        #
        # CCM path ONLY (page_fill=True): the defect this gate 守備 is intra-symbol
        # text overlap. DD-11b: the opt-in is the CCM page_fill flag, NOT
        # page_scale>1.0. The old page_scale>1.0 guard silently DISARMED the gate
        # whenever the pitch-scan bottomed out at 2.54 (page_scale==1.0) — but text
        # overlap is SCALE-INVARIANT (name and body shrink together), so a 2.54
        # PASS was a false negative (the user-rejected v2 defect). DD-11a fixed the
        # geometry so same-edge names never collide at any scale; the gate must now
        # stay armed at scale 1.0 too. Non-CCM callers (page_fill=False, every
        # netlist/legacy path and the byte-identical TV-2 rail) skip it: a dense
        # connector legitimately renders adjacent name boxes touching by
        # construction (KiCad-default packed render), and those callers have no
        # shared ledger contract — keeping page_fill-only preserves TV-2
        # byte-identity and zero blast-radius, exactly like the M4-2 ink gate.
        _intra_violations = (
            _ledger.intra_symbol_text_overlaps() if page_fill else []
        )
        # DD-12: intra-symbol overlap is now an OBSERVATION log, not a driving gate.
        # The symbol geometry is constructive (DD-2 need_w + DD-11a horiz_pitch +
        # DD-11a2 corner_span size every body so pin NAME boxes cannot collide by
        # construction), so a nonzero count here means the constructive formula has
        # a bug — which the ledger assertion below still catches fail-loud. This
        # measurement is retained as a `[gate]` line for the human reviewer; it does
        # not raise or drive any retry/elimination (there is no scan to feed).
        if _intra_violations:
            import json as _json
            import tempfile as _tempfile
            _isnap = _ledger.snapshot()
            _isnap["violations"] = [
                {"a": a.to_dict(), "b": b.to_dict()} for a, b in _intra_violations
            ]
            _ifd, _isnap_path = _tempfile.mkstemp(
                prefix=f"intra_overlap_{project_name}_", suffix=".json"
            )
            with open(_ifd, "w", encoding="utf-8") as _isf:
                _json.dump(_isnap, _isf, ensure_ascii=False, indent=2)
            warnings.append(
                f"[gate] page={project_name} intra_overlap={len(_intra_violations)} "
                f"verdict=NONZERO snapshot={_isnap_path} (observation; constructive "
                f"geometry should yield 0 — investigate the formula, not retry)"
            )

        _lbl_violations = _ledger.overlaps_of_kinds(frozenset({"label"}))
        if _lbl_violations:
            import json as _json
            import tempfile as _tempfile
            _snap = _ledger.snapshot()
            _snap["violations"] = [
                {"a": a.to_dict(), "b": b.to_dict()} for a, b in _lbl_violations
            ]
            _fd, _snap_path = _tempfile.mkstemp(
                prefix=f"ledger_snapshot_{project_name}_", suffix=".json"
            )
            with open(_fd, "w", encoding="utf-8") as _sf:
                _json.dump(_snap, _sf, ensure_ascii=False, indent=2)
            warnings.append(
                f"[gate] ASSERTION_FAILED page={project_name} "
                f"violations={len(_lbl_violations)} snapshot={_snap_path}"
            )
            raise LedgerAssertionFailed(_lbl_violations, _snap)
        warnings.append(
            f"[gate] page={project_name} paper={paper} intra_overlap=0 "
            f"label_overlap=0 rects={len(_ledger)} PASS"
        )

    route_stats: RouteStats | None = None
    if style == "draftsman":
        placements = {c.ref: c for c in components}

        def _pin_resolvable(ref: str, pin: str) -> bool:
            return ref in placements

        route_stats = _build_route_stats(nets, net_kinds, placements, _pin_resolvable, emit,
                                         label_nets=label_nets, label_reasons=label_reasons)

        # DD-11: the anti-fusion guard may have down-graded some nets from drawn
        # wire to label AFTER _build_route_stats counted them as wired. Reconcile
        # so route_stats mirrors the actual emission (visible, never silent).
        fusion_fallbacks = getattr(emit, "fusion_label_fallbacks", [])
        if fusion_fallbacks:
            downgraded = {d["net"] for d in fusion_fallbacks}
            already = {d["net"] for d in route_stats.label_fallback_reasons}
            for d in fusion_fallbacks:
                if d["net"] not in already:
                    route_stats.label_fallback_reasons.append(d)
                    route_stats.labelled_nets += 1
                    route_stats.wired_nets = max(0, route_stats.wired_nets - 1)
            warnings.append(
                f"anti-fusion guard down-graded {len(downgraded)} net(s) to label "
                f"to avoid cross-net collinear wire fusion: {sorted(downgraded)}")

    result = ComposeResult(
        emit=emit,
        placed=emit.component_count,
        nets=emit.net_count,
        warnings=warnings,
        style=style,
        clusters=clusters,
        route_stats=route_stats,
        sheet_fit=sheet_fit,
        ledger=_ledger,
        wire_body_intrusions=list(getattr(emit, "wire_body_intrusions", [])),
        inputs={
            "symbol_libraries": sorted(_libs_used.values(), key=lambda d: d["path"]),
            "symbol_dirs_searched": [str(_d) for _d in symbol_dirs],
            # The spec arrives as a dict, never as a file compose opens, so there
            # is no path to report for it. Its digest is still the only way to
            # tell two runs apart when the caller generated it from a source that
            # changed underneath -- which is the reported failure mode.
            "spec_sha256": hashlib.sha256(
                json.dumps(spec, sort_keys=True, ensure_ascii=False,
                           default=str).encode("utf-8")).hexdigest(),
            "spec_components": len(spec.get("components", [])),
            "expect_sha_checked": sorted(expect_sha) if expect_sha else [],
            # Not what was read -- what did the reading. See _engine_provenance.
            "engine": _engine_provenance(),
        },
    )

    # M6-5 (DD-12 companion): expose the observe-only true-ink gate verdict so the
    # closed-form sizer can read ink_ok and reject sub-floor candidates. Only set when
    # the page_fill gate actually ran (>A4 page); None on the A4-exempt / non-page_fill
    # path. measure_ink below (if requested) overwrites with the full ink report.
    if _ink_gate_verdict is not None:
        result.ink_metrics = _ink_gate_verdict

    if measure_ink and style == "draftsman":
        from .ink_metrics import measure_schematic_ink
        result.ink_metrics = measure_schematic_ink(emit.schematic_path)

    if validate:
        result.validation = validate_kicad_schematic(emit.schematic_path)

    # BR1: post-emit fidelity gate. ERC/netlist-export (validate=) is BLIND to net
    # FUSION (collinear-wire shorts): fewer nets, no dangling, ERC looks cleaner.
    # Compare the spec's expected net PARTITION against the KiCad-exported
    # partition; diverge => fail-loud (never ship a silently-shorted schematic).
    if fidelity:
        from .fidelity import verify_partition_fidelity, FidelityError
        report = verify_partition_fidelity(nets, emit.schematic_path)
        result.fidelity = report
        if not report.ok:
            raise FidelityError(report)
    return result
