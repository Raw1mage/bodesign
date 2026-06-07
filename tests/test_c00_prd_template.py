import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import C00TemplateError, load_c00_prd_rubric, load_c00_prd_template


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


if __name__ == "__main__":
    unittest.main()
