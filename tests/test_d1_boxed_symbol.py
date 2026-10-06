"""R6 presentation asset: Bodesign_Presentation:PESD5V0L4UF_Boxed (D1 only).

Populations:
  * the authored symbol loads through the repo loader by explicit path and keeps
    the whole six-pin identity (number / name / type / hidden-stacked) from the
    datasheet pin table (Nexperia PESDXL4UF_G_W_4, Table 3 p.2);
  * the asset is NOT registered in the resolver and does NOT shadow the stock
    symbol: default resolution of Power_Protection:PESD5V0L4UF is unchanged and
    an unrelated ref resolves identically with and without the vendor dir;
  * library Footprint property is empty (non-fabricable presentation asset);
  * a fresh native emit + kicad-cli netlist export loads and lists the six pins.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.elk_layout import resolve_symbol_geometry
from bodesign_eda_bridge.kicad_emit import (
    EmitComponent,
    emit_kicad_schematic,
    load_symbol,
    resolve_symbol_library,
)

REPO = Path(__file__).resolve().parents[1]
VENDOR_DIR = REPO / "packages" / "eda-bridge" / "vendor_symbols"
SYSTEM_DIR = "/usr/share/kicad/symbols"
BOXED = "Bodesign_Presentation:PESD5V0L4UF_Boxed"
STOCK = "Power_Protection:PESD5V0L4UF"
HAVE_SYMBOLS = Path(SYSTEM_DIR, "Power_Protection.kicad_sym").is_file()
HAVE_KICAD = bool(shutil.which("kicad-cli"))

# Datasheet Table 3 (p.2), PESD3V3L4UF; PESD5V0L4UF rows.
DATASHEET_FUNCTION = {"1": "cathode", "2": "common anode", "3": "cathode",
                      "4": "cathode", "5": "common anode", "6": "cathode"}
EXPECTED_NAMES = {"1": "K1", "2": "A", "3": "K2", "4": "K3", "5": "A", "6": "K4"}


def _lib_text() -> str:
    return (VENDOR_DIR / "Bodesign_Presentation.kicad_sym").read_text(encoding="utf-8")


class AuthoredSymbolIdentity(unittest.TestCase):
    def test_six_pin_partition_matches_datasheet_function(self):
        text = _lib_text()
        pins = re.findall(
            r'\(pin (\w+) line\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*\(length [\d.]+\)\s*(\(hide yes\))?\s*'
            r'\(name "([^"]+)".*?\(number "(\d+)"', text, re.S)
        got = {p[6]: (p[5], p[0], p[4] != "") for p in pins}
        self.assertEqual(sorted(got), sorted(DATASHEET_FUNCTION))
        for number, function in DATASHEET_FUNCTION.items():
            name, ptype, hidden = got[number]
            self.assertEqual(name, EXPECTED_NAMES[number])
            self.assertEqual(ptype, "passive")
            self.assertEqual(name.startswith("K"), function == "cathode")
            self.assertEqual(name == "A", function == "common anode")
        # pin 5 is a distinct hidden pin object; pin 2 stays visible
        self.assertTrue(got["5"][2])
        self.assertFalse(got["2"][2])

    def test_pins_2_and_5_stacked_and_cathodes_distinct(self):
        _d, tips = load_symbol(BOXED, [str(VENDOR_DIR), SYSTEM_DIR])
        self.assertEqual(sorted(tips), ["1", "2", "3", "4", "5", "6"])
        self.assertEqual(tips["2"], tips["5"])
        cathodes = {tips[p][:2] for p in ("1", "3", "4", "6")}
        self.assertEqual(len(cathodes), 4, "cathode tips must be distinct points")
        self.assertNotIn(tips["2"][:2], cathodes)
        for p in ("1", "3", "4", "6"):
            self.assertEqual(tips[p][2], 0.0)       # left side, pointing out
        self.assertEqual(tips["2"][2], 180.0)       # right side

    def test_fixed_property_values(self):
        text = _lib_text()
        self.assertRegex(text, r'\(property "Footprint" ""')
        self.assertNotIn("Package_TO_SOT_SMD", text)
        self.assertIn('(property "Value" "PESD5V0L4UF"', text)
        self.assertIn("https://assets.nexperia.com/documents/data-sheet/PESDXL4UF_G_W.pdf", text)

    def test_body_graphics_present(self):
        d, _tips = load_symbol(BOXED, [str(VENDOR_DIR), SYSTEM_DIR])
        self.assertEqual(len(re.findall(r"\(rectangle", d)), 1)
        self.assertEqual(len(re.findall(r"\(circle", d)), 3)   # anode-bus junction dots only


@unittest.skipUnless(HAVE_SYMBOLS, f"KiCad symbol library not at {SYSTEM_DIR}")
class ExplicitSelectionOnly(unittest.TestCase):
    def test_not_registered_in_resolver(self):
        # symbol_resolver imports kiutils (absent on the host interpreter), so the
        # resolver source is read as text instead of imported: it must not mention
        # the authored library or symbol at all.
        src = (Path(__file__).resolve().parent.parent / "packages" / "eda-bridge"
               / "bodesign_eda_bridge" / "symbol_resolver.py").read_text(encoding="utf-8")
        self.assertNotIn("Bodesign_Presentation", src)
        self.assertNotIn("PESD5V0L4UF_Boxed", src)
        self.assertNotIn('"PESD5V0L4UF"', src)

    def test_stock_symbol_not_shadowed_by_vendor_dir(self):
        with_vendor = resolve_symbol_library(STOCK, [str(VENDOR_DIR), SYSTEM_DIR])
        without = resolve_symbol_library(STOCK, [SYSTEM_DIR])
        self.assertEqual(with_vendor, without)
        self.assertEqual(with_vendor.name, "Power_Protection.kicad_sym")
        self.assertFalse((VENDOR_DIR / "Power_Protection.kicad_sym").exists())
        a, _ = load_symbol(STOCK, [str(VENDOR_DIR), SYSTEM_DIR])
        b, _ = load_symbol(STOCK, [SYSTEM_DIR])
        self.assertEqual(a, b)

    def test_unrelated_ref_resolves_identically_and_d1_selects_by_lib_id(self):
        comps = [
            EmitComponent(ref="R1", lib_id="Device:R", value="5.1k", footprint="", x=0, y=0),
            EmitComponent(ref="D1", lib_id=BOXED, value="PESD5V0L4UF", footprint="", x=0, y=0),
            EmitComponent(ref="D9", lib_id=STOCK, value="PESD5V0L4UF", footprint="", x=0, y=0),
        ]
        both = resolve_symbol_geometry(comps, [str(VENDOR_DIR), SYSTEM_DIR])
        plain = resolve_symbol_geometry(comps[:1] + comps[2:], [SYSTEM_DIR])
        self.assertEqual(both["R1"].pins, plain["R1"].pins)
        self.assertEqual(both["R1"].gfx, plain["R1"].gfx)
        self.assertEqual(both["D9"].pins, plain["D9"].pins)     # stock D resolves as before
        self.assertNotEqual(both["D1"].pins, both["D9"].pins)   # boxed one is the explicit pick

    def test_boxed_symbol_unreachable_without_explicit_dir(self):
        with self.assertRaises((FileNotFoundError, KeyError)):
            load_symbol(BOXED, [SYSTEM_DIR])


@unittest.skipUnless(HAVE_SYMBOLS and HAVE_KICAD,
                     "needs the KiCad symbol library and kicad-cli (named, not silently green)")
class FreshNativeExport(unittest.TestCase):
    def test_emit_loads_in_kicad_cli_and_lists_six_pins(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("XDG_RUNTIME_DIR")) as td:
            comps = [EmitComponent(ref="D1", lib_id=BOXED, value="PESD5V0L4UF",
                                   footprint="", x=100.33, y=77.47)]
            res = emit_kicad_schematic(td, "tb", comps, [], symbol_dir=[str(VENDOR_DIR), SYSTEM_DIR],
                                       connection_style="wire", power_ports=False)
            sch = Path(res.schematic_path)
            net = Path(td) / "tb.net"
            subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                            "-o", str(net), str(sch)], check=True, capture_output=True)
            text = net.read_text(encoding="utf-8")
            self.assertIn("Bodesign_Presentation", text)
            nums = re.findall(r'\(pin \(num "(\d+)"\) \(name "([^"]+)"\) \(type "passive"\)\)', text)
            self.assertEqual({n: nm for n, nm in nums}, EXPECTED_NAMES)
            svg = Path(td) / "svg"
            subprocess.run(["kicad-cli", "sch", "export", "svg", "-o", str(svg), str(sch)],
                           check=True, capture_output=True)
            self.assertTrue(list(svg.glob("*.svg")))


if __name__ == "__main__":
    unittest.main()
