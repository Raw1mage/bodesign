"""round 8: perpendicular crossing pass-through + its cross-net junction safety gate.

Two rules that must NOT share one output:

  - COLLINEAR overlap (same axis, overlapping projection) stays REJECTED. Two
    wires laid on top of each other are visually indistinguishable and KiCad may
    merge them; that is what the anti-fusion guard exists for.
  - PERPENDICULAR crossing is ALLOWED. `.kicad_sch` connectivity is EXPLICIT --
    two wires crossing with no junction at that point are electrically separate,
    and every real schematic is full of such crossings. Rejecting them made any
    non-trivial board undrawable.

Allowing the crossing is safe ONLY while no junction lands on the crossing
point. `cross_net_junction_shorts` is that precondition, tested here directly
because the router's own guards make the short hard to provoke through natural
input -- and an assertion nobody can fire is indistinguishable from one that
cannot fail.
"""

import unittest

from bodesign_eda_bridge.kicad_emit import cross_net_junction_shorts
from bodesign_eda_bridge.occupancy import LedgerRect, OccupancyLedger

PERP = frozenset({"wire"})


def _ledger_with_horizontal_wire():
    """A ledger holding ONE horizontal wire of NET_A, shaped as _reserve_wire
    would have inflated it (a 0.2 mm thick rect)."""
    led = OccupancyLedger(paper="A4")
    ok = led.try_reserve(LedgerRect(100.0, 99.9, 150.0, 100.1, "NET_A", "wire")).ok
    assert ok, "fixture invalid: the baseline wire did not enter the ledger"
    return led


class PerpendicularCrossingReserveTests(unittest.TestCase):
    def test_collinear_overlap_is_still_rejected(self):
        """The dangerous class must stay blocked even with the exemption on."""
        led = _ledger_with_horizontal_wire()
        collinear = LedgerRect(120.0, 99.9, 170.0, 100.1, "NET_B", "wire")
        res = led.try_reserve(collinear, kinds=PERP, perpendicular_ok_kinds=PERP)
        self.assertFalse(res.ok, "a collinear overlap was allowed into the ledger")
        self.assertEqual(["NET_A"], [c.owner for c in res.conflicts],
                         "rejected, but by the wrong rect -- the probe would pass "
                         "for the wrong reason")

    def test_perpendicular_crossing_is_allowed(self):
        led = _ledger_with_horizontal_wire()
        crossing = LedgerRect(124.9, 80.0, 125.1, 120.0, "NET_C", "wire")
        res = led.try_reserve(crossing, kinds=PERP, perpendicular_ok_kinds=PERP)
        self.assertTrue(res.ok,
                        "a perpendicular crossing was rejected; this is the normal "
                        "schematic case and blocking it makes dense boards undrawable")

    def test_crossing_is_rejected_without_the_exemption(self):
        """CONTROL: the flag is what changed the verdict, not the geometry.

        Without this, 'crossings are allowed' and 'this ledger allows everything'
        share one green.
        """
        led = _ledger_with_horizontal_wire()
        crossing = LedgerRect(124.9, 80.0, 125.1, 120.0, "NET_C", "wire")
        res = led.try_reserve(crossing, kinds=PERP)   # no perpendicular_ok_kinds
        self.assertFalse(res.ok)

    def test_path_clear_agrees_with_try_reserve(self):
        """The accept-gate and the reserve MUST apply the same predicate.

        When they disagreed (round 7), a wire was drawn but never entered the
        ledger, so later nets could not see it.
        """
        led = _ledger_with_horizontal_wire()
        clear_cross, _ = led.path_clear(
            [(130.0, 80.0), (130.0, 120.0)], kinds=PERP, perpendicular_ok_kinds=PERP)
        self.assertTrue(clear_cross, "accept-gate rejects a crossing that reserve accepts")

        clear_coll, hit = led.path_clear(
            [(110.0, 100.0), (160.0, 100.0)], kinds=PERP, perpendicular_ok_kinds=PERP)
        self.assertFalse(clear_coll, "accept-gate accepts a collinear overlap")
        self.assertEqual("NET_A", hit.owner)

    def test_default_call_is_unchanged(self):
        """Every pre-round-8 caller passes no exemption and must see old behaviour."""
        led = _ledger_with_horizontal_wire()
        crossing = LedgerRect(124.9, 80.0, 125.1, 120.0, "NET_C", "wire")
        self.assertFalse(led.try_reserve(crossing).ok)


class CrossNetJunctionShortTests(unittest.TestCase):
    """The precondition that makes crossing pass-through legitimate."""

    SEGS = {
        "NET_A": [((100.0, 100.0), (130.0, 100.0)), ((130.0, 100.0), (130.0, 60.0))],
        "NET_B": [((130.0, 80.0), (130.0, 120.0))],
    }

    def test_junction_on_another_nets_wire_is_a_short(self):
        shorts = cross_net_junction_shorts([(130.0, 100.0, "NET_A")], self.SEGS)
        self.assertEqual(1, len(shorts))
        self.assertEqual("NET_A", shorts[0]["junction_net"])
        self.assertEqual("NET_B", shorts[0]["shorted_to"],
                         "flagged, but naming the wrong net -- the report would "
                         "send a reader to the wrong wire")
        self.assertEqual([130.0, 100.0], shorts[0]["at"])

    def test_junction_clear_of_the_other_net_is_clean(self):
        """NEGCTRL: move the junction off NET_B and the flag must disappear."""
        self.assertEqual([], cross_net_junction_shorts([(110.0, 100.0, "NET_A")], self.SEGS))

    def test_junction_on_its_own_net_is_not_a_short(self):
        """NEGCTRL: a junction ON its own net is the NORMAL case (that is what a
        junction IS). Flagging it would make the check fire on every valid board,
        i.e. 'always red' is as useless as 'always green'."""
        own = {"NET_A": self.SEGS["NET_A"]}
        self.assertEqual([], cross_net_junction_shorts([(130.0, 100.0, "NET_A")], own))

    def test_no_junctions_is_clean(self):
        self.assertEqual([], cross_net_junction_shorts([], self.SEGS))


if __name__ == "__main__":
    unittest.main()
