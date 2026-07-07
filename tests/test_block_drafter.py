"""Unit + integration tests for block_drafter (eda_draftsman-v2 task 1.3/1.4).

Pure-logic class: exercises the deterministic geometry helpers (_edge_of,
_pin_end, _label_box, _Box overlap + stagger) with NO kicad-cli/symbols needed.

Integration class (guarded): draws a real official symbol then runs the QA
gates, asserting the draft→render→QA loop closes green on a unique-net pinout.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.block_drafter import (
    _Box,
    _edge_of,
    _label_box,
    _pin_end,
    _power_lib_id,
    STAGGER_STEP,
    draw_block,
)
from bodesign_eda_bridge.block_qa import qa_block
from bodesign_eda_bridge.kicad_emit import _power_net_kind
from bodesign_eda_bridge.symbol_resolver import _VENDOR_ROOT

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
HAS_KICAD_CLI = shutil.which("kicad-cli") is not None
HAS_VENDOR = (_VENDOR_ROOT / "ST_vendor.kicad_sym").exists()
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class BlockDrafterUnitTests(unittest.TestCase):
    """Pure-logic tests — no KiCad needed."""

    def test_edge_of_angle_mapping(self):
        # KiCad pin angle = direction pin points AWAY from body.
        self.assertEqual(_edge_of(0), "left")     # extends right -> left edge
        self.assertEqual(_edge_of(180), "right")  # extends left  -> right edge
        self.assertEqual(_edge_of(90), "bottom")  # extends up    -> bottom edge
        self.assertEqual(_edge_of(270), "top")    # extends down  -> top edge

    def test_edge_of_wraps_and_rounds(self):
        self.assertEqual(_edge_of(360.0), "left")   # 360 % 360 == 0
        self.assertEqual(_edge_of(89.6), "bottom")  # rounds to 90
        self.assertEqual(_edge_of(-90), "top")      # -90 % 360 == 270

    def test_pin_end_coordinates(self):
        # angle 0: free end extends +X
        self.assertEqual(_pin_end(0, 0, 0, 2.54), (2.54, 0))
        # angle 180: free end extends -X
        self.assertEqual(_pin_end(0, 0, 180, 2.54), (-2.54, 0))
        # angle 90: KiCad Y grows downward, "up" = -Y
        self.assertEqual(_pin_end(0, 0, 90, 2.54), (0, -2.54))
        # angle 270: "down" = +Y
        self.assertEqual(_pin_end(0, 0, 270, 2.54), (0, 2.54))

    def test_pin_end_respects_origin(self):
        self.assertEqual(_pin_end(5, 3, 0, 1.0), (6, 3))
        self.assertEqual(_pin_end(5, 3, 180, 1.0), (4, 3))

    def test_label_box_justify_left(self):
        # anchor at left, text extends right
        box = _label_box("ABCD", ax=10.0, ay=0.0, justify="left")
        self.assertAlmostEqual(box.x0, 10.0)
        self.assertGreater(box.x1, box.x0)
        # width scales with char count
        self.assertAlmostEqual(box.x1 - box.x0, 4 * 1.27)

    def test_label_box_justify_right(self):
        # anchor at right, text extends left
        box = _label_box("ABCD", ax=10.0, ay=0.0, justify="right")
        self.assertAlmostEqual(box.x1, 10.0)
        self.assertLess(box.x0, box.x1)
        self.assertAlmostEqual(box.x1 - box.x0, 4 * 1.27)

    def test_label_box_justify_center(self):
        box = _label_box("ABCD", ax=10.0, ay=0.0, justify="center")
        w = 4 * 1.27
        self.assertAlmostEqual(box.x0, 10.0 - w / 2)
        self.assertAlmostEqual(box.x1, 10.0 + w / 2)

    def test_label_box_min_width_for_empty(self):
        # a zero-length string still gets >=1 char width (no degenerate box)
        box = _label_box("", ax=0.0, ay=0.0, justify="left")
        self.assertAlmostEqual(box.x1 - box.x0, 1.27)

    def test_box_overlap_detects_collision(self):
        a = _Box(0, 0, 5, 2)
        b = _Box(1, 0, 6, 2)   # heavily overlapping in x
        self.assertTrue(a.overlaps(b))

    def test_box_overlap_clear_when_separated(self):
        a = _Box(0, 0, 5, 2)
        b = _Box(10, 0, 15, 2)  # well apart in x (> pad)
        self.assertFalse(a.overlaps(b))

    def test_stagger_resolves_same_anchor_collision(self):
        # Two labels initially at the SAME anchor+justify collide; replicating
        # the drafter's outward-stagger loop must separate them into two
        # non-overlapping boxes (this is the anti-"stacked labels" invariant).
        text = "NETNAME"
        ax, ay, justify = 0.0, 0.0, "right"
        placed: list[_Box] = []

        def place_one():
            nonlocal ax
            local_ax = ax
            box = _label_box(text, local_ax, ay, justify)
            tries = 0
            while any(box.overlaps(b) for b in placed) and tries < 6:
                local_ax -= STAGGER_STEP   # left edge staggers -X (matches drafter)
                box = _label_box(text, local_ax, ay, justify)
                tries += 1
            placed.append(box)
            return box

        box1 = place_one()
        box2 = place_one()
        self.assertFalse(box1.overlaps(box2),
                         "stagger must separate two same-anchor labels")
        self.assertEqual(len(placed), 2)

    def test_power_net_classifier_routes_power_and_signal(self):
        # DD-9 Part 1 pure-logic contract: the power-net classifier (REUSED from
        # kicad_emit, the legacy SSOT) sends ground/supply names down the
        # power-port path (kind is not None -> a stock power lib_id) and signal
        # names down the ordinary label path (kind is None). This locks the
        # drafter's routing decision without needing kicad-cli/symbols.
        for gnd in ("GND", "VSS", "AGND", "DGND", "VSSA"):
            self.assertEqual(_power_net_kind(gnd), "gnd", gnd)
            self.assertEqual(_power_lib_id(gnd, "gnd"), "power:GND", gnd)
        for sup in ("VDD", "VCC", "+3V3", "+5V", "+1V8", "VDDA"):
            self.assertEqual(_power_net_kind(sup), "supply", sup)
            # supply lib_id is the net name verbatim under the power: nickname
            self.assertEqual(_power_lib_id(sup, "supply"), f"power:{sup}", sup)
        # signal nets are NOT power: they must fall through to the label path
        for sig in ("UCPD1_CC1", "SPI1_SCK", "PH2", "NET_FOO", "RESET_N"):
            self.assertIsNone(_power_net_kind(sig), sig)


@unittest.skipUnless(HAS_SYMBOLS and HAS_KICAD_CLI, "KiCad symbols + cli required")
class BlockDrafterIntegrationTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-blockdraft-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_draw_then_qa_unique_nets_pass(self):
        # A 4-pin connector where every pin has a UNIQUE net: no multi-pin
        # connectivity class to reconstruct, so fidelity has nothing to diverge
        # on and the render/roundtrip gates carry the verdict -> PASS.
        pin_map = {"1": "SIG_A", "2": "SIG_B", "3": "SIG_C", "4": "SIG_D"}
        blk = draw_block("Connector_Generic:Conn_01x04", pin_map, out_dir=self.work)
        self.assertTrue(Path(blk.sch_path).exists(), "block .kicad_sch not emitted")
        self.assertEqual(set(blk.ports), {"SIG_A", "SIG_B", "SIG_C", "SIG_D"})

        verdict = qa_block(blk.sch_path, blk.pin_map, block_id=blk.block_id)
        # render + roundtrip must always be clean on a valid emit
        self.assertEqual(verdict.roundtrip_exit, 0, verdict.summary())
        self.assertTrue(verdict.render_qa_ok, verdict.summary())
        self.assertTrue(verdict.ok, verdict.summary())

    def test_shared_gnd_connector_connects_and_passes(self):
        # Regression lock for task 1.5: two pins mapped to the SAME net (GND) on a
        # connector. Before the fix, draw_block placed floating local labels and
        # (worse) emitted a symbol instance kicad-cli could not bind to its
        # libpart, so the shared GND never joined -> fidelity FAIL(2)
        # CONNECTIVITY_DIVERGE. The fix draws a stub wire from each pin's ROOT
        # connection point (Y-mirrored) to its label anchor AND keys the
        # lib_symbols entry by the full lib_id + emits per-pin instance uuids, so
        # the two GND pins now reconstruct into ONE net. This is the exact case
        # that failed before; it MUST now pass BOTH gates (fidelity + render_qa).
        pin_map = {"1": "SIG_A", "2": "SIG_B", "3": "GND", "4": "GND"}
        blk = draw_block("Connector_Generic:Conn_01x04", pin_map, out_dir=self.work,
                         block_id="shared_gnd")
        verdict = qa_block(blk.sch_path, blk.pin_map, block_id=blk.block_id)
        self.assertEqual(verdict.roundtrip_exit, 0, verdict.summary())
        self.assertTrue(verdict.fidelity_ok,
                        "shared GND must reconstruct into one net: " + verdict.summary())
        self.assertEqual(verdict.fidelity_diff, 0, verdict.summary())
        self.assertTrue(verdict.ok, verdict.summary())


@unittest.skipUnless(HAS_VENDOR and HAS_KICAD_CLI,
                     "vendor STM32 symbol + kicad-cli required")
class BlockDrafterStm32IntegrationTests(unittest.TestCase):
    """DD-8 + DD-9 + rotated-axis lock-in on the dense VFBGA223 vendor symbol.

    The STM32N657 crammed identical power labels onto dense top/bottom edges
    (24xVDD / 17xGND) and anchored signal labels onto the vendor pin-name grid.
    DD-9 routes power/ground nets to stock power-port symbols (auto-joining,
    compact -> density dissolves) and seeds the vendor pin-name/number boxes into
    the stagger `placed` list (signal labels avoid vendor pin text). This test
    asserts the whole loop closes green on a REALISTIC readable pin_map (power
    rails via power-ports forming >=2-pin fidelity classes + a modest signal set),
    NOT all 223 balls as text labels.
    """
    VENDOR_LIB = "ST_vendor:STM32N657L0H3Q"

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-stm32-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _realistic_pin_map(self):
        from bodesign_eda_bridge.symbol_index import resolve
        _, sym = resolve(self.VENDOR_LIB, _VENDOR_ROOT)
        pins = [p for u in sym.units for p in u.pins]
        by_name = {}
        for p in pins:
            by_name.setdefault(p.name, []).append(p.number)
        pin_map = {}
        # ground + supply rails -> power-ports (each a >=2-pin fidelity class)
        for pn in by_name.get("VSS", []):
            pin_map[pn] = "GND"
        for pn in by_name.get("VDD", []):
            pin_map[pn] = "+3V3"
        for pn in by_name.get("VDDIO2", []):
            pin_map[pn] = "+1V8"
        # a modest set of signal labels (unique nets -> plain labels)
        signal = [p for p in pins
                  if p.name not in ("VSS", "VDD", "VDDIO2", "NC")
                  and p.name and p.name != "~"][:8]
        for p in signal:
            pin_map[p.number] = f"NET_{p.name}"
        return pin_map

    def test_stm32n657_block_reaches_verdict_ok(self):
        pin_map = self._realistic_pin_map()
        blk = draw_block(self.VENDOR_LIB, pin_map, out_dir=self.work,
                         block_id="stm32n657", lib_root=_VENDOR_ROOT)
        # power rails chosen all have stock symbols -> no gaps expected here
        self.assertEqual(blk.power_gaps, [], f"unexpected power gaps: {blk.power_gaps}")
        verdict = qa_block(blk.sch_path, blk.pin_map, block_id=blk.block_id)
        self.assertEqual(verdict.roundtrip_exit, 0, verdict.summary())
        self.assertTrue(verdict.fidelity_ok,
                        "shared power rails must reconstruct: " + verdict.summary())
        self.assertTrue(verdict.render_qa_ok,
                        "scoped render_qa must be clean (power-ports dissolve "
                        "density; signal labels avoid pin text): " + verdict.summary())
        self.assertTrue(verdict.ok, verdict.summary())


if __name__ == "__main__":
    unittest.main()
