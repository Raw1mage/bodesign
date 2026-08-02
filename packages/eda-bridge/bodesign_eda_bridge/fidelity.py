"""Post-emit schematic fidelity gate (BR1 · 2026-07-06).

Battle-proven in the aiguard C03 v03 session: caught GND(141)/BAT_SENSE(177)/
+3V3_PB(189) collinear-wire fusion shorts that `validate=True` (ERC + netlist
export) passed silently. ERC is blind to net FUSION — fewer nets, no dangling,
ERC actually looks cleaner.

Principle: compare by PARTITION, not by net NAME. The electrical truth a
schematic must preserve is "which pins share a net". Build node-sets on both
sides (expected spec partition vs KiCad-exported netlist connected components),
then require the two partitions of the shared node universe to be identical.
Net names are ignored entirely — power ports rename GND/supply endpoints so
name alignment is unreliable.

Seed: issues/assets_20260706_c03_session/fidelity_cc.py (verified).
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FidelityReport:
    ok: bool
    baseline_nets: int
    baseline_nodes: int
    candidate_nets: int
    candidate_nodes: int
    shared: int
    moved: list[str] = field(default_factory=list)          # partition-class changed
    only_baseline: list[str] = field(default_factory=list)  # missing from candidate (had peers)
    only_candidate: list[str] = field(default_factory=list) # extra in candidate
    singleton_only_baseline: list[str] = field(default_factory=list)  # ignored isolated pins
    singleton_only_candidate: list[str] = field(default_factory=list)  # ditto, candidate side
    # BR_20260802 (instrument repair): `moved` says a node's partition class
    # changed but NOT which way, so an OPEN CIRCUIT and a SHORT read identically.
    # These three refine it by the DIRECTION of the peer-set change, so the gate
    # can name the mechanism it actually measured instead of asserting one.
    disconnected: list[str] = field(default_factory=list)  # peers LOST only  -> open circuit
    fused: list[str] = field(default_factory=list)         # peers GAINED only -> short / fusion
    regrouped: list[str] = field(default_factory=list)     # lost AND gained   -> re-partition

    def diagnosis(self) -> list[str]:
        """Mechanism names DERIVED from what was measured — never asserted.

        Returns the mechanisms this report actually evidences, most specific
        first. An empty list means the partition matched (or the divergence is
        of a shape this gate cannot name — in which case it says exactly that,
        rather than naming a mechanism it did not observe).
        """
        out: list[str] = []
        if self.disconnected:
            out.append(f"open circuit: {len(self.disconnected)} node(s) lost every peer "
                       f"they share a net with in the spec")
        if self.fused:
            out.append(f"net fusion / short: {len(self.fused)} node(s) gained peers "
                       f"they must not be connected to")
        if self.regrouped:
            out.append(f"re-partition: {len(self.regrouped)} node(s) both lost and "
                       f"gained peers")
        if self.only_baseline:
            out.append(f"node absent from candidate: {len(self.only_baseline)} node(s) "
                       f"the spec declares are not present in the emitted schematic "
                       f"at all")
        if self.only_candidate:
            out.append(f"node absent from spec: {len(self.only_candidate)} node(s) exist "
                       f"in the emitted schematic but not in the spec")
        return out

    def summary(self) -> str:
        head = (f"baseline nets={self.baseline_nets} nodes={self.baseline_nodes} | "
                f"candidate nets={self.candidate_nets} nodes={self.candidate_nodes} | "
                f"shared={self.shared}")
        verdict = ("FIDELITY PASS diff 0/0" if self.ok else
                   f"FIDELITY FAIL moved={len(self.moved)} "
                   f"only_baseline={len(self.only_baseline)} "
                   f"only_candidate={len(self.only_candidate)}")
        lines = [head, verdict]
        if not self.ok:
            dx = self.diagnosis()
            if dx:
                lines.append("  MEASURED MECHANISM:")
                lines.extend(f"    - {d}" for d in dx)
            else:
                # Never silently imply a mechanism we did not observe.
                lines.append("  MEASURED MECHANISM: none of the known shapes matched "
                             "— divergence is real but unclassified")
        if self.moved:
            lines.append(f"  MOVED (partition class changed): {self.moved[:40]}")
        if self.only_baseline:
            lines.append(f"  ONLY_BASELINE (missing from candidate): {self.only_baseline[:40]}")
        if self.only_candidate:
            lines.append(f"  ONLY_CANDIDATE (extra in candidate): {self.only_candidate[:40]}")
        return "\n".join(lines)


class FidelityError(RuntimeError):
    """Raised (fail-loud) when a composed schematic's partition diverges from spec."""

    def __init__(self, report: FidelityReport):
        self.report = report
        # BR_20260802 (instrument repair): the mechanism named here is DERIVED
        # from the report, never hardcoded. The previous message asserted
        # "(collinear-wire fusion / label collision)" for EVERY divergence; two
        # readers independently went looking for a fusion that was not there,
        # because the instrument named a cause it had not measured.
        dx = report.diagnosis()
        cause = "; ".join(dx) if dx else "mechanism unclassified"
        super().__init__("schematic fidelity gate FAILED — net partition diverged "
                         f"from spec ({cause}):\n"
                         + report.summary())


