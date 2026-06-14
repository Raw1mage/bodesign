import os, shutil, tempfile, unittest
from pathlib import Path
from bodesign_eda_bridge import render_board_model, render_enclosure_model, ModelRenderResult

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class ModelRenderTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-model-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_degrades_gracefully_on_bad_input(self):
        # A missing/invalid glb must yield a structured result, never crash, and
        # never claim it rendered. (no-deps if parser/draco absent; error otherwise.)
        res = render_board_model(self.work / "nope.glb", self.work)
        self.assertIsInstance(res, ModelRenderResult)
        self.assertIn(res.status, {"error", "no-deps", "empty"})
        self.assertNotEqual(res.status, "rendered")
        self.assertEqual(res.images, [])
        self.assertIn("status", res.to_dict())

    def test_enclosure_missing_stl_is_structured_error(self):
        # A missing STL must yield a structured result, never crash, never claim
        # it rendered. (error for missing file; no-deps if trimesh absent.)
        res = render_enclosure_model(self.work / "nope.stl", self.work)
        self.assertIsInstance(res, ModelRenderResult)
        self.assertIn(res.status, {"error", "no-deps"})
        self.assertNotEqual(res.status, "rendered")
        self.assertEqual(res.images, [])
        self.assertIn("status", res.to_dict())

    def test_enclosure_renders_real_stl_cube(self):
        # When trimesh + GL are present, a real STL must render to top/iso PNGs.
        # Where the toolchain is absent (e.g. host without GL), accept the honest
        # degraded states instead — never a crash, never a false "rendered".
        try:
            import trimesh
        except ImportError:
            self.skipTest("trimesh not installed in this environment")
        box = trimesh.creation.box(extents=(50.0, 30.0, 12.0))
        stl = self.work / "Enclosure.stl"
        box.export(str(stl))
        res = render_enclosure_model(stl, self.work, views=("top", "iso"))
        self.assertIsInstance(res, ModelRenderResult)
        if res.status == "rendered":
            self.assertEqual(len(res.images), 2)
            for img in res.images:
                self.assertTrue(Path(img).exists())
            self.assertEqual(res.bounds_mm[:3], [-25.0, -15.0, -6.0])  # STL already mm
        else:
            self.assertIn(res.status, {"no-deps", "no-gl"})


if __name__ == "__main__":
    unittest.main()
