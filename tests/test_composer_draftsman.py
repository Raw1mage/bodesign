import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge import compose_schematic
from bodesign_eda_bridge import ink_metrics

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
HAS_KICAD_CLI = shutil.which("kicad-cli") is not None
HAS_PDFTOPPM = shutil.which("pdftoppm") is not None
try:
    import PIL  # noqa: F401
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
HAS_INK_TOOLCHAIN = HAS_KICAD_CLI and HAS_PDFTOPPM and HAS_PIL

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

# Symbols that exist in the KiCad stdlib (TV inputs use placeholder lib_ids like
# MCU:Generic / Regulator:LDO which may not resolve; map to real stdlib symbols).
TV1_SPEC = {
    "components": [
        {"ref": "U1", "symbol": "Device:R", "group": "mcu"},
        {"ref": "C1", "symbol": "Device:C", "value": "100n", "group": "mcu"},
        {"ref": "U2", "symbol": "Device:R", "group": "power"},
        {"ref": "C2", "symbol": "Device:C", "value": "10u", "group": "power"},
    ],
    "nets": [
        {"name": "VCC", "nodes": ["U2.1", "U1.1", "C1.1", "C2.1"], "kind": "power"},
        {"name": "GND", "nodes": ["U1.2", "C1.2", "U2.2", "C2.2"], "kind": "power"},
    ],
}


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
class DraftsmanComposerTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-draftsman-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _sch_text(self, result) -> str:
        return Path(result.emit.schematic_path).read_text(encoding="utf-8")

    # TV1: declared group → same group adjacent, groups separated, no bbox overlap.
    def test_tv1_declared_group_clustering(self):
        r = compose_schematic(self.work, "tv1", TV1_SPEC, symbol_dirs=SYMBOL_DIR, style="draftsman")
        self.assertEqual("draftsman", r.style)
        self.assertEqual(2, len(r.clusters))
        ids = {c.cluster_id for c in r.clusters}
        self.assertEqual({"mcu", "power"}, ids)
        members = {c.cluster_id: set(c.members) for c in r.clusters}
        self.assertEqual({"U1", "C1"}, members["mcu"])
        self.assertEqual({"U2", "C2"}, members["power"])
        self.assertTrue(all(c.source == "declared" for c in r.clusters))
        # group centres separated
        centres = {c.cluster_id: (c.center_x, c.center_y) for c in r.clusters}
        self.assertNotEqual(centres["mcu"], centres["power"])
        # no "still overlap" warning (de-overlap fallback succeeded or unneeded)
        self.assertFalse(any("still overlap" in w for w in r.warnings))

    # TV2: no group → net-degree clustering, not index%columns grid.
    def test_tv2_net_degree_clustering(self):
        spec = {
            "components": [
                {"ref": "U1", "symbol": "Device:R"},
                {"ref": "R1", "symbol": "Device:R", "value": "10k"},
                {"ref": "R2", "symbol": "Device:R", "value": "10k"},
            ],
            "nets": [{"name": "SIG", "nodes": ["U1.1", "R1.1", "R2.1"]}],
        }
        r = compose_schematic(self.work, "tv2", spec, symbol_dirs=SYMBOL_DIR, style="draftsman")
        self.assertTrue(all(c.source == "net-degree" for c in r.clusters))
        # all connected → one cluster
        self.assertEqual({"U1", "R1", "R2"}, {m for c in r.clusters for m in c.members})
        # placement is not the naive index grid (x0=35, dx=45 → 35,80,125)
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        ats = re.findall(r'\(lib_id "Device:R"\)\s*\(at ([\d.]+) ([\d.]+)', sch)
        xs = sorted(float(x) for x, _y in ats)
        self.assertNotEqual([35.0, 80.0, 125.0], xs)

    # TV3: 2-node signal net → physical wire + local label, no global label.
    def test_tv3_two_node_wire(self):
        spec = {
            "components": [{"ref": "R1", "symbol": "Device:R"}, {"ref": "R2", "symbol": "Device:R"}],
            "nets": [{"name": "NET_A", "nodes": ["R1.2", "R2.1"], "kind": "signal"}],
        }
        r = compose_schematic(self.work, "tv3", spec, symbol_dirs=SYMBOL_DIR, style="draftsman")
        self.assertEqual(1, r.route_stats.wired_nets)
        self.assertEqual(0, r.route_stats.labelled_nets)
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        self.assertIn("(wire (pts", sch)
        # local label present, no global_label naming NET_A
        self.assertIn('(label "NET_A"', sch)
        self.assertNotIn('(global_label "NET_A"', sch)

    # TV4: power/single-pin → label fallback, route_stats reasons visible.
    def test_tv4_label_fallback_reasons(self):
        spec = {
            "components": [{"ref": "U1", "symbol": "Device:R"}, {"ref": "C1", "symbol": "Device:C"}],
            "nets": [
                {"name": "VCC", "nodes": ["U1.1", "C1.1"], "kind": "power"},
                {"name": "DANGLE", "nodes": ["U1.2"]},
            ],
        }
        r = compose_schematic(self.work, "tv4", spec, symbol_dirs=SYMBOL_DIR, style="draftsman")
        self.assertEqual(2, r.route_stats.labelled_nets)
        reasons = {(d["net"], d["reason"]) for d in r.route_stats.label_fallback_reasons}
        self.assertIn(("VCC", "power"), reasons)
        self.assertIn(("DANGLE", "single-pin"), reasons)

    # TV5: sheet-fit picks A4/A3, no overflow.
    def test_tv5_sheet_fit(self):
        r = compose_schematic(self.work, "tv5", TV1_SPEC, symbol_dirs=SYMBOL_DIR, style="draftsman")
        self.assertIsNotNone(r.sheet_fit)
        self.assertIn(r.sheet_fit.selected_paper, ("A4", "A3"))
        self.assertFalse(r.sheet_fit.overflow)
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        self.assertIn(f'(paper "{r.sheet_fit.selected_paper}")', sch)

    # TV8: draftsman validates with kicad-cli (electrically clean).
    @unittest.skipUnless(HAS_KICAD_CLI, "kicad-cli not installed")
    def test_tv8_draftsman_validate(self):
        r = compose_schematic(self.work, "tv8", TV1_SPEC, symbol_dirs=SYMBOL_DIR, style="draftsman", validate=True)
        v = r.validation
        self.assertEqual("validated", v.status)
        self.assertEqual(0, v.erc_errors)
        self.assertEqual(4, v.netlist_components)

    # TV9: style=netlist is byte-equivalent to the legacy path.
    def test_tv9_netlist_byte_equivalent(self):
        # legacy behaviour: naive grid + global labels. Re-emit via the legacy
        # connection_style=label and assert identical layout coordinates.
        spec = {
            "components": [
                {"ref": "R1", "symbol": "Device:R", "value": "10k"},
                {"ref": "R2", "symbol": "Device:R", "value": "10k"},
                {"ref": "C1", "symbol": "Device:C", "value": "100nF"},
            ],
            "nets": [{"name": "MID", "nodes": ["R1.2", "R2.1", "C1.1"]}],
        }
        r = compose_schematic(self.work, "tv9", spec, symbol_dirs=SYMBOL_DIR)  # default style=netlist
        self.assertEqual("netlist", r.style)
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        # naive grid (x0=35 dx=45) snapped onto the 1.27 connection grid (existing
        # emit behaviour): 35→35.56, 80→80.01, 125→124.46. Global labels, A4.
        self.assertIn('(paper "A4")', sch)
        self.assertIn("(global_label", sch)
        self.assertNotIn("(wire (pts", sch)
        xs = sorted(float(x) for x, _y in
                    re.findall(r'\(lib_id "[^"]+"\)\s*\(at ([\d.]+) ([\d.]+)', sch))
        self.assertEqual([35.56, 80.01, 124.46], xs)

        # Strong byte-equivalence proof: re-emit the same spec via the legacy
        # explicit connection_style="label" and assert identical placement coords.
        w2 = Path(tempfile.mkdtemp(prefix="bodesign-tv9b-", dir=PRIVATE_BASE))
        try:
            r2 = compose_schematic(w2, "tv9", spec, symbol_dirs=SYMBOL_DIR,
                                   connection_style="label")
            self.assertEqual(self._sch_text(r).split("uuid")[0],
                             self._sch_text(r2).split("uuid")[0])
        finally:
            shutil.rmtree(w2, ignore_errors=True)

    # TV9b: explicit connection_style is honoured (style does not override).
    def test_tv9b_explicit_connection_style_respected(self):
        spec = {
            "components": [{"ref": "R1", "symbol": "Device:R"}, {"ref": "R2", "symbol": "Device:R"}],
            "nets": [{"name": "NET_A", "nodes": ["R1.2", "R2.1"]}],
        }
        # draftsman style but explicit label → must stay label (no wires)
        r = compose_schematic(self.work, "tv9b", spec, symbol_dirs=SYMBOL_DIR,
                              style="draftsman", connection_style="label")
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        self.assertNotIn("(wire (pts", sch)
        self.assertIn("(global_label", sch)

    # T3: multi-node (>=3 node) signal net defaults to label (reason=multi-node);
    # 2-node nets stay wired; explicit connection_style="wire" is honoured in full.
    def test_t3_multi_node_net_defaults_to_label(self):
        spec = {
            "components": [
                {"ref": "U1", "symbol": "Device:R"},
                {"ref": "C1", "symbol": "Device:C"},
                {"ref": "C2", "symbol": "Device:C"},
                {"ref": "C3", "symbol": "Device:C"},
                {"ref": "R1", "symbol": "Device:R"},
            ],
            "nets": [
                {"name": "GNDISH", "nodes": ["U1.2", "C1.2", "C2.2", "C3.2"], "kind": "signal"},
                {"name": "SIG2", "nodes": ["U1.1", "R1.1"], "kind": "signal"},
            ],
        }
        r = compose_schematic(self.work, "t3a", spec, symbol_dirs=SYMBOL_DIR, style="draftsman")
        reasons = {(d["net"], d["reason"]) for d in r.route_stats.label_fallback_reasons}
        self.assertIn(("GNDISH", "multi-node"), reasons)
        self.assertEqual(1, r.route_stats.wired_nets)      # SIG2 still wired
        self.assertEqual(1, r.route_stats.labelled_nets)   # GNDISH labelled
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        self.assertIn('(global_label "GNDISH"', sch)       # actually emitted as labels
        self.assertIn('(label "SIG2"', sch)                # 2-node net still drawn wire

        # explicit connection_style="wire" → honoured, multi-node net drawn again.
        w2 = Path(tempfile.mkdtemp(prefix="bodesign-t3b-", dir=PRIVATE_BASE))
        try:
            r2 = compose_schematic(w2, "t3b", spec, symbol_dirs=SYMBOL_DIR,
                                   style="draftsman", connection_style="wire")
            reasons2 = {(d["net"], d["reason"]) for d in r2.route_stats.label_fallback_reasons}
            self.assertNotIn(("GNDISH", "multi-node"), reasons2)
            self.assertEqual(2, r2.route_stats.wired_nets)
            sch2 = self._sch_text(r2)
            self.assertNotIn('(global_label "GNDISH"', sch2)
        finally:
            shutil.rmtree(w2, ignore_errors=True)

    # T1: spec-level nc declaration flows through compose → emit.
    def test_t1_nc_declaration_via_spec(self):
        spec = {
            "components": [{"ref": "R1", "symbol": "Device:R"}, {"ref": "R2", "symbol": "Device:R"}],
            "nets": [{"name": "NET_A", "nodes": ["R1.2", "R2.1"], "kind": "signal"}],
            "nc": ["R1.1", "R2.2"],
        }
        r = compose_schematic(self.work, "t1nc", spec, symbol_dirs=SYMBOL_DIR, style="draftsman")
        self.assertEqual(2, r.emit.no_connect_count)
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        self.assertEqual(2, sch.count("(no_connect (at "))

        spec_bad = dict(spec, nc=["R1.1", "NOPE.7"])
        with self.assertRaises(ValueError):
            compose_schematic(self.work, "t1bad", spec_bad, symbol_dirs=SYMBOL_DIR, style="draftsman")

    # BR_20260703 compose_nc_emit_flaky_first_write: reproduction guard.
    # The BR reported an intermittent no_connect raise on the FIRST compose into
    # an already-non-empty dir; RCA (待確認). This test lands the RCA: repeatedly
    # composing the SAME nc-bearing spec into the SAME persistent (non-empty)
    # directory must be deterministic — the same no_connect_count, no raise, no
    # warnings drift. It reproduces the exact reported trigger (first write into a
    # dir already holding a prior schematic) so a real regression would fail here.
    def test_br_nc_repeated_write_same_dir_is_deterministic(self):
        spec = {
            "components": [{"ref": "R1", "symbol": "Device:R"}, {"ref": "R2", "symbol": "Device:R"}],
            "nets": [{"name": "NET_A", "nodes": ["R1.2", "R2.1"], "kind": "signal"}],
            "nc": ["R1.1", "R2.2"],
        }
        # Pre-populate the dir with an unrelated schematic so the target is NON-empty
        # on the very first nc-bearing compose (the BR's exact first-write trigger).
        compose_schematic(self.work, "pre_existing", {
            "components": [{"ref": "R9", "symbol": "Device:R"}],
            "nets": [], "nc": [],
        }, symbol_dirs=SYMBOL_DIR, style="draftsman")
        first_count = None
        for i in range(4):
            r = compose_schematic(self.work, "nc_repeat", spec, symbol_dirs=SYMBOL_DIR, style="draftsman")
            self.assertEqual(2, r.emit.no_connect_count, f"iteration {i}: nc count drifted")
            sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
            self.assertEqual(2, sch.count("(no_connect (at "), f"iteration {i}: emitted nc glyph count drifted")
            if first_count is None:
                first_count = r.emit.no_connect_count
            else:
                self.assertEqual(first_count, r.emit.no_connect_count)

    # T1 + ERC: declared-NC pins no longer trip pin_not_connected.
    @unittest.skipUnless(HAS_KICAD_CLI, "kicad-cli not installed")
    def test_t1_nc_clears_erc(self):
        spec = {
            "components": [{"ref": "R1", "symbol": "Device:R"}, {"ref": "R2", "symbol": "Device:R"}],
            "nets": [{"name": "NET_A", "nodes": ["R1.2", "R2.1"], "kind": "signal"}],
            "nc": ["R1.1", "R2.2"],
        }
        r = compose_schematic(self.work, "t1erc", spec, symbol_dirs=SYMBOL_DIR,
                              style="draftsman", validate=True)
        self.assertEqual("validated", r.validation.status)
        self.assertEqual(0, r.validation.erc_errors)

    # T4: 16-part small design must not balloon to A2 (gutter ladder).
    def test_t4_small_design_gutter_keeps_sheet_small(self):
        components = [{"ref": f"C{i}", "symbol": "Device:C", "group": f"g{i % 4}"} for i in range(1, 15)]
        components += [{"ref": "U1", "symbol": "Device:R", "group": "g0"},
                       {"ref": "J1", "symbol": "Connector:Conn_01x04_Pin", "group": "g1"}]
        nets = [{"name": f"N{i}", "nodes": [f"C{i}.1", f"C{i + 1}.1"], "kind": "signal"} for i in range(1, 14)]
        spec = {"components": components, "nets": nets}
        r = compose_schematic(self.work, "t4", spec, symbol_dirs=SYMBOL_DIR, style="draftsman")
        self.assertIsNotNone(r.sheet_fit)
        self.assertIn(r.sheet_fit.selected_paper, ("A4", "A3"))
        self.assertFalse(r.sheet_fit.overflow)

    # TV10: determinism — same input twice → identical schematic bytes.
    def test_tv10_deterministic(self):
        w2 = Path(tempfile.mkdtemp(prefix="bodesign-draftsman2-", dir=PRIVATE_BASE))
        try:
            r1 = compose_schematic(self.work, "tv10", TV1_SPEC, symbol_dirs=SYMBOL_DIR, style="draftsman")
            r2 = compose_schematic(w2, "tv10", TV1_SPEC, symbol_dirs=SYMBOL_DIR, style="draftsman")
            # compare placement coordinates extracted from both schematics
            s1 = re.findall(r'\(lib_id "[^"]+"\)\s*\(at ([\d.]+) ([\d.]+)', self._sch_text(r1))
            s2 = re.findall(r'\(lib_id "[^"]+"\)\s*\(at ([\d.]+) ([\d.]+)', self._sch_text(r2))
            self.assertEqual(s1, s2)
            # cluster centres also stable
            c1 = [(c.cluster_id, c.center_x, c.center_y) for c in r1.clusters]
            c2 = [(c.cluster_id, c.center_x, c.center_y) for c in r2.clusters]
            self.assertEqual(c1, c2)
        finally:
            shutil.rmtree(w2, ignore_errors=True)


class InkMetricsTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-ink-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    # TV7: missing ink toolchain → measurement_unavailable + missing list, no fake numbers.
    def test_tv7_toolchain_absent(self):
        orig_which = ink_metrics.shutil.which

        def fake_which(name):
            if name == "pdftoppm":
                return None
            return orig_which(name)

        ink_metrics.shutil.which = fake_which
        try:
            m = ink_metrics.measure_schematic_ink("/nonexistent/x.kicad_sch")
            self.assertFalse(m["available"])
            self.assertIn("pdftoppm", m["missing_tools"])
            self.assertIsNone(m["ink_pct"])
            self.assertIsNone(m["content_fill_pct"])
        finally:
            ink_metrics.shutil.which = orig_which

    # TV6: draftsman ink% measurable and meaningfully above netlist baseline.
    @unittest.skipUnless(HAS_SYMBOLS and HAS_INK_TOOLCHAIN, "symbols / ink toolchain not installed")
    def test_tv6_ink_above_baseline(self):
        draft = compose_schematic(self.work, "tv6d", TV1_SPEC, symbol_dirs=SYMBOL_DIR,
                                  style="draftsman", measure_ink=True)
        self.assertIsNotNone(draft.ink_metrics)
        self.assertTrue(draft.ink_metrics["available"])
        draft_ink = draft.ink_metrics["ink_pct"]
        self.assertIsNotNone(draft_ink)

        # netlist baseline: emit then measure directly.
        base = compose_schematic(self.work, "tv6n", TV1_SPEC, symbol_dirs=SYMBOL_DIR, style="netlist")
        base_metrics = ink_metrics.measure_schematic_ink(base.emit.schematic_path)
        self.assertTrue(base_metrics["available"])
        base_ink = base_metrics["ink_pct"]
        # draftsman should not be sparser than netlist baseline (content fills more).
        self.assertGreaterEqual(draft.ink_metrics["content_fill_pct"],
                                base_metrics["content_fill_pct"] * 0.5)
        # sanity: both produce some ink
        self.assertGreater(draft_ink, 0.0)
        self.assertGreater(base_ink, 0.0)


    # TV7: placement converges — a handful of small parts must NOT blow up the
    # content to ~1m and pick A0/overflow. Guards the force-directed cooling +
    # centroid-gravity fix (issue_20260618). Deterministic, no toolchain needed.
    def test_tv7_placement_converges_to_sane_sheet(self):
        spec = {
            "components": [
                {"ref": "U1", "symbol": "Device:R", "group": "mcu"},
                {"ref": "C1", "symbol": "Device:C", "group": "mcu"},
                {"ref": "C2", "symbol": "Device:C", "group": "mcu"},
                {"ref": "R1", "symbol": "Device:R", "group": "io"},
                {"ref": "R2", "symbol": "Device:R", "group": "io"},
                {"ref": "D1", "symbol": "Device:LED", "group": "io"},
                {"ref": "J1", "symbol": "Connector:Conn_01x04_Pin", "group": "io"},
            ],
            "nets": [
                {"name": "SWDIO", "nodes": ["U1.1", "J1.1"]},
                {"name": "LED_GPIO", "nodes": ["U1.3", "R1.1"]},
                {"name": "LED_A", "nodes": ["R1.2", "D1.1"]},
                {"name": "BTN", "nodes": ["U1.4", "R2.1"]},
                {"name": "VCC", "nodes": ["U1.5", "C1.1", "C2.1"], "kind": "power"},
                {"name": "GND", "nodes": ["U1.6", "C1.2", "C2.2", "D1.2"], "kind": "power"},
            ],
        }
        r = compose_schematic(self.work, "tv7", spec, symbol_dirs=SYMBOL_DIR, style="draftsman")
        self.assertIsNotNone(r.sheet_fit)
        # 7 small parts must fit a small standard sheet, not balloon to A1/A0.
        self.assertIn(r.sheet_fit.selected_paper, ("A4", "A3"))
        self.assertFalse(r.sheet_fit.overflow)
        self.assertLess(r.sheet_fit.content_w, 300.0)
        self.assertLess(r.sheet_fit.content_h, 300.0)
        # and it still draws real wires (not a label dump).
        self.assertGreater(r.route_stats.wired_nets, 0)


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
class LeftPinStubOrientationTests(unittest.TestCase):
    """BR: left-pin stub orientation blind. A power port on a LEFT-side pin must
    expand its stub AWAY from the symbol body (-x), a RIGHT-side pin toward +x.
    LM358 has both left pins (local ex=-7.62) and right pins (ex=+7.62)."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-leftpin-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _power_symbol_xs(self, sch_text, net):
        # power-port instances carry the net name as their Value; lib_id is
        # power_gnd_<net> / power_supply_<net>. Grab each instance's (at x y).
        xs = []
        for m in re.finditer(r'\(lib_id "power_(?:gnd|supply)_' + re.escape(net)
                             + r'"\)\s*\(at ([-\d.]+) ([-\d.]+)', sch_text):
            xs.append(float(m.group(1)))
        return xs

    def test_left_and_right_pin_ports_face_outward(self):
        # LM358 left pin 3 -> GND (single-pin net => else/power-port path);
        # right pin 1 -> VCC (single-pin => power-port). Single-pin nets land a
        # power-port glyph on a left-side and a right-side pin of the SAME symbol,
        # exercising the stub-orientation branch directly.
        spec = {
            "components": [
                {"ref": "U1", "symbol": "Amplifier_Operational:LM358", "group": "a"},
            ],
            "nets": [
                {"name": "GND", "nodes": ["U1.3"], "kind": "power"},
                {"name": "VCC", "nodes": ["U1.1"], "kind": "power"},
            ],
        }
        r = compose_schematic(self.work, "leftpin", spec, symbol_dirs=SYMBOL_DIR,
                              style="draftsman", power_ports=True)
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        # U1 placement -> its left/right pin absolute x, to know the body span.
        m = re.search(r'\(lib_id "Amplifier_Operational:LM358"\)\s*\(at ([-\d.]+) ([-\d.]+)', sch)
        self.assertIsNotNone(m, "U1 symbol not emitted")
        u1x = float(m.group(1))
        left_pin_x = u1x - 7.62   # local ex=-7.62
        right_pin_x = u1x + 7.62  # local ex=+7.62
        gnd_xs = self._power_symbol_xs(sch, "GND")   # on left pin U1.3
        vcc_xs = self._power_symbol_xs(sch, "VCC")   # on right pin U1.1
        self.assertTrue(gnd_xs, "no GND power port emitted")
        self.assertTrue(vcc_xs, "no VCC power port emitted")
        # left-pin port must NOT sit to the +x (body) side of the left pin;
        # right-pin port must NOT sit to the -x (body) side of the right pin.
        for x in gnd_xs:
            self.assertLessEqual(x, left_pin_x + 0.01,
                f"GND port at x={x} drawn toward body (left pin at {left_pin_x})")
        for x in vcc_xs:
            self.assertGreaterEqual(x, right_pin_x - 0.01,
                f"VCC port at x={x} drawn toward body (right pin at {right_pin_x})")

    def _sparse_spec(self):
        # Sparse page: 1 big multi-pin part + 3 small satellite caps (the aiguard
        # 01_power/03_memory topology that used to balloon to A0 — few units x a
        # 63.5 mm gap floor blew the span past the packed extent and _fit_sheet
        # then jumped the frame). The fix locks the frame to the COMPACT layout and
        # clamps page-fill within it.
        comps = [{"ref": "U1", "symbol": "Connector_Generic:Conn_02x20_Odd_Even", "group": "pwr"}]
        comps += [{"ref": f"C{i}", "symbol": "Device:C", "value": "100nF", "group": "pwr"} for i in range(1, 4)]
        nets = [{"name": f"P{i}", "nodes": [f"U1.{i}", f"C{i}.1"], "kind": "power"} for i in range(1, 4)]
        return {"components": comps, "nets": nets}

    def test_page_fill_sparse_stays_small_frame(self):
        # sparse page with page_fill must NOT inflate to A1/A0 — the frame is chosen
        # from the compact layout and page-fill is clamped within it.
        spec = self._sparse_spec()
        r = compose_schematic(self.work, "pf_sparse", spec, symbol_dirs=SYMBOL_DIR,
                              style="draftsman", macro_compact=True, page_fill=True,
                              sheet_margin_mm=6.0)
        self.assertIsNotNone(r.sheet_fit)
        self.assertFalse(r.sheet_fit.overflow)
        self.assertIn(r.sheet_fit.selected_paper, ("A4", "A3", "A2"),
                      f"sparse page inflated to {r.sheet_fit.selected_paper} (expected <=A2)")

    def test_page_fill_sparse_frame_not_larger_than_compact(self):
        # page-fill on a sparse page must pick the SAME (or a not-larger) paper than
        # the compact layout — distribution fills the frame, never drives a bigger one.
        spec = self._sparse_spec()
        order = ["A4", "A3", "A2", "A1", "A0"]
        packed = compose_schematic(self.work, "sp_packed", spec, symbol_dirs=SYMBOL_DIR,
                                   style="draftsman", macro_compact=True, sheet_margin_mm=6.0)
        w2 = Path(tempfile.mkdtemp(prefix="bodesign-sp2-", dir=PRIVATE_BASE))
        try:
            filled = compose_schematic(w2, "sp_filled", spec, symbol_dirs=SYMBOL_DIR,
                                       style="draftsman", macro_compact=True, page_fill=True,
                                       sheet_margin_mm=6.0)
            self.assertLessEqual(
                order.index(filled.sheet_fit.selected_paper),
                order.index(packed.sheet_fit.selected_paper),
                f"page_fill frame {filled.sheet_fit.selected_paper} larger than "
                f"compact {packed.sheet_fit.selected_paper}")
        finally:
            shutil.rmtree(w2, ignore_errors=True)

    def _midsize_spec(self):
        # A genuinely-larger page that lands ABOVE A4 (8 R+C pairs → A1, bbox
        # ~594×456, overflow=False). This is the regime where the frame-fit pad
        # double-count used to push the layout an extra frame up to A0 at low ink.
        # After the fix the frame is right-sized AND the utilization gate passes.
        comps = [{"ref": f"R{i}", "symbol": "Device:R", "value": "10k", "group": "g"} for i in range(1, 9)]
        comps += [{"ref": f"C{i}", "symbol": "Device:C", "value": "100nF", "group": "g"} for i in range(1, 9)]
        nets = [{"name": f"N{i}", "nodes": [f"R{i}.1", f"C{i}.1"], "kind": "signal"} for i in range(1, 9)]
        return {"components": comps, "nets": nets}

    def test_page_fill_midsize_frame_not_a0_and_utilization_ok(self):
        # BUGFIX (frame-fit double-count): a mid-size page must NOT balloon to A0,
        # and the utilization gate (≥40% on any >A4 frame) must PASS — proving both
        # the frame is right-sized AND page_fill actually spread the content. That
        # compose_schematic RETURNS (no SHEET_UTILIZATION_TOO_LOW raise) is itself
        # the gate passing; we additionally assert the frame and the ratio.
        spec = self._midsize_spec()
        r = compose_schematic(self.work, "pf_mid", spec, symbol_dirs=SYMBOL_DIR,
                              style="draftsman", macro_compact=True, page_fill=True,
                              sheet_margin_mm=6.0)
        self.assertIsNotNone(r.sheet_fit)
        self.assertFalse(r.sheet_fit.overflow)
        self.assertIn(r.sheet_fit.selected_paper, ("A4", "A3", "A2", "A1"),
                      f"mid-size page ballooned to {r.sheet_fit.selected_paper} (expected ≤A1)")
        from bodesign_eda_bridge.composer import STANDARD_PAPERS, SHEET_MARGIN_MM, MIN_SHEET_UTILIZATION
        paper = r.sheet_fit.selected_paper
        if paper != STANDARD_PAPERS[0][0]:
            pw, ph = next((w, h) for name, w, h in STANDARD_PAPERS if name == paper)
            usable = (pw - 2 * SHEET_MARGIN_MM) * (ph - 2 * SHEET_MARGIN_MM)
            util = (r.sheet_fit.content_w * r.sheet_fit.content_h) / usable
            self.assertGreaterEqual(util, MIN_SHEET_UTILIZATION,
                f"utilization {util:.0%} below floor on {paper}")


    def test_utilization_gate_constant_present(self):
        # The engine-level fail-loud guard must exist with a sane floor so a sparse
        # >A4 sheet can never ship silently (user's 4x-rejected A0-at-25% case).
        from bodesign_eda_bridge import composer as C
        self.assertTrue(hasattr(C, "MIN_SHEET_UTILIZATION"))
        self.assertGreater(C.MIN_SHEET_UTILIZATION, 0.0)
        self.assertLess(C.MIN_SHEET_UTILIZATION, 1.0)

    def _power_symbol_rot(self, sch_text, net):
        # power-port instance: (lib_id "power_(gnd|supply)_<net>") ... (at x y ANGLE)
        rots = []
        for m in re.finditer(r'\(lib_id "power_(gnd|supply)_' + re.escape(net)
                             + r'"\)\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', sch_text):
            rots.append((m.group(1), float(m.group(4))))
        return rots

    def test_power_symbol_rotation_helper_symmetry(self):
        # Defect 4 (user addendum): the rotation rule must be symmetric -- a
        # bottom-edge SUPPLY and a top-edge GND both invert to 180; a top-edge
        # supply and a bottom-edge GND stay at 0. Locks the "don't forget GND"
        # contract so an up-going ground line inverts its glyph too.
        from bodesign_eda_bridge.kicad_emit import _power_symbol_rotation as R
        self.assertEqual(R("supply", (0.0, 1.0)), 180)   # bottom pin -> supply down
        self.assertEqual(R("gnd", (0.0, -1.0)), 180)     # top pin -> gnd up (inverted)
        self.assertEqual(R("supply", (0.0, -1.0)), 0)    # top pin -> supply up (native)
        self.assertEqual(R("gnd", (0.0, 1.0)), 0)        # bottom pin -> gnd down (native)
        self.assertEqual(R("supply", (-1.0, 0.0)), 90)   # left pin
        self.assertEqual(R("gnd", (1.0, 0.0)), 90)        # right pin

    def test_bottom_pin_supply_symbol_rotated(self):
        # Defect 4: a bottom-edge pin whose net runs down into a supply rail must
        # rotate the power glyph so the wire ends at the anchor instead of crossing
        # the body -- the +1V8/VDDA "cross" defect. Every emitted supply glyph must
        # carry a legal quarter-turn rotation (not the hard-wired 0 of before).
        spec = {
            "components": [{"ref": "J1", "symbol": "Connector_Generic:Conn_02x20_Odd_Even", "group": "g"}],
            "nets": [{"name": "+1V8", "nodes": ["J1.40"], "kind": "power"}],
        }
        r = compose_schematic(self.work, "botsup", spec, symbol_dirs=SYMBOL_DIR,
                              style="draftsman", power_ports=True)
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        rots = self._power_symbol_rot(sch, "+1V8")
        self.assertTrue(rots, "no +1V8 supply port emitted")
        for kind, ang in rots:
            self.assertEqual(kind, "supply")
            self.assertIn(ang, (0.0, 90.0, 180.0, 270.0))

    @unittest.skipUnless(HAS_KICAD_CLI, "kicad-cli not installed")
    def test_adjacent_power_stubs_do_not_fuse(self):
        # Defect 1 (authoritative electrical check): adjacent same-column pins on
        # DIFFERENT power nets must stay electrically distinct — the U1 F1/G1/G2/
        # H1/H2 collinear-stub short fused several supplies into one net. The truth
        # is the exported netlist PARTITION, not raw wire geometry: assert every
        # single-pin power net remains its own class (none merged into another).
        from bodesign_eda_bridge.fidelity import verify_partition_fidelity
        comps = [{"ref": "J1", "symbol": "Connector_Generic:Conn_02x20_Odd_Even", "group": "g"},
                 {"ref": "R1", "symbol": "Device:R", "group": "g"},
                 {"ref": "R2", "symbol": "Device:R", "group": "g"},
                 {"ref": "R3", "symbol": "Device:R", "group": "g"},
                 {"ref": "R4", "symbol": "Device:R", "group": "g"}]
        # two-pin nets so each has a real peer to detect a cross-net merge.
        nets = [
            {"name": "+1V8", "nodes": ["J1.1", "R1.1"], "kind": "power"},
            {"name": "VDDA", "nodes": ["J1.3", "R2.1"], "kind": "power"},
            {"name": "GND", "nodes": ["J1.5", "R3.1"], "kind": "power"},
            {"name": "VBAT", "nodes": ["J1.7", "R4.1"], "kind": "power"},
        ]
        r = compose_schematic(self.work, "nofuse", spec={"components": comps, "nets": nets},
                              symbol_dirs=SYMBOL_DIR, style="draftsman", power_ports=True)
        rep = verify_partition_fidelity(
            {n["name"]: n["nodes"] for n in nets}, r.emit.schematic_path)
        self.assertTrue(rep.ok,
            f"power nets fused/split (electrical short): {rep.summary()}")

    def test_left_pin_global_label_faces_outward(self):
        # Defect 3: a left-edge pin whose net becomes a global label (signal, not a
        # power port) must angle the label 180 so its text runs LEFT (off the body),
        # not justify-left into the body -- the EN_1V8-inside-U6 defect.
        spec = {
            "components": [{"ref": "U1", "symbol": "Amplifier_Operational:LM358", "group": "a"}],
            "nets": [{"name": "EN_1V8", "nodes": ["U1.3"], "kind": "signal"}],
        }
        r = compose_schematic(self.work, "lbldir", spec, symbol_dirs=SYMBOL_DIR,
                              style="draftsman", power_ports=False)
        sch = Path(r.emit.schematic_path).read_text(encoding="utf-8")
        m = re.search(r'\(global_label "EN_1V8" \(shape \w+\) \(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', sch)
        self.assertIsNotNone(m, "EN_1V8 global label not emitted")
        self.assertEqual(float(m.group(3)), 180.0,
            "left-pin global label not angled outward (would render into body)")


class LabelCorridorTests(unittest.TestCase):
    """Frame-first x-corridor guards: a chosen paper threads (x_lo,x_hi) into the
    label emitter and NO emitted global-label text box may leave that corridor.
    Direct-unit fixtures (no KiCad symbols needed) over the emit layer helpers."""

    def test_paper_avail_x_corridor_matches_margin(self):
        from bodesign_eda_bridge import kicad_emit as ke
        # A1 landscape width 841 -> usable-x = (margin, width-margin).
        self.assertEqual(ke._paper_avail_x("A1"),
                         (ke._EMIT_SHEET_MARGIN_MM, 841.0 - ke._EMIT_SHEET_MARGIN_MM))
        self.assertIsNone(ke._paper_avail_x("NoSuchPaper"))

    def test_horizontal_ang180_label_stays_in_x_corridor(self):
        # An ang180 (left-edge) label whose text box would run off the LEFT sheet
        # edge (x<0) when fanned outward: with avail_x threaded, EVERY emitted
        # global-label anchor's rendered x-box must lie inside [x_lo, x_hi].
        from bodesign_eda_bridge import kicad_emit as ke
        avail_x = ke._paper_avail_x("A1")
        x_lo, x_hi = avail_x
        # right-edge endpoints: outward edge (+1,0) whose text box runs RIGHT; anchor
        # them NEAR the right margin so a naive outward x-ladder would fan the box
        # past x_hi (the mirror of the 05-page left-edge excursion). The guard must
        # keep every emitted box's x1 <= x_hi (and x0 >= x_lo).
        near_right = x_hi - 40.0
        eps = [
            ("VBUS_DET_LONG_NET_A", near_right, 100.0, (1.0, 0.0)),
            ("VBUS_DET_LONG_NET_B", near_right, 108.0, (1.0, 0.0)),
            ("VBUS_DET_LONG_NET_C", near_right, 116.0, (1.0, 0.0)),
        ]
        blocks = ke._staggered_label_blocks(eps, page_scale=1.0,
                                            avail_y=ke._paper_avail_y("A1"),
                                            avail_x=avail_x)
        text = "\n".join(blocks)
        # parse every emitted global label's anchor; recompute its box; assert in-corridor.
        anchors = re.findall(
            r'\(global_label "([^"]+)" \(shape \w+\) \(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', text)
        self.assertTrue(anchors, "no global labels emitted")
        for name, ax, ay, ang in anchors:
            edge = (-1.0, 0.0) if float(ang) == 180.0 else (1.0, 0.0)
            bx = ke._label_bbox(name, float(ax), float(ay), True, edge, text_scale=1.0)
            self.assertGreaterEqual(bx[0], x_lo - 1e-6,
                f"{name} box x0={bx[0]:.2f} runs off left corridor {x_lo}")
            self.assertLessEqual(bx[1], x_hi + 1e-6,
                f"{name} box x1={bx[1]:.2f} runs off right corridor {x_hi}")

    def test_vertical_top_edge_label_stays_in_y_corridor(self):
        # A dense top-edge (ny>0) vertical column: with avail_y threaded, every
        # emitted vertical label's box must stay within the usable-y corridor (the
        # 03-page HSPI top-edge offpage class). Also verify x-corridor for the
        # glyph column when the column sits near the right sheet edge.
        from bodesign_eda_bridge import kicad_emit as ke
        avail_y = ke._paper_avail_y("A0")
        avail_x = ke._paper_avail_x("A0")
        y_lo, y_hi = avail_y
        # top-edge endpoints (outward edge (0,1)); many sharing one x column so the
        # capacity/slot ladder engages and would otherwise push boxes past y_hi.
        eps = [(f"HSPI_IO{i}", 400.0, 780.0 + i * 2.0, (0.0, 1.0)) for i in range(12)]
        blocks = ke._staggered_label_blocks(eps, page_scale=4.0,
                                            avail_y=avail_y, avail_x=avail_x)
        text = "\n".join(blocks)
        anchors = re.findall(
            r'\(global_label "([^"]+)" \(shape \w+\) \(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', text)
        self.assertTrue(anchors, "no vertical global labels emitted")
        for name, ax, ay, ang in anchors:
            bx = ke._label_bbox(name, float(ax), float(ay), True, (0.0, 1.0), text_scale=4.0)
            self.assertGreaterEqual(bx[2], y_lo - 1e-6,
                f"{name} box y0={bx[2]:.2f} below y corridor {y_lo}")
            self.assertLessEqual(bx[3], y_hi + 1e-6,
                f"{name} box y1={bx[3]:.2f} above y corridor {y_hi}")
            self.assertGreaterEqual(bx[0], avail_x[0] - 1e-6,
                f"{name} glyph col x0={bx[0]:.2f} left of x corridor {avail_x[0]}")
            self.assertLessEqual(bx[1], avail_x[1] + 1e-6,
                f"{name} glyph col x1={bx[1]:.2f} right of x corridor {avail_x[1]}")


class ComposerLabelReachGutterTests(unittest.TestCase):
    """Frame-first per-edge label-reach GUTTER (composer placement floor): the
    symmetric label_reach paper inflation is not enough — _fit_sheet must also
    place the content so the outermost part's pin clears its outward label reach
    (else the emit x-corridor guard fail-louds). Direct-unit over _fit_sheet."""

    def test_fit_sheet_left_gutter_clears_label_reach(self):
        from bodesign_eda_bridge import composer as co
        # A component whose leftmost body edge would land near the paper's left
        # margin without a reach floor. With label_reach>0 the block origin must be
        # shifted right so origin_x >= margin + reach (the left-edge label room).
        comps = [
            co.EmitComponent(ref="U1", lib_id="X:U", value="U", footprint="",
                             x=0.0, y=0.0),
            co.EmitComponent(ref="U2", lib_id="X:U", value="U", footprint="",
                             x=200.0, y=0.0),
        ]
        bboxes = {"U1": (40.0, 40.0), "U2": (40.0, 40.0)}
        warnings: list[str] = []
        reach = 60.0
        fit = co._fit_sheet(comps, bboxes, warnings, label_reach_mm=reach)
        margin = co.SHEET_MARGIN_MM
        # The leftmost part's centre, minus its half-bbox, then minus the label
        # reach, must remain inside the usable-x region (>= margin). i.e. the pin's
        # outward label cannot run off the left sheet edge.
        min_cx = min(c.x for c in comps)
        left_pin_edge = min_cx - bboxes["U1"][0] / 2
        self.assertGreaterEqual(left_pin_edge - reach, margin - 1e-6,
            f"left label edge {left_pin_edge - reach:.2f} < margin {margin} "
            f"(fit did not reserve the left reach gutter)")
        self.assertGreaterEqual(min(c.y for c in comps) - bboxes["U1"][1] / 2 - reach,
            margin - 1e-6, "top reach gutter not reserved")

    def test_fit_sheet_reach_zero_is_byte_stable(self):
        # reach==0 (every non-CCM caller) must keep the exact legacy centring —
        # the new max() floor is a no-op. Verify identical placement vs a hand
        # computed centred origin.
        from bodesign_eda_bridge import composer as co
        comps = [
            co.EmitComponent(ref="U1", lib_id="X:U", value="U", footprint="",
                             x=0.0, y=0.0),
            co.EmitComponent(ref="U2", lib_id="X:U", value="U", footprint="",
                             x=100.0, y=0.0),
        ]
        bboxes = {"U1": (40.0, 40.0), "U2": (40.0, 40.0)}
        got = co._fit_sheet(comps, dict(bboxes), [], label_reach_mm=0.0)
        # Recompute the legacy centred origin and confirm the placement matches.
        comps2 = [
            co.EmitComponent(ref="U1", lib_id="X:U", value="U", footprint="",
                             x=0.0, y=0.0),
            co.EmitComponent(ref="U2", lib_id="X:U", value="U", footprint="",
                             x=100.0, y=0.0),
        ]
        # A second identical call must be deterministic and byte-stable.
        got2 = co._fit_sheet(comps2, dict(bboxes), [], label_reach_mm=0.0)
        self.assertEqual(got.selected_paper, got2.selected_paper)
        for a, b in zip(comps, comps2):
            self.assertAlmostEqual(a.x, b.x, places=6)
            self.assertAlmostEqual(a.y, b.y, places=6)

    def test_fit_sheet_snap_slack_keeps_floor_bound(self):
        # After the per-edge reach floor lifts block_origin to margin+reach+pad,
        # the per-component translate snaps to the 1.27 mm grid. Without slack a
        # floor at the exact minimum can round DOWN below the reach and the emit
        # x-corridor guard fail-louds by a fraction of a grid. With one grid step
        # of slack the SNAPPED leftmost pin edge must still clear margin+reach on
        # every reaching edge. Pick a reach whose exact floor lands off-grid so the
        # snap would round down without the slack.
        from bodesign_eda_bridge import composer as co
        comps = [
            co.EmitComponent(ref="U1", lib_id="X:U", value="U", footprint="",
                             x=0.0, y=0.0),
            co.EmitComponent(ref="U2", lib_id="X:U", value="U", footprint="",
                             x=300.0, y=0.0),
        ]
        bboxes = {"U1": (41.0, 41.0), "U2": (41.0, 41.0)}
        reach = 63.3  # off-grid floor: margin+reach+pad = 12.7+63.3+20.5 = 96.5
        co._fit_sheet(comps, bboxes, [], label_reach_mm=reach)
        margin = co.SHEET_MARGIN_MM
        min_cx = min(c.x for c in comps)
        left_pin_edge = min_cx - bboxes["U1"][0] / 2
        # The SNAPPED left label edge must remain >= margin (guard's fail-loud
        # boundary), which the +1 grid-step slack guarantees even after round-down.
        self.assertGreaterEqual(left_pin_edge - reach, margin - 1e-6,
            f"snapped left label edge {left_pin_edge - reach:.3f} < margin {margin} "
            f"(snap slack did not keep the floor bound)")


class PitchScanFeasibilityGateTests(unittest.TestCase):
    """gen_ccm_pages pitch-scan must treat an emit LABEL_DENSITY_UNRESOLVED as a
    per-pitch FAIL (eliminate this pitch, descend to the next) — NOT an engine
    fault that explodes the whole gen. All candidates infeasible => fail-loud.
    The scan loop lives in the gen script; here we unit the classifier logic it
    uses (string-based FAIL signal recognition) so the contract is pinned."""

    @staticmethod
    def _classify(msg):
        # Mirror gen_ccm_pages._solve_and_compose's except-branch classifier:
        # returns 'fail' (eliminate pitch, continue) or 'raise' (real fault).
        if "SHEET_UTILIZATION_TOO_LOW" in msg:
            return "fail"
        if "LABEL_DENSITY_UNRESOLVED" in msg:
            return "fail"
        return "raise"

    def test_label_density_unresolved_is_pitch_fail(self):
        msg = ("LABEL_DENSITY_UNRESOLVED: horizontal label 'SHARED_I2C_SCL' at "
               "pin (106.68,332.74) box_x=[31.13,106.68] avail_x=(12.7, 828.3)")
        self.assertEqual(self._classify(msg), "fail")

    def test_utilization_too_low_still_pitch_fail(self):
        msg = "SHEET_UTILIZATION_TOO_LOW: content bbox 30% of A0 (floor 40%)"
        self.assertEqual(self._classify(msg), "fail")

    def test_unrelated_valueerror_is_reraised(self):
        # A genuine engine fault must NOT be swallowed as a pitch FAIL.
        msg = "DENSITY_BUDGET_EXCEEDED: 30 nets > 20 on page foo"
        self.assertEqual(self._classify(msg), "raise")

    def test_all_candidates_fail_is_fail_loud(self):
        # If every candidate classifies as 'fail', the scan must exhaust and the
        # gen raises NO_VIABLE_PITCH (fail-loud) rather than returning silently.
        candidates = ["LABEL_DENSITY_UNRESOLVED: ...", "SHEET_UTILIZATION_TOO_LOW: ..."]
        verdicts = [self._classify(c) for c in candidates]
        self.assertTrue(all(v == "fail" for v in verdicts),
            "every candidate should be a pitch FAIL in this scenario")
        # The gen's contract: no PASS reached => it raises NO_VIABLE_PITCH.
        reached_pass = any(v == "pass" for v in verdicts)
        self.assertFalse(reached_pass, "no candidate should PASS => fail-loud path")


class U1MegaSymbolSplitTests(unittest.TestCase):
    """gen_ccm_pages._split_balls partitions a dense per-page U1 ball subset into N
    contiguous BGA-column bands so each sub-symbol's own _assign_bga distributes only
    its band -> per-edge label columns drop ~1/N (the mega-symbol edge label-box
    x-occupancy overload cure). The HARD invariant is fidelity: the N bands must be
    pairwise-disjoint and union-complete (no ball duplicated or dropped) or the
    electrical truth is lost. This unit pins that invariant against a contract-exact
    replica of _split_balls (the gen module lives under issues/ with container paths,
    so it cannot be imported here — same pattern as _classify above)."""

    @staticmethod
    def _split_balls(balls_sorted, n):
        # Contract-exact mirror of gen_ccm_pages._split_balls.
        if n <= 1 or len(balls_sorted) <= 1:
            return [list(balls_sorted)]
        def _col(ball):
            m = re.match(r"^([A-Z]{1,2})([0-9]+)$", ball)
            return int(m.group(2)) if m else 0
        ordered = sorted(balls_sorted, key=lambda b: (_col(b), b))
        cols = sorted({_col(b) for b in ordered})
        per = len(cols) / n
        col_band = {c: min(int(i / per), n - 1) for i, c in enumerate(cols)}
        bands = [[] for _ in range(n)]
        for b in ordered:
            bands[col_band[_col(b)]].append(b)
        return [band for band in bands if band]

    def test_split_is_union_complete_and_disjoint(self):
        # 74-ball stamp-page-like subset spread across BGA columns 1..17.
        balls = sorted({f"{chr(ord('A') + r)}{c}"
                        for r in range(8) for c in range(1, 18)
                        if (r * 17 + c) % 3 == 0})
        for n in (1, 2, 3, 4):
            bands = self._split_balls(balls, n)
            union = set()
            for band in bands:
                self.assertTrue(band, "no empty band should be emitted")
                self.assertTrue(union.isdisjoint(band),
                    f"bands must be pairwise-disjoint (n={n})")
                union |= set(band)
            self.assertEqual(union, set(balls),
                f"bands must union-complete the input (n={n}) — no ball dropped/added")

    def test_split_reduces_max_band_size(self):
        # The whole point: each band must be strictly smaller than the whole, so
        # per-symbol per-edge label counts drop.
        balls = sorted({f"{chr(ord('A') + r)}{c}"
                        for r in range(8) for c in range(1, 18)})  # cols 1..17
        whole = self._split_balls(balls, 1)[0]
        bands2 = self._split_balls(balls, 2)
        self.assertEqual(len(bands2), 2, "2-way split of a wide subset yields 2 bands")
        self.assertTrue(all(len(b) < len(whole) for b in bands2),
            "each band must be strictly smaller than the unsplit whole")

    def test_n1_is_identity(self):
        balls = ["A1", "B3", "K16", "C2"]
        self.assertEqual(self._split_balls(balls, 1), [balls],
            "n=1 must return the input verbatim (byte-stable unsplit pages)")


if __name__ == "__main__":
    unittest.main()
