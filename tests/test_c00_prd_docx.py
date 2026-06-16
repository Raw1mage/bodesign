import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    C00DocxArchitectureError,
    load_c00_docx_architecture,
    render_c00_prd_docx_package,
    scaffold_c00_prd_package,
    c00_update_answers,
)


PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class C00PrdDocxTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c00docx-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_architecture_descriptor_loads_with_expected_shape(self):
        arch = load_c00_docx_architecture()
        files = {d["file"]: d for d in arch.documents}
        self.assertIn("Project_Requirements.md", files)
        self.assertIn("RF_Requirements.md", files)
        self.assertEqual(len(files["Project_Requirements.md"]["sections"]), 12)
        self.assertEqual(len(files["RF_Requirements.md"]["sections"]), 3)
        # every project section declares a body_layout and a stored .dotx
        for d in arch.documents:
            self.assertTrue(d["template_dotx"].endswith(".dotx"))
            for s in d["sections"]:
                self.assertTrue(s["body_layout"])

    def test_render_requires_scaffold(self):
        with self.assertRaises(Exception):
            render_c00_prd_docx_package(self.work)  # no C00-PRD/answer_state.json yet

    def test_render_produces_assemblable_packages(self):
        scaffold_c00_prd_package(self.work, project_name="TestProduct", include_rf=True)
        res = render_c00_prd_docx_package(self.work)
        stems = {p.stem for p in res.packages}
        self.assertEqual(stems, {"Project_Requirements", "RF_Requirements"})
        for pkg in res.packages:
            d = Path(pkg.package_dir)
            self.assertTrue((d / "body.md").exists())
            self.assertTrue((d / "outline.md").exists())
            self.assertTrue((d / "manifest.json").exists())
            self.assertTrue((d / "template" / "template.dotx").exists())
            manifest = json.loads((d / "manifest.json").read_text())
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["format"], "docx")
            # assemble-required artifacts present
            artifact_paths = {a["path"] for a in manifest["artifacts"]}
            self.assertIn("outline.md", artifact_paths)
            self.assertIn("template/template.dotx", artifact_paths)

    def test_cover_and_section_headings_present(self):
        scaffold_c00_prd_package(self.work, project_name="TestProduct", include_rf=False)
        res = render_c00_prd_docx_package(self.work)
        proj = next(p for p in res.packages if p.stem == "Project_Requirements")
        body = proj.body_md
        self.assertIn("TestProduct", body)  # cover product name
        self.assertIn("Product Development Proposal", body)  # cover doc type
        self.assertIn("# Revision History", body)
        # all 12 section headings rendered
        for n in range(1, 13):
            self.assertIn(f"# {n}.", body)
        # outline carries cover-heading comments for assemble
        self.assertIn("<!-- cover heading:", proj.outline_md)

    def test_field_states_stay_visible_and_tables_render(self):
        scaffold_c00_prd_package(self.work, project_name="TestProduct", include_rf=False)
        c00_update_answers(
            self.work,
            {
                "s03_project_objectives.functional_objectives": {
                    "value": ["Achieve DVT maturity", "One-button setup"],
                    "state": "drafted",
                },
                "s06_electrical_requirements.compute": "Cortex-M33 with FPU",
                "s12_team_roster.internal_contacts": {
                    "value": [
                        {
                            "title": "CTO",
                            "name": "Jane",
                            "phone": "+886",
                            "email": "j@x.com",
                            "functional_role": "Lead",
                        }
                    ],
                    "state": "answered",
                },
            },
            regenerate=False,
        )
        res = render_c00_prd_docx_package(self.work)
        body = next(p for p in res.packages if p.stem == "Project_Requirements").body_md
        # objective table with sequential labels + visible drafted tag (honesty)
        self.assertIn("| OBJECTIVE 1 | Achieve DVT maturity _[drafted]_ |", body)
        self.assertIn("| OBJECTIVE 2 | One-button setup _[drafted]_ |", body)
        # electrical bullet-table answered value
        self.assertIn("| Cortex-M33 with FPU |", body)
        # contact card rows
        self.assertIn("| Title | CTO |", body)
        self.assertIn("| EMAIL | j@x.com |", body)

    def test_render_never_marks_human_approval(self):
        scaffold_c00_prd_package(self.work, project_name="TestProduct", include_rf=False)
        res = render_c00_prd_docx_package(self.work)
        self.assertFalse(res.to_dict()["human_approved"])


if __name__ == "__main__":
    unittest.main()
