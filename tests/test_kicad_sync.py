import os
from pathlib import Path
import tempfile
import unittest

from bodesign_eda_bridge.composer import compose_schematic, _refine, _macro_compact
from bodesign_eda_bridge.kicad_sync import (
    diff_kicad_schematic, apply_user_pinning, _placements,
)


class KiCadSyncTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "scratch" / "kicad-sync-tests"
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def sch(self, name, x=50, y=60, rotation=0, extra=""):
        path = self.work / name
        path.write_text(f'''(kicad_sch
          (lib_symbols (symbol "ignored" (at 999 999 0)))
          (symbol (at {x} {y} {rotation})
            (property "Reference" "R1" (at 5 6 0))
            (property "Value" "quoted (value) \\"ok\\"")) {extra})''')
        return path

    def test_nudge_and_rotation_are_pinned_without_mutation(self):
        before = self.sch("before.kicad_sch")
        after = self.sch("after.kicad_sch", 52.125, 61.375, 90)
        diff = diff_kicad_schematic(before, after)
        self.assertEqual(diff, {"R1": {"x": 52.125, "y": 61.375, "rotation": 90}})
        spec = {"components": [{"ref": "R1", "symbol": "Test:R"}]}
        merged = apply_user_pinning(spec, diff)
        self.assertTrue(merged["components"][0]["user_pinned"])
        self.assertEqual(merged["components"][0]["x"], 52.125)
        self.assertNotIn("x", spec["components"][0])

    def test_rotation_only_and_unchanged(self):
        before = self.sch("before", rotation=0)
        self.assertEqual(diff_kicad_schematic(before, before), {})
        self.assertIn("R1", diff_kicad_schematic(before, self.sch("after", rotation=90)))

    def test_invalid_and_added_components_fail(self):
        before = self.sch("before")
        after = self.sch("after", extra='(symbol (at 1 2 0) (property "Reference" "R2"))')
        with self.assertRaisesRegex(ValueError, "COMPONENT_SET_CHANGED"):
            diff_kicad_schematic(before, after)
        after.write_text('(kicad_sch (symbol')
        with self.assertRaisesRegex(ValueError, "INVALID_SEXPR"):
            diff_kicad_schematic(before, after)
        with self.assertRaisesRegex(ValueError, "UNKNOWN_REFERENCE"):
            apply_user_pinning({"components": []}, {"R1": {"x": 1, "y": 2, "rotation": 0}})

    def test_refine_and_macro_avoid_fixed_obstacles(self):
        fixed = {"R1": (0.125, 0.375)}
        boxes = {"R1": (10, 10), "R2": (10, 10), "R3": (10, 10)}
        adjacency = {r: set(boxes) - {r} for r in boxes}
        refined = _refine(list(boxes), adjacency, boxes, fixed=fixed)
        packed = _macro_compact({r: fixed["R1"] for r in boxes}, boxes, adjacency, [], fixed=fixed)
        for positions in (refined, packed):
            self.assertEqual(positions["R1"], fixed["R1"])
            for ref in ("R2", "R3"):
                x, y = positions[ref]
                self.assertTrue(abs(x - .125) >= 12.54 or abs(y - .375) >= 12.54)

    def test_compose_retains_exact_coordinates_in_written_schematic(self):
        (self.work / "Test.kicad_sym").write_text('''(kicad_symbol_lib
          (version 20231120) (generator "test")
          (symbol "R" (property "Reference" "R" (at 0 3 0))
            (property "Value" "R" (at 0 -3 0))
            (symbol "R_0_1" (rectangle (start -2 -2) (end 2 2)
              (stroke (width 0) (type default)) (fill (type none))))))''')
        baseline = self.sch("baseline")
        current = self.sch("current", 80.125, 90.375)
        spec = apply_user_pinning({"components": [
            {"ref": "R1", "symbol": "Test:R"},
            {"ref": "R2", "symbol": "Test:R"},
        ], "nets": []}, diff_kicad_schematic(baseline, current))
        for style, compact, fill in (("netlist", False, False), ("draftsman", False, False),
                                     ("draftsman", True, False), ("draftsman", True, True)):
            with self.subTest(style=style, compact=compact, fill=fill):
                name = f"case_{style}_{compact}_{fill}"
                compose_schematic(self.work, name, spec, symbol_dirs=self.work,
                                  style=style, macro_compact=compact, page_fill=fill)
                pose = _placements(self.work / f"{name}.kicad_sch")["R1"]
                self.assertEqual((pose["x"], pose["y"]), (80.125, 90.375))

    def test_rotated_pin_is_rejected_before_emit(self):
        spec = {"components": [{"ref": "R1", "symbol": "Test:R", "x": 50,
                                "y": 60, "rotation": 90, "user_pinned": True}]}
        with self.assertRaisesRegex(ValueError, "ROTATION_UNSUPPORTED"):
            compose_schematic(self.work, "rotated", spec, symbol_dirs=self.work)

    def test_missing_pose_and_overlapping_pins_fail(self):
        spec = {"components": [{"ref": "R1", "symbol": "Test:R", "user_pinned": True}]}
        with self.assertRaisesRegex(ValueError, "MISSING_POSE"):
            compose_schematic(self.work, "missing", spec, symbol_dirs=self.work)
        with self.assertRaisesRegex(ValueError, "USER_PINNED_OVERLAP"):
            _macro_compact({"R1": (20, 20), "R2": (20, 20)},
                           {"R1": (10, 10), "R2": (10, 10)}, {}, [],
                           fixed={"R1": (20, 20), "R2": (20, 20)})

    def test_duplicate_reference_and_nonfinite_pose_fail(self):
        before = self.sch("before")
        duplicate = self.sch("duplicate", extra='(symbol (at 1 2 0) (property "Reference" "R1"))')
        with self.assertRaisesRegex(ValueError, "DUPLICATE_REFERENCE"):
            diff_kicad_schematic(before, duplicate)
        with self.assertRaisesRegex(ValueError, "INVALID_POSE"):
            diff_kicad_schematic(before, self.sch("invalid", x="nan"))


if __name__ == "__main__":
    unittest.main()
