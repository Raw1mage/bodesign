import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import (
    EmitComponent,
    EmitNet,
    emit_kicad_schematic,
    load_symbol,
    validate_kicad_schematic,
)

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
HAS_KICAD_CLI = shutil.which("kicad-cli") is not None
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


def _divider() -> tuple[list[EmitComponent], list[EmitNet]]:
    components = [
        EmitComponent("R1", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", 100, 100),
        EmitComponent("R2", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", 120, 100),
        EmitComponent("C1", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric", 120, 120),
    ]
    nets = [
        EmitNet("VIN", [("R1", "1")]),
        EmitNet("MID", [("R1", "2"), ("R2", "1"), ("C1", "1")]),
        EmitNet("GND", [("R2", "2"), ("C1", "2")]),
    ]
    return components, nets


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries are not installed")
class KiCadEmitTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-emit-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_load_symbol_returns_definition_and_pin_endpoints(self):
        definition, pins = load_symbol("Device:R", SYMBOL_DIR)

        self.assertIn('(symbol "Device:R"', definition)
        self.assertEqual({"1", "2"}, set(pins))
        # Device:R pins sit on the vertical axis at +/-3.81 in the library frame.
        self.assertEqual((0.0, 3.81), pins["1"])
        self.assertEqual((0.0, -3.81), pins["2"])

    def test_emit_produces_self_contained_schematic_with_connectivity(self):
        components, nets = _divider()

        result = emit_kicad_schematic(self.work, "divider", components, nets, symbol_dir=SYMBOL_DIR)

        self.assertEqual(3, result.component_count)
        self.assertEqual(["Device:C", "Device:R"], result.embedded_symbols)
        self.assertEqual([], result.unresolved_pins)
        self.assertEqual([], result.warnings)
        # MID has 3 nodes, GND has 2, VIN has 1 -> 6 global labels placed on pins.
        self.assertEqual(6, result.label_count)
        schematic = Path(result.schematic_path).read_text(encoding="utf-8")
        self.assertIn("(lib_symbols", schematic)
        self.assertIn('(global_label "MID"', schematic)
        self.assertIn('(lib_id "Device:R")', schematic)
        self.assertTrue(Path(result.project_path).exists())

    def test_emit_records_unresolved_pins_for_unknown_symbol(self):
        components = [EmitComponent("U1", "Device:DoesNotExist", x=100, y=100)]
        nets = [EmitNet("N1", [("U1", "1")])]

        result = emit_kicad_schematic(self.work, "bad", components, nets, symbol_dir=SYMBOL_DIR)

        self.assertEqual(0, result.component_count)
        self.assertTrue(result.warnings)
        self.assertEqual(["U1.1"], result.unresolved_pins)

    @unittest.skipUnless(HAS_KICAD_CLI, "kicad-cli is not installed")
    def test_emitted_schematic_passes_kicad_cli_erc_and_netlist(self):
        components, nets = _divider()
        result = emit_kicad_schematic(self.work, "divider", components, nets, symbol_dir=SYMBOL_DIR)

        validation = validate_kicad_schematic(result.schematic_path)

        self.assertEqual("validated", validation.status)
        self.assertEqual(0, validation.erc_errors)
        self.assertEqual(3, validation.netlist_components)
        nets_by_name = {net["name"]: set(net["nodes"]) for net in validation.netlist_nets}
        self.assertEqual({"R1.2", "R2.1", "C1.1"}, nets_by_name["MID"])
        self.assertEqual({"R2.2", "C1.2"}, nets_by_name["GND"])


if __name__ == "__main__":
    unittest.main()