def _net_blocks(s: str) -> list[str]:
    """Balanced-paren split of each top-level (net ...) block."""
    out: list[str] = []
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
    """Parse a KiCad .net into node-sets (one per net); names discarded."""
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
    """Export each sheet to netlist, then UNION-FIND merge node-sets across sheets.

    A net carried across sheets appears as separate (net ...) blocks sharing node
    identifiers; merging by shared node reconstructs the whole-board net.
    """
    parent: dict = {}

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
            continue
        for cls in parse_net_file(out):
            nodes = list(cls)
            # BR_20260802 (fidelity instrument repair): SEED every node before
            # unioning. The previous loop only touched nodes[1:], so a SINGLE-node
            # net (`unconnected-(R1-Pad1)`) never entered `parent` at all and
            # vanished from the candidate universe entirely. That made
            # `only_candidate` STRUCTURALLY unable to be non-zero for an
            # open-circuit pin: the node was not "extra", it was invisible. Two
            # readers independently mis-diagnosed a broken net as a FUSION because
            # of exactly this. Seeding is a no-op for multi-node nets (find()
            # already self-parents them on the first union).
            for n in nodes:
                find(n)
            for n in nodes[1:]:
                union(nodes[0], n)
    comps = defaultdict(set)
    for node in parent:
        comps[find(node)].add(node)
    return [frozenset(v) for v in comps.values()]


def _drop_power_flags(classes):
    """Strip synthetic power-flag/port pseudo-nodes (#PWR*, #FLG*) — drawing
    artifacts, not real component pins."""
    cleaned = []
    for cls in classes:
        real = frozenset(n for n in cls if not n.startswith("#"))
        if real:
            cleaned.append(real)
    return cleaned


def _index(classes):
    idx = {}
    for cls in classes:
        for n in cls:
            idx[n] = cls
    return idx


def expected_partition_from_nets(nets) -> dict[str, list[str]]:
    """Build the expected partition from spec nets (the electrical SSOT).

    `nets` is an iterable of objects/dicts exposing name + nodes; nodes are
    "REF.PIN" strings or (ref, pin) tuples. A net = one node-set = one class.
    This is the pure-data truth, independent of any KiCad emit/export round-trip.
    """
    part: dict[str, list[str]] = {}
    for net in nets:
        name = getattr(net, "name", None) or (net.get("name") if isinstance(net, dict) else None)
        raw_nodes = getattr(net, "nodes", None)
        if raw_nodes is None and isinstance(net, dict):
            raw_nodes = net.get("nodes", [])
        nodes = []
        for nd in raw_nodes or []:
            if isinstance(nd, (tuple, list)) and len(nd) == 2:
                nodes.append(f"{nd[0]}.{nd[1]}")
            else:
                nodes.append(str(nd))
        if name and nodes:
            part[str(name)] = nodes
    return part


