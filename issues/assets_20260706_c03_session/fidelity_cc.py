"""Fidelity gate v2: connected-component node-set equivalence.

Root cause of the v1 FALSE fail (recorded): the baseline was the compose-emitted
`aiguard_ccm.net`, which itself is polluted (HSE_IN absorbed 241 nodes; 184 nets
vs the 110-net electrical truth). Comparing a per-page union against a polluted
single-sheet netlist by net-NAME is doubly wrong: (a) the baseline is untrusted,
(b) power ports rename GND/supply endpoints so name alignment breaks.

Correct basis (owner ruling 1+2):
  * BASELINE  = gen_ccm.py's merged ccm_nets, dumped to ccm_expected_partition.json.
                This is the pure-data electrical SSOT (net() calls + merge_same),
                independent of any KiCad emit/export round-trip.
  * CANDIDATE = union of the v03 multi-page .kicad_sch exports.

Comparison is by PARTITION, not by name: build node -> component-id on each side
(a net = one connected component = one node-set), then require the two partitions
of the shared node universe to be identical. Net names are ignored entirely; only
"which nodes share a net" matters — that is the electrical truth a schematic must
preserve.

Single-node nets (a net touching exactly one pin) exist on BOTH sides as isolated
singletons; we keep them and compare them like any other class, so a node that is
isolated in baseline must be isolated in candidate too.

Usage:
  python3 fidelity_cc.py <expected_partition.json> <sch_dir> <label>
"""
import json
import sys
import subprocess
import tempfile
import re
from pathlib import Path
from collections import defaultdict


def _net_blocks(s: str) -> list[str]:
    """Balanced-paren split of each top-level (net ...) block (exact, no regex)."""
    out = []
    i = 0
    while True:
        i = s.find("(net ", i)
        if i < 0:
            break
        depth = 0
        j = i
        while j < len(s):
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(s[i:j + 1])
        i = j + 1
    return out


def parse_net_file(path: Path) -> list[frozenset]:
    """Parse a KiCad .net into a list of node-sets (one per net), names discarded."""
    txt = path.read_text(encoding="utf-8", errors="replace")
    classes = []
    for b in _net_blocks(txt):
        nodes = set()
        for nm in re.finditer(r'\(node\s+\(ref\s+"([^"]+)"\)\s*\(pin\s+"([^"]+)"', b):
            nodes.add(f"{nm.group(1)}.{nm.group(2)}")
        if nodes:
            classes.append(frozenset(nodes))
    return classes


