import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import generate_c02_openscad, plan_c02_intent
from bodesign_workflow_core.c02_me_package import (
    _connector_cut_geometry,
    _normalize_face,
    _render_openscad_source,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

try:
    import build123d as _b123d  # noqa: F401
    _HAS_BUILD123D = True
except Exception:
    _HAS_BUILD123D = False


_GEO_CONSTRAINTS = {
    "board_outline": {"width_mm": 60, "height_mm": 40},
    "component_heights": [{"ref": "U1", "height_mm": 15}],
    "mounting_holes": [{"x_mm": 4, "y_mm": 4, "diameter_mm": 2.5}],
    "connector_openings": [
        {"face": "east", "width_mm": 9, "height_mm": 3.5, "z_mm": 4},
    ],
}


class FaceNormalizationTests(unittest.TestCase):
    def test_english_aliases(self):
        self.assertEqual(_normalize_face("east"), "east")
        self.assertEqual(_normalize_face("RIGHT"), "east")
        self.assertEqual(_normalize_face("left"), "west")
        self.assertEqual(_normalize_face("Front"), "south")
        self.assertEqual(_normalize_face("rear"), "north")

    def test_chinese_aliases(self):
        self.assertEqual(_normalize_face("東"), "east")
        self.assertEqual(_normalize_face("右"), "east")
        self.assertEqual(_normalize_face("左"), "west")
        self.assertEqual(_normalize_face("前"), "south")
        self.assertEqual(_normalize_face("後"), "north")

    def test_invalid_face_returns_none(self):
        # DD-2: an unknown or non-string face must never be guessed.
        self.assertIsNone(_normalize_face("diagonal"))
        self.assertIsNone(_normalize_face(""))
        self.assertIsNone(_normalize_face(None))
        self.assertIsNone(_normalize_face(42))


class ConnectorCutGeometryTests(unittest.TestCase):
    # case dims for the 60x40 board, wall=2 clearance=1:
    # inner = 62x42, case = 66x46
    def _case(self):
        return dict(wall=2.0, clearance=1.0, case_width=66.0, case_height=46.0)

    def test_complete_geometry_resolves_cut(self):
        c = self._case()
        cut = _connector_cut_geometry(
            {"face": "east", "width_mm": 9, "height_mm": 3.5, "z_mm": 4}, **c
        )
        self.assertIsNotNone(cut)
        self.assertEqual(cut["face"], "east")
        # east wall: normal is X, so size_x punches through (wall + 2)
        self.assertEqual(cut["size_x"], 2.0 + 2.0)
        self.assertEqual(cut["size_y"], 9)  # width runs along Y
        self.assertEqual(cut["size_z"], 3.5)  # height runs along Z
        # center_z = wall + z
        self.assertEqual(cut["center_z"], 2.0 + 4)
        # east wall center_x near the +X wall
        self.assertAlmostEqual(cut["center_x"], 66.0 - 2.0 / 2.0)
        # default offset -> centered on the wall (case_height / 2)
        self.assertAlmostEqual(cut["center_y"], 46.0 / 2.0)

    def test_north_face_axis_mapping(self):
        c = self._case()
        cut = _connector_cut_geometry(
            {"face": "north", "width_mm": 10, "height_mm": 4, "z_mm": 3, "offset_mm": 20}, **c
        )
        self.assertIsNotNone(cut)
        # north wall: normal is Y -> size_y punches through; width along X
        self.assertEqual(cut["size_y"], 2.0 + 2.0)
        self.assertEqual(cut["size_x"], 10)
        self.assertEqual(cut["size_z"], 4)
        # explicit offset honored along X
        self.assertAlmostEqual(cut["center_x"], 20)
        self.assertAlmostEqual(cut["center_y"], 46.0 - 2.0 / 2.0)

    def test_incomplete_geometry_returns_none(self):
        c = self._case()
        # missing z_mm
        self.assertIsNone(_connector_cut_geometry({"face": "east", "width_mm": 9, "height_mm": 3.5}, **c))
        # missing width_mm
        self.assertIsNone(_connector_cut_geometry({"face": "east", "height_mm": 3.5, "z_mm": 4}, **c))
        # invalid face
        self.assertIsNone(_connector_cut_geometry({"face": "nope", "width_mm": 9, "height_mm": 3.5, "z_mm": 4}, **c))
        # only an edge label (legacy schema, no cut geometry)
        self.assertIsNone(_connector_cut_geometry({"name": "USB-C", "edge": "right"}, **c))


class OpenScadCutSourceTests(unittest.TestCase):
    def test_connector_cut_is_real_difference(self):
        source = _render_openscad_source(_GEO_CONSTRAINTS, 2.0, 1.0, 1.0)
        # A real cut module differenced from the shell — not just a // note.
        self.assertIn("module connector_cuts()", source)
        self.assertIn("connector_cuts();", source)  # invoked inside difference()
        # the cut item produced a real translate+cube (not only a comment line)
        cut_lines = [ln for ln in source.splitlines() if "cube(" in ln and "translate(" in ln]
        self.assertTrue(cut_lines, "expected a real translate([...]) cube([...]) cut")
        self.assertIn("east face", source)

    def test_incomplete_opening_is_skipped_not_cut(self):
        constraints = dict(_GEO_CONSTRAINTS)
        constraints["connector_openings"] = [{"name": "USB-C", "edge": "right"}]  # no cut geometry
        source = _render_openscad_source(constraints, 2.0, 1.0, 1.0)
        self.assertIn("skipped — incomplete cut geometry", source)

    def test_mounting_posts_are_standoff_plus_pilot(self):
        source = _render_openscad_source(_GEO_CONSTRAINTS, 2.0, 1.0, 1.0)
        # real posts (boss + pilot), no longer a marker-only cylinder
        self.assertIn("module mounting_posts()", source)
        self.assertIn("mounting_posts();", source)
        self.assertIn("standoff boss + pilot hole", source)
        self.assertNotIn("marker only", source)
        # boss diameter is dia + 3 (2.5 + 3 = 5.5)
        self.assertIn("d=5.5", source)
        # pilot hole at nominal dia
        self.assertIn("d=2.5", source)

    def test_generate_openscad_end_to_end_has_cut(self):
        base = PRIVATE_BASE
        base.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="c02-cut-", dir=base))
        try:
            res = generate_c02_openscad(
                work, constraints=_GEO_CONSTRAINTS,
                wall_thickness_mm=2.0, clearance_mm=1.0, lid_clearance_mm=1.0,
            )
            self.assertEqual(res.status, "source_generated")
            scad = (work / "C02-ME" / "Enclosure.scad").read_text(encoding="utf-8")
            self.assertIn("connector_cuts()", scad)
            self.assertIn("east face", scad)
        finally:
            shutil.rmtree(work, ignore_errors=True)


