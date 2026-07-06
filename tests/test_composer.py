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


class ComposeSkipContractTests(unittest.TestCase):
    """Silent-skip fail-fast contract (BR): pcbnew/kicad-free — pure spec parsing."""

    def _work(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        d = Path(tempfile.mkdtemp(prefix="bodesign-skip-", dir=PRIVATE_BASE))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    def test_all_components_skipped_fails_fast(self):
        # 13 declared components all lack a symbol -> empty schematic would be a
        # false green (0 ERC violations). Must raise, not return ok.
        spec = {"components": [{"ref": f"R{i}", "lib": "Device", "part": "R"}
                               for i in range(13)],
                "nets": []}
        with self.assertRaises(ValueError) as ctx:
            compose_schematic(self._work(), "all_skip_demo", spec, symbol_dirs=self._work())
        msg = str(ctx.exception)
        self.assertIn("COMPOSE_ALL_COMPONENTS_SKIPPED", msg)
        # every skip reason is enumerated
        self.assertIn("component #0", msg)
        self.assertIn("component #12", msg)
        self.assertIn("missing", msg)

    @unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
    def test_partial_skip_warns_with_correct_shape_hint(self):
        # one good + one malformed component: proceed, but warn with the correct
        # symbol: "Lib:Part" shape hint (not a fail-fast).
        spec = {
            "components": [
                {"ref": "R1", "symbol": "Device:R", "value": "10k"},
                {"ref": "R2", "lib": "Device", "part": "R"},  # wrong shape -> skip
            ],
            "nets": [],
        }
        result = compose_schematic(self._work(), "partial_skip_demo", spec, symbol_dirs=SYMBOL_DIR)
        skip_warnings = [w for w in result.warnings if "skipped" in w]
        self.assertTrue(skip_warnings, f"expected a skip warning, got {result.warnings!r}")
        self.assertTrue(any('symbol: "Lib:Part"' in w or 'Lib:Part' in w for w in skip_warnings),
                        f"skip warning should hint the correct shape, got {skip_warnings!r}")
        self.assertGreaterEqual(result.placed, 1)


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
        # result.placed == emit.component_count, which now counts ALL emitted symbol
        # blocks (the 4 user parts PLUS any synthesized power-port / PWR_FLAG glyphs),
        # so it is >= the user-component count. Assert that floor plus a clean emit
        # rather than a brittle exact total that shifts whenever power-symbol emission
        # adds glyphs.
        self.assertGreaterEqual(result.placed, 4)
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
