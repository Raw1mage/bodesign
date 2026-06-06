import json
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    crosscheck_nets,
    extract_schematic_net_labels,
    reference_nets_from_component_knowledge,
    render_crosscheck_markdown,
)

REPO = Path("/home/pkcs12/projects/bodesign")
GEN_SCH = REPO / "plans/product_openmv_datasheet_kicad_source/generated/openmv_n6_subsystem/openmv_n6_subsystem.kicad_sch"
FLASH_KNOW = REPO / "plans/product_openmv_datasheet_kicad_source/mx25um25645g-component-knowledge.json"


class ReferenceCrosscheckTests(unittest.TestCase):
    def test_incomplete_vs_reference_reports_missing(self):
        chk = crosscheck_nets({"A", "B", "C"}, {"A", "B", "C", "D"}, "iface")
        self.assertEqual(["A", "B", "C"], chk.matched)
        self.assertEqual(["D"], chk.missing)
        self.assertEqual([], chk.extra)
        self.assertEqual(75, chk.coverage_pct)
        self.assertIn("incomplete", chk.verdict)

    def test_exact_match(self):
        chk = crosscheck_nets({"A", "B"}, {"A", "B"}, "iface")
        self.assertEqual(100, chk.coverage_pct)
        self.assertIn("matches the reference", chk.verdict)

    def test_extra_nets_flagged(self):
        chk = crosscheck_nets({"A", "B", "E"}, {"A", "B"}, "iface")
        self.assertEqual(["E"], chk.extra)
        self.assertIn("extra", chk.verdict)

    @unittest.skipUnless(GEN_SCH.exists() and FLASH_KNOW.exists(), "generated schematic / flash knowledge not present")
    def test_real_flash_crosscheck_against_openmv_control_group(self):
        generated = extract_schematic_net_labels(GEN_SCH, pattern="XSPI")
        reference, provenance = reference_nets_from_component_knowledge(json.loads(FLASH_KNOW.read_text()), pattern="XSPI")

        chk = crosscheck_nets(generated, reference, "Flash XSPI (U7) vs OpenMV", provenance)

        # every generated XSPI net is a real OpenMV net (names correct), but wiring is incomplete
        self.assertEqual([], chk.extra)
        self.assertTrue(chk.missing)  # reference has nets we didn't wire (e.g. CLK_N, WP#)
        self.assertIn("XSPIM_P2_CLK_N", chk.missing)
        self.assertTrue(0 < chk.coverage_pct < 100)
        self.assertEqual("OpenMV-N6-Schematic-Rev4.pdf", provenance.get("file"))
        self.assertIn("Reference cross-check", render_crosscheck_markdown([chk], "OpenMV N6"))


if __name__ == "__main__":
    unittest.main()
