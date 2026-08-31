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
        # Endpoints are (x, y, rotation) since DD-26/27: rotation is the pin's
        # outward direction (270 = -y for the top pin, 90 = +y for the bottom
        # one). Asserted in full on purpose — a wrong rotation must turn this
        # test red, since it is the sole edge signal for label placement.
        self.assertEqual((0.0, 3.81, 270.0), pins["1"])
        self.assertEqual((0.0, -3.81, 90.0), pins["2"])

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


class GuardCInsetClampTests(unittest.TestCase):
    """BR_20260804b: guard C shrinks each component's body box by a fixed inset
    (`_PWR_STUB_STEP_MM/4` = 1.905mm) so a power port hugging the body edge is
    tolerated. On a body narrower than 2*inset the shrink INVERTED the interval
    (bx0 > bx1), making `bx0 < ex < bx1` unsatisfiable -- the guard then reported
    nothing for that component, which is byte-identical to "no intrusion found".

    These lock the GEOMETRIC PREMISE, not a fidelity verdict: a downstream change
    that silently restores the inversion must fail here even if no page happens to
    have an intruding port at that moment. Measured on this repo: 516 of 21437
    flattened library symbols inverted on at least one axis, `Device:R` among them.
    """

    INSET = 1.905          # _PWR_STUB_STEP_MM / 4.0
    CX = CY = 100.0

    def _extent(self, lib_id):
        """The component's body extent, placed at (CX, CY) -- guard C's INPUT."""
        from bodesign_eda_bridge.kicad_emit import (
            load_symbol, _body_rect, _PWR_STUB_STEP_MM,
        )
        self.assertAlmostEqual(_PWR_STUB_STEP_MM / 4.0, self.INSET, places=6,
                               msg="inset constant drifted; update this fixture")
        block, _pmap = load_symbol(lib_id)
        rect = _body_rect(block)
        self.assertIsNotNone(rect, f"{lib_id} has no rectangle; not a guard-C case")
        rx0, ry0, rx1, ry1 = rect
        xs = [self.CX + rx0, self.CX + rx1]
        ys = [self.CY - ry0, self.CY - ry1]
        return min(xs), max(xs), min(ys), max(ys)

    def _box(self, lib_id):
        """Guard C's body box for `lib_id`, obtained by CALLING the production
        helper -- never by re-deriving it here.

        The first version of this suite recomputed the shrink inline. It passed,
        and it kept passing when the clamp was mutated out of the emitter: a test
        that reimplements the rule verifies its own copy, so its green says nothing
        about the code that ships. That is the exact defect class this file exists
        to catch, one level up."""
        from bodesign_eda_bridge.kicad_emit import _guard_c_body_box
        return _guard_c_body_box(*self._extent(lib_id))

    @staticmethod
    def _inside(box, px, py):
        bx0, bx1, by0, by1 = box
        return bx0 < px < bx1 and by0 < py < by1

    def test_narrow_body_box_does_not_invert(self):
        """`Device:R` (2.032mm wide) and `Device:Polyfuse` (1.524mm) are both
        narrower than 2*inset. Without the clamp bx0 > bx1 and the guard is blind."""
        for lib in ("Device:R", "Device:Polyfuse"):
            with self.subTest(lib=lib):
                bx0, bx1, by0, by1 = self._box(lib)
                self.assertLess(bx0, bx1, f"{lib}: x interval inverted (guard blind)")
                self.assertLess(by0, by1, f"{lib}: y interval inverted (guard blind)")

    def test_narrow_body_box_has_discriminating_power(self):
        """Not inverting is necessary but not sufficient: the box must actually
        contain points that lie inside the real body. The component's own centre
        is unambiguously interior."""
        for lib in ("Device:R", "Device:Polyfuse"):
            with self.subTest(lib=lib):
                box = self._box(lib)
                self.assertTrue(self._inside(box, self.CX, self.CY),
                                f"{lib}: centre not inside box -- guard still blind")

    def test_far_point_is_outside(self):
        """Control. If the predicate said yes to everything, the test above would
        pass for the wrong reason."""
        for lib in ("Device:R", "Device:Polyfuse",
                    "Connector:USB_C_Receptacle_USB2.0_16P"):
            with self.subTest(lib=lib):
                box = self._box(lib)
                self.assertFalse(self._inside(box, 1000.0, 1000.0),
                                 f"{lib}: predicate accepts a point 900mm away")

    def test_non_degenerate_body_is_untouched(self):
        """Blast-radius control, and the reason the degrade is CONDITIONAL rather
        than `min(inset, span*k)`. Any min() form perturbs every body in the band
        `span < inset/k`, including ones whose unclamped box was perfectly valid --
        measured: `min(inset, span/4)` moved 1631 never-blind symbols, AMS1117
        (y-span 6.985mm) among them. Tightening the guard on already-verified pages
        is how a fix manufactures new raises.

        The real no-op threshold is `span > 2*inset` (3.81mm) -- exactly the
        condition under which the unclamped box is non-degenerate. AMS1117 sits
        between 2*inset and 4*inset, so it is precisely the symbol that tells the
        two rules apart: it MUST be untouched here."""
        from bodesign_eda_bridge.kicad_emit import load_symbol, _body_rect
        for lib in ("Connector:USB_C_Receptacle_USB2.0_16P",
                    "Regulator_Linear:AMS1117-3.3"):
            with self.subTest(lib=lib):
                block, _pmap = load_symbol(lib)
                rx0, ry0, rx1, ry1 = _body_rect(block)
                xs = [self.CX + rx0, self.CX + rx1]
                ys = [self.CY - ry0, self.CY - ry1]
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                self.assertGreater(x1 - x0, 2 * self.INSET,
                                   f"{lib} is degenerate on x; pick another")
                self.assertGreater(y1 - y0, 2 * self.INSET,
                                   f"{lib} is degenerate on y; pick another")
                del xs, ys
                unclamped = (x0 + self.INSET, x1 - self.INSET,
                             y0 + self.INSET, y1 - self.INSET)
                self.assertEqual(self._box(lib), unclamped,
                                 f"{lib}: degrade perturbed a non-degenerate body")

    def test_ams1117_is_the_discriminating_case(self):
        """Control for the control. If AMS1117 ever stopped sitting in the band
        `2*inset < span <= 4*inset`, the test above would still pass while having
        lost the only sample that distinguishes the conditional rule from a
        `min(inset, span/4)` one."""
        from bodesign_eda_bridge.kicad_emit import load_symbol, _body_rect
        block, _pmap = load_symbol("Regulator_Linear:AMS1117-3.3")
        rx0, ry0, rx1, ry1 = _body_rect(block)
        span_y = abs((self.CY - ry1) - (self.CY - ry0))
        self.assertGreater(span_y, 2 * self.INSET)
        self.assertLessEqual(span_y, 4 * self.INSET,
                             "AMS1117 left the discriminating band; find another "
                             "symbol with 3.81 < span <= 7.62 or these tests no "
                             "longer tell the two clamp forms apart")


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries are not installed")
class GuardCFloatingPointBoundaryTests(unittest.TestCase):
    """BR_20260804b §8: the CONDITIONAL degrade compared `span > 2*inset`, and a
    span sitting ONE ULP above the threshold took the "wide enough" branch --
    shrinking by the full inset and leaving a box ~5e-16 wide. That box is just as
    unsatisfiable as an inverted one, so the guard reported nothing, which is
    byte-identical to "no intrusion found": the exact defect the conditional
    degrade was introduced to remove, surviving on a rounding artefact.

    Measured by two independent sweeps of /usr/share/kicad/symbols (223 libs,
    21437 root-level symbols, 3 load failures reported): `Mechanical:Housing_Pad`
    is the ONLY symbol in the library whose span lands in that one-ULP band, and
    the tolerance moves exactly that one axis of that one symbol.

    Every box below comes from CALLING the production helper. A test that
    recomputes the rule verifies its own copy and stays green when the shipped
    code is mutated.
    """

    BOUNDARY = "Mechanical:Housing_Pad"

    def _helper(self):
        from bodesign_eda_bridge.kicad_emit import _guard_c_body_box
        return _guard_c_body_box

    def _inset(self):
        from bodesign_eda_bridge.kicad_emit import _PWR_STUB_STEP_MM
        return _PWR_STUB_STEP_MM / 4.0

    def _width(self, span):
        """Guard C's box width for a square body of side `span`."""
        box = self._helper()(0.0, span, 0.0, span)
        return box[1] - box[0]

    def test_boundary_span_is_exactly_one_ulp_above_the_threshold(self):
        """Fixture control. The whole point of a one-ULP tolerance is that this
        symbol's span is a rounding artefact, not a genuinely wider body. If the
        library ever ships a real 3.82mm pad this test must fail rather than let
        the tolerance quietly cover a body it was never measured against."""
        import math
        from bodesign_eda_bridge.kicad_emit import load_symbol, _body_rect
        block, _pins = load_symbol(self.BOUNDARY, SYMBOL_DIR)
        rect = _body_rect(block)
        self.assertIsNotNone(rect, f"{self.BOUNDARY} lost its rectangle")
        span_x = rect[2] - rect[0]
        threshold = 2 * self._inset()
        self.assertGreater(span_x, threshold,
                           "span no longer sits ABOVE the threshold; the old "
                           "comparison would already degrade it and this suite "
                           "no longer tests anything")
        self.assertEqual(span_x - threshold, math.ulp(threshold),
                         "span is no longer exactly one ULP above 2*inset")

    def test_boundary_symbol_box_is_usable(self):
        """The defect itself: the box must have real width, not ~5e-16."""
        from bodesign_eda_bridge.kicad_emit import load_symbol, _body_rect
        block, _pins = load_symbol(self.BOUNDARY, SYMBOL_DIR)
        rx0, ry0, rx1, ry1 = _body_rect(block)
        bx0, bx1, by0, by1 = self._helper()(rx0, rx1, ry0, ry1)
        width = bx1 - bx0
        self.assertGreater(
            width, 0.1,
            f"{self.BOUNDARY}: guard C box is {width!r} wide -- the predicate "
            f"`bx0 < ex < bx1` is unsatisfiable, i.e. still blind")
        # Discriminating power, not merely non-degeneracy: the body centre is
        # unambiguously interior and must be inside the box.
        self.assertTrue(bx0 < (rx0 + rx1) / 2 < bx1,
                        f"{self.BOUNDARY}: centre not inside box -- still blind")

    def test_wide_bodies_keep_the_full_inset(self):
        """Reverse-direction control -- the risk this fix carries. A tolerance wide
        enough to catch the boundary must NOT push genuinely wide bodies onto the
        clamp branch. Measured over the whole library: 0 such symbols move, and
        the 40.64 sample is not vacuous (768 axes hit it exactly)."""
        inset = self._inset()
        for span in (10.0, 40.64):
            with self.subTest(span=span):
                self.assertAlmostEqual(
                    self._width(span), span - 2 * inset, places=9,
                    msg=f"span {span} left the inset branch -- the tolerance is "
                        f"perturbing bodies it was never measured against")

    def test_below_threshold_bodies_are_unchanged(self):
        """Control on the other side of the boundary: a span just BELOW the
        threshold already degraded before this fix and must still degrade the
        same way (span/4), or the tolerance changed more than the one axis it
        was measured to change."""
        for span in (3.809999999999999, 2.032, 1.524):
            with self.subTest(span=span):
                self.assertAlmostEqual(self._width(span), span / 2.0, places=9,
                                       msg=f"span {span} left the clamp branch")


