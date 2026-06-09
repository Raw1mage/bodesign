import unittest

from bodesign_eda_bridge import build_kicad_native_extension_contract, length_match_bus, plan_kicad_bridge, solve_impedance, widen_bus_tracks


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

    def test_impedance_solver_returns_structured_classes(self):
        result = solve_impedance(
            {"dielectric_height_mm": 0.18, "er": 4.2, "copper_thickness_mm": 0.035},
            {
                "usb_se": {"impedance_ohm": 50},
                "usb_diff": {"kind": "differential", "impedance_ohm": 90, "gap_mm": 0.15},
            },
        )

        self.assertIn("warnings", result)
        self.assertIn("usb_se", result["classes"])
        self.assertIn("usb_diff", result["classes"])
        self.assertGreater(result["classes"]["usb_se"]["width_mm"], 0)
        self.assertAlmostEqual(50, result["classes"]["usb_se"]["actual_ohm"], delta=0.2)
        self.assertEqual(0.15, result["classes"]["usb_diff"]["gap_mm"])
        self.assertAlmostEqual(90, result["classes"]["usb_diff"]["actual_ohm"], delta=0.2)
        self.assertGreater(result["classes"]["usb_diff"]["ps_per_mm"], 0)

    def test_impedance_solver_fails_fast_without_required_inputs(self):
        with self.assertRaisesRegex(ValueError, "stackup"):
            solve_impedance({}, {"se": 50})
        with self.assertRaisesRegex(ValueError, "targets"):
            solve_impedance({"dielectric_height_mm": 0.18, "er": 4.2}, {})
        with self.assertRaisesRegex(ValueError, "gap_mm.*width_mm"):
            solve_impedance({"dielectric_height_mm": 0.18, "er": 4.2}, {"diff": {"kind": "differential", "impedance_ohm": 90}})

    def test_widen_bus_tracks_is_importable_and_validates_inputs_before_pcbnew(self):
        self.assertTrue(callable(widen_bus_tracks))
        with self.assertRaisesRegex(ValueError, "nets"):
            widen_bus_tracks("in.kicad_pcb", "out.kicad_pcb", [], 0.2)
        with self.assertRaisesRegex(ValueError, "target_mm"):
            widen_bus_tracks("in.kicad_pcb", "out.kicad_pcb", ["D0"], 0)
        with self.assertRaisesRegex(ValueError, "clearance_mm"):
            widen_bus_tracks("in.kicad_pcb", "out.kicad_pcb", ["D0"], 0.2, clearance_mm=-0.1)

    def test_length_match_bus_is_importable_and_validates_inputs_before_pcbnew(self):
        self.assertTrue(callable(length_match_bus))
        with self.assertRaisesRegex(ValueError, "nets"):
            length_match_bus("in.kicad_pcb", "out.kicad_pcb", [], 25, 5.97)
        with self.assertRaisesRegex(ValueError, "budget_ps"):
            length_match_bus("in.kicad_pcb", "out.kicad_pcb", ["D0"], -1, 5.97)
        with self.assertRaisesRegex(ValueError, "ps_per_mm"):
            length_match_bus("in.kicad_pcb", "out.kicad_pcb", ["D0"], 25, 0)
        with self.assertRaisesRegex(ValueError, "clearance_mm"):
            length_match_bus("in.kicad_pcb", "out.kicad_pcb", ["D0"], 25, 5.97, clearance_mm=-0.1)


if __name__ == "__main__":
    unittest.main()
