"""Feasibility triage sets the C04 delivery tier by the hardest driver."""
import unittest
from bodesign_workflow_core import classify_product_feasibility


class FeasibilityTests(unittest.TestCase):
    def test_simple_esp32_is_tier1_fab_ready(self):
        v = classify_product_feasibility(layer_count=4, finest_bga_pitch_mm=0.8,
                                         high_speed_nets=0, rf=False, source="C00-estimate")
        self.assertEqual(v.tier, 1)
        self.assertIn("fab-ready", v.label)
        self.assertEqual(v.confidence, "estimate")

    def test_rf_or_controlled_z_is_tier2(self):
        v = classify_product_feasibility(layer_count=4, finest_bga_pitch_mm=0.5,
                                         high_speed_nets=4, rf=True, source="C03-componentset")
        self.assertEqual(v.tier, 2)
        self.assertEqual(v.confidence, "firm")
        self.assertTrue(any("RF" in d for d in v.drivers))

    def test_phone_class_hdi_is_tier3_handoff(self):
        v = classify_product_feasibility(layer_count=12, finest_bga_pitch_mm=0.4,
                                         hdi_required=True, high_speed_nets=48, rf=True)
        self.assertEqual(v.tier, 3)
        self.assertIn("pro-EDA", v.c04_target)
        # worst-driver: HDI/pitch/layers all present
        self.assertTrue(any("HDI" in d for d in v.drivers))

    def test_worst_driver_wins_even_if_rest_simple(self):
        # everything trivial except a single 0.4mm BGA → still Tier 3
        v = classify_product_feasibility(layer_count=2, finest_bga_pitch_mm=0.4, high_speed_nets=0)
        self.assertEqual(v.tier, 3)

    def test_unknown_signals_dont_push_tier(self):
        v = classify_product_feasibility()  # all None/0
        self.assertEqual(v.tier, 1)
        self.assertEqual(v.drivers, [])


if __name__ == "__main__":
    unittest.main()
