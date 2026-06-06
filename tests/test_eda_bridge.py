import unittest

from bodesign_eda_bridge import build_kicad_native_extension_contract, plan_kicad_bridge


class EdaBridgeTests(unittest.TestCase):
    def test_kicad_bridge_plan_stays_behind_adapter_boundary(self):
        plan = plan_kicad_bridge("board", "board-design")

        self.assertEqual("plugin-submodule-auto-workflow", plan.integration_posture)
        self.assertEqual("not-executed", plan.execution_status)
        self.assertIn("adapter", plan.adapter_boundary.lower())
        self.assertTrue(any(path.endswith(".kicad_pcb") for path in plan.planned_outputs))
        self.assertTrue(any("DRC" in check for check in plan.planned_checks))

    def test_kicad_native_extension_contract_keeps_kicad_as_editor(self):
        contract = build_kicad_native_extension_contract("board")

        self.assertEqual("kicad-action-plugin-plus-bodesign-mcp-sidecar", contract.integration_model)
        self.assertIn("KiCad native application owns schematic editor", contract.native_editor_owner)
        self.assertIn("bodesign MCP/API sidecar", contract.sidecar_boundary)
        self.assertIn("Companion dashboard", contract.bodesign_role)
        self.assertTrue(any(capability.capability_id == "apply-approved-patch" and capability.owner == "kicad-plugin" for capability in contract.capabilities))
        self.assertIn("browser-native schematic editor", contract.blocked_browser_features)
        self.assertIn("browser-native PCB layout editor", contract.blocked_browser_features)


if __name__ == "__main__":
    unittest.main()
