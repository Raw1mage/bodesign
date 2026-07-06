import unittest

from bodesign_eda_bridge import build_kicad_native_extension_contract, length_match_bus, plan_kicad_bridge, resolve_connector_pads, si_status, solve_impedance, widen_bus_tracks
from bodesign_eda_bridge.routing import PCBNEW_AVAILABLE, _parse_plane_spec, pour_planes


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

    # ---- H1: connector pin expansion is not silently refdes-gated ---------------------
    def test_connector_expansion_applies_to_usb_c_on_any_refdes(self):
        # USB-C at J5 (NOT J1): the built-in table must still expand VBUS -> 4 pads.
        pads, expanded = resolve_connector_pads(
            "J5", "VBUS", "VBUS", connectors={}, usb_refs={"J5"})
        self.assertTrue(expanded)
        self.assertEqual(["A4", "A9", "B4", "B9"], pads)

    def test_connector_expansion_backward_compatible_on_j1(self):
        # DD-3: the original OpenMV J1 board keeps identical expansion.
        pads, expanded = resolve_connector_pads(
            "J1", "GND", "GND", connectors={}, usb_refs={"J1"})
        self.assertTrue(expanded)
        self.assertEqual(["A1", "A12", "B1", "B12"], pads)

    def test_connector_explicit_pinmap_wins(self):
        pads, expanded = resolve_connector_pads(
            "J5", "VBUS", "VBUS",
            connectors={"J5": {"VBUS": ["P1", "P2"]}}, usb_refs=set())
        self.assertTrue(expanded)
        self.assertEqual(["P1", "P2"], pads)

    def test_connector_no_match_keeps_single_pin_and_reports_not_expanded(self):
        # A non-connector net node stays as its single pin; expanded=False signals
        # "no silent multi-pad expansion happened" so the caller can report it.
        pads, expanded = resolve_connector_pads(
            "U1", "DATA0", "B7", connectors={}, usb_refs=set())
        self.assertFalse(expanded)
        self.assertEqual(["B7"], pads)

    # ---- H2: SI status thresholds are caller-overridable, not hardcoded ----------------
    def test_si_status_default_thresholds(self):
        self.assertEqual("pass", si_status(5.0, 4.0, 10.0, 20.0))
        self.assertEqual("warn", si_status(15.0, 2.0, 10.0, 20.0))
        self.assertEqual("fail", si_status(25.0, 2.0, 10.0, 20.0))

    def test_si_status_respects_overridden_thresholds(self):
        # A stricter device: 15% overshoot is a fail when pass<5 / warn<10.
        self.assertEqual("fail", si_status(15.0, 2.0, 5.0, 10.0))
        # A looser device: same 15% is a pass when pass<20.
        self.assertEqual("pass", si_status(15.0, 2.0, 20.0, 30.0))


class PourPlanesSpecTests(unittest.TestCase):
    """BR fix 2b: plane spec parsing fails fast with a clear POUR_PLANES_BAD_SPEC
    message BEFORE any getattr(pcbnew, ...), so a swapped/malformed spec never leaks
    a misleading `AttributeError: pcbnew has no attribute 'GND'`. Pure, pcbnew-free."""

    @unittest.skipUnless(PCBNEW_AVAILABLE, "pcbnew not importable on this host")
    def test_valid_spec_parses(self):
        self.assertEqual(("B.Cu", "GND"), _parse_plane_spec("B.Cu:GND"))

    def test_swapped_fields_raise_bad_spec_not_attributeerror(self):
        # "GND:B.Cu" would have hit getattr(pcbnew, 'GND') -> misleading error.
        with self.assertRaisesRegex(ValueError, "POUR_PLANES_BAD_SPEC"):
            _parse_plane_spec("GND:B.Cu")

    def test_missing_colon_raises_bad_spec(self):
        with self.assertRaisesRegex(ValueError, "POUR_PLANES_BAD_SPEC"):
            _parse_plane_spec("B.Cu-GND")

    def test_too_many_colons_raises_bad_spec(self):
        with self.assertRaisesRegex(ValueError, "POUR_PLANES_BAD_SPEC"):
            _parse_plane_spec("B.Cu:GND:extra")

    def test_empty_field_raises_bad_spec(self):
        with self.assertRaisesRegex(ValueError, "POUR_PLANES_BAD_SPEC"):
            _parse_plane_spec("B.Cu:")

    def test_illegal_pad_connection_fails_fast_before_pcbnew(self):
        # pad_connection validation happens before _need_pcbnew(), so it raises on
        # any host regardless of pcbnew availability.
        with self.assertRaisesRegex(ValueError, "POUR_PLANES_BAD_PAD_CONNECTION"):
            pour_planes("in.kicad_pcb", "out.kicad_pcb", ["B.Cu:GND"], pad_connection="bogus")


if __name__ == "__main__":
    unittest.main()
