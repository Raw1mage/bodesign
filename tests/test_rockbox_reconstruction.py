from pathlib import Path
import unittest

from bodesign_reverse_core import reconstruct_rockbox_placeholder


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


if __name__ == "__main__":
    unittest.main()
