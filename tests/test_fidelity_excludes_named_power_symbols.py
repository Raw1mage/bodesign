"""A power symbol the spec gave its own name must be excluded like `#FLG*` is.

BR_20260802. `_drop_power_flags` stripped nodes whose ref starts with `#` -- the
prefix KiCad auto-annotates onto power symbols it names itself. A spec is free to
name one: the aiguard C03 page declares `PWR_FLAG_3V3PB`, a `power:PWR_FLAG`
instance with a reference of its own. KiCad's netlist exporter omits it exactly
as it omits `#FLG0001`, but the `#` test does not catch it -- so the baseline kept
a node the candidate could never contain, and the gate reported a permanent
phantom open circuit indistinguishable from a real one.

The mechanism was measured, not inferred. On the real page, changing ONLY the
instance's `lib_id` from `power:PWR_FLAG` to `Device:R` -- leaving the reference
name untouched -- took the exported component count from 46 to 47 and made the
node appear. Renaming the reference while leaving `lib_id` alone changed nothing.
The exclusion is driven by the SYMBOL.

Two things this test is careful about:

  * the exemption is read from the DRAWING, never from the spec. Reading it from
    the spec would also swallow "the component was never placed at all", which is
    a real defect this gate must keep reporting.
  * the exemption must not swallow anything else. Every assertion that something
    disappeared is paired with one that the other findings survived -- otherwise
    "the fix worked" and "the gate stopped measuring" share one output.
"""

import unittest

from bodesign_eda_bridge import fidelity as fid
from bodesign_eda_bridge.fidelity import (
    compare_partitions,
    power_symbol_refs,
    verify_partition_fidelity,
)

# Minimal schematic text in KiCad's own shape: a lib_symbols section declaring
# one power symbol and one ordinary one, then two placed instances. Parsed as
# text -- no kicad-cli needed, so this test states a fact about our parser rather
# than about the toolchain.
SCH_WITH_NAMED_POWER = """\
(kicad_sch
  (lib_symbols
    (symbol "power:PWR_FLAG"
      (power)
      (pin_names (offset 0))
      (property "Reference" "#FLG" (at 0 1.905 0))
      (symbol "PWR_FLAG_0_0"
        (pin power_out line (at 0 0 90) (length 0))
      )
    )
    (symbol "Device:R"
      (pin_numbers (hide yes))
      (property "Reference" "R" (at 2.032 0 90))
      (symbol "R_0_1"
        (pin passive line (at 0 3.81 270) (length 1.27))
      )
    )
  )
  (symbol
    (lib_id "power:PWR_FLAG")
    (at 100 100 0)
    (property "Reference" "PWR_FLAG_3V3PB" (at 100 98 0))
    (property "Value" "PWR_FLAG" (at 100 102 0))
  )
  (symbol
    (lib_id "Device:R")
    (at 120 100 0)
    (property "Reference" "R1" (at 120 98 0))
    (property "Value" "10k" (at 120 102 0))
  )
)
"""

# Control: byte-for-byte the same, except the instance points at Device:R. This
# is the mutation that was run against the real page, kept here so the claim
# "the symbol decides, not the name" has a re-runnable form.
SCH_SAME_NAME_ORDINARY_SYMBOL = SCH_WITH_NAMED_POWER.replace(
    '(lib_id "power:PWR_FLAG")', '(lib_id "Device:R")', 1)


class TestPowerSymbolRefs(unittest.TestCase):
    def _refs(self, text, tmpname="s.kicad_sch"):
        import tempfile
        from pathlib import Path
        d = tempfile.mkdtemp()
        p = Path(d) / tmpname
        p.write_text(text, encoding="utf-8")
        return power_symbol_refs([p])

    def test_a_named_power_symbol_is_recognised(self):
        self.assertIn("PWR_FLAG_3V3PB", self._refs(SCH_WITH_NAMED_POWER))

    def test_the_same_name_on_an_ordinary_symbol_is_not(self):
        """Control for the assertion above, and the load-bearing one.

        Without it, a detector that returned every reference in the file would
        also satisfy the first test. It also pins the mechanism: what changed
        between these two inputs is the lib_id, not the name.
        """
        refs = self._refs(SCH_SAME_NAME_ORDINARY_SYMBOL)
        self.assertNotIn("PWR_FLAG_3V3PB", refs)

    def test_ordinary_components_are_never_classified_as_power(self):
        self.assertNotIn("R1", self._refs(SCH_WITH_NAMED_POWER))

    def test_a_drawing_with_no_power_symbols_yields_nothing(self):
        text = SCH_WITH_NAMED_POWER.replace("(power)\n", "")
        self.assertEqual(self._refs(text), set())


