"""Deterministic, topology-only passive motifs for the P1 schematic pipeline.

Recognition is deliberately conservative: a shared rail does not establish
which of several ICs owns a capacitor. Ambiguous hosts are not guessed.
Coordinates use sheet axes (y down); pin maps use KiCad library axes (y up).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Motif:
    kind: str
    host: tuple[str, str]
    # (ref, pin on host/tap net, opposite pin), in template order.
    branches: tuple[tuple[str, str, str], ...]
    net: str
    ground_nodes: tuple[tuple[str, str], ...] = ()


@dataclass
class MotifGeometry:
    offsets: dict[str, tuple[float, float]]
    ground_glyphs: dict[tuple[str, str], tuple[float, float]]
    pin_alignments: dict[tuple[str, str], tuple[float, float]]
    net: str
    nodes: tuple[tuple[str, str], ...]
    tap: tuple[float, float]


def detect_motifs(components, nets) -> list[Motif]:
    """Recognize non-overlapping motifs from composer-style component/net dicts.

    Divider and RC templates take precedence over singleton pull/shunt motifs.
    Rail semantics come from explicit kind or the emitter's canonical predicate;
    values never imply an electrical function or a component requirement.
    """
    from .kicad_emit import _power_net_kind

    comps = {c["ref"]: c for c in components}
    if len(comps) != len(components):
        raise ValueError("MOTIF_DUPLICATE_REF")
    members, kinds, by_pin = {}, {}, {}
    for net in nets:
        name = net["name"]
        if name in members:
            raise ValueError(f"MOTIF_DUPLICATE_NET: {name}")
        nodes = {tuple(n.split(".", 1)) if isinstance(n, str) else tuple(n)
                 for n in net["nodes"]}
        for node in nodes:
            if len(node) != 2 or node[0] not in comps:
                raise ValueError(f"MOTIF_INVALID_NODE: {node}")
            if node in by_pin:
                raise ValueError(f"MOTIF_PIN_MULTIPLE_NETS: {node}")
            by_pin[node] = name
        members[name] = nodes
        declared = net.get("kind")
        kinds[name] = ({"power": "supply", "ground": "gnd"}.get(declared, declared)
                       or _power_net_kind(name))

    def passive(ref):
        return comps[ref].get("symbol", "").split(":")[-1] in {"R", "R_Small", "C", "C_Small"}

    def resistor(ref):
        return comps[ref].get("symbol", "").split(":")[-1] in {"R", "R_Small"}

    def hosts(name):
        return sorted(n for n in members[name] if not passive(n[0])
                      and (comps[n[0]].get("type") == "ic" or n[0].startswith("U")))

    def other(ref, pin):
        pins = sorted(p for r, p in by_pin if r == ref)
        if len(pins) != 2:
            return None
        return next(p for p in pins if p != pin)

    result, claimed = [], set()
    for name in sorted(members):
        hs = hosts(name)
        if len(hs) != 1:
            continue
        branches = []
        for ref, pin in sorted(members[name]):
            if passive(ref) and other(ref, pin) is not None:
                branches.append((ref, pin, other(ref, pin)))
        lows = [b for b in branches if kinds[by_pin[(b[0], b[2])]] == "gnd"]
        series = [b for b in branches if resistor(b[0])
                  and kinds[by_pin[(b[0], b[2])]] != "gnd"]
        # A unique resistor above a shunt defines the pair; multiple candidates
        # are an ambiguous network, not permission to pick the first resistor.
        if len(series) == 1 and len(lows) == 1:
            upper, lower = series[0], lows[0]
            pair = (upper, lower)
            if not any(b[0] in claimed for b in pair):
                kind = "voltage_divider" if resistor(lower[0]) else "rc_filter"
                result.append(Motif(kind, hs[0], pair, name, ((lower[0], lower[2]),)))
                claimed.update(b[0] for b in pair)
    for name in sorted(members):
        hs = hosts(name)
        if len(hs) != 1:
            continue
        for ref, pin in sorted(members[name]):
            if not passive(ref) or ref in claimed:
                continue
            opposite = other(ref, pin)
            if opposite is None:
                continue
            far = by_pin[(ref, opposite)]
            if resistor(ref) and kinds[far] in {"gnd", "supply"} and not kinds[name]:
                kind = "pull_resistor"
            elif not resistor(ref) and kinds[name] == "supply" and kinds[far] == "gnd":
                kind = "decoupling_shunt"
            else:
                continue
            grounds = ((ref, opposite),) if kinds[far] == "gnd" else ()
            result.append(Motif(kind, hs[0], ((ref, pin, opposite),), name, grounds))
            claimed.add(ref)
    return result


def synthesize_motif_geometry(motif: Motif, pin_maps, *, lane: int = 0) -> MotifGeometry:
    """Return host-relative positions using the SAME scaled pin maps as emit.

    This template supports upright, two-pin symbols. Incompatible symbol
    geometry is refused rather than silently rotating electrical pin identities.
    Explicitly placed motifs are handled by the caller, never repositioned here.
    """
    if motif.kind not in {"voltage_divider", "rc_filter", "pull_resistor", "decoupling_shunt"}:
        raise ValueError(f"MOTIF_KIND_UNSUPPORTED: {motif.kind}")
    if lane < 0:
        raise ValueError("MOTIF_INVALID_LANE")
    try:
        hp = pin_maps[motif.host[0]][motif.host[1]]
        # Use the host's true outward direction where available.
        if len(hp) < 3 or int(hp[2]) % 360 not in (0, 180):
            raise ValueError(f"MOTIF_HOST_EDGE_UNSUPPORTED: {motif.host}")
        rot = int(hp[2]) % 360
        dx = -1 if rot == 0 else 1
        tap = (hp[0] + dx * (5.08 + lane * 12.7), -hp[1])
        offsets, alignments = {}, {}
        paired = len(motif.branches) == 2
        for i, (ref, near, far) in enumerate(motif.branches):
            p, q = pin_maps[ref][near], pin_maps[ref][far]
            if abs(p[0] - q[0]) > 1e-6 or abs(p[1] - q[1]) < 1e-6:
                raise ValueError(f"MOTIF_PIN_ALIGNMENT_UNSUPPORTED: {ref}")
            # The upper resistor's near pin must face down; the lower shunt's
            # near pin faces up. Refuse reverse pin numbering explicitly.
            upper = paired and i == 0
            if (upper and p[1] >= q[1]) or (not upper and p[1] <= q[1]):
                raise ValueError(f"MOTIF_PIN_ORIENTATION_UNSUPPORTED: {ref}.{near}")
            target = (tap[0], tap[1] + (-2.54 if upper else (2.54 if paired else 0)))
            offsets[ref] = (round(target[0] - p[0], 4), round(target[1] + p[1], 4))
            for pin, ep in pin_maps[ref].items():
                alignments[(ref, pin)] = (round(offsets[ref][0] + ep[0], 4),
                                          round(offsets[ref][1] - ep[1], 4))
        grounds = {node: (alignments[node][0], round(alignments[node][1] + 2.54, 4))
                   for node in motif.ground_nodes}
    except KeyError as exc:
        raise ValueError(f"MOTIF_PIN_GEOMETRY_MISSING: {exc}") from exc
    return MotifGeometry(offsets, grounds, alignments, motif.net,
                         (motif.host, *((b[0], b[1]) for b in motif.branches)), tap)
