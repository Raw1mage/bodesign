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

        # BR_20260804c: what must hold is that NO TWO NETS FUSED -- not that the
        # guard did something. The old assertion required `fusion_jogged_nets or
        # fusion_label_fallbacks` to be non-empty, i.e. it asserted THE DEFECT WAS
        # PRESENT: once the escape-stub over-shoot was fixed (commit 4690737) this
        # layout no longer produces a cross-net collinear run at all, so the guard
        # correctly does nothing and a "the guard must have acted" test necessarily
        # goes red. Do not restore it, and do not silence this by de-duplicating
        # segments -- read the partition instead.
        #
        # KiCad computes the partition itself, so ask IT rather than inferring net
        # ownership from wire geometry: the emitted netlist is the same instrument
        # a real short would show up in.
        validation = validate_kicad_schematic(result.schematic_path)
        self.assertEqual("validated", validation.status)
        emitted = {frozenset(n["nodes"]) for n in validation.netlist_nets
                   if len(n.get("nodes", ())) > 1}
        declared = {frozenset(f"{ref}.{pin}" for ref, pin in net.nodes) for net in nets}
        self.assertEqual(declared, emitted,
                         "net partition diverged from the spec -- two nets fused")

        # Geometry-level backstop, now net-aware: two segments may legally be
        # collinear when they belong to the SAME net (a straight run split at a
        # waypoint). Only a CROSS-net overlap is a short.
        owner = self._segment_owner(validation.netlist_nets, components)
        segs = self._wire_segments(Path(result.schematic_path).read_text(encoding="utf-8"))
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                if owner(segs[i]) is not None and owner(segs[i]) == owner(segs[j]):
                    continue                      # same net -- collinearity is fine
                self.assertFalse(
                    _collinear_overlap(segs[i], segs[j]),
                    f"collinear CROSS-NET fusion survived: {segs[i]} X {segs[j]}")

    def _segment_owner(self, netlist_nets, components):
        """Map a wire segment to the net name that owns it, by matching either
        endpoint against a pin coordinate of a component on that net. Returns a
        callable; None means "could not attribute" (an interior elbow), which the
        caller must treat as cross-net rather than assuming same-net -- an
        unattributable segment has to fail safe, or the check loses its power."""
        pins = {}
        for comp in components:
            _defn, pmap = load_symbol(comp.lib_id, SYMBOL_DIR)
            for number, (lx, ly, *_rest) in pmap.items():
                pins[(round(comp.x + lx, 2), round(comp.y - ly, 2))] = f"{comp.ref}.{number}"
        node_net = {}
        for entry in netlist_nets:
            for node in entry.get("nodes", ()):
                node_net[node] = entry["name"]

        def owner(seg):
            for pt in seg:
                node = pins.get((round(pt[0], 2), round(pt[1], 2)))
                if node is not None and node in node_net:
                    return node_net[node]
            return None
        return owner

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


