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
CLUSTER_GUTTER_MM = 30.0
BBOX_MARGIN_MM = 2.54
SHEET_MARGIN_MM = 12.7


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
class ComposeResult:
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
def _estimate_bbox(lib_id: str, symbol_dir, _cache: dict) -> tuple[float, float] | None:
    """Estimate (width, height) in mm from a symbol's pin endpoints + margin.

    Returns None when the symbol cannot be loaded — caller must treat as
    fail-visible (warning + skip from refinement), never substitute a default.
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
        # square so two such symbols still repel, but mark deterministically.
        bbox = (2 * BBOX_MARGIN_MM, 2 * BBOX_MARGIN_MM)
        _cache[lib_id] = bbox
        return bbox
    xs = [px for (px, _py) in pins.values()]
    ys = [py for (_px, py) in pins.values()]
    w = (max(xs) - min(xs)) + 2 * BBOX_MARGIN_MM
    h = (max(ys) - min(ys)) + 2 * BBOX_MARGIN_MM
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
def _refine(members: list[str], adjacency: dict[str, set[str]], bboxes: dict[str, tuple[float, float] | None]) -> dict[str, tuple[float, float]]:
    """Return deterministic local (x, y) offsets per member around (0, 0).

    Spring (shared-net attraction) + repulsion (overlap avoidance). Members
    whose bbox is None (symbol load failed) are excluded from the model
    (fail-visible) but still placed on the deterministic grid.
    """
    if not members:
        return {}
    # Deterministic initial grid: ref-sorted, square-ish.
    ordered = sorted(members)
    cols = max(1, int(len(ordered) ** 0.5 + 0.9999))
    step = 25.4  # 1 inch initial spacing
    pos: dict[str, list[float]] = {}
    for i, ref in enumerate(ordered):
        pos[ref] = [float((i % cols) * step), float((i // cols) * step)]

    active = [r for r in ordered if bboxes.get(r) is not None]
    if len(active) < 2:
        return {r: (pos[r][0], pos[r][1]) for r in ordered}

    member_set = set(active)
    for _ in range(PLACEMENT_ITERATIONS):
        disp: dict[str, list[float]] = {r: [0.0, 0.0] for r in active}
        # Repulsion between every active pair.
        for i, a in enumerate(active):
            for b in active[i + 1 :]:
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                dist2 = dx * dx + dy * dy
                if dist2 < 1e-6:
                    # Deterministic tie-break: push along ref order, not random.
                    dx = (1.0 if a < b else -1.0)
                    dy = 0.0
                    dist2 = 1.0
                inv = REPULSE_K / dist2
                disp[a][0] += dx * inv
                disp[a][1] += dy * inv
                disp[b][0] -= dx * inv
                disp[b][1] -= dy * inv
        # Spring attraction along shared-net edges (within this cluster).
        for a in active:
            for b in sorted(adjacency.get(a, ())):
                if b in member_set and a < b:
                    dx = pos[b][0] - pos[a][0]
                    dy = pos[b][1] - pos[a][1]
                    disp[a][0] += dx * SPRING_K
                    disp[a][1] += dy * SPRING_K
                    disp[b][0] -= dx * SPRING_K
                    disp[b][1] -= dy * SPRING_K
        for r in active:
            pos[r][0] += disp[r][0]
            pos[r][1] += disp[r][1]

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
) -> dict[str, tuple[float, float]]:
    """Deterministic AABB de-overlap fallback (R1 / E-DRAFT-004).

    After force-directed convergence, if any two components still overlap, lay
    the whole set out on a deterministic gutter grid sized to the largest bbox.
    Non-random; identical input ⇒ identical output.
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
    max_w = max((bboxes[r][0] for r in sized), default=2 * BBOX_MARGIN_MM)
    max_h = max((bboxes[r][1] for r in sized), default=2 * BBOX_MARGIN_MM)
    cell_w = max_w + CLUSTER_GUTTER_MM
    cell_h = max_h + CLUSTER_GUTTER_MM
    cols = max(1, int(len(refs) ** 0.5 + 0.9999))
    out: dict[str, tuple[float, float]] = {}
    for i, ref in enumerate(sized + unsized):
        out[ref] = (float((i % cols) * cell_w), float((i // cols) * cell_h))
    return out


# ---------------------------------------------------------------------------
# DD-5: sheet-fit. Compute content AABB, pick the smallest standard paper that
# fits (with margin), and translate content to the margin origin.
# ---------------------------------------------------------------------------
def _fit_sheet(components: list[EmitComponent], bboxes: dict[str, tuple[float, float] | None], warnings: list[str]) -> SheetFit:
    if not components:
        return SheetFit(selected_paper="A4", content_w=0.0, content_h=0.0, overflow=False)
    min_x = min(c.x for c in components)
    min_y = min(c.y for c in components)
    max_x = max(c.x for c in components)
    max_y = max(c.y for c in components)
    # Pad by the largest bbox so symbol bodies/pins are not clipped at edges.
    pad_w = max((bb[0] for bb in bboxes.values() if bb is not None), default=2 * BBOX_MARGIN_MM)
    pad_h = max((bb[1] for bb in bboxes.values() if bb is not None), default=2 * BBOX_MARGIN_MM)
    content_w = (max_x - min_x) + pad_w
    content_h = (max_y - min_y) + pad_h

    needed_w = content_w + 2 * SHEET_MARGIN_MM
    needed_h = content_h + 2 * SHEET_MARGIN_MM
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
    for c in components:
        c.x = _snap_grid((c.x - min_x) + block_origin_x)
        c.y = _snap_grid((c.y - min_y) + block_origin_y)

    return SheetFit(selected_paper=paper_name, content_w=content_w, content_h=content_h, overflow=overflow)


def _build_route_stats(nets: list[EmitNet], net_kinds: dict[str, str], placements: dict[str, EmitComponent], pin_resolvable, emit: SchematicEmitResult) -> RouteStats:
    """Derive route statistics deterministically from the resolved IR.

    A net is wired iff: not power/bus kind, all nodes resolve, and >=2 distinct
    resolvable endpoints. Otherwise it is labelled (with an explicit reason).
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
) -> ComposeResult:
    """Compose a schematic from a declarative spec.

    style (DD-3, opt-in — default preserves pre-upgrade behaviour):
      - "netlist" (DEFAULT): naive grid + global-label. Byte-equivalent to the
        old composer. Existing callers are unaffected (no-silent-change rail).
      - "draftsman": subsystem-clustered deterministic force-directed placement
        + drawn-wire connectivity + sheet-fit.

    connection_style: if the caller passes this explicitly it is honoured and
    `style` does NOT override it. When None, it is derived from `style`
    (netlist→"label", draftsman→"wire").
    """
    if style not in ("netlist", "draftsman"):
        raise ValueError(f"style must be 'netlist' or 'draftsman', got {style!r}")

    raw_components = spec.get("components", [])
    raw_nets = spec.get("nets", [])
    warnings: list[str] = []

    # Effective connection style: explicit caller value wins; else derive from style.
    if connection_style is not None:
        effective_conn = connection_style
    else:
        effective_conn = "wire" if style == "draftsman" else "label"

    # Parse components into a working list preserving spec order/index.
    parsed: list[dict] = []
    for index, comp in enumerate(raw_components):
        ref = str(comp.get("ref", "")).strip()
        symbol = str(comp.get("symbol", "")).strip()
        if not ref or not symbol:
            warnings.append(f"component #{index} missing ref/symbol; skipped")
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

    clusters: list[Cluster] = []
    sheet_fit: SheetFit | None = None
    bboxes: dict[str, tuple[float, float] | None] = {}

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
        bbox_cache: dict = {}
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
        cell = max(max_w, max_h) * 3 + CLUSTER_GUTTER_MM
        for ci, cluster in enumerate(clusters):
            cx = (ci % ccols) * cell
            cy = (ci // ccols) * cell
            cluster.center_x = cx
            cluster.center_y = cy
            local = _refine(cluster.members, adjacency, bboxes)
            for ref, (lx, ly) in local.items():
                if ref in explicit:
                    abs_pos[ref] = explicit[ref]
                else:
                    abs_pos[ref] = (cx + lx, cy + ly)

        # De-overlap fallback only for non-explicit components.
        non_explicit_pos = {r: p for r, p in abs_pos.items() if r not in explicit}
        resolved = _resolve_overlaps(non_explicit_pos, bboxes, warnings)
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

        sheet_fit = _fit_sheet(components, bboxes, warnings)
        paper = sheet_fit.selected_paper

    emit = emit_kicad_schematic(
        out_dir, project_name, components, nets,
        symbol_dir=symbol_dirs, connection_style=effective_conn, paper=paper,
    )
    warnings.extend(emit.warnings)

    route_stats: RouteStats | None = None
    if style == "draftsman":
        placements = {c.ref: c for c in components}

        def _pin_resolvable(ref: str, pin: str) -> bool:
            return ref in placements

        route_stats = _build_route_stats(nets, net_kinds, placements, _pin_resolvable, emit)

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
    return result
