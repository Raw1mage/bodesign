import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from bodesign_eda_bridge.visual_companion import generate_visual_diff


class VisualCompanionTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "scratch" / "visual-companion-tests"
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)

    def file(self, name, text):
        path = self.work / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_schematic_changes_diagnostics_and_escaping(self):
        before = self.file("before.kicad_sch", '(kicad_sch (symbol (uuid u1) (at 10 20 0) (property "Reference" "U1") (property "Value" "old")))')
        after = self.file("after.kicad_sch", '(kicad_sch (symbol (uuid u1) (at 12 20 0) (property "Reference" "U1") (property "Value" "new")) (wire (uuid w1) (pts (xy 12 20) (xy 30 20))))')
        out = self.work / "diff.svg"
        kwargs = {"diagnostics": [{"code": "pin_not_connected", "source": "ERC fixture", "message": "<unsafe>&", "x": 12, "y": 20}], "user_pinned_refs": ["U1"]}
        report = generate_visual_diff(before, after, out, **kwargs)
        svg = out.read_text()
        ET.fromstring(svg)
        self.assertEqual([c["status"] for c in report["changes"]], ["changed", "added"])
        self.assertTrue(report["changes"][0]["user_pinned"])
        for token in ("#16803c", "#e0ad00", "#cc2222", "pin_not_connected", "&lt;unsafe&gt;&amp;", "DRAFT"):
            self.assertIn(token, svg)
        self.assertFalse(report["png_rendered"])
        self.assertEqual(report["files"], [str(out)])
        self.assertEqual(report, generate_visual_diff(before, after, out, **kwargs))
        self.assertEqual(svg, out.read_text())

    def test_pcb_pad_transform_via_net_track_and_unsupported(self):
        before = self.file("before.kicad_pcb", '(kicad_pcb (net 0 ""))')
        after = self.file("after.kicad_pcb", '''(kicad_pcb (net 0 "") (net 1 "GND")
          (footprint "R" (uuid f1) (at 10 20 90) (property "Reference" "R1")
            (pad "1" smd rect (uuid p1) (at 2 0) (net 1 "GND")))
          (segment (uuid s1) (start 10 18) (end 30 18) (width 0.2) (layer "F.Cu") (net 1))
          (via (uuid v1) (at 30 18) (size 0.6) (drill 0.3) (net 1))
          (arc (uuid a1)) (zone (net 1)))''')
        report = generate_visual_diff(before, after, self.work / "pcb.svg")
        changes = {c["id"]: c for c in report["changes"]}
        self.assertEqual(set(changes), {"f1", "p1", "s1", "v1", "net:GND"})
        self.assertEqual(changes["p1"]["after"]["points"], [[10, 18]])
        self.assertEqual(changes["s1"]["after"]["attributes"]["net"], "GND")
        self.assertEqual(report["unsupported_present"], ["arc", "zone"])
        self.assertEqual(report["diagnostics_status"], "not_supplied")

    def test_removed_and_empty_diagnostics_not_pass(self):
        before = self.file("b", '(kicad_sch (label "X" (uuid l1) (at 1 2 0)))')
        after = self.file("a", '(kicad_sch (sheet (uuid hierarchy)))')
        report = generate_visual_diff(before, after, self.work / "diff.svg", diagnostics=[])
        self.assertEqual(report["changes"][0]["status"], "removed")
        self.assertEqual(report["unsupported_present"], ["sheet"])
        self.assertEqual(report["diagnostics_status"], "supplied_only_not_verified")

    def test_moved_trace_and_net_id_renumbering(self):
        before = self.file("b", '(kicad_pcb (net 1 "GND") (segment (uuid s) (start 1 2) (end 3 4) (net 1)))')
        same = self.file("same", '(kicad_pcb (net 8 "GND") (segment (uuid s) (start 1 2) (end 3 4) (net 8)))')
        out = self.work / "diff.svg"
        self.assertEqual(generate_visual_diff(before, same, out)["changes"], [])
        moved = self.file("moved", '(kicad_pcb (net 8 "GND") (segment (uuid s) (start 2 2) (end 4 4) (net 8)))')
        changes = generate_visual_diff(before, moved, out)["changes"]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["status"], "changed")
        self.assertIn("#e0ad00", out.read_text())

    def test_value_change_without_movement(self):
        before = self.file("b", '(kicad_sch (symbol (uuid u) (at 20 30 0) (property "Value" "10k")))')
        after = self.file("a", '(kicad_sch (symbol (uuid u) (at 20 30 0) (property "Value" "22k")))')
        changes = generate_visual_diff(before, after, self.work / "diff.svg")["changes"]
        self.assertEqual(changes[0]["before"]["points"], changes[0]["after"]["points"])
        self.assertEqual(changes[0]["status"], "changed")

    def test_fail_fast_inputs(self):
        good = self.file("good", '(kicad_sch)')
        for text in ('(kicad_sch', '(kicad_sch (symbol (at 1 2 0)))',
                     '(kicad_sch (symbol (uuid u) (at nan 2 0)))',
                     '(kicad_sch (symbol (uuid u) (at 1 2 0)) (symbol (uuid u) (at 2 3 0)))', '(kicad_pcb)'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                generate_visual_diff(good, self.file("bad", text), self.work / "bad.svg")
        with self.assertRaisesRegex(ValueError, "LOCATED_DIAGNOSTIC"):
            generate_visual_diff(good, good, self.work / "bad.svg", diagnostics=[{"code": "unlocated"}])
        self.assertFalse((self.work / "bad.svg").exists())
