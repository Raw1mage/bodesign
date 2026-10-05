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


def assign_motif_lanes(motifs: list[Motif], pin_maps: dict) -> dict[Motif, int]:
    """Allocate non-colliding lateral lanes for motifs attached to host ICs.

    Motifs attached to the same host IC and edge are assigned lanes (columns offset
    by dx * (5.08 + lane * 12.7)) such that:
      1. No two motifs in the same lane overlap vertically.
      2. A motif's horizontal connection wire does not cross through any motif
         in inner lanes (unless sharing the same host pin and net).
      3. No outer lane motif's horizontal connection wire crosses through this motif.

    Pins on each host edge are sorted by schematic Y descending (bottom to top),
    so downward-hanging passives on lower pins take inner lanes, allowing higher
    pins' horizontal wires to cross freely above them to reach outer lanes.
    """
    grouped: dict[tuple[str, int], list[Motif]] = {}
    for m in motifs:
        hp = pin_maps[m.host[0]][m.host[1]]
        rot = int(hp[2]) % 360
        key = (m.host[0], rot)
        grouped.setdefault(key, []).append(m)

    assignments: dict[Motif, int] = {}
    for key, mlist in grouped.items():
        # Sort by schematic Y descending (-hp[1] descending), then pin, then first branch ref
        mlist.sort(
            key=lambda m: (-pin_maps[m.host[0]][m.host[1]][1], m.host[1], m.branches[0][0]),
            reverse=True,
        )
        placed_in_lane: dict[int, list[tuple[Motif, float, float, float]]] = {}
        for m in mlist:
            g0 = synthesize_motif_geometry(m, pin_maps, lane=0)
            all_y = [g0.tap[1]]
            all_y.extend(y for (x, y) in g0.pin_alignments.values())
            all_y.extend(y for (x, y) in g0.ground_glyphs.values())
            y_min = min(all_y) - 1.27
            y_max = max(all_y) + 2.54
            tap_y = g0.tap[1]

            target_lane = 0
            while True:
                # Invariant 1: No vertical overlap with motifs in target_lane
                inv1 = True
                for (om, oy_min, oy_max, otap_y) in placed_in_lane.get(target_lane, []):
                    if not (y_max < oy_min or y_min > oy_max):
                        inv1 = False
                        break
                if not inv1:
                    target_lane += 1
                    continue

                # Invariant 2: Horizontal wire at tap_y clears inner lanes k < target_lane
                inv2 = True
                for k in range(target_lane):
                    for (om, oy_min, oy_max, otap_y) in placed_in_lane.get(k, []):
                        if om.host == m.host and om.net == m.net:
                            continue  # Parallel branch sharing same pin & net
                        if oy_min <= tap_y <= oy_max:
                            inv2 = False
                            break
                    if not inv2:
                        break
                if not inv2:
                    target_lane += 1
                    continue

                # Invariant 3: Outer lanes' wires do not pass through this motif
                inv3 = True
                for j in [l for l in placed_in_lane if l > target_lane]:
                    for (om, oy_min, oy_max, otap_y) in placed_in_lane.get(j, []):
                        if om.host == m.host and om.net == m.net:
                            continue
                        if y_min <= otap_y <= y_max:
                            inv3 = False
                            break
                    if not inv3:
                        break
                if not inv3:
                    target_lane += 1
                    continue

                break

            assignments[m] = target_lane
            placed_in_lane.setdefault(target_lane, []).append((m, y_min, y_max, tap_y))

    return assignments
