import json
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import AgentRegistryError, load_agent_registry
from bodesign_workflow_core.agent_registry import DOWNSTREAM_CODES, LAYER_CODES, load_agent_registry as _load


class AgentRegistryTests(unittest.TestCase):
    def test_loads_all_seven_layers_from_committed_template(self):
        reg = load_agent_registry()
        self.assertEqual(reg.schema, "bodesign.agent_registry.v1")
        self.assertEqual(reg.codes(), LAYER_CODES)

    def test_c00_is_the_only_contract_owner(self):
        reg = load_agent_registry()
        owners = [r.code for r in reg.roles if r.is_contract_owner]
        self.assertEqual(owners, ["C00"])
        self.assertEqual([r.code for r in reg.downstream()], DOWNSTREAM_CODES)

    def test_each_layer_carries_identity_from_architecture_template(self):
        reg = load_agent_registry()
        c01 = reg.get("C01")
        self.assertEqual(c01.key, "id")
        self.assertEqual(c01.target_role, "industrial_design")
        self.assertEqual(c01.owner, "ID team")
        self.assertIn("ID designer", c01.human_gate)
        self.assertTrue(c01.skills)

    def test_downstream_agents_cannot_change_direction_or_approve(self):
        reg = load_agent_registry()
        for role in reg.downstream():
            self.assertIn("return_blocker", role.allowed_actions)
            self.assertIn("change_product_direction", role.forbidden_actions)
            self.assertIn("mark_human_approved", role.forbidden_actions)
            self.assertIn("claim_professional_signoff", role.forbidden_actions)
            self.assertTrue(role.return_to_c00_when)

    def test_c00_owner_has_dispatch_and_ingest_authority(self):
        c00 = load_agent_registry().get("C00")
        self.assertIn("dispatch_work_packet", c00.allowed_actions)
        self.assertIn("ingest_blocker", c00.allowed_actions)
        self.assertEqual(c00.return_to_c00_when, [])

    def test_unknown_code_fails_fast(self):
        with self.assertRaises(AgentRegistryError):
            load_agent_registry().get("C99")

    def test_missing_layer_in_template_fails_fast(self):
        reg_data = json.loads(
            (Path(__file__).resolve().parents[1]
             / "packages/workflow-core/bodesign_workflow_core/templates/doc_architecture.template.json"
             ).read_text(encoding="utf-8")
        )
        reg_data["sections"] = [s for s in reg_data["sections"] if s.get("code") != "C03"]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(reg_data, fh)
            bad_path = fh.name
        with self.assertRaises(AgentRegistryError):
            _load(bad_path)

    def test_missing_template_file_fails_fast(self):
        with self.assertRaises(AgentRegistryError):
            _load("/nonexistent/doc_architecture.template.json")


if __name__ == "__main__":
    unittest.main()