class TestTheExemptionAppliesToBothSides(unittest.TestCase):
    # A spec net whose members are two real pins plus a named power flag, and a
    # candidate partition that -- like every KiCad export -- simply has no such
    # node. Before the fix this produced only_baseline=['PWR_FLAG_3V3PB.1'].
    EXPECTED = {"+3V3": ["U1.1", "U2.1", "PWR_FLAG_3V3PB.1"],
                "GND": ["U1.2", "U2.2"]}
    CANDIDATE = [frozenset({"U1.1", "U2.1"}), frozenset({"U1.2", "U2.2"})]

    def test_without_the_exemption_the_flag_reads_as_a_missing_node(self):
        """The defect itself, kept as a test so the fix cannot be silently
        reverted into a state that merely looks clean."""
        rep = compare_partitions(self.EXPECTED, self.CANDIDATE, frozenset())
        self.assertEqual(rep.only_baseline, ["PWR_FLAG_3V3PB.1"])
        self.assertFalse(rep.ok)

    def test_with_the_exemption_it_is_gone(self):
        rep = compare_partitions(self.EXPECTED, self.CANDIDATE,
                                 frozenset({"PWR_FLAG_3V3PB"}))
        self.assertEqual(rep.only_baseline, [])
        self.assertTrue(rep.ok)

    def test_the_exemption_does_not_swallow_a_real_missing_node(self):
        """Paired with the assertion above, and the reason the refs are read
        from the drawing rather than from the spec.

        U2.1 is absent from the candidate for a reason that has nothing to do
        with power symbols. Exempting the flag must not quiet it."""
        cand = [frozenset({"U1.1", "U3.1"}), frozenset({"U1.2", "U2.2"})]
        rep = compare_partitions(self.EXPECTED, cand,
                                 frozenset({"PWR_FLAG_3V3PB"}))
        self.assertIn("U2.1", rep.only_baseline)
        self.assertNotIn("PWR_FLAG_3V3PB.1", rep.only_baseline)
        self.assertFalse(rep.ok)

    def test_the_exemption_does_not_swallow_a_short(self):
        """Second half of the same guard, on the other direction of defect."""
        welded = [frozenset({"U1.1", "U2.1", "U1.2", "U2.2"})]
        rep = compare_partitions(self.EXPECTED, welded,
                                 frozenset({"PWR_FLAG_3V3PB"}))
        self.assertTrue(rep.fused, "a welded candidate must still report fusion")
        self.assertFalse(rep.ok)


class TestTheExemptionIsVisible(unittest.TestCase):
    def test_named_exclusions_are_reported_even_on_a_pass(self):
        """An exemption the reader cannot see is indistinguishable from a check
        that was never made -- and this one removes nodes from BOTH sides, so a
        clean report that hides it is the more misleading of the two."""
        rep = compare_partitions(
            {"+3V3": ["U1.1", "U2.1", "PWR_FLAG_3V3PB.1"]},
            [frozenset({"U1.1", "U2.1"})],
            frozenset({"PWR_FLAG_3V3PB"}))
        self.assertTrue(rep.ok, "precondition: this case passes")
        self.assertIn("PWR_FLAG_3V3PB", rep.summary())

    def test_auto_annotated_flags_are_not_listed_as_noteworthy(self):
        """Control: `#FLG0001` was always excluded and always will be. Listing
        the 87 of them on the real page would bury the one that matters."""
        rep = compare_partitions(
            {"+3V3": ["U1.1", "U2.1"]},
            [frozenset({"U1.1", "U2.1"})],
            frozenset({"#FLG0001", "#PWR012"}))
        self.assertEqual(rep.excluded_power_refs, [])


class TestTheProductionEntryPointIsWired(unittest.TestCase):
    """Every other test in this file calls compare_partitions directly.

    That left the one line callers actually reach -- verify_partition_fidelity
    passing the measured refs through -- covered by nothing. A mutation deleting
    that argument survived all ten of them: the exemption existed, was correct,
    was visible, and reached no production caller. Both call sites in this repo
    (composer.py and block_qa.py) enter here, so a guard that is not asserted at
    this door is not in the product.
    """

    def test_verify_partition_fidelity_passes_the_measured_refs_through(self):
        import tempfile
        from pathlib import Path

        d = Path(tempfile.mkdtemp())
        sch = d / "p.kicad_sch"
        sch.write_text(SCH_WITH_NAMED_POWER, encoding="utf-8")

        # kicad-cli is stubbed so this test states a fact about OUR wiring, not
        # about the toolchain's availability. power_symbol_refs still runs for
        # real, against the real file -- it is the argument-passing that is
        # under test.
        real = fid.sch_union_classes
        fid.sch_union_classes = lambda files, wd: [frozenset({"U1.1", "U2.1"})]
        try:
            rep = verify_partition_fidelity(
                {"+3V3": ["U1.1", "U2.1", "PWR_FLAG_3V3PB.1"]}, sch)
        finally:
            fid.sch_union_classes = real

        self.assertEqual(rep.excluded_power_refs, ["PWR_FLAG_3V3PB"],
                         "the entry point dropped the refs it measured")
        self.assertEqual(rep.only_baseline, [])
        self.assertTrue(rep.ok)

    def test_the_stub_itself_can_fail(self):
        """Control for the test above.

        Without it, a stub returning something that happens to match would make
        the assertion pass for the wrong reason. Here the candidate genuinely
        lacks U2.1, so the gate must still fail -- proving the stubbed path is
        the one being measured.
        """
        import tempfile
        from pathlib import Path

        d = Path(tempfile.mkdtemp())
        sch = d / "p.kicad_sch"
        sch.write_text(SCH_WITH_NAMED_POWER, encoding="utf-8")

        real = fid.sch_union_classes
        fid.sch_union_classes = lambda files, wd: [frozenset({"U1.1", "U3.1"})]
        try:
            rep = verify_partition_fidelity(
                {"+3V3": ["U1.1", "U2.1", "PWR_FLAG_3V3PB.1"]}, sch)
        finally:
            fid.sch_union_classes = real

        self.assertIn("U2.1", rep.only_baseline)
        self.assertFalse(rep.ok)


if __name__ == "__main__":
    unittest.main()
