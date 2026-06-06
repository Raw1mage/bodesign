from pathlib import Path
import unittest

from bodesign_reverse_core import fuse_drill_and_ipc, reconstruct_rockbox_placeholder

FIXTURE_DIR = Path("/home/pkcs12/projects/bodesign/fixtures/private/rockbox/gerber")


class RockboxReconstructionTests(unittest.TestCase):
    def test_fixture_reconstruction_extracts_components_and_ipc_nets(self):
        fixture_dir = Path("/home/pkcs12/projects/bodesign/fixtures/private/rockbox/gerber")
        artifact_paths = [str(path) for path in fixture_dir.iterdir()]

        board_design = reconstruct_rockbox_placeholder("rockbox", artifact_paths)

        self.assertEqual(board_design.version, "0.2.0-rockbox-summary")
        self.assertEqual(len(board_design.components), 327)
        self.assertEqual(len(board_design.nets), 208)
        self.assertEqual(len(board_design.layers), 6)
        self.assertEqual(board_design.confidence_summary["status"], "summary-reconstructed")
        self.assertEqual(board_design.confidence_summary["ipc_pads"], 938.0)
        self.assertEqual(board_design.confidence_summary["ipc_vias"], 817.0)
        self.assertIn("U401", {component.refdes for component in board_design.components})
        self.assertIn("MDBT53-P1M", {component.part_number for component in board_design.components})
        self.assertIn("1V8_EN", {net.name for net in board_design.nets})

    def test_drill_via_spatial_fusion_matches_ipc_vias_in_shared_frame(self):
        ipc_files = [str(FIXTURE_DIR / "ROCKBOX_V2.ipc")]
        drill_files = [str(FIXTURE_DIR / "ROCKBOX_V2-1-6.drl")]

        fusion = fuse_drill_and_ipc("rockbox", ipc_files, drill_files)

        self.assertEqual(fusion.status, "spatial-fusion")
        self.assertEqual(fusion.frame, "ipc-drill-mil-scale")
        self.assertEqual(fusion.ipc_via_count, 817)
        self.assertEqual(fusion.ipc_pad_count, 938)
        self.assertEqual(fusion.drill_hit_count, 789)
        # Drill hits and IPC vias resolve to the same physical point, so matching is exact.
        self.assertEqual(fusion.matched_via_hits, 783)
        self.assertEqual(fusion.unmatched_holes, 6)
        self.assertGreater(fusion.match_ratio, 0.99)
        self.assertEqual(fusion.distinct_via_nets, 92)
        # GND dominates the via census on a 6-layer board with a ground plane.
        self.assertEqual(fusion.top_via_nets[0]["net"], "GND")
        self.assertTrue(fusion.geometry_primitives)
        self.assertEqual(fusion.geometry_primitives[0].primitive_type, "via")
        # Placement<->IPC co-registration is an explicit gap, not a silent omission.
        self.assertTrue(any("placement" in warning.lower() for warning in fusion.warnings))

    def test_spatial_fusion_degrades_safely_without_evidence(self):
        fusion = fuse_drill_and_ipc("empty", [], [])

        self.assertEqual(fusion.status, "no-spatial-evidence")
        self.assertEqual(fusion.matched_via_hits, 0)
        self.assertEqual(fusion.geometry_primitives, [])


if __name__ == "__main__":
    unittest.main()