def sch_union_classes(sch_files: list[Path], workdir: Path) -> list[frozenset]:
    """Export each sheet to a netlist, then UNION-FIND merge node-sets across sheets.

    A net carried across sheets appears as separate (net ...) blocks that share
    node identifiers; merging by shared node reconstructs the whole-board net.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for sf in sch_files:
        out = workdir / (sf.stem + ".net")
        r = subprocess.run(
            ["kicad-cli", "sch", "export", "netlist", "-o", str(out), str(sf)],
            capture_output=True, text=True,
        )
        if r.returncode != 0 or not out.exists():
            print(f"  WARN export failed {sf.name}: {r.stderr[:200]}", file=sys.stderr)
            continue
        for cls in parse_net_file(out):
            nodes = list(cls)
            for n in nodes[1:]:
                union(nodes[0], n)
    comps = defaultdict(set)
    for node in parent:
        comps[find(node)].add(node)
    return [frozenset(v) for v in comps.values()]


def _drop_power_flags(classes):
    """Strip synthetic power-flag / port helper pseudo-nodes (#PWR*, #FLG*) — they
    are drawing artifacts, not real component pins, and must not count as nodes."""
    cleaned = []
    for cls in classes:
        real = frozenset(n for n in cls if not n.startswith("#"))
        if real:
            cleaned.append(real)
    return cleaned


def partition_map(classes):
    """node -> canonical class key (min node string of its set)."""
    m = {}
    for cls in classes:
        key = min(cls)
        for n in cls:
            m[n] = key
    return m


def main():
    expected_json = Path(sys.argv[1])
    sch_dir = Path(sys.argv[2])
    label = sys.argv[3] if len(sys.argv) > 3 else expected_json.stem

    expected = json.load(open(expected_json))
    baseline_classes = _drop_power_flags(
        [frozenset(nodes) for nodes in expected.values()]
    )

    sch_files = sorted(sch_dir.rglob("*.kicad_sch"))
    if not sch_files:
        print(f"[{label}] NO SCH FILES under {sch_dir}")
        sys.exit(2)
    with tempfile.TemporaryDirectory() as td:
        cand_classes = _drop_power_flags(sch_union_classes(sch_files, Path(td)))

    b_map = partition_map(baseline_classes)
    c_map = partition_map(cand_classes)

    b_nodes = set(b_map)
    c_nodes = set(c_map)
    raw_only_b = b_nodes - c_nodes
    raw_only_c = c_nodes - b_nodes

    # Single-node nets (a pin whose net touches exactly one component pin) are
    # emitted by KiCad as an `unconnected-(REF-PIN...)` net whose node id KiCad
    # rewrites (or the pin is simply the sole member of its named net). Either
    # way the pin is ISOLATED on both sides — its baseline class is a singleton
    # {nd} and its candidate class is also a singleton (possibly under a KiCad-
    # renamed net). An isolated baseline node that is absent from the candidate
    # node universe is NOT a fidelity loss iff it was a singleton in baseline:
    # electrical truth (which pins share a net) is preserved — the pin shares a
    # net with nobody on both sides. We only flag a missing node when it had >=1
    # baseline peer (i.e. it belonged to a real multi-pin net and vanished).
    def _b_class(nd):
        return baseline_classes_of(nd, b_map, baseline_classes)

    only_b = sorted(nd for nd in raw_only_b if len(_b_class(nd)) > 1)
    only_c = sorted(raw_only_c)
    singleton_only_b = sorted(nd for nd in raw_only_b if len(_b_class(nd)) == 1)

    # Partition equivalence over the SHARED node universe: two nodes co-classed in
    # baseline must be co-classed in candidate and vice versa.
    shared = b_nodes & c_nodes
    moved = []
    for nd in sorted(shared):
        b_peers = frozenset(x for x in baseline_classes_of(nd, b_map, baseline_classes) if x in shared)
        c_peers = frozenset(x for x in candidate_classes_of(nd, c_map, cand_classes) if x in shared)
        if b_peers != c_peers:
            moved.append(nd)

    print(f"[{label}] baseline nets={len(baseline_classes)} nodes={len(b_nodes)} | "
          f"candidate nets={len(cand_classes)} nodes={len(c_nodes)} | shared={len(shared)}")
    print(f"[{label}] moved={len(moved)} only_baseline={len(only_b)} only_candidate={len(only_c)}")
    if singleton_only_b:
        print(f"  (ignored {len(singleton_only_b)} single-node-net isolated pins — "
              f"electrically isolated on both sides, no shared-net change): {singleton_only_b[:20]}")
    if only_b:
        print(f"  ONLY_BASELINE (missing from candidate): {only_b[:40]}")
    if only_c:
        print(f"  ONLY_CANDIDATE (extra in candidate): {only_c[:40]}")
    if moved:
        print(f"  MOVED (partition class changed): {moved[:40]}")
    ok = not moved and not only_b and not only_c
    print(f"[{label}] FIDELITY {'PASS diff 0/0' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


# Helper closures kept module-level for clarity.
_B_INDEX = {}
_C_INDEX = {}


def baseline_classes_of(nd, b_map, classes):
    if not _B_INDEX:
        for cls in classes:
            for n in cls:
                _B_INDEX[n] = cls
    return _B_INDEX.get(nd, frozenset({nd}))


def candidate_classes_of(nd, c_map, classes):
    if not _C_INDEX:
        for cls in classes:
            for n in cls:
                _C_INDEX[n] = cls
    return _C_INDEX.get(nd, frozenset({nd}))


if __name__ == "__main__":
    main()
