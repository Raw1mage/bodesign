import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import compose_schematic, load_symbol

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
HAS_KICAD_CLI = shutil.which("kicad-cli") is not None
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

SPEC = {
    "components": [
        {"ref": "R1", "symbol": "Device:R", "value": "10k"},
        {"ref": "R2", "symbol": "Device:R", "value": "10k"},
        {"ref": "C1", "symbol": "Device:C", "value": "100nF"},
        {"ref": "J1", "symbol": "Connector:Conn_01x02_Pin", "value": "IN"},
    ],
    "nets": [
        {"name": "VIN", "nodes": ["J1.1", "R1.1"]},
        {"name": "MID", "nodes": ["R1.2", "R2.1", "C1.1"]},
        {"name": "GND", "nodes": ["J1.2", "R2.2", "C1.2"]},
    ],
}


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
class ComposerTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-composer-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_multi_source_load_symbol_falls_through_dirs(self):
        # a bogus dir first, then the real stdlib — must still resolve.
        definition, pins = load_symbol("Device:R", [self.work, SYMBOL_DIR])
        self.assertIn('(symbol "Device:R"', definition)
        self.assertEqual({"1", "2"}, set(pins))

    def test_compose_auto_places_and_emits(self):
        result = compose_schematic(self.work, "divider_demo", SPEC, symbol_dirs=SYMBOL_DIR)
        self.assertEqual(4, result.placed)
        self.assertEqual(3, result.nets)
        self.assertEqual([], result.emit.unresolved_pins)
        self.assertEqual([], result.warnings)

    @unittest.skipUnless(HAS_KICAD_CLI, "kicad-cli not installed")
    def test_compose_validates_with_kicad_cli(self):
        result = compose_schematic(self.work, "divider_demo", SPEC, symbol_dirs=SYMBOL_DIR, validate=True)
        v = result.validation
        self.assertEqual("validated", v.status)
        self.assertEqual(0, v.erc_errors)
        self.assertEqual(4, v.netlist_components)
        nets = {n["name"]: set(n["nodes"]) for n in v.netlist_nets}
        self.assertEqual({"R1.2", "R2.1", "C1.1"}, nets["MID"])
        self.assertEqual({"J1.1", "R1.1"}, nets["VIN"])


if __name__ == "__main__":
    unittest.main()
