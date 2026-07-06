"""A7 page-density lint regression (DD-10, BR_20260706_schematic_text_render_qa_gap).

The density lint fail-fasts BEFORE placement, so exceeding the net/component
budget needs no KiCad symbols to trigger — the pin-per-symbol metric silently
skips unloadable symbols (fail-visible via the existing bbox warnings). These
tests therefore run without a symbol library except where the pin metric is
exercised explicitly.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import compose_schematic
from bodesign_eda_bridge.composer import DENSITY_BUDGET_DEFAULTS

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class DensityBudgetLintTests(unittest.TestCase):
    def _work(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        d = Path(tempfile.mkdtemp(prefix="bodesign-density-", dir=PRIVATE_BASE))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    # Over-net budget: 25 nets > default 20 → fail-fast before placement (no
    # symbols needed; components use placeholder symbols that never load).
    def test_over_net_budget_fails_fast(self):
        spec = {
            "components": [{"ref": f"R{i}", "symbol": "Device:R"} for i in range(5)],
            "nets": [{"name": f"N{i}", "nodes": [f"R0.1", f"R1.1"]} for i in range(25)],
        }
        with self.assertRaises(ValueError) as ctx:
            compose_schematic(self._work(), "over_nets", spec,
                              symbol_dirs=self._work(), density_budget={})
        msg = str(ctx.exception)
        self.assertIn("DENSITY_BUDGET_EXCEEDED", msg)
        self.assertIn("nets/page", msg)
        self.assertIn("25", msg)
        self.assertIn("20", msg)

    # Over-component budget: 20 components > default 15 → fail-fast.
    def test_over_component_budget_fails_fast(self):
        spec = {
            "components": [{"ref": f"R{i}", "symbol": "Device:R"} for i in range(20)],
            "nets": [],
        }
        with self.assertRaises(ValueError) as ctx:
            compose_schematic(self._work(), "over_comps", spec,
                              symbol_dirs=self._work(), density_budget={})
        msg = str(ctx.exception)
        self.assertIn("DENSITY_BUDGET_EXCEEDED", msg)
        self.assertIn("components/page", msg)

    # density_budget=None (default) MUST NOT lint — an over-dense spec composes
    # fine (byte-stable legacy behaviour; zero break).
    def test_density_none_never_triggers(self):
        spec = {
            "components": [{"ref": f"R{i}", "symbol": "Device:R"} for i in range(20)],
            "nets": [{"name": f"N{i}", "nodes": ["R0.1", "R1.1"]} for i in range(25)],
        }
        # No density_budget passed → lint disabled → no raise. (Components lack a
        # real symbol so they are skipped with warnings, but that is the existing
        # skip path, not the density lint.)
        result = compose_schematic(self._work(), "no_lint", spec,
                                   symbol_dirs=self._work())
        self.assertIsNotNone(result)

    # Explicit override raises the ceiling so a previously-failing spec passes.
    def test_override_raises_ceiling(self):
        spec = {
            "components": [{"ref": f"R{i}", "symbol": "Device:R"} for i in range(5)],
            "nets": [{"name": f"N{i}", "nodes": ["R0.1", "R1.1"]} for i in range(25)],
        }
        # 25 nets would trip the default 20; override to 30 → passes the lint.
        # (Symbols still don't load, but the lint runs before placement and does
        # not raise DENSITY_BUDGET_EXCEEDED.)
        try:
            compose_schematic(self._work(), "override_ok", spec,
                              symbol_dirs=self._work(),
                              density_budget={"max_nets_per_page": 30})
        except ValueError as e:
            self.assertNotIn("DENSITY_BUDGET_EXCEEDED", str(e))

    # A within-budget spec passes the lint cleanly (with real symbols so it emits).
    @unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
    def test_within_budget_passes(self):
        spec = {
            "components": [
                {"ref": "R1", "symbol": "Device:R"},
                {"ref": "R2", "symbol": "Device:R"},
                {"ref": "C1", "symbol": "Device:C"},
            ],
            "nets": [{"name": "MID", "nodes": ["R1.2", "R2.1", "C1.1"], "kind": "signal"}],
        }
        result = compose_schematic(self._work(), "within", spec,
                                   symbol_dirs=SYMBOL_DIR, density_budget={})
        self.assertGreaterEqual(result.placed, 3)

    # Per-symbol pin metric: a high-pin-count connector exceeds max_pins_per_symbol.
    @unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
    def test_over_pins_per_symbol_fails_fast(self):
        # Conn_02x20_Odd_Even has 40 pins; override the pin ceiling low to trip it
        # deterministically without depending on a specific 64+ pin part existing.
        conn = "Connector_Generic:Conn_02x20_Odd_Even"
        spec = {"components": [{"ref": "J1", "symbol": conn}], "nets": []}
        with self.assertRaises(ValueError) as ctx:
            compose_schematic(self._work(), "over_pins", spec,
                              symbol_dirs=SYMBOL_DIR,
                              density_budget={"max_pins_per_symbol": 10})
        msg = str(ctx.exception)
        self.assertIn("DENSITY_BUDGET_EXCEEDED", msg)
        self.assertIn("pins/symbol", msg)

    def test_defaults_are_midband(self):
        # Guard the calibrated defaults so a future edit that drifts them off the
        # aiguard PASS/FAIL midband trips here.
        self.assertEqual(20, DENSITY_BUDGET_DEFAULTS["max_nets_per_page"])
        self.assertEqual(15, DENSITY_BUDGET_DEFAULTS["max_components_per_page"])
        self.assertEqual(64, DENSITY_BUDGET_DEFAULTS["max_pins_per_symbol"])


if __name__ == "__main__":
    unittest.main()
