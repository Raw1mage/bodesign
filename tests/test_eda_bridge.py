from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bodesign_eda_bridge import build_kicad_native_extension_contract, emit_kicad_symbol_library_from_pin_table, emit_openmv_n6_subsystem_schematic, plan_kicad_bridge


REPO_ROOT = Path(__file__).resolve().parents[1]
PIN_TABLE = REPO_ROOT / "plans/product_openmv_datasheet_kicad_source/stm32n657-vfbga223-pin-table.json"
OPENMV_PLAN = REPO_ROOT / "plans/product_openmv_datasheet_kicad_source"


class EdaBridgeTests(unittest.TestCase):
    def test_kicad_bridge_plan_stays_behind_adapter_boundary(self):
        plan = plan_kicad_bridge("rockbox", "rockbox-board-design")

        self.assertEqual("plugin-submodule-auto-workflow", plan.integration_posture)
        self.assertEqual("not-executed", plan.execution_status)
        self.assertIn("adapter", plan.adapter_boundary.lower())
        self.assertTrue(any(path.endswith(".kicad_pcb") for path in plan.planned_outputs))
        self.assertTrue(any("DRC" in check for check in plan.planned_checks))

    def test_kicad_native_extension_contract_keeps_kicad_as_editor(self):
        contract = build_kicad_native_extension_contract("rockbox")

        self.assertEqual("kicad-action-plugin-plus-bodesign-mcp-sidecar", contract.integration_model)
        self.assertIn("KiCad native application owns schematic editor", contract.native_editor_owner)
        self.assertIn("bodesign MCP/API sidecar", contract.sidecar_boundary)
        self.assertIn("Companion dashboard", contract.bodesign_role)
        self.assertTrue(any(capability.capability_id == "apply-approved-patch" and capability.owner == "kicad-plugin" for capability in contract.capabilities))
        self.assertIn("browser-native schematic editor", contract.blocked_browser_features)
        self.assertIn("browser-native PCB layout editor", contract.blocked_browser_features)

    def test_emit_project_local_openmv_symbol_from_verified_pin_table(self):
        with TemporaryDirectory() as work:
            output = Path(work) / "libraries/symbols/openmv_generated.kicad_sym"

            result = emit_kicad_symbol_library_from_pin_table(PIN_TABLE, output)

            self.assertEqual("STM32N657L0_VFBGA223", result.symbol_name)
            self.assertEqual(223, result.pin_count)
            self.assertEqual(output, Path(result.library_path))
            self.assertTrue(output.exists())
            self.assertFalse(Path(work, "sym-lib-table").exists())
            symbol = output.read_text(encoding="utf-8")
            self.assertIn('(kicad_symbol_lib', symbol)
            self.assertIn('(symbol "STM32N657L0_VFBGA223"', symbol)
            self.assertEqual(223, symbol.count("\t\t\t(pin "))
            for pin_name in ("NRST", "BOOT0", "OSC32_IN", "OSC32_OUT", "PB4", "PB5"):
                self.assertIn(f'(name "{pin_name}"', symbol)
            self.assertIn('(property "BodesignEvidence"', symbol)
            self.assertIn('raw_pdf_text_committed=false', symbol)

    def test_emit_project_local_openmv_subsystem_schematic(self):
        with TemporaryDirectory() as work:
            result = emit_openmv_n6_subsystem_schematic(OPENMV_PLAN, Path(work) / "generated/openmv_n6_subsystem")

            schematic_path = Path(result.schematic_path)
            project_path = Path(result.project_path)
            self.assertTrue(schematic_path.exists())
            self.assertTrue(project_path.exists())
            self.assertEqual(2, result.component_count)
            self.assertGreaterEqual(result.net_count, 12)
            self.assertFalse(Path(work, "sym-lib-table").exists())
            self.assertFalse(Path(work, "fp-lib-table").exists())

            first = schematic_path.read_text(encoding="utf-8")
            second_result = emit_openmv_n6_subsystem_schematic(OPENMV_PLAN, Path(work) / "generated/openmv_n6_subsystem_2")
            second = Path(second_result.schematic_path).read_text(encoding="utf-8")
            self.assertEqual(first, second)
            for text in (
                'openmv_generated:STM32N657L0_VFBGA223',
                'openmv_generated:MX25UM25645GXDI00_24BGA',
                'STM32N657L0_VFBGA223',
                'MX25UM25645GXDI00',
                'XSPIM_P2_IO0',
                'XSPIM_P2_IO7',
                'XSPIM_P2_DQS0',
                'XSPIM_P2_NCS1',
                'XSPIM_P2_CLK_P',
                'XSPIM_P2_RST#',
                'VCC_1.8V_GATED',
                'raw_pdf_text_committed=false',
            ):
                self.assertIn(text, first)


if __name__ == "__main__":
    unittest.main()
