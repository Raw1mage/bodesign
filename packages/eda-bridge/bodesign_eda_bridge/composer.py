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

from dataclasses import dataclass, field
from pathlib import Path

from .kicad_emit import (
    DEFAULT_SYMBOL_DIR,
    EmitComponent,
    EmitNet,
    SchematicEmitResult,
    emit_kicad_schematic,
    load_symbol,
    validate_kicad_schematic,
    _snap_grid,
    _LABEL_STUB_STEP_MM,
    _LABEL_CW_MM,
    _LABEL_GLYPH_MM,
    _LABEL_HMARGIN_MM,
)

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
# Half-extent margin added to every part's bbox ONLY for _page_fill_distribute's
# edge-to-edge gap math. A part's symbol bbox does not include its emitted power-
# port zone (stub _STUB_MM=2.54 + up to 8 stagger tiers × _PWR_STUB_STEP_MM=7.62
# ≈ 61 mm reaching OUTSIDE the body). page-fill spreads by body edges only, so a
# neighbour with body gap>0 could still sweep its port zone into an adjacent body
# (guard C: POWER_PORT_INSIDE_SYMBOL_BODY). Reserving this clearance on each side
# keeps the port zone out of every neighbour. Conservative upper bound of the
# worst-case outward reach; only widens page-fill gaps (never sizes/sheet-fit).
PORT_CLEARANCE_MM = 63.5  # 2.54 stub + 8×7.62 stagger, rounded up to a grid mult


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
    fidelity: object | None = None  # BR1: FidelityReport when fidelity=True


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


def _estimate_bbox(lib_id: str, symbol_dir, _cache: dict) -> tuple[float, float] | None:
    """Estimate (width, height) in mm — pin endpoints ∪ ref/value text envelope.

    Effective bbox = pin graphic extent + margin, then widened/heightened by the
    ref/value text envelope (BR: text-overlap 治本 — placement must reserve room
    for the labels, not just the pin graphics). Returns None when the symbol
    cannot be loaded — caller treats as fail-visible (warning + skip from
    refinement), never substitutes a default.
    """
    if lib_id in _cache:
        return _cache[lib_id]
    try:
        _definition, pins = load_symbol(lib_id, symbol_dir)
    except (FileNotFoundError, KeyError):
        _cache[lib_id] = None
        return None
    if not pins:
        # A symbol with no parsable pins gives no extent proxy; treat as a small
        # square (still text-padded so its ref/value has room) so two such
        # symbols still repel, deterministically.
        side = 2 * BBOX_MARGIN_MM
        bbox = (max(side, _TEXT_PAD_W_MM), max(side, _TEXT_PAD_H_MM))
        _cache[lib_id] = bbox
        return bbox
    xs = [px for (px, _py) in pins.values()]
    ys = [py for (_px, py) in pins.values()]
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
        sat_w = max((_bb(s)[0] for s in sats), default=0.0)
        # big↔satellite-column horizontal gap: clear the port zone when the widest
        # satellite is a real body (a port on the big's right edge could fall in).
        big_sat_gap = _sat_gap(True, (sat_w, max((_bb(s)[1] for s in sats), default=0.0))) if sats else 0.0
        sat_h_total = 0.0
        _prev_sat_bb: tuple[float, float] | None = None
        for s in sats:
            g = _sat_gap(False, _prev_sat_bb) if _prev_sat_bb is not None else 0.0
            sat_h_total += g + _bb(s)[1]
            _prev_sat_bb = _bb(s)
        core_w = bw + (big_sat_gap + sat_w if sats else 0.0)
        core_h = max(bh, sat_h_total)
        unit_bbox[b] = (core_w + 2 * _pad, core_h + 2 * _pad)
        offs: dict[str, tuple[float, float]] = {}
        # big body centre: left region, vertically centred in the core (offset by pad).
        offs[b] = (_pad + bw / 2.0, _pad + core_h / 2.0)
        # satellite column: to the big body's right, vertically centred block.
        sat_x0 = _pad + bw + big_sat_gap
        sy = _pad + (core_h - sat_h_total) / 2.0
        _prev_sat_bb = None
        for s in sats:
            sw, sh = _bb(s)
            if _prev_sat_bb is not None:
                sy += _sat_gap(False, _prev_sat_bb)
            offs[s] = (sat_x0 + sat_w / 2.0, sy + sh / 2.0)
            sy += sh
            _prev_sat_bb = (sw, sh)
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
    pad_w = max((bb[0] for bb in bboxes.values() if bb is not None), default=2 * BBOX_MARGIN_MM) / 2
    pad_h = max((bb[1] for bb in bboxes.values() if bb is not None), default=2 * BBOX_MARGIN_MM) / 2
    # label_reach_mm: mirror _fit_sheet exactly (labels hang outside the AABB).
    content_w = (max_x - min_x) + pad_w + 2 * label_reach_mm
    content_h = (max_y - min_y) + pad_h + 2 * label_reach_mm
    needed_w = content_w + 2 * margin
    needed_h = content_h + 2 * margin
    for _name, pw, ph in STANDARD_PAPERS:
        if needed_w <= pw and needed_h <= ph:
            # usable span for the CONTENT AABB (centres±half-bbox) on this paper:
            # paper − pad (edge clipping guard) − 2×margin, and − the label reach so
            # page_fill spreads WITHIN the label-inclusive frame. Hard upper bound.
            return (max(pw - pad_w - 2 * margin - 2 * label_reach_mm, 1.0),
                    max(ph - pad_h - 2 * margin - 2 * label_reach_mm, 1.0))
    return None  # overflow even largest paper → let legacy grow handle it


