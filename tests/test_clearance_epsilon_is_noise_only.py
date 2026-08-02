"""BR_20260802 layer-1: the clearance comparison must not be decided by float noise.

A gap of EXACTLY one grid (1.27 mm) is the common case in this emitter, and the
coordinates reaching `_bbox_clear` are grid multiples accumulated by addition. Exact
`>=` therefore decides identical nominal geometries by the sign of rounding error:
in the recorded defect, 8 labels with the SAME nominal gap split 5/3, and the 3
losers had their anchors pushed off their pin endpoints into a silent open circuit.

These tests pin BOTH directions: the tolerance must absorb float noise, and it must
NOT absorb any difference the schematic file can actually express (>= 1e-4 mm, the
finest `round(v, 4)` the emitter writes).
"""
import unittest

from bodesign_eda_bridge.kicad_emit import (
    _CLEARANCE_EPS_MM,
    _CLEARANCE_MM,
    _bbox_clear,
)


def _pair(gap: float):
    """Two boxes separated on the y axis by exactly `gap`, overlapping in x."""
    a = (0.0, 2.0, 0.0, 2.0)
    b = (0.0, 2.0, 2.0 + gap, 4.0 + gap)
    return a, b


class EpsilonAbsorbsNoise(unittest.TestCase):
    def test_nominal_one_grid_gap_is_clear(self):
        self.assertTrue(_bbox_clear(*_pair(_CLEARANCE_MM)))

    def test_float_noise_below_one_grid_is_still_clear(self):
        # The exact value measured in the defect. Before the fix this returned
        # False and cost three nets their connectivity.
        self.assertTrue(_bbox_clear(*_pair(1.2699999999999818)),
                        "a gap short of one grid by 1.8e-14 mm is float noise, "
                        "not a clearance violation")

    def test_the_other_measured_deviation_is_also_clear(self):
        self.assertTrue(_bbox_clear(*_pair(1.269999999999996)))


class EpsilonDoesNotBlindRealViolations(unittest.TestCase):
    """The control half: without these, the test above passes for eps=1.0 too."""

    def test_smallest_expressible_shortfall_is_still_a_violation(self):
        # 1e-4 mm is the finest difference `round(v, 4)` can put in the file, so
        # it is the smallest REAL geometry change. It must still fail.
        self.assertFalse(_bbox_clear(*_pair(_CLEARANCE_MM - 1e-4)),
                         "1e-4 mm is expressible geometry, not noise")

    def test_visible_shortfalls_are_violations(self):
        for gap in (1.2, 1.0, 0.5, 0.1, 0.0):
            with self.subTest(gap=gap):
                self.assertFalse(_bbox_clear(*_pair(gap)))

    def test_overlap_is_a_violation(self):
        self.assertFalse(_bbox_clear(*_pair(-1.0)))

    def test_epsilon_is_orders_below_expressible_geometry(self):
        # Pins the derivation itself: if someone widens the tolerance toward the
        # expressible floor, this fails and tells them why.
        self.assertLess(_CLEARANCE_EPS_MM, 1e-4 / 1000,
                        "epsilon must stay far below the smallest geometric "
                        "difference the emitted file can express (1e-4 mm)")
        self.assertGreater(_CLEARANCE_EPS_MM, 1e-13,
                           "epsilon must stay above the float noise floor it exists "
                           "to absorb (worst measured deviation 1.8e-14 mm)")


if __name__ == "__main__":
    unittest.main()
