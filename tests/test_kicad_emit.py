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


class ExtendsFlattenTests(unittest.TestCase):
    """Regression: a derived symbol (`(extends "Base")`) must be flattened into a
    standalone symbol, since kicad-cli refuses a schematic whose embedded symbol
    still references an unresolved base (e.g. Regulator_Linear:AMS1117-3.3)."""

    FIXTURE = '''(kicad_symbol_lib
  (symbol "Base"
    (pin_names (offset 0))
    (in_bom yes) (on_board yes)
    (property "Reference" "U" (at 0 0 0))
    (property "Value" "Base" (at 0 0 0))
    (symbol "Base_0_1"
      (rectangle (start -2 2) (end 2 -2))
    )
    (symbol "Base_1_1"
      (pin power_in line (at -5 0 0) (length 3) (name "VIN") (number "3"))
      (pin power_out line (at 5 0 0) (length 3) (name "VOUT") (number "2"))
      (pin power_in line (at 0 -5 90) (length 3) (name "GND") (number "1"))
    )
  )
  (symbol "Deriv"
    (extends "Base")
    (property "Reference" "U" (at 0 0 0))
    (property "Value" "Deriv-3.3" (at 0 0 0))
  )
)
'''

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-extends-", dir=PRIVATE_BASE))
        (self.work / "Test.kicad_sym").write_text(self.FIXTURE, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_derived_symbol_is_flattened(self):
        definition, pins = load_symbol("Test:Deriv", self.work)
        self.assertNotIn("(extends", definition)               # extends resolved away
        self.assertIn("Deriv_0_1", definition)                  # base units renamed to derived
        self.assertIn("Deriv_1_1", definition)
        self.assertNotIn("Base_0_1", definition)                # no leftover base unit names
        self.assertIn('"Deriv-3.3"', definition)                # derived property override kept
        self.assertEqual({"1", "2", "3"}, set(pins))            # pins inherited from base