# ---------------------------------------------------------------------------
# DD-5: sheet-fit. Compute content AABB, pick the smallest standard paper that
# fits (with margin), and translate content to the margin origin.
# ---------------------------------------------------------------------------
def _fit_sheet(components: list[EmitComponent], bboxes: dict[str, tuple[float, float] | None], warnings: list[str], sheet_margin_mm: float | None = None, label_reach_mm: float = 0.0) -> SheetFit:
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
    content_w = (max_x - min_x) + pad_w + 2 * label_reach_mm
    content_h = (max_y - min_y) + pad_h + 2 * label_reach_mm

    needed_w = content_w + 2 * margin
    needed_h = content_h + 2 * margin
    selected = STANDARD_PAPERS[-1]
    overflow = True
    for name, pw, ph in STANDARD_PAPERS:
        if needed_w <= pw and needed_h <= ph:
            selected = (name, pw, ph)
            overflow = False
            break
    paper_name, paper_w, paper_h = selected
    if overflow:
        warnings.append("content exceeds largest standard sheet; consider splitting into multiple sheets")

    # Centre the content block on the chosen paper.
    block_origin_x = (paper_w - content_w) / 2.0 + pad_w / 2.0
    block_origin_y = (paper_h - content_h) / 2.0 + pad_h / 2.0
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
    if label_reach_mm > 0.0:
        block_origin_x = max(block_origin_x, margin + label_reach_mm + pad_w + _SNAP_SLACK_MM)
        block_origin_y = max(block_origin_y, margin + label_reach_mm + pad_h + _SNAP_SLACK_MM)
    for c in components:
        c.x = _snap_grid((c.x - min_x) + block_origin_x)
        c.y = _snap_grid((c.y - min_y) + block_origin_y)

    return SheetFit(selected_paper=paper_name, content_w=content_w, content_h=content_h, overflow=overflow)


