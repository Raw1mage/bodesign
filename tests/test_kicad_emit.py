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
from bodesign_eda_bridge.kicad_emit import _collinear_overlap, _segment_fuses

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

        # component_count counts ALL emitted symbol blocks: the 3 user parts PLUS
        # any synthesized power-port / PWR_FLAG glyphs (GND is a power net here, so
        # its endpoints become power ports + one flag). Assert the user-part floor
        # rather than a brittle exact total that shifts with power-symbol emission.
        self.assertGreaterEqual(result.component_count, 3)
        # embedded_symbols now also carries synthesized power-port / PWR_FLAG defs
        # (GND/VIN become power ports); assert the user part libs are present rather
        # than an exact list that shifts with power-symbol emission.
        self.assertLessEqual({"Device:C", "Device:R"}, set(result.embedded_symbols))
        self.assertEqual([], result.unresolved_pins)
        self.assertEqual([], result.warnings)
        # MID has 3 nodes (signal net -> global labels); GND/VIN are power nets now
        # emitted as power ports instead of labels, so only MID's 3 pins carry labels.
        self.assertEqual(3, result.label_count)
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

    def test_emit_places_no_connect_glyphs_for_declared_nc_pins(self):
        components, nets = _divider()
        # VIN leaves R1.1 attached; declare C1.2's partner-free R2.2... use a truly
        # open pin: R1.1 is on VIN (single-pin net) — declare it NC instead.
        result = emit_kicad_schematic(
            self.work, "ncok", components, nets, symbol_dir=SYMBOL_DIR, nc=["R1.1"]
        )

        self.assertEqual(1, result.no_connect_count)
        schematic = Path(result.schematic_path).read_text(encoding="utf-8")
        self.assertIn("(no_connect (at ", schematic)

    def test_emit_raises_on_unresolvable_nc_entries(self):
        components, nets = _divider()

        with self.assertRaises(ValueError) as ctx:
            emit_kicad_schematic(
                self.work, "ncbad", components, nets, symbol_dir=SYMBOL_DIR,
                nc=["R1.1", "ZZ9.1", "R2.99"],
            )
        message = str(ctx.exception)
        self.assertIn("ZZ9.1", message)
        self.assertIn("R2.99", message)
        self.assertNotIn("R1.1,", message)  # resolvable entry not reported as bad

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

    # DD-11 anti-fusion guard: two DIFFERENT nets whose drawn wires would run
    # COLLINEAR on the same x column must NOT share any collinear-overlapping
    # segment after emit (KiCad fuses those into one net = short). The guard
    # deterministically jogs the free axis or down-grades to label (recorded).
    def _wire_segments(self, sch: str) -> list[tuple]:
        # parse every (wire (pts (xy X Y) (xy X Y))) into ((x1,y1),(x2,y2)).
        import re as _re
        out = []
        for m in _re.finditer(
            r"\(wire \(pts \(xy (-?[\d.]+) (-?[\d.]+)\) \(xy (-?[\d.]+) (-?[\d.]+)\)\)", sch):
            x1, y1, x2, y2 = map(float, m.groups())
            out.append(((x1, y1), (x2, y2)))
        return out

    def test_anti_fusion_guard_prevents_collinear_cross_net_wires(self):
        # Four resistors stacked on ONE x column. NET_A joins R1.2→R4.1 (a long
        # vertical run spanning the column); NET_B joins R2.2→R3.1 which is NESTED
        # inside NET_A's span on the SAME column — the two runs are collinear and
        # their intervals overlap, so KiCad would fuse them into one net. The guard
        # must jog NET_B off the column (or down-grade it).
        components = [
            EmitComponent("R1", "Device:R", "", "", 100, 100),
            EmitComponent("R2", "Device:R", "", "", 100, 110),
            EmitComponent("R3", "Device:R", "", "", 100, 120),
            EmitComponent("R4", "Device:R", "", "", 100, 130),
        ]
        nets = [
            EmitNet("NET_A", [("R1", "2"), ("R4", "1")]),
            EmitNet("NET_B", [("R2", "2"), ("R3", "1")]),
        ]
        result = emit_kicad_schematic(
            self.work, "fusion", components, nets,
            symbol_dir=SYMBOL_DIR, connection_style="wire")
        sch = Path(result.schematic_path).read_text(encoding="utf-8")
        segs = self._wire_segments(sch)
        # Assert NO two emitted wire segments collinearly overlap. If the guard
        # down-graded a net to label, that net contributes no wire segment (so no
        # overlap) AND is recorded in fusion_label_fallbacks (visible).
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                self.assertFalse(
                    _collinear_overlap(segs[i], segs[j]),
                    f"collinear cross-segment fusion survived: {segs[i]} X {segs[j]}")
        # The guard must have acted (either jogged NET_B off the column or
        # down-graded it): the fusion never silently ships.
        acted = bool(result.fusion_jogged_nets) or bool(result.fusion_label_fallbacks)
        self.assertTrue(acted, "guard did not act on a collinear cross-net layout")

    def test_anti_fusion_guard_untouched_when_no_collision(self):
        # A layout with NO cross-net collinearity (two horizontally-separated Rs on
        # a single 2-node net) must not trip the guard at all: no jog, no label
        # down-grade. Guard only mutates geometry on a detected collision (R6).
        components = [
            EmitComponent("R1", "Device:R", "", "", 100, 100),
            EmitComponent("R2", "Device:R", "", "", 140, 100),
        ]
        nets = [EmitNet("NET_X", [("R1", "2"), ("R2", "1")])]
        r = emit_kicad_schematic(self.work, "clean", components, nets,
                                 symbol_dir=SYMBOL_DIR, connection_style="wire")
        self.assertEqual([], r.fusion_label_fallbacks)
        self.assertEqual([], r.fusion_jogged_nets)

    def test_collinear_overlap_helper_semantics(self):
        # unit-level guard math: same vertical line, overlapping interval = fuse.
        self.assertTrue(_collinear_overlap(((5, 0), (5, 10)), ((5, 4), (5, 12))))
        # same line, only touching at one point = NOT a fusing overlap.
        self.assertFalse(_collinear_overlap(((5, 0), (5, 10)), ((5, 10), (5, 20))))
        # different vertical lines = no overlap.
        self.assertFalse(_collinear_overlap(((5, 0), (5, 10)), ((6, 0), (6, 10))))


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