# ---------------------------------------------------------------------------
# BR_20260723e regression fixture — collinear-wire fusion on a minimal 2-node net.
#
# SHRUNK from the BR's original repro (U1=AMS1117 + R1 + R2 series divider) by
# delta-debug, each cut re-checked for reproduction and the final candidate
# re-checked that ONE MORE cut stops reproducing (BR_20260804 §minimality):
#   drop VIN (1-pin net)          -> still reproduces
#   drop VO  (U1->R1 link)        -> still reproduces
#   drop U1  entirely             -> still reproduces      <- LDO is NOT needed
#   remove the 2nd net            -> STOPS  (nothing to fuse into)
#   remove R1 (single resistor)   -> STOPS  (no 2-node net -> no drawn wire)
#   swap which R2 pin each net uses -> STOPS (wire no longer spans the body)
# So the minimal trigger is TWO RESISTORS, not a three-part series chain, and
# the BR's "same column series chain" framing is not the necessary condition.
#
# MECHANISM (measured, not inferred): with R1/R2 side by side, the 2-node VOUT
# wire enters R2's TOP pin from BELOW, so its vertical leg runs the full height
# of R2's body and passes exactly through R2's BOTTOM pin -- which belongs to
# GND. KiCad fuses a wire to any pin it crosses, so VOUT and GND short.
#
# All three anti-fusion layers are blind to this by construction:
#   guard A (_segment_fuses vs fusion_registry) - GND has no registered segment
#       yet (emission order) and, once down-graded to a label, never gets one.
#   guard C (body keep-out) - R2 is an ENDPOINT HOST of VOUT, so its own box is
#       dropped by _obstacles_excluding(); the box WOULD have blocked the leg.
#   the jog retry - the route is 5 waypoints and _jog_free_axis only handles
#       len 2 and 3, so all three "retries" return the input unchanged.
#
# These tests lock the GEOMETRIC PRECONDITION on the _orthogonal_route path, not
# just the fidelity verdict: BR_20260723b (power-port bypass) also surfaces as
# `fused` at the fidelity layer, so a fidelity-only assertion cannot tell "723e
# was fixed" from "723e became unreachable".
# ---------------------------------------------------------------------------
class CollinearFusionMinimalTests(unittest.TestCase):
    # R2 sits at this sheet position in the minimal spec; both values come from
    # the emitted schematic, and the test re-derives them so it fails loudly if
    # placement changes rather than silently testing nothing.
    VOUT_LEG = ((199.39, 110.49), (199.39, 100.33))
    R2_BOTTOM_PIN = (199.39, 109.22)   # GND node
    R2_TOP_PIN = (199.39, 101.6)       # VOUT node (the wire's legitimate end)

    def test_wire_leg_crosses_the_other_pin_of_its_own_endpoint_host(self):
        """The fusion precondition itself: VOUT's leg contains R2's GND pin."""
        from bodesign_eda_bridge.kicad_emit import _point_on_segment
        self.assertTrue(_point_on_segment(self.R2_BOTTOM_PIN, self.VOUT_LEG),
                        "fusion precondition gone -- re-derive the fixture")
        # CONTROL: the probe must also see the leg's own endpoint ...
        self.assertTrue(_point_on_segment(self.R2_TOP_PIN, self.VOUT_LEG))
        # ... and must NOT see a point in a different column, or one past the end.
        self.assertFalse(_point_on_segment((175.26, 109.22), self.VOUT_LEG))
        self.assertFalse(_point_on_segment((199.39, 120.0), self.VOUT_LEG))

    def test_own_host_box_would_have_blocked_the_leg_but_is_excluded(self):
        """guard C had the geometry to stop this; _obstacles_excluding drops it."""
        from bodesign_eda_bridge.kicad_emit import (
            WIRE_KEEPOUT_MM, _body_rect, _seg_hits_box)
        block, _pins = load_symbol("Device:R", SYMBOL_DIR)
        rect = _body_rect(block)
        self.assertIsNotNone(rect, "Device:R lost its body rectangle")
        rx0, ry0, rx1, ry1 = rect
        cx, cy = 199.39, 105.41                      # R2 placement
        m = WIRE_KEEPOUT_MM
        box = (min(cx + rx0, cx + rx1) - m, max(cx + rx0, cx + rx1) + m,
               min(cy - ry0, cy - ry1) - m, max(cy - ry0, cy - ry1) + m)
        a, b = self.VOUT_LEG
        self.assertTrue(_seg_hits_box(a, b, box),
                        "R2's own keep-out box no longer covers the leg")
        # CONTROL: a far-away segment must NOT hit the same box.
        self.assertFalse(_seg_hits_box((50.0, 50.0), (50.0, 60.0), box))

    def test_jog_retry_is_a_silent_noop_beyond_three_waypoints(self):
        """_guard_route retries 3x; on a 5-waypoint route every retry is identical."""
        from bodesign_eda_bridge.kicad_emit import _jog_free_axis
        five = [(199.39, 109.22), (199.39, 110.49), (101.6, 110.49),
                (101.6, 114.3), (101.6, 113.03)]
        for offset in (-3.81, 2.54, 1.27):
            self.assertEqual(five, _jog_free_axis(five, offset),
                             "jog now handles 5 waypoints -- update this test")
        # CONTROL: the two documented arities DO change, so the probe has power.
        two = [(100.0, 100.0), (100.0, 110.0)]
        three = [(100.0, 100.0), (110.0, 100.0), (110.0, 120.0)]
        self.assertNotEqual(two, _jog_free_axis(two, 2.54))
        self.assertNotEqual(three, _jog_free_axis(three, 2.54))


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries are not installed")
@unittest.skipUnless(HAS_KICAD_CLI, "kicad-cli is not installed")
class CollinearFusionComposeTests(unittest.TestCase):
    """End-to-end half of the BR_20260723e fixture. Self-contained: the spec is
    literal here, nothing is read from issues/assets_* or experiments/."""

    MINIMAL_SPEC = {
        "components": [
            {"ref": "R1", "symbol": "Device:R", "value": "20k"},
            {"ref": "R2", "symbol": "Device:R", "value": "10k"},
        ],
        "nets": [
            {"name": "VOUT", "nodes": ["R1.2", "R2.1"]},
            {"name": "GND", "nodes": ["R2.2"]},
        ],
    }

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-fusion-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _compose(self, spec, name):
        from bodesign_eda_bridge.composer import compose_schematic
        return compose_schematic(self.work / name, name, spec, symbol_dirs=SYMBOL_DIR,
                                 style="draftsman", validate=True, fidelity=True)

    def test_minimal_two_resistor_spec_still_shorts(self):
        """XFAIL-style guard: this MUST raise until the fusion defect is fixed.

        When it stops raising, that is the fix landing -- delete the raise
        expectation and assert the partition instead. It must NOT be relaxed to
        `try/except: pass`, which would make a fix and a regression identical."""
        from bodesign_eda_bridge.fidelity import FidelityError
        with self.assertRaises(FidelityError) as ctx:
            self._compose(self.MINIMAL_SPEC, "min")
        # Lock WHICH nodes move, so an unrelated fidelity failure cannot pass.
        message = str(ctx.exception)
        self.assertIn("R2.1", message)
        self.assertIn("R2.2", message)

    def test_one_more_cut_stops_reproducing(self):
        """Minimality control. If these start raising, the fixture is no longer
        isolating the fusion mechanism and the shrink must be redone."""
        single_net = {"components": self.MINIMAL_SPEC["components"],
                      "nets": [{"name": "VOUT", "nodes": ["R1.2", "R2.1"]}]}
        self._compose(single_net, "cut_net")          # must not raise
        swapped = {"components": self.MINIMAL_SPEC["components"],
                   "nets": [{"name": "VOUT", "nodes": ["R1.2", "R2.2"]},
                            {"name": "GND", "nodes": ["R2.1"]}]}
        self._compose(swapped, "cut_swap")            # must not raise