def _build_route_stats(nets: list[EmitNet], net_kinds: dict[str, str], placements: dict[str, EmitComponent], pin_resolvable, emit: SchematicEmitResult, multi_node_to_label: bool = False) -> RouteStats:
    """Derive route statistics deterministically from the resolved IR.

    A net is wired iff: not power/bus kind, all nodes resolve, and >=2 distinct
    resolvable endpoints. Otherwise it is labelled (with an explicit reason).

    multi_node_to_label (T3): when the composer routes multi-node (>=3 endpoint)
    nets via labels by default, count them as labelled with reason "multi-node"
    so the stats mirror what was actually emitted.
    """
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
        if multi_node_to_label and len(resolvable) >= 3:
            stats.labelled_nets += 1
            stats.label_fallback_reasons.append({"net": net.name, "reason": "multi-node"})
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
) -> ComposeResult:
    """Compose a schematic from a declarative spec.

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

    raw_components = spec.get("components", [])
    raw_nets = spec.get("nets", [])
    warnings: list[str] = []

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

    # T1: declared no-connect pins (forwarded verbatim; emitter fail-fasts on
    # unresolvable entries).
    nc_list = [str(n) for n in spec.get("nc", [])]

    # T3: per-net label override — only in the derived (non-explicit) draftsman
    # default. Multi-node (>=3 node) nets go to labels (reason "multi-node").
    #
    # T3b (all_label): connector-dense boards (product board) pack dozens of pins
    # on tight x columns; the 2-node drawn-wire route runs COLLINEAR on such
    # columns and KiCad fuses collinear wire runs into one net (short). Callers may
    # set spec["all_label"]=True to force EVERY net (2-node included) onto global
    # labels — zero drawn wire, collinearity-free by construction. Electrical
    # definition is untouched; only the drawn-vs-label rendering decision changes.
    label_nets: set[str] | None = None
    multi_node_to_label = False
    all_label = bool(spec.get("all_label", False))
    if all_label:
        multi_node_to_label = True
        label_nets = {net.name for net in nets}
    elif style == "draftsman" and not explicit_conn:
        multi_node_to_label = True
        label_nets = {net.name for net in nets if len(net.nodes) >= 3}

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
        for c in parsed:
            bboxes[c["ref"]] = _estimate_bbox(c["symbol"], symbol_dirs, bbox_cache)
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
        if page_fill:
            avail = _compact_frame_avail(resolved, bboxes, sheet_margin_mm, label_reach_mm=_label_reach)
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

        sheet_fit = _fit_sheet(components, bboxes, warnings, sheet_margin_mm=sheet_margin_mm, label_reach_mm=_label_reach)
        paper = sheet_fit.selected_paper

        # Utilization gate (opt-in via page_fill; the CCM sheet-fill contract).
        # After frame selection, the content AABB must occupy a minimum fraction
        # of the chosen paper's usable region. This fail-loud catches the exact
        # regression user rejected 4× (a sparse page ballooning to A0 with ~25%
        # ink): if the frame is far larger than the content, either frame-fit is
        # double-counting bbox pad or page_fill failed to spread — both must be
        # fixed at the engine, never shipped as an empty sheet. Not overflow.
        # NOTE: exempt the smallest standard paper (A4). A few tiny parts cannot
        # fill A4 no matter how tightly packed — that is genuinely-small content,
        # not a sparse-inflation bug. The gate only fires when a LARGER-than-A4
        # frame is under-filled (i.e. a smaller frame existed but was not chosen,
        # or fill failed to spread) — exactly the A0-at-25% case user rejected.
        smallest_paper = STANDARD_PAPERS[0][0]
        if page_fill and not sheet_fit.overflow and components and paper != smallest_paper:
            pw, ph = next((w, h) for name, w, h in STANDARD_PAPERS if name == paper)
            usable = max((pw - 2 * SHEET_MARGIN_MM) * (ph - 2 * SHEET_MARGIN_MM), 1.0)
            util = (sheet_fit.content_w * sheet_fit.content_h) / usable
            if util < MIN_SHEET_UTILIZATION:
                raise ValueError(
                    f"SHEET_UTILIZATION_TOO_LOW: content bbox "
                    f"{sheet_fit.content_w:.0f}\u00d7{sheet_fit.content_h:.0f} mm occupies only "
                    f"{util * 100:.0f}% of {paper} usable area (floor "
                    f"{MIN_SHEET_UTILIZATION * 100:.0f}%). Either frame-fit over-padded "
                    f"the bbox or page_fill under-spread; fix the engine, do not ship a sparse sheet.")

    # Fail-fast: if the caller declared components but EVERY one was skipped, the
    # emitted schematic would be empty and ERC would report 0 violations — a false
    # green. Refuse to ship it and list each skip reason (BR: silent-skip → assert).
    if raw_components and not parsed:
        raise ValueError(
            "COMPOSE_ALL_COMPONENTS_SKIPPED: every declared component was skipped, "
            "the schematic would be empty (0 violations is a false green). Reasons: "
            + "; ".join(skips))

    emit = emit_kicad_schematic(
        out_dir, project_name, components, nets,
        symbol_dir=symbol_dirs, connection_style=effective_conn, paper=paper,
        nc=nc_list or None, label_nets=label_nets, power_ports=power_ports,
        page_scale=page_scale,
    )
    warnings.extend(emit.warnings)

    route_stats: RouteStats | None = None
    if style == "draftsman":
        placements = {c.ref: c for c in components}

        def _pin_resolvable(ref: str, pin: str) -> bool:
            return ref in placements

        route_stats = _build_route_stats(nets, net_kinds, placements, _pin_resolvable, emit, multi_node_to_label=multi_node_to_label)

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
    )

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
