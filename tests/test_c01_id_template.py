import json
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    C01TemplateError,
    load_c01_id_rubric,
    load_c01_id_template,
    validate_c01_outputs_binding,
)
from bodesign_workflow_core.c01_id_template import validate_c01_outputs_binding as _bind, C01IdTemplate


class C01TemplateTests(unittest.TestCase):
    def test_loads_committed_template_and_rubric(self):
        tpl = load_c01_id_template()
        self.assertEqual(tpl.folder, "C01-ID")
        carriers = tpl.draft_carriers()
        self.assertIn("Ai file/Design_Direction.md", carriers)
        self.assertIn("CMF/CMF_Direction.md", carriers)
        rub = load_c01_id_rubric()
        self.assertIn("missing", rub.to_dict()["readiness_states"])
        self.assertIn("Ai file", rub.to_dict()["artifact_gates"])

    def test_emitter_is_bound_to_template_carriers(self):
        result = validate_c01_outputs_binding()
        self.assertTrue(result["bound"])
        # Every template carrier is produced by the emitter (folder-prefixed).
        self.assertIn("C01-ID/Ai file/Design_Direction.md", result["emitter_carriers"])

    def test_binding_fails_when_template_declares_a_carrier_emitter_lacks(self):
        tpl = load_c01_id_template()
        data = json.loads(json.dumps(tpl.data))
        data["target_package"]["outputs"].append(
            {"rockbox_deliverable": "Ghost", "draft_carrier": "Ghost/Nope.md", "format_role": "x"}
        )
        drifted = C01IdTemplate(path="<mem>", data=data)
        with self.assertRaises(C01TemplateError):
            _bind(drifted)

    def test_missing_template_fails_fast(self):
        with self.assertRaises(C01TemplateError):
            load_c01_id_template("/nonexistent/c01_id.template.json")

    def test_invalid_template_shape_fails_fast(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"name": "x"}, fh)  # no target_package
            bad = fh.name
        with self.assertRaises(C01TemplateError):
            load_c01_id_template(bad)


if __name__ == "__main__":
    unittest.main()
