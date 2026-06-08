import os, shutil, tempfile, unittest
from pathlib import Path
from bodesign_eda_bridge import render_board_model, ModelRenderResult

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


if __name__ == "__main__":
    unittest.main()