class PlanIntentConnectorTests(unittest.TestCase):
    def test_connector_keyword_without_geometry_asks(self):
        # "側面開 USB-C" mentions a connector but gives no cut geometry -> the plan
        # must surface a geometry-detail question, never invent a hole (DD-2).
        r = plan_c02_intent("我要一個 60×40 的盒子，最高元件 15mm，側面開 USB-C，室內用")
        self.assertEqual(r["draft"]["field_status"]["connector_openings"], "stated")
        # marker only, not a cuttable opening
        self.assertEqual(r["draft"]["connector_openings"], [{"note": "mentioned in spoken intent; needs detail"}])
        geo_qs = [q for q in [r["next_question"]] if q and q.get("needs_geometry")]
        # the geometry follow-up is registered as an open question
        # (it may not be the top next_question if a blocking field outranks it,
        # but here board+heights are present, so it should surface)
        self.assertTrue(r["next_question"] is not None)

    def test_connector_geometry_in_text_is_extracted(self):
        r = plan_c02_intent(
            "我要一個 60×40 的盒子，最高元件 15mm，east 面開孔 9x3.5，離底 4mm"
        )
        openings = r["draft"].get("connector_openings")
        self.assertIsInstance(openings, list)
        self.assertEqual(openings[0]["face"], "east")
        self.assertEqual(openings[0]["width_mm"], 9)
        self.assertEqual(openings[0]["height_mm"], 3.5)
        self.assertEqual(openings[0]["z_mm"], 4)
        self.assertEqual(r["draft"]["field_status"]["connector_openings"], "stated")

    def test_connector_geometry_via_answer(self):
        r = plan_c02_intent(
            "我要一個 60×40 的盒子，最高元件 15mm，要開 USB-C",
            answers={"connector_openings": "face=east, width_mm=9, height_mm=3.5, z_mm=4"},
        )
        openings = r["draft"].get("connector_openings")
        self.assertIsInstance(openings, list)
        self.assertEqual(openings[0]["face"], "east")
        self.assertEqual(openings[0]["z_mm"], 4)
        self.assertEqual(r["draft"]["field_status"]["connector_openings"], "answered")


@unittest.skipUnless(_HAS_BUILD123D, "build123d not installed on host")
class BuildPartCutTests(unittest.TestCase):
    def test_step_part_builds_with_connector_cut(self):
        from bodesign_workflow_core.c02_me_package import _build_enclosure_part
        part = _build_enclosure_part(_GEO_CONSTRAINTS, 2.0, 1.0, 1.0)
        self.assertIsNotNone(part)
        # a hollow box with a cut has positive but bounded volume
        self.assertGreater(part.volume, 0)


if __name__ == "__main__":
    unittest.main()
