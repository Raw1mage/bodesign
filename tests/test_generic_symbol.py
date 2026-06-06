import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import emit_kicad_symbol, load_symbol

HAS_KICAD_CLI = shutil.which("kicad-cli") is not None
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

PINS = [
    {"number": "1", "name": "VIN", "type": "S"},
    {"number": "2", "name": "GND", "type": "S"},
    {"number": "3", "name": "EN", "type": "I"},
    {"number": "4", "name": "OUT", "type": "O"},
]


class GenericSymbolTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-gensym-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_emit_generic_symbol_and_resolve(self):
        # file named after the library part of the lib_id (load_symbol convention)
        lib = self.work / "charger_gen.kicad_sym"
        result = emit_kicad_symbol("BQ24075", PINS, lib, footprint_filter="*QFN*")

        self.assertEqual(4, result.pin_count)
        self.assertTrue(lib.exists())
        text = lib.read_text(encoding="utf-8")
        self.assertIn('(symbol "BQ24075"', text)
        self.assertIn('(name "VIN"', text)
        # power/passive inference: VIN/GND -> power_in/passive (S), EN -> input, OUT -> output
        self.assertIn("(pin input line", text)
        self.assertIn("(pin output line", text)

        # resolvable via load_symbol with lib_id "charger_gen:BQ24075"
        definition, pins = load_symbol("charger_gen:BQ24075", self.work)
        self.assertIn('(symbol "charger_gen:BQ24075"', definition)
        self.assertEqual({"1", "2", "3", "4"}, set(pins))

    def test_empty_pins_rejected(self):
        with self.assertRaises(ValueError):
            emit_kicad_symbol("X", [], self.work / "x.kicad_sym")

    @unittest.skipUnless(HAS_KICAD_CLI, "kicad-cli not installed")
    def test_generated_symbol_is_kicad_valid(self):
        import subprocess
        lib = self.work / "part_gen.kicad_sym"
        emit_kicad_symbol("PART", PINS, lib)
        proc = subprocess.run(["kicad-cli", "sym", "export", "svg", str(lib), "-o", str(self.work)],
                              capture_output=True, text=True)
        svgs = list(self.work.glob("*.svg"))
        self.assertTrue(svgs, f"kicad-cli produced no svg: {proc.stderr or proc.stdout}")


if __name__ == "__main__":
    unittest.main()
