"""Worker-side integration: frozen-face placement → real pcbnew board → DRC roundtrip.

EPIC refs-derived-design, tasks 2.3 / 2.6 / 5.1 worker-side tail. Unlike the
core P1 tests (pure solver, bare host), these drive the ACTUAL pcbnew build:
solve_face_placement → placement_to_coords → net2pcb_board (real .kicad_pcb) →
kicad-cli DRC. They skip cleanly when pcbnew / kicad-cli is absent, so the suite
stays green on a bare host, but on a KiCad-equipped worker they prove the frozen
face actually lands on the physical board edge (the "USB won't plug in" guard).
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    parse_face_layout,
    solve_face_placement,
    placement_to_coords,
)

try:
    import pcbnew  # type: ignore  # noqa: F401
    from bodesign_eda_bridge.routing import net2pcb_board, drc_gate
    _PCBNEW = True
except Exception:
    _PCBNEW = False

_HAVE_KICAD_CLI = shutil.which("kicad-cli") is not None

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

# Two SMD resistors + a USB-C connector footprint that exist in the KiCad stock
# libraries, so FootprintLoad resolves without a custom fpdir.
_NETLIST = """(export (version "E")
 (components
  (comp (ref "J1") (value "USB_C") (footprint "Connector_USB:USB_C_Receptacle_GCT_USB4085"))
  (comp (ref "R1") (value "10k") (footprint "Resistor_SMD:R_0402_1005Metric"))
  (comp (ref "R2") (value "10k") (footprint "Resistor_SMD:R_0402_1005Metric")))
 (nets
  (net (code 1) (name "GND")
   (node (ref "J1") (pin "A1")) (node (ref "R1") (pin "2")) (node (ref "R2") (pin "2")))
  (net (code 2) (name "VBUS")
   (node (ref "J1") (pin "A4")) (node (ref "R1") (pin "1")))
  (net (code 3) (name "SIG")
   (node (ref "R2") (pin "1")))))
"""

_FACE_LAYOUT = {
    "schema": "bodesign.c01.face_layout.v1",
    "frozen": True,
    "board_outline": {"width_mm": 30.0, "height_mm": 20.0},
    "connectors": [
        {"ref": "J1", "component": "USB-C", "face": "BOTTOM",
         "provenance": "aiguard/C01_物理配置SSOT.md:L12"},
    ],
}


@unittest.skipUnless(_PCBNEW and _HAVE_KICAD_CLI,
                     "worker-side: needs pcbnew + kicad-cli (KiCad/EE worker)")
class FrozenFacePcbnewRoundtripTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-ws-", dir=PRIVATE_BASE))
        self.net = self.work / "board.net"
        self.net.write_text(_NETLIST, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_frozen_bottom_face_lands_on_bottom_edge_of_real_board(self):
        # solver → adapter → real pcbnew build
        fl = parse_face_layout(_FACE_LAYOUT)
        placements = solve_face_placement(fl)
        coords = placement_to_coords(placements, fl.board_outline)
        self.assertIn("J1", coords)
        x, y, rot = coords["J1"]
        # BOTTOM edge of a 30×20 board is y == height (20), rotated 180°.
        self.assertAlmostEqual(y, 20.0, places=3)
        self.assertAlmostEqual(rot, 180.0, places=3)

        out = self.work / "board.kicad_pcb"
        res = net2pcb_board(str(self.net), str(out), placement=coords)
        self.assertTrue(out.exists(), "net2pcb_board produced no board file")
        self.assertEqual(res["placed"], 3)

        # The frozen connector actually sits on the bottom edge of the real board:
        # re-open and read J1's footprint position from pcbnew itself.
        board = pcbnew.LoadBoard(str(out))
        j1 = next(fp for fp in board.GetFootprints() if fp.GetReference() == "J1")
        j1_y_mm = pcbnew.ToMM(j1.GetPosition().y)
        self.assertAlmostEqual(j1_y_mm, 20.0, places=1,
                               msg="frozen BOTTOM face did not land on the board's bottom edge")

    def test_drc_gate_runs_on_the_built_board(self):
        fl = parse_face_layout(_FACE_LAYOUT)
        coords = placement_to_coords(solve_face_placement(fl), fl.board_outline)
        out = self.work / "board.kicad_pcb"
        net2pcb_board(str(self.net), str(out), placement=coords)
        # DRC roundtrip: the gate must run and return the honest copper/unconnected/
        # silk split on a real board (an unrouted board legitimately has unconnected
        # items — we assert the gate mechanism works, not that a stub board is clean).
        report = drc_gate(str(out))
        for key in ("copper", "unconnected", "silk", "clean"):
            self.assertIn(key, report)
        self.assertIsInstance(report["clean"], bool)


if __name__ == "__main__":
    unittest.main()
