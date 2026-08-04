"""The fidelity gate must say when its own BASELINE is not a partition.

BR_20260802. `expected_partition_from_nets` builds the expected classes straight
from the spec's nets. If the spec declares one pin in several nets, those classes
OVERLAP -- and a set of overlapping classes is not a partition. The gate then
compares against it anyway, which amounts to asking the emitter to keep apart
what the spec declares joined. Every node in the transitive closure of such a pin
lands in `fused` no matter what the emitter does.

Measured on the aiguard C03 page before this was surfaced: 6 such pins, whose
closure accounted for ALL 17 fused nodes with zero left over. Two conclusions
were drawn from that column that day and both were wrong -- not because the
number was miscomputed, but because a reader cannot tell a spec-declared join
from an emitter short by looking at it.

What is asserted here is narrow on purpose:

  * the overlap is DETECTED (and the detector is shown to discriminate, by a
    clean spec that must yield nothing);
  * the qualifier travels WITH the fused count, in the same string, so it cannot
    be separated from the number it qualifies by quoting;
  * it is reported even when nothing fused, because a non-partition baseline is
    a defect in this gate's INPUT and is true regardless of the emitter;
  * it does NOT raise. Whether those declarations are aliases or a missing
    component is a design decision, and a gate that refuses to run has settled
    that decision by force. Asserted explicitly so that "make it fail loud" is
    never implemented as "make it throw" without someone re-reading this.
"""

import unittest

from bodesign_eda_bridge.fidelity import (
    _spec_overlapping_nodes,
    compare_partitions,
    expected_partition_from_nets,
)


# One pin (SHARED.1) declared in two nets -- the shape taken from the real page,
# where J1.A4B9 sits in PP_VBUS, USB_ESD_VBUS and VBUS_5V at once.
OVERLAPPING_NETS = [
    {"name": "NET_A", "nodes": ["SHARED.1", "A1.1"]},
    {"name": "NET_B", "nodes": ["SHARED.1", "B1.1"]},
    {"name": "NET_C", "nodes": ["C1.1", "C2.1"]},
]

CLEAN_NETS = [
    {"name": "NET_A", "nodes": ["A0.1", "A1.1"]},
    {"name": "NET_B", "nodes": ["B0.1", "B1.1"]},
    {"name": "NET_C", "nodes": ["C1.1", "C2.1"]},
]


class TestOverlapDetection(unittest.TestCase):
    def test_a_pin_in_two_nets_is_detected(self):
        ov = _spec_overlapping_nodes(expected_partition_from_nets(OVERLAPPING_NETS))
        self.assertEqual(sorted(ov), ["SHARED.1"])
        self.assertEqual(ov["SHARED.1"], ["NET_A", "NET_B"])

    def test_a_clean_spec_yields_nothing(self):
        """Control for the assertion above.

        Without it, a detector that returned every node would also satisfy the
        first test. This is the pairing the BR's own false disproof lacked: its
        control checked that coordinate matching does not misfire, not that the
        thing being counted was the thing intended.
        """
        self.assertEqual(_spec_overlapping_nodes(expected_partition_from_nets(CLEAN_NETS)), {})

    def test_detection_survives_a_ready_made_dict(self):
        """compare_partitions accepts a prebuilt dict, so the check cannot live
        only in expected_partition_from_nets."""
        rep = compare_partitions({"X": ["P.1", "Q.1"], "Y": ["P.1", "R.1"]},
                                 [frozenset({"P.1", "Q.1", "R.1"})])
        self.assertEqual(sorted(rep.spec_overlapping_nodes), ["P.1"])


class TestTheQualifierTravelsWithTheNumber(unittest.TestCase):
    def _diagnosis(self, nets, candidate):
        return compare_partitions(expected_partition_from_nets(nets), candidate).diagnosis()

    def test_fused_count_carries_the_caveat_in_the_same_string(self):
        # candidate welds NET_A and NET_B together -- exactly what an overlapping
        # spec forces, and what the emitter was blamed for.
        cand = [frozenset({"SHARED.1", "A1.1", "B1.1"}), frozenset({"C1.1", "C2.1"})]
        fused_lines = [d for d in self._diagnosis(OVERLAPPING_NETS, cand) if d.startswith("net fusion")]
        self.assertEqual(len(fused_lines), 1, "expected exactly one fused line")
        self.assertIn("spec declares", fused_lines[0],
                      "the fused count can be quoted without its caveat -- that is the defect")
        self.assertIn("SHARED.1", fused_lines[0])

    def test_a_clean_spec_produces_no_caveat(self):
        """Control: the caveat must not be attached unconditionally."""
        cand = [frozenset({"A0.1", "A1.1", "B0.1", "B1.1"}), frozenset({"C1.1", "C2.1"})]
        fused_lines = [d for d in self._diagnosis(CLEAN_NETS, cand) if d.startswith("net fusion")]
        self.assertEqual(len(fused_lines), 1, "control must still produce a fused line")
        self.assertNotIn("spec declares", fused_lines[0])

    def test_reported_even_when_nothing_fused(self):
        """A non-partition baseline is a defect in the INPUT, true whatever the
        emitter did -- so silence here would make 'sound spec' and 'unsound spec
        that happened not to fuse' look identical."""
        cand = [frozenset({"SHARED.1", "A1.1", "B1.1"}), frozenset({"C1.1", "C2.1"})]
        rep = compare_partitions(expected_partition_from_nets(OVERLAPPING_NETS), cand)
        rep.fused = []  # force the no-fusion branch
        self.assertTrue(any("not a partition" in d for d in rep.diagnosis()))


class TestItDoesNotRaise(unittest.TestCase):
    def test_an_overlapping_spec_still_produces_a_report(self):
        """Deliberate, and load-bearing.

        verify_partition_fidelity sits on composer.py's production path. Raising
        here would turn an unresolved design question -- are those declarations
        aliases, or is a component missing? -- into a hard compose failure, which
        decides that question by refusing to run. Surface it; let a human rule.
        """
        cand = [frozenset({"SHARED.1", "A1.1", "B1.1"}), frozenset({"C1.1", "C2.1"})]
        rep = compare_partitions(expected_partition_from_nets(OVERLAPPING_NETS), cand)
        self.assertIsNotNone(rep)
        self.assertTrue(rep.spec_overlapping_nodes)


if __name__ == "__main__":
    unittest.main()
