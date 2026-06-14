import json
import os
import unittest
from pathlib import Path

from bodesign_workflow_core import plan_c02_intent

VECTORS = json.loads(
    (Path(__file__).resolve().parents[1] / "plans" / "c02_voice-to-design" / "test-vectors.json").read_text(encoding="utf-8")
)


def _by_name(name: str) -> dict:
    for v in VECTORS:
        if v["name"] == name:
            return v
    raise KeyError(name)


class C02PlanIntentTests(unittest.TestCase):
    def test_extract_dimensions_wxh(self):
        v = _by_name("extract_dimensions_wxh")
        r = plan_c02_intent(v["input"]["spec_text"], v["input"].get("answers"))
        self.assertEqual(r["draft"]["board_outline"], {"width_mm": 50, "height_mm": 30})
        self.assertEqual(r["draft"]["field_status"]["board_outline"], "stated")
        self.assertEqual(r["draft"]["field_status"]["connector_openings"], "stated")
        self.assertEqual(r["draft"]["field_status"]["environment_targets"], "stated")
        self.assertEqual(r["draft"]["field_status"]["component_heights"], "missing")
        self.assertEqual(r["next_question"]["key"], "component_heights")
        self.assertEqual(r["status"], "needs-clarification")

    def test_extract_height_with_unit(self):
        v = _by_name("extract_height_with_unit")
        r = plan_c02_intent(v["input"]["spec_text"], v["input"].get("answers"))
        self.assertEqual(r["draft"]["board_outline"], {"width_mm": 60, "height_mm": 40})
        self.assertEqual(r["draft"]["component_heights"], [{"height_mm": 15}])
        self.assertEqual(r["draft"]["field_status"]["component_heights"], "stated")

    def test_missing_dimension_not_guessed(self):
        v = _by_name("missing_dimension_not_guessed")
        r = plan_c02_intent(v["input"]["spec_text"], v["input"].get("answers"))
        self.assertEqual(r["draft"]["field_status"]["board_outline"], "missing")
        self.assertEqual(r["next_question"]["key"], "board_outline")
        self.assertTrue(r["next_question"]["blocks_source"])
        self.assertEqual(r["status"], "needs-clarification")
        self.assertFalse(r["can_generate_cad_source"])
        # DD-2: no board_outline value was invented
        self.assertNotIn("board_outline", r["draft"])

    def test_answers_merge_promotes_status(self):
        v = _by_name("answers_merge_promotes_status")
        r = plan_c02_intent(v["input"]["spec_text"], v["input"].get("answers"))
        self.assertEqual(r["draft"]["field_status"]["board_outline"], "answered")
        self.assertEqual(r["draft"]["field_status"]["component_heights"], "answered")
        self.assertTrue(r["can_generate_cad_source"])

    def test_secondary_missing_does_not_block(self):
        v = _by_name("secondary_missing_does_not_block")
        r = plan_c02_intent(v["input"]["spec_text"], v["input"].get("answers"))
        self.assertTrue(r["can_generate_cad_source"])
        self.assertEqual(r["draft"]["field_status"]["heat_sources"], "missing")
        self.assertEqual(r["draft"]["field_status"]["antenna_keepouts"], "missing")
        self.assertEqual(r["status"], "ready-for-approval")

    def test_approval_gate_not_auto_generate(self):
        # plan_c02_intent itself never generates; full constraints + wall/clearance
        # yield ready-for-approval, and the orchestrator (voice_to_design) must see
        # approve=true before any CAD. Here we assert the plan stops at approval.
        v = _by_name("approval_gate_not_auto_generate")
        r = plan_c02_intent(v["input"]["spec_text"], v["input"].get("answers"))
        self.assertEqual(r["status"], "ready-for-approval")
        self.assertEqual(r["gen_params"].get("wall_thickness_mm"), 2.0)
        self.assertEqual(r["gen_params"].get("clearance_mm"), 1.0)

    def test_empty_spec_is_structured_error(self):
        r = plan_c02_intent("")
        self.assertEqual(r["error"], "C02_VTD_EMPTY_SPEC")
        self.assertEqual(r["status"], "needs-clarification")
        self.assertFalse(r["can_generate_cad_source"])


class C02VoiceToDesignGateTests(unittest.TestCase):
    """Orchestration approval gate without OpenSCAD/GL — exercises DD-4 not-approved path."""

    def test_not_approved_does_not_generate(self):
        from bodesign_workflow_core import voice_to_design
        v = _by_name("approval_gate_not_auto_generate")
        base = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"
        base.mkdir(parents=True, exist_ok=True)
        import tempfile
        work = tempfile.mkdtemp(prefix="c02-vtd-", dir=base)
        r = voice_to_design(work, v["input"]["spec_text"], v["input"].get("answers"), approve=False)
        self.assertEqual(r["status"], "ready-for-approval")
        self.assertFalse(r.get("generated_source"))
        # no Enclosure.scad must have been written when not approved
        self.assertFalse((Path(work) / "C02-ME" / "Enclosure.scad").exists())


if __name__ == "__main__":
    unittest.main()
