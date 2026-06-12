"""G7 reference comparator core (DD-10..DD-13) — deterministic IR-vs-IR matching.

Algorithm skeleton follows pcbGPT (arXiv 2606.01188):
  1. two-stage component matching: required components first, optional after
     (optional absence is never penalized)
  2. pin neighborhood signatures -> pairwise similarity matrix
  3. Hungarian (Kuhn–Munkres) global assignment — pure Python, no new deps
  4. weighted score S = w_comp*S_comp(Dice) + w_attr*S_attr + w_conn*S_conn
  5. symmetric two-pin passives normalize pin names to __sym__
  6. flexible_pin_groups members are interchangeable for connectivity matching

Determinism guarantees: stable tie-breaking by refdes lexical order everywhere;
same input always produces byte-identical output. No LLM involvement.

Fail-fast (errors.md): CMP_IR_INVALID — invalid input IR aborts the whole
comparison; no partial results, no silently skipped components.
"""

from dataclasses import dataclass, field

from bodesign_design_ir.contracts import BoardDesign, ComponentInstance

from .config import DEFAULT_SCORING_CONFIG, CompareError, ScoringConfig

SYM_PIN = "__sym__"


# ── Input validation (DD-13: fail fast, no partial comparison) ─────────


def _pad_to_refdes_pin(pad: str, design_id: str) -> tuple[str, str]:
    """connected_pads entries are '<REFDES>-<PIN>' (board_reconstruct.py)."""
    refdes, sep, pin = pad.partition("-")
    if not sep or not refdes or not pin:
        raise CompareError(
            f"CMP_IR_INVALID: comparator input IR invalid: net pad {pad!r} in design "
            f"'{design_id}' is not '<refdes>-<pin>'; no partial comparison performed"
        )
    return refdes, pin


def _validate_design(design: BoardDesign, side: str) -> None:
    if not design.components:
        raise CompareError(
            f"CMP_IR_INVALID: comparator input IR invalid: {side} design '{design.id}' has "
            "no components; no partial comparison performed"
        )
    refdes_seen: set[str] = set()
    for comp in design.components:
        if not comp.refdes or not comp.refdes.strip():
            raise CompareError(
                f"CMP_IR_INVALID: comparator input IR invalid: {side} design '{design.id}' has "
                "a component without a refdes; no partial comparison performed"
            )
        if comp.refdes in refdes_seen:
            raise CompareError(
                f"CMP_IR_INVALID: comparator input IR invalid: duplicate refdes "
                f"{comp.refdes!r} in {side} design '{design.id}'"
            )
        refdes_seen.add(comp.refdes)
    for net in design.nets:
        for pad in net.connected_pads:
            refdes, _pin = _pad_to_refdes_pin(pad, design.id)
            if refdes not in refdes_seen:
                raise CompareError(
                    f"CMP_IR_INVALID: comparator input IR invalid: net {net.name!r} in {side} "
                    f"design '{design.id}' references unknown component {refdes!r}"
                )


# ── Pin normalization (DD-12: __sym__, FlexiblePin) ────────────────────


def _is_symmetric_passive(comp: ComponentInstance, config: ScoringConfig, pin_count: int) -> bool:
    prefix = "".join(ch for ch in comp.refdes if ch.isalpha())
    return prefix.upper() in config.symmetric_passive_prefixes and pin_count <= 2


def _normalize_pin(comp: ComponentInstance, pin: str, config: ScoringConfig,
                   pin_count: int) -> str:
    if _is_symmetric_passive(comp, config, pin_count):
        return SYM_PIN
    for group_name, members in sorted(comp.flexible_pin_groups.items()):
        if pin in members:
            return f"__flex__{group_name}"
    return pin


@dataclass(slots=True)
class _CompView:
    """Pre-computed per-component view used by signature + scoring steps."""

    comp: ComponentInstance
    # normalized pin -> sorted tuple of net names that pin touches
    pin_nets: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def part_key(self) -> str:
        return (self.comp.part_number or "").strip().lower()

    @property
    def signature(self) -> frozenset[tuple[str, frozenset[str]]]:
        """Pin neighborhood signature: {(normalized_pin, {neighbor part_keys})}."""
        return frozenset(
            (pin, frozenset(nets)) for pin, nets in self.pin_nets.items()
        )


def _build_views(design: BoardDesign, config: ScoringConfig) -> dict[str, _CompView]:
    views = {c.refdes: _CompView(comp=c) for c in design.components}
    pin_counts: dict[str, set[str]] = {}
    for net in design.nets:
        for pad in net.connected_pads:
            refdes, pin = _pad_to_refdes_pin(pad, design.id)
            pin_counts.setdefault(refdes, set()).add(pin)
    raw_pins = {refdes: len(pins) for refdes, pins in pin_counts.items()}
    for net in sorted(design.nets, key=lambda n: n.name):
        for pad in net.connected_pads:
            refdes, pin = _pad_to_refdes_pin(pad, design.id)
            view = views[refdes]
            norm = _normalize_pin(view.comp, pin, config, raw_pins.get(refdes, 0))
            existing = view.pin_nets.get(norm, ())
            view.pin_nets[norm] = tuple(sorted({*existing, net.name}))
    return views


# ── Pin-neighborhood similarity ────────────────────────────────────────


