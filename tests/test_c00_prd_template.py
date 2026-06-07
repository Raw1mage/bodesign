import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import C00TemplateError, load_c00_prd_rubric, load_c00_prd_template, scaffold_c00_prd_package


PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class C00PrdTemplateTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c00-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_loads_committed_prd_template(self):
        template = load_c00_prd_template()

        self.assertGreaterEqual(len(template.project_sections), 12)
        self.assertGreaterEqual(len(template.rf_sections), 3)
        self.assertIn("Project_Requirements.md", template.to_dict()["documents"])
        first = template.project_sections[0]
        self.assertEqual("s01_business_strategy", first["id"])
        self.assertTrue(first["required_fields"])
        self.assertTrue(first["consultant_prompts"])
        self.assertTrue(first["handoff_targets"])

    def test_loads_committed_prd_rubric(self):
        rubric = load_c00_prd_rubric()
        data = rubric.data

        self.assertIn("answered", data["field_states"])
        self.assertIn("accepted-risk", data["scoring_policy"]["complete_states"])
        self.assertIn("business_contract", rubric.to_dict()["document_gates"])
        self.assertIn("C03", rubric.to_dict()["downstream_targets"])

    def test_missing_template_fails_fast(self):
        with self.assertRaises(C00TemplateError):
            load_c00_prd_template(self.work / "missing.json")

    def test_invalid_template_shape_fails_fast(self):
        path = self.work / "bad_template.json"
        path.write_text(json.dumps({"documents": [{"file": "Project_Requirements.md", "sections": [{"id": "s01", "title": "Bad"}]}]}), encoding="utf-8")

        with self.assertRaises(C00TemplateError) as context:
            load_c00_prd_template(path)

        self.assertIn("required_fields", str(context.exception))

    def test_invalid_rubric_shape_fails_fast(self):
        path = self.work / "bad_rubric.json"
        path.write_text(json.dumps({"field_states": {"answered": "ok"}}), encoding="utf-8")

        with self.assertRaises(C00TemplateError) as context:
            load_c00_prd_rubric(path)

        self.assertIn("document_gates", str(context.exception))

    def test_scaffold_creates_project_prd_and_missing_answer_state(self):
        result = scaffold_c00_prd_package(self.work, project_name="C00 POC")

        self.assertEqual("scaffold_created", result.status)
        self.assertFalse(result.to_dict()["readiness_computed"])
        self.assertFalse(result.to_dict()["prd_emitted"])
        self.assertFalse(result.to_dict()["human_approved"])
        self.assertIn("C00-PRD/Project_Requirements.md", result.files)
        self.assertIn("C00-PRD/answer_state.json", result.files)
        self.assertNotIn("C00-PRD/RF_Requirements.md", result.files)
        project = (self.work / "C00-PRD" / "Project_Requirements.md").read_text(encoding="utf-8")
        self.assertIn("Project: C00 POC", project)
        self.assertIn("State: `missing`", project)
        self.assertIn("{missing}", project)
        state = json.loads((self.work / "C00-PRD" / "answer_state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["readiness_computed"])
        self.assertFalse(state["prd_emitted"])
        self.assertIn("Project_Requirements.md", state["documents"])
        self.assertNotIn("RF_Requirements.md", state["documents"])
        first_section = state["documents"]["Project_Requirements.md"]["sections"][0]
        self.assertEqual("missing", first_section["state"])
        self.assertTrue(first_section["fields"])
        self.assertTrue(all(field["state"] == "missing" for field in first_section["fields"].values()))

    def test_scaffold_include_rf_creates_rf_source_and_state(self):
        result = scaffold_c00_prd_package(self.work, include_rf=True)

        self.assertIn("C00-PRD/RF_Requirements.md", result.files)
        self.assertGreaterEqual(result.rf_section_count, 3)
        self.assertTrue((self.work / "C00-PRD" / "RF_Requirements.md").exists())
        state = json.loads((self.work / "C00-PRD" / "answer_state.json").read_text(encoding="utf-8"))
        self.assertTrue(state["include_rf"])
        self.assertIn("RF_Requirements.md", state["documents"])
        rf_sections = state["documents"]["RF_Requirements.md"]["sections"]
        self.assertTrue(rf_sections)
        self.assertTrue(all(section["state"] == "missing" for section in rf_sections))


if __name__ == "__main__":
    unittest.main()