class PowerPortIntrusionsFieldTests(unittest.TestCase):
    """BR_20260804f: `SchematicEmitResult.power_port_intrusions` was declared with
    a docstring promising the guard-C intrusions are "recorded here", and was never
    assigned -- so an instrument reading it per the docstring got [] while the SAME
    compose emitted a warning naming an intrusion. [] meant both "none found" and
    "nobody wrote it".

    The warning string is lossy (truncates at 12 + "(+N more)"), so this field is
    the only channel that can carry entry 13. These lock that it is populated AND
    that it agrees with the warning."""

    SPEC = "experiments/e2e-led-driver/C03-EE/e2e-led-driver-npn.spec.json"
    PREFIX = "POWER_PORT_INSIDE_SYMBOL_BODY:"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ppi_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        repo = Path(__file__).resolve().parents[1]
        self.spec_path = repo / self.SPEC
        if not self.spec_path.exists():
            self.skipTest(f"real-page spec absent: {self.spec_path}")

    def _warning_count(self, warnings):
        import re as _re
        for w in warnings:
            if self.PREFIX in w:
                tail = w.split("blind): ", 1)[1]
                m = _re.search(r"\(\+(\d+) more\)$", tail)
                more = int(m.group(1)) if m else 0
                listed = _re.sub(r"\s*\(\+\d+ more\)$", "", tail)
                return len([e for e in listed.split("; ") if e.strip()]) + more
        return 0

    def test_field_is_populated_and_agrees_with_the_warning(self):
        import json
        from bodesign_eda_bridge.composer import compose_schematic
        spec = json.loads(self.spec_path.read_text())
        result = compose_schematic(os.path.join(self.tmp, "p"), "ppi", spec,
                                   validate=False, style="netlist",
                                   power_port_gate="warn")
        field = list(getattr(result.emit, "power_port_intrusions", []) or [])
        warned = self._warning_count(result.warnings)
        # Control: if this page stopped producing an intrusion the test would pass
        # vacuously (0 == 0), so require the page to still exercise the guard.
        self.assertGreater(warned, 0,
                           "page no longer trips guard C; fixture needs revisiting")
        self.assertEqual(len(field), warned,
                         "field disagrees with the warning it is supposed to mirror")
        for entry in field:
            self.assertRegex(entry, r"^.+@\(.+,.+\) inside .+$")


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
class GuardCNoRectFallbackTests(unittest.TestCase):
    """BR_20260804g: guard C read ONLY `body_rects`, so a symbol that draws no
    `(rectangle ...)` fell through to the pin-tip extent -- which is DEGENERATE
    (zero width or height) whenever the pins are collinear or there is one pin.
    `bx0 < ex < bx1` is then unsatisfiable and the guard reports nothing, which is
    byte-identical to "no intrusion found".

    Measured over /usr/share/kicad/symbols (22582 top-level symbols, 150 load
    failures reported): 4216 draw no rectangle, 1198 of those produce a degenerate
    box, and the drawn-graphics extent recovers a real 2-D body for 1192 of them.

    The fallback is a LAST RESORT, not a preference. Guard C asks "is this point
    INSIDE the body", so a larger box means FALSE POSITIVES -- the opposite of the
    obstacle-avoidance consumers (:1169/:1567) which prefer graphics precisely
    because larger is safer there. Preferring graphics here would change the
    verdict for 1026 of the 1030 rect-bearing symbols whose graphics differ from
    their rect, on pages that are already verified.

    Every assertion below drives the real `emit_kicad_schematic`; none recomputes
    the box. A suite that re-derives the rule verifies its own copy and stays green
    when the emitter is mutated (the defect class BR_20260804b's suite exists to
    catch, one level up)."""

    # Rect-bearing host that carries the power pins the ports are drawn from.
    HOST = "Regulator_Linear:AMS1117-3.3"
    # NO-RECT, 2-pin, pins collinear on x -> pin-tip box is 0-wide (the defect).
    NORECT = "Device:C"
    # Rect-bearing AND graphics != rect: its polyline body frame runs 6.35 mm
    # ABOVE the rectangle, so body-first and graphics-first disagree on the y span
    # (11.43 mm vs 17.78 mm). This is what makes it the discriminating sample.
    RECT_BEARING = "4xxx_IEEE:4006"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="norect_", dir=str(PRIVATE_BASE)
                                    if PRIVATE_BASE.exists() else None)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _emit(self, other_ref, other_lib, ox, oy, hx=150.0, hy=100.0):
        components = [
            EmitComponent(ref="U1", lib_id=self.HOST, x=hx, y=hy),
            EmitComponent(ref=other_ref, lib_id=other_lib, x=ox, y=oy),
        ]
        nets = [
            EmitNet(name="GND", nodes=[("U1", "1"), (other_ref, "1")]),
            EmitNet(name="VIN", nodes=[("U1", "3"), (other_ref, "2")]),
        ]
        return emit_kicad_schematic(self.tmp, "norect", components, nets,
                                    symbol_dir=SYMBOL_DIR,
                                    power_port_gate="warn")

    def _guard_c_inputs(self, **kwargs):
        """Every (x0, x1, y0, y1) extent guard C fed to the production helper.

        Spying on the helper is what makes this test see the emitter's OWN choice
        of rect. Reading only `power_port_intrusions` cannot: a page where the box
        changed but no port happens to land in it reports the same count as a page
        where the fallback never ran -- absent and unchanged share one output."""
        import bodesign_eda_bridge.kicad_emit as ke
        captured = []
        original = ke._guard_c_body_box

        def spy(x0, x1, y0, y1, inset=None):
            captured.append((x0, x1, y0, y1))
            return original(x0, x1, y0, y1) if inset is None \
                else original(x0, x1, y0, y1, inset)

        ke._guard_c_body_box = spy
        try:
            self._emit(**kwargs)
        finally:
            ke._guard_c_body_box = original
        return captured

    @staticmethod
    def _degenerate(extent):
        x0, x1, y0, y1 = extent
        return x1 - x0 <= 0.0 or y1 - y0 <= 0.0

    def test_norect_symbol_no_longer_yields_a_degenerate_extent(self):
        """M-A target. Without the fallback `Device:C` reaches the helper as a
        0-wide extent and the guard is blind for it."""
        extents = self._guard_c_inputs(other_ref="C1", other_lib=self.NORECT,
                                       ox=142.38, oy=100.0)
        # Control: the emitter must actually have built a box per component, or
        # "no degenerate extents" would be true because there are no extents.
        self.assertEqual(len(extents), 2,
                         "guard C did not build one box per component")
        degenerate = [e for e in extents if self._degenerate(e)]
        self.assertEqual(degenerate, [],
                         f"a degenerate extent survived: {degenerate}")

    def test_norect_symbol_actually_reports_an_intrusion(self):
        """M-A target, end to end: the recovered box must not merely be non-
        degenerate, it must let the guard SEE a port that sits inside the body.
        Measured on this fixture: 0 intrusions before the fallback, 1 after."""
        result = self._emit(other_ref="C1", other_lib=self.NORECT,
                            ox=142.38, oy=100.0)
        found = [e for e in (result.power_port_intrusions or [])
                 if "inside C1" in e]
        self.assertEqual(len(found), 1,
                         f"expected exactly one intrusion inside C1, got "
                         f"{result.power_port_intrusions}")

    def test_far_port_placement_reports_nothing(self):
        """Control for the two above. If the recovered box accepted everything,
        they would pass for the wrong reason."""
        result = self._emit(other_ref="C1", other_lib=self.NORECT,
                            ox=142.38, oy=250.0)
        found = [e for e in (result.power_port_intrusions or [])
                 if "inside C1" in e]
        self.assertEqual(found, [],
                         f"guard C accepted a port 150mm from the body: {found}")

    def test_rect_bearing_symbol_still_uses_its_rectangle(self):
        """M-B / M-C target: the fallback is reachable ONLY when there is no
        rectangle. `4xxx_IEEE:4006` HAS one, and its drawn graphics are 6.35 mm
        taller, so an unconditional `graphics or rect` would hand guard C a
        17.78 mm span instead of the rectangle's 11.43 mm -- silently widening
        the keep-out on 1026 already-verified symbols."""
        from bodesign_eda_bridge.kicad_emit import (
            load_symbol, _body_rect, _graphics_bbox)
        block, _pins = load_symbol(self.RECT_BEARING, SYMBOL_DIR)
        rect, graphics = _body_rect(block), _graphics_bbox(block)
        self.assertIsNotNone(rect, f"{self.RECT_BEARING} lost its rectangle")

        # Compare ASPECT RATIOS, not absolute spans. `_vendor_sym_scale` lifts a
        # >=4-pin symbol's geometry so its rendered pin pitch reaches the page
        # floor -- this one is a 13-pin part loaded at scale 3.0, so the extent the
        # emitter builds is 3x what an unscaled `load_symbol` here reports. The
        # first version of this test asserted the raw span and failed at 45.72 vs
        # 15.24: a control that does not go through the same pipeline as the thing
        # it controls measures a different quantity. Scaling multiplies both axes
        # equally, so h/w survives it.
        def _ratio(box):
            return abs(box[3] - box[1]) / abs(box[2] - box[0])

        rect_ratio, graphics_ratio = _ratio(rect), _ratio(graphics)
        # Fixture control: the two must still DISAGREE, or this test cannot tell
        # body-first from graphics-first at all.
        self.assertNotAlmostEqual(
            rect_ratio, graphics_ratio, places=3,
            msg=f"{self.RECT_BEARING} graphics no longer differ from its rect; "
                f"this sample can no longer discriminate the two orders")

        extents = self._guard_c_inputs(other_ref="U2",
                                       other_lib=self.RECT_BEARING,
                                       ox=60.0, oy=60.0, hx=120.0, hy=60.0)
        # Guard C shrinks each extent by a fixed inset on both axes, which is NOT
        # ratio-preserving, so undo it before comparing. The helper's own constant
        # is the source of truth for how much came off.
        from bodesign_eda_bridge.kicad_emit import _PWR_STUB_STEP_MM
        ratios = [round(abs(y1 - y0) / abs(x1 - x0), 3)
                  for x0, x1, y0, y1 in extents if abs(x1 - x0) > 0]
        self.assertIn(round(rect_ratio, 3), ratios,
                      f"guard C never saw the rectangle's shape (h/w "
                      f"{rect_ratio:.3f}); saw {ratios}")
        self.assertNotIn(round(graphics_ratio, 3), ratios,
                         f"guard C used the GRAPHICS shape (h/w "
                         f"{graphics_ratio:.3f}) for a symbol that HAS a "
                         f"rectangle; the fallback is no longer conditional")
        del _PWR_STUB_STEP_MM