def _neighbor_profile(view: _CompView, views_by_net: dict[str, set[str]],
                      views: dict[str, _CompView]) -> dict[str, frozenset[str]]:
    """normalized pin -> the set of neighbor component part_keys across its nets."""
    profile: dict[str, frozenset[str]] = {}
    for pin, nets in view.pin_nets.items():
        neighbors: set[str] = set()
        for net in nets:
            for other_refdes in views_by_net.get(net, ()):  # type: ignore[arg-type]
                if other_refdes != view.comp.refdes:
                    neighbors.add(views[other_refdes].part_key or "?")
        profile[pin] = frozenset(neighbors)
    return profile


def _pin_similarity(a: dict[str, frozenset[str]], b: dict[str, frozenset[str]]) -> float:
    """Dice-style similarity over pin neighborhood profiles."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    score = 0.0
    for key in keys:
        pa, pb = a.get(key), b.get(key)
        if pa is None or pb is None:
            continue
        if not pa and not pb:
            score += 1.0
        else:
            inter = len(pa & pb)
            denom = len(pa) + len(pb)
            score += (2.0 * inter / denom) if denom else 0.0
    return score / len(keys)


def _component_similarity(gen: _CompView, ref: _CompView,
                          gen_profile: dict[str, frozenset[str]],
                          ref_profile: dict[str, frozenset[str]]) -> float:
    part_score = 1.0 if (gen.part_key and gen.part_key == ref.part_key) else 0.0
    pin_score = _pin_similarity(gen_profile, ref_profile)
    # part identity dominates; neighborhood breaks ties between same-part instances
    return 0.6 * part_score + 0.4 * pin_score


# ── Hungarian assignment (pure Python Kuhn–Munkres, O(n^3)) ────────────


def _hungarian_max(matrix: list[list[float]]) -> list[tuple[int, int]]:
    """Maximize total similarity. Returns (row, col) pairs.

    Implements the O(n^3) potentials algorithm on the squared/padded cost
    matrix (cost = max - value). Deterministic for equal inputs.
    """
    if not matrix or not matrix[0]:
        return []
    n_rows, n_cols = len(matrix), len(matrix[0])
    n = max(n_rows, n_cols)
    big = max(max(row) for row in matrix) if matrix else 0.0
    # padded square cost matrix
    cost = [[big - (matrix[i][j] if i < n_rows and j < n_cols else 0.0)
             for j in range(n)] for i in range(n)]

    INF = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)   # p[j] = row matched to column j (1-based)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    pairs = []
    for j in range(1, n + 1):
        i = p[j]
        if 1 <= i <= n_rows and 1 <= j <= n_cols:
            pairs.append((i - 1, j - 1))
    return sorted(pairs)


# ── Two-stage matching ─────────────────────────────────────────────────


@dataclass(slots=True)
class ComponentMatch:
    generated_refdes: str
    reference_refdes: str
    similarity: float
    part_match: bool
    value_match: bool | None  # None when neither side declares a value


def _match_components(
    gen_views: dict[str, _CompView],
    ref_views: dict[str, _CompView],
    gen_profiles: dict[str, dict[str, frozenset[str]]],
    ref_profiles: dict[str, dict[str, frozenset[str]]],
    config: ScoringConfig,
) -> tuple[list[ComponentMatch], list[str], list[str], list[str]]:
    """Returns (matches, missing_required, missing_optional, extra_generated)."""

    def run_stage(ref_pool: list[str], gen_pool: list[str]) -> list[ComponentMatch]:
        if not ref_pool or not gen_pool:
            return []
        matrix = [
            [_component_similarity(gen_views[g], ref_views[r], gen_profiles[g], ref_profiles[r])
             for r in ref_pool]
            for g in gen_pool
        ]
        matches: list[ComponentMatch] = []
        for gi, ri in _hungarian_max(matrix):
            sim = matrix[gi][ri]
            if sim < config.min_match_similarity:
                continue
            gen_v, ref_v = gen_views[gen_pool[gi]], ref_views[ref_pool[ri]]
            gv = (gen_v.comp.value or "").strip().lower()
            rv = (ref_v.comp.value or "").strip().lower()
            matches.append(ComponentMatch(
                generated_refdes=gen_v.comp.refdes,
                reference_refdes=ref_v.comp.refdes,
                similarity=round(sim, 6),
                part_match=bool(gen_v.part_key and gen_v.part_key == ref_v.part_key),
                value_match=(gv == rv) if (gv or rv) else None,
            ))
        return matches

    ref_required = sorted(r for r, v in ref_views.items() if not v.comp.optional)
    ref_optional = sorted(r for r, v in ref_views.items() if v.comp.optional)
    gen_all = sorted(gen_views)

    # Stage 1: required reference components claim generated components first.
    stage1 = run_stage(ref_required, gen_all)
    used_gen = {m.generated_refdes for m in stage1}
    matched_ref = {m.reference_refdes for m in stage1}

    # Stage 2: optional reference components match remaining generated ones.
    remaining_gen = sorted(set(gen_all) - used_gen)
    stage2 = run_stage(ref_optional, remaining_gen)
    used_gen |= {m.generated_refdes for m in stage2}
    matched_ref |= {m.reference_refdes for m in stage2}

    missing_required = sorted(set(ref_required) - matched_ref)
    missing_optional = sorted(set(ref_optional) - matched_ref)
    extra_generated = sorted(set(gen_all) - used_gen)
    matches = sorted(stage1 + stage2, key=lambda m: m.reference_refdes)
    return matches, missing_required, missing_optional, extra_generated
