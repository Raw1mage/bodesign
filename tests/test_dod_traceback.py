import unittest

from bodesign_workflow_core import dod_refs_traceback


class DodTracebackTests(unittest.TestCase):
    # ── TV-5: 憑空發明版（漏 WiFi/BT/PHY/IMU）被擋（切面 5）────────────────────
    def test_tv5_fabricated_version_blocked(self):
        # deliverable omits the high-value parts the SSOT requires, and its
        # delivered items carry no provenance → both failure directions fire.
        deliverable = [
            {"ref": "MCU"}, {"ref": "LED"}, {"ref": "R1"},  # no provenance
        ]
        ssot_required = ["MCU", "LED", "R1", "LBEE5KL1YN", "RTL8211FI-CG", "LSM6DSMTR"]
        rep = dod_refs_traceback(deliverable, ssot_required)
        self.assertTrue(rep.blocking)
        self.assertFalse(rep.dod_ok)
        # untraceable: delivered items with no SSOT anchor (憑空發明).
        self.assertEqual(len(rep.untraceable), 3)
        # unfulfilled: SSOT-required parts absent from the deliverable (漏做).
        self.assertEqual(set(rep.unfulfilled), {"LBEE5KL1YN", "RTL8211FI-CG", "LSM6DSMTR"})

    # ── TV-6: refs-derived 版全數可追溯 → 通過（切面 5）─────────────────────────
    def test_tv6_refs_derived_version_passes(self):
        ssot = "C03_元件與腳位SSOT.md"
        ssot_required = ["MCU", "LBEE5KL1YN", "RTL8211FI-CG", "LSM6DSMTR"]
        deliverable = [
            {"ref": r, "provenance": f"{ssot}:L{i+1}"} for i, r in enumerate(ssot_required)
        ]
        rep = dod_refs_traceback(deliverable, ssot_required, ssot_anchors=[ssot])
        self.assertFalse(rep.blocking)
        self.assertTrue(rep.dod_ok)
        self.assertEqual(len(rep.traced), 4)
        self.assertEqual(rep.unfulfilled, [])
        self.assertEqual(rep.untraceable, [])

    def test_untraceable_only_still_blocks(self):
        # all SSOT parts present, but one invented with no anchor → blocking.
        deliverable = [
            {"ref": "MCU", "provenance": "ssot.md:L1"},
            {"ref": "GHOST", "provenance": ""},  # invented
        ]
        rep = dod_refs_traceback(deliverable, ["MCU"])
        self.assertTrue(rep.blocking)
        self.assertEqual(len(rep.untraceable), 1)
        self.assertEqual(rep.untraceable[0]["ref"], "GHOST")
        self.assertEqual(rep.unfulfilled, [])

    def test_provenance_from_unknown_ssot_source_is_untraceable(self):
        # provenance points at a file NOT in the ssot_anchors allowlist → untraceable.
        deliverable = [{"ref": "MCU", "provenance": "random_notes.txt:L1"}]
        rep = dod_refs_traceback(deliverable, ["MCU"], ssot_anchors=["C03_SSOT.md"])
        self.assertTrue(rep.blocking)
        self.assertEqual(len(rep.untraceable), 1)

    def test_clean_when_no_ssot_requirement_and_all_traced(self):
        deliverable = [{"ref": "R1", "provenance": "ssot.md:L9"}]
        rep = dod_refs_traceback(deliverable, [])
        self.assertTrue(rep.dod_ok)
        self.assertFalse(rep.blocking)


if __name__ == "__main__":
    unittest.main()
