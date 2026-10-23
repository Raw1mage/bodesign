"""
Unit tests for Layout Tidy Primitives.

Verifies:
- Geometric primitives (BoundingBox, Point2D, intersection detection).
- Grid snapping for component placement coordinates (flat and nested).
- Linear passive array distribution and secondary axis alignment.
- Silk-Over-Pad collision detection and automated clearance repositioning.
- KiCad PCB S-expression parsing, snapping, and silkscreen tidying.
"""

from pathlib import Path
import tempfile
import unittest

from bodesign_workflow_core import (
    BoundingBox,
    FootprintSilkRecord,
    PadGeometry,
    Point2D,
    distribute_passives,
    has_silk_pad_overlap,
    normalize_silk_rotation,
    snap_components,
    snap_coord,
    snap_point,
    tidy_all_footprints,
    tidy_footprint_silk,
    tidy_kicad_pcb,
    tidy_kicad_pcb_content,
)


class TestLayoutTidy(unittest.TestCase):

    def test_bounding_box_operations(self) -> None:
        """Verify BoundingBox geometry, intersection, and expansion."""
        box1 = BoundingBox(0.0, 0.0, 10.0, 10.0)
        box2 = BoundingBox(5.0, 5.0, 15.0, 15.0)
        box3 = BoundingBox(12.0, 12.0, 20.0, 20.0)

        self.assertTrue(box1.intersects(box2))
        self.assertFalse(box1.intersects(box3))
        # Expansion with margin connects box1 and box3
        self.assertTrue(box1.intersects(box3, margin=2.5))

        union_box = box1.union(box2)
        self.assertEqual(union_box.xmin, 0.0)
        self.assertEqual(union_box.ymin, 0.0)
        self.assertEqual(union_box.xmax, 15.0)
        self.assertEqual(union_box.ymax, 15.0)
        self.assertEqual(union_box.center_x, 7.5)
        self.assertEqual(union_box.center_y, 7.5)

    def test_grid_snap_primitives(self) -> None:
        """Verify scalar, point, and component list grid snapping."""
        self.assertEqual(snap_coord(12.432, step_mm=0.1), 12.4)
        self.assertEqual(snap_coord(12.467, step_mm=0.1), 12.5)
        self.assertEqual(snap_coord(10.024, step_mm=0.05), 10.0)
        self.assertEqual(snap_coord(10.038, step_mm=0.05), 10.05)

        x, y = snap_point(15.228, 44.881, step_mm=0.1)
        self.assertEqual((x, y), (15.2, 44.9))

        # Test flat components
        flat_comps = [
            {"ref": "R1", "x": 10.04, "y": 20.06},  # moves to 10.0, 20.1
            {"ref": "R2", "x": 10.10, "y": 20.20},  # already on 0.1 grid
        ]
        updated_flat, count = snap_components(flat_comps, grid_mm=0.1)
        self.assertEqual(count, 1)
        self.assertEqual(updated_flat[0]["x"], 10.0)
        self.assertEqual(updated_flat[0]["y"], 20.1)
        self.assertEqual(updated_flat[1]["x"], 10.1)
        self.assertEqual(updated_flat[1]["y"], 20.2)

        # Test nested placement dicts
        nested_comps = [
            {"refdes": "C1", "placement": {"x": 30.123, "y": 40.567}},
        ]
        updated_nested, count_nested = snap_components(nested_comps, grid_mm=0.1)
        self.assertEqual(count_nested, 1)
        self.assertEqual(updated_nested[0]["placement"]["x"], 30.1)
        self.assertEqual(updated_nested[0]["placement"]["y"], 40.6)

    def test_distribute_passives_x_axis(self) -> None:
        """Verify linear distribution of decoupling capacitor array along X axis."""
        caps = [
            {"ref": "C1", "x": 10.3, "y": 20.0},
            {"ref": "C2", "x": 11.2, "y": 20.2},
            {"ref": "C3", "x": 15.8, "y": 19.9},
            {"ref": "C4", "x": 18.0, "y": 20.1},
        ]

        # Pitch = 2.0mm, align Y to 20.0mm
        result, moved_count = distribute_passives(
            caps,
            axis="x",
            pitch_mm=2.0,
            align_cross_axis=True,
            cross_axis_coord=20.0,
            grid_mm=0.1,
        )

        self.assertEqual(moved_count, 3)
        self.assertEqual(result[0]["x"], 10.3)
        self.assertEqual(result[0]["y"], 20.0)
        self.assertEqual(result[1]["x"], 12.3)
        self.assertEqual(result[1]["y"], 20.0)
        self.assertEqual(result[2]["x"], 14.3)
        self.assertEqual(result[2]["y"], 20.0)
        self.assertEqual(result[3]["x"], 16.3)
        self.assertEqual(result[3]["y"], 20.0)

    def test_distribute_passives_y_axis(self) -> None:
        """Verify linear distribution of resistor array along Y axis."""
        resistors = [
            {"ref": "R1", "x": 50.1, "y": 10.0},
            {"ref": "R2", "x": 49.9, "y": 12.0},
            {"ref": "R3", "x": 50.3, "y": 14.0},
        ]

        result, moved_count = distribute_passives(
            resistors,
            axis="y",
            pitch_mm=1.5,
            align_cross_axis=True,
            cross_axis_coord=50.0,
            grid_mm=0.1,
        )

        self.assertEqual(result[0]["x"], 50.0)
        self.assertEqual(result[0]["y"], 10.0)
        self.assertEqual(result[1]["x"], 50.0)
        self.assertEqual(result[1]["y"], 11.5)
        self.assertEqual(result[2]["x"], 50.0)
        self.assertEqual(result[2]["y"], 13.0)

    def test_silk_over_pad_detection_and_repair(self) -> None:
        """Verify detection and repair of silkscreen text overlapping component pads."""
        # Create an 0402 resistor footprint: two pads at (-0.5, 0) and (0.5, 0), each 0.6x0.5mm
        pads = [
            PadGeometry(name="1", rel_x=-0.5, rel_y=0.0, width=0.6, height=0.5),
            PadGeometry(name="2", rel_x=0.5, rel_y=0.0, width=0.6, height=0.5),
        ]

        # Silkscreen text initially placed right on top of Pad 1
        record = FootprintSilkRecord(
            refdes="R1",
            origin_x=20.0,
            origin_y=30.0,
            pads=pads,
            silk_ref_text="R1",
            silk_pos_x=-0.5,  # Exactly over pad 1
            silk_pos_y=0.0,
            silk_rotation=45.0,  # Awkward angle
            font_size_x=1.0,
            font_size_y=1.0,
        )

        # Check overlap initially true
        self.assertTrue(has_silk_pad_overlap(record, clearance_mm=0.2))

        # Run tidy
        tidied, changed = tidy_footprint_silk(record, clearance_mm=0.25)
        self.assertTrue(changed)

        # Rotation must be normalized to standard 0° or 90°
        self.assertIn(tidied.silk_rotation, (0.0, 90.0))

        # Overlap must be completely eliminated
        self.assertFalse(has_silk_pad_overlap(tidied, clearance_mm=0.25))

        # Verify text was pushed outside pad cluster (e.g. y <= -0.7 or y >= 0.7)
        self.assertTrue(abs(tidied.silk_pos_y) >= 0.65 or abs(tidied.silk_pos_x) >= 1.0)

    def test_normalize_silk_rotation(self) -> None:
        """Verify angle normalization to 0°/90°."""
        self.assertEqual(normalize_silk_rotation(0.0), 0.0)
        self.assertEqual(normalize_silk_rotation(45.0), 90.0)
        self.assertEqual(normalize_silk_rotation(90.0), 90.0)
        self.assertEqual(normalize_silk_rotation(180.0), 0.0)
        self.assertEqual(normalize_silk_rotation(270.0), 90.0)
        self.assertEqual(normalize_silk_rotation(360.0), 0.0)

    def test_kicad_pcb_s_expression_tidy(self) -> None:
        """Verify parsing and modifying real KiCad PCB S-expression text."""
        kicad_sample = """(kicad_pcb (version 20240108) (generator "bodesign")
  (general (thickness 1.6))
  (footprint "Resistor_SMD:R_0402_1005Metric"
    (layer "F.Cu")
    (at 12.3456 45.6789 90)
    (property "Reference" "R1" (at 0.0 0.0 45.0)
      (effects (font (size 1 1) (thickness 0.15)))
    )
    (pad "1" smd roundrect (at -0.5 0.0) (size 0.6 0.5) (layers "F.Cu" "F.Paste" "F.Mask"))
    (pad "2" smd roundrect (at 0.5 0.0) (size 0.6 0.5) (layers "F.Cu" "F.Paste" "F.Mask"))
  )
)"""

        updated_text, stats = tidy_kicad_pcb_content(
            kicad_sample,
            actions=["grid_snap", "silk_tidy"],
            grid_mm=0.1,
            silk_clearance_mm=0.25,
        )

        self.assertEqual(stats["footprints_processed"], 1)
        self.assertEqual(stats["footprints_snapped"], 1)
        self.assertEqual(stats["silk_overlaps_resolved"], 1)

        # Footprint at 12.3456 45.6789 must be snapped to 12.3000 45.7000
        self.assertIn("(at 12.3000 45.7000 90)", updated_text)

        # Silkscreen reference at (0 0 45) must be moved away from pads and normalized to 0 or 90
        self.assertNotIn('(at 0.0 0.0 45.0)', updated_text)
        self.assertIn('(property "Reference" "R1" (at ', updated_text)

    def test_tidy_kicad_pcb_file_io(self) -> None:
        """Verify reading and writing .kicad_pcb file on disk."""
        kicad_sample = """(kicad_pcb (version 20240108) (generator "bodesign")
  (footprint "Capacitor_SMD:C_0603_1608Metric"
    (at 22.33 33.44)
    (property "Reference" "C1" (at 0.0 0.0 0.0))
    (pad "1" smd rect (at -0.75 0.0) (size 0.8 0.8))
    (pad "2" smd rect (at 0.75 0.0) (size 0.8 0.8))
  )
)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "test_board.kicad_pcb"
            src_file.write_text(kicad_sample, encoding="utf-8")

            res = tidy_kicad_pcb(src_file, grid_mm=0.1)
            self.assertEqual(res["stats"]["footprints_snapped"], 1)
            self.assertEqual(res["stats"]["silk_overlaps_resolved"], 1)

            saved_content = src_file.read_text(encoding="utf-8")
            self.assertIn("(at 22.3000 33.4000)", saved_content)


if __name__ == "__main__":
    unittest.main()