def compare_partitions(expected: dict[str, list[str]],
                       candidate_classes: list[frozenset]) -> FidelityReport:
    baseline_classes = _drop_power_flags(
        [frozenset(nodes) for nodes in expected.values()])
    cand_classes = _drop_power_flags(candidate_classes)

    b_idx = _index(baseline_classes)
    c_idx = _index(cand_classes)
    b_nodes = set(b_idx)
    c_nodes = set(c_idx)
    raw_only_b = b_nodes - c_nodes
    raw_only_c = c_nodes - b_nodes

    # Singleton baseline nets (a pin isolated on both sides) are not a loss: the
    # pin shares a net with nobody either way. Only flag a missing node that had
    # >=1 baseline peer (belonged to a real multi-pin net and vanished).
    only_b = sorted(nd for nd in raw_only_b if len(b_idx.get(nd, {nd})) > 1)
    singleton_only_b = sorted(nd for nd in raw_only_b if len(b_idx.get(nd, {nd})) == 1)
    # BR_20260802 (instrument repair, symmetry): the SAME exemption on the
    # candidate side. A candidate node the spec never mentions is only a fidelity
    # violation if it CONNECTS to something — an isolated pin (e.g. the 34 unused
    # ways of a 40-pin connector, which kicad-cli emits as `unconnected-(J1-PadN)`)
    # shares a net with nobody and therefore cannot short anything.
    #
    # This asymmetry was invisible until the union-find seeding fix above: before
    # it, a singleton candidate net could never reach `raw_only_c` at all, so the
    # missing exemption had nothing to act on. Fixing one defect exposed the other
    # — they are the same defect seen from the two sides of the comparison.
    #
    # Kept VISIBLE (`singleton_only_candidate`), never silently dropped: an
    # exemption the reader cannot see is indistinguishable from a check that was
    # never made.
    only_c = sorted(nd for nd in raw_only_c if len(c_idx.get(nd, {nd})) > 1)
    singleton_only_c = sorted(nd for nd in raw_only_c if len(c_idx.get(nd, {nd})) == 1)

    shared = b_nodes & c_nodes
    moved = []
    # BR_20260802 (instrument repair): classify each moved node by the DIRECTION
    # of its peer-set change. `moved` alone cannot tell an open circuit from a
    # short — both are "partition class changed". Losing peers only == the net was
    # cut; gaining peers only == two nets were welded together; both == the
    # partition was reshuffled. The gate must report the one it measured.
    disconnected, fused, regrouped = [], [], []
    for nd in sorted(shared):
        b_peers = frozenset(x for x in b_idx.get(nd, frozenset({nd})) if x in shared)
        c_peers = frozenset(x for x in c_idx.get(nd, frozenset({nd})) if x in shared)
        if b_peers != c_peers:
            moved.append(nd)
            lost = b_peers - c_peers
            gained = c_peers - b_peers
            if lost and gained:
                regrouped.append(nd)
            elif lost:
                disconnected.append(nd)
            else:
                fused.append(nd)

    ok = not moved and not only_b and not only_c
    return FidelityReport(
        ok=ok,
        baseline_nets=len(baseline_classes), baseline_nodes=len(b_nodes),
        candidate_nets=len(cand_classes), candidate_nodes=len(c_nodes),
        shared=len(shared),
        moved=moved, only_baseline=only_b, only_candidate=only_c,
        singleton_only_baseline=singleton_only_b,
        singleton_only_candidate=singleton_only_c,
        disconnected=disconnected, fused=fused, regrouped=regrouped,
    )


def verify_partition_fidelity(expected_nets, sch_path: str | Path) -> FidelityReport:
    """Whole check: expected spec nets vs the KiCad-exported partition of the
    schematic file (or every *.kicad_sch under a directory).

    expected_nets: iterable of EmitNet-like (name + nodes) OR a ready dict
    {netname: [REF.PIN,...]}.
    """
    if isinstance(expected_nets, dict):
        expected = expected_nets
    else:
        expected = expected_partition_from_nets(expected_nets)

    p = Path(sch_path)
    sch_files = sorted(p.rglob("*.kicad_sch")) if p.is_dir() else [p]
    if not sch_files:
        raise FileNotFoundError(f"no .kicad_sch under {p}")
    with tempfile.TemporaryDirectory() as td:
        cand = sch_union_classes(sch_files, Path(td))
    return compare_partitions(expected, cand)
