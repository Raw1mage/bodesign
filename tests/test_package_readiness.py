import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import assess_package_readiness, render_readiness_markdown

THESMARTAI = Path("/home/pkcs12/projects/documents/gdrive/@利善美/03.研發資料/03.TheSmartAI")
HAS_THESMARTAI = THESMARTAI.exists()
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class PackageReadinessTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-readiness-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _status(self, readiness):
        return {d.key: d.status for d in readiness.deliverables}

    def test_prd_and_bom_present_schematic_missing(self):
        (self.work / "C00-PRD").mkdir()
        (self.work / "C00-PRD" / "TheSmartAI_Project_requirements.md").write_text("PRD", encoding="utf-8")
        (self.work / "C03-電路設計").mkdir()
        (self.work / "C03-電路設計" / "key_part_BOM.csv").write_text("ref,part", encoding="utf-8")
        (self.work / "C01-ID設計").mkdir()  # external

        r = assess_package_readiness(self.work, "POC")
        status = self._status(r)

        self.assertEqual("present", status["prd"])
        self.assertEqual("present", status["bom"])
        self.assertEqual("missing", status["schematic"])
        # the BOM file must NOT be mis-counted as the pin/GPIO allocation deliverable
        self.assertEqual("missing", status["pinmap"])
        self.assertIn("ID", r.external_sections)
        self.assertIn("schematic", r.next_step.lower())
        self.assertIn("Package readiness", render_readiness_markdown(r))

    def test_schematic_present_when_kicad_sch_exists(self):
        (self.work / "C03-電路設計").mkdir()
        (self.work / "C03-電路設計" / "design.kicad_sch").write_text("(kicad_sch)", encoding="utf-8")

        r = assess_package_readiness(self.work, "POC")
        self.assertEqual("present", self._status(r)["schematic"])

    @unittest.skipUnless(HAS_THESMARTAI, "TheSmartAI client folder not present")
    def test_real_thesmartai_folder_is_partial_with_external_marked(self):
        r = assess_package_readiness(THESMARTAI, "POC")

        status = self._status(r)
        self.assertEqual("present", status["prd"])
        self.assertEqual("present", status["bom"])
        self.assertEqual("missing", status["schematic"])
        self.assertEqual({"FW", "ID", "ME"}, set(r.external_sections))
        self.assertTrue(0 < r.readiness_pct < 100)


if __name__ == "__main__":
    unittest.main()
