import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_reverse_core import ingest_project_folder, render_index_markdown

ROCKBOX = Path("/home/pkcs12/projects/documents/gdrive/@利善美/03.研發資料/01.ROCKBOX")
HAS_ROCKBOX = ROCKBOX.exists()
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class ProjectIngestTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-ingest-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_classifies_and_flags_companions(self):
        (self.work / "C03-電路設計").mkdir()
        (self.work / "C03-電路設計" / "design.kicad_sch").write_text("(kicad_sch)", encoding="utf-8")
        (self.work / "C03-電路設計" / "board.DSN").write_text("orcad", encoding="utf-8")
        (self.work / "C03-電路設計" / "board.png").write_text("img", encoding="utf-8")  # companion for the .DSN
        (self.work / "C03-電路設計" / "project.BOM.xlsx").write_text("x", encoding="utf-8")
        (self.work / "gerber").mkdir()
        (self.work / "gerber" / "L1_top.art").write_text("G04", encoding="utf-8")

        index = ingest_project_folder(self.work)

        self.assertEqual(5, index.file_count)
        self.assertEqual(["C03-電路設計"], index.sections)
        self.assertEqual(1, index.role_counts.get("gerber"))
        self.assertEqual(1, index.role_counts.get("schematic"))
        self.assertEqual(1, index.role_counts.get("orcad-schematic"))
        by_path = {f.rel_path: f for f in index.files}
        # .kicad_sch is non-readable -> needs an (auto-rendered) companion, none exists yet
        sch = by_path["C03-電路設計/design.kicad_sch"]
        self.assertTrue(sch.needs_companion)
        self.assertEqual("", sch.companion)
        self.assertIn("auto-render", sch.note)
        # .DSN is non-readable but a .png sibling exists -> companion detected, not flagged as missing
        dsn = by_path["C03-電路設計/board.DSN"]
        self.assertTrue(dsn.needs_companion)
        self.assertEqual("C03-電路設計/board.png", dsn.companion)
        self.assertNotIn(dsn, index.needs_companion)
        # the .kicad_sch (no companion) IS in the needs-companion list
        self.assertIn(sch, index.needs_companion)
        self.assertIn("# Project folder index", render_index_markdown(index))

    @unittest.skipUnless(HAS_ROCKBOX, "Rockbox client corpus not present")
    def test_ingests_real_rockbox_project(self):
        index = ingest_project_folder(ROCKBOX)

        self.assertGreater(index.file_count, 100)
        # full C01-C07 product document architecture
        self.assertTrue(any(s.startswith("C03") for s in index.sections))
        self.assertEqual(7, len(index.sections))
        self.assertGreater(index.role_counts.get("gerber", 0), 10)
        self.assertEqual(1, index.role_counts.get("orcad-schematic"))
        # the OrCAD .DSN has its .png companion auto-detected
        dsn = [f for f in index.files if f.ext == ".dsn"][0]
        self.assertTrue(dsn.companion.endswith(".png"))


if __name__ == "__main__":
    unittest.main()
