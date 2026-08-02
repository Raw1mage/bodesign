"""BR_20260802 instrument repair: the fidelity gate must report the mechanism it
MEASURED, and must be structurally capable of seeing an open circuit.

Two defects this pins down (both found while doing the RCA on the gate's own red
light, and both of which made two independent readers diagnose a FUSION that was
never there):

1. `sch_union_classes` only unioned `nodes[1:]`, so a SINGLE-node net
   (`unconnected-(R1-Pad1)` — exactly what an open circuit produces) never entered
   the union-find `parent` dict and vanished from the candidate universe. That made
   `only_candidate` structurally unable to be non-zero for a broken net.
2. `FidelityError` hardcoded "(collinear-wire fusion / label collision)" for EVERY
   divergence — naming a cause it had not measured.

Every test here carries a control: an assertion that the same instrument reports
something DIFFERENT for the opposite input, so a vacuous "always passes" check
cannot masquerade as a real one.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.fidelity import (
    FidelityError,
    compare_partitions,
    expected_partition_from_nets,
    parse_net_file,
    sch_union_classes,
)

# One 2-pin net (N1) and one 3-pin net (GND). The spec's electrical truth.
SPEC_NETS = [
    {"name": "N1", "nodes": ["J1.1", "R1.1"]},
    {"name": "GND", "nodes": ["R1.2", "R2.2", "J1.2"]},
]

# A KiCad netlist in which N1 has been CUT: each of its pins is alone on its own
# auto-named net, which is literally what kicad-cli emits for an unconnected pin.
NETLIST_OPEN_CIRCUIT = """
(export (version "E")
  (nets
    (net (code "1") (name "GND")
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "R2") (pin "2") (pintype "passive"))
      (node (ref "J1") (pin "2") (pintype "passive")))
    (net (code "2") (name "unconnected-(J1-Pad1)")
      (node (ref "J1") (pin "1") (pintype "passive")))
    (net (code "3") (name "unconnected-(R1-Pad1)")
      (node (ref "R1") (pin "1") (pintype "passive")))))
"""

# The same board with N1 intact — the control.
NETLIST_FAITHFUL = """
(export (version "E")
  (nets
    (net (code "1") (name "GND")
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "R2") (pin "2") (pintype "passive"))
      (node (ref "J1") (pin "2") (pintype "passive")))
    (net (code "2") (name "N1")
      (node (ref "J1") (pin "1") (pintype "passive"))
      (node (ref "R1") (pin "1") (pintype "passive")))))
"""


def _parse(text: str):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.net"
        p.write_text(text, encoding="utf-8")
        return parse_net_file(p)


class SingleNodeNetSurvivesUnionFind(unittest.TestCase):
    """Defect 1: an open-circuit pin must stay in the candidate universe."""

    def _universe(self, netlist_text: str):
        """Run the REAL sch_union_classes over a stubbed kicad-cli export."""
        classes = _parse(netlist_text)
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            sch = work / "board.kicad_sch"
            sch.write_text("(kicad_sch)", encoding="utf-8")
            # Stub the export: write the fixture where sch_union_classes will read it.
            real_run = subprocess.run

            def fake_run(cmd, *a, **kw):
                Path(cmd[cmd.index("-o") + 1]).write_text(netlist_text, encoding="utf-8")
                return subprocess.CompletedProcess(cmd, 0, "", "")

            subprocess.run = fake_run
            try:
                out = sch_union_classes([sch], work)
            finally:
                subprocess.run = real_run
        return set().union(*out) if out else set()

    def test_open_circuit_pin_is_not_dropped_from_the_universe(self):
        universe = self._universe(NETLIST_OPEN_CIRCUIT)
        for pin in ("J1.1", "R1.1"):
            self.assertIn(pin, universe,
                          f"{pin} is an open-circuit pin; dropping it from the "
                          f"candidate universe is what made only_candidate "
                          f"structurally unable to be non-zero")

    def test_universe_matches_the_raw_netlist_exactly(self):
        # Control: the union-find universe must equal what the parser saw. If the
        # two ever diverge again, this fails regardless of which node was lost.
        raw = set().union(*_parse(NETLIST_OPEN_CIRCUIT))
        self.assertEqual(self._universe(NETLIST_OPEN_CIRCUIT), raw)

    def test_multi_node_net_still_merges(self):
        # Control in the OTHER direction: seeding must not stop nets from merging.
        classes = _parse(NETLIST_FAITHFUL)
        gnd = [c for c in classes if "R1.2" in c][0]
        self.assertEqual(gnd, frozenset({"R1.2", "R2.2", "J1.2"}))


class DiagnosisIsDerivedNotAsserted(unittest.TestCase):
    """Defect 2: the named mechanism must be the one actually measured."""

    def _report(self, netlist_text: str):
        return compare_partitions(expected_partition_from_nets(SPEC_NETS),
                                  _parse(netlist_text))

    def test_open_circuit_is_named_open_circuit(self):
        rep = self._report(NETLIST_OPEN_CIRCUIT)
        self.assertFalse(rep.ok)
        self.assertEqual(sorted(rep.disconnected), ["J1.1", "R1.1"])
        self.assertEqual(rep.fused, [], "nothing gained peers; nothing was fused")
        joined = " ".join(rep.diagnosis()).lower()
        self.assertIn("open circuit", joined)
        self.assertNotIn("fusion", joined,
                         "the gate must not name a mechanism it did not measure")

    def test_fusion_is_named_fusion(self):
        # The opposite input: N1 and GND welded into one net. Same instrument,
        # different verdict -> proves the classifier discriminates.
        fused_candidate = [frozenset({"J1.1", "R1.1", "R1.2", "R2.2", "J1.2"})]
        rep = compare_partitions(expected_partition_from_nets(SPEC_NETS),
                                 fused_candidate)
        self.assertFalse(rep.ok)
        self.assertEqual(rep.disconnected, [], "nothing lost peers; nothing was cut")
        self.assertTrue(rep.fused)
        joined = " ".join(rep.diagnosis()).lower()
        self.assertIn("fusion", joined)
        self.assertNotIn("open circuit", joined)

    def test_faithful_board_passes_and_names_nothing(self):
        rep = self._report(NETLIST_FAITHFUL)
        self.assertTrue(rep.ok, rep.summary())
        self.assertEqual(rep.diagnosis(), [])

    def test_error_message_carries_the_measured_mechanism(self):
        rep = self._report(NETLIST_OPEN_CIRCUIT)
        msg = str(FidelityError(rep))
        self.assertIn("open circuit", msg.lower())
        self.assertNotIn("collinear-wire fusion / label collision", msg,
                         "the hardcoded cause must be gone from the raised message")

    def test_error_message_differs_between_the_two_mechanisms(self):
        # Control: if both inputs produced the same message, the assertions above
        # would pass vacuously on any hardcoded string containing both words.
        open_msg = str(FidelityError(self._report(NETLIST_OPEN_CIRCUIT)))
        fused_msg = str(FidelityError(compare_partitions(
            expected_partition_from_nets(SPEC_NETS),
            [frozenset({"J1.1", "R1.1", "R1.2", "R2.2", "J1.2"})])))
        self.assertNotEqual(open_msg, fused_msg)


if __name__ == "__main__":
    unittest.main()
