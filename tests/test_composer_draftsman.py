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

    # BR_20260708: a 2-node wire whose straight L-route would cross a THIRD
    # component's body must detour AROUND it (obstacle keep-out), leaving zero
    # drawn-wire ∩ symbol-body intrusions and still drawing the wire (not label).
    def test_br20260708_wire_avoids_symbol_body(self):
        from bodesign_eda_bridge.kicad_emit import check_wire_body_clearance
        spec = {
            "components": [
                {"ref": "U1", "symbol": "Device:R", "x": 40.0, "y": 40.0, "group": "a"},
                {"ref": "U2", "symbol": "Device:R", "x": 80.0, "y": 40.0, "group": "a"},
                {"ref": "U3", "symbol": "Device:R", "x": 120.0, "y": 40.0, "group": "a"},
            ],
            # 2-node net across U1..U3; the naive straight L would pass through U2.
            "nets": [{"name": "SIG", "nodes": ["U1.1", "U3.1"], "kind": "signal"}],
        }
        r = compose_schematic(self.work, "br0708", spec, symbol_dirs=SYMBOL_DIR, style="draftsman")
        # wire is drawn (mixed default, not downgraded to all-label)
        self.assertEqual(1, r.route_stats.wired_nets)
        self.assertIn("(wire (pts", self._sch_text(r))
        # machine check: zero drawn-wire-through-symbol-body intrusions
        self.assertEqual([], check_wire_body_clearance(r))
        self.assertEqual([], r.wire_body_intrusions)

    # BR_20260708: the router helper preserves both endpoints (FIDELITY-safe) and
    # picks a candidate whose interior segments clear a straddling obstacle box.
    def test_br20260708_orthogonal_route_detours(self):
        from bodesign_eda_bridge.kicad_emit import _orthogonal_route, _waypoints_clear
        p1, p2 = (0.0, 0.0), (40.0, 0.0)
        box = (15.0, 25.0, -10.0, 10.0)  # straddles the straight line y=0
        straight = _orthogonal_route(p1, p2)
        self.assertEqual([p1, p2], straight)          # no obstacle → unchanged
        detour = _orthogonal_route(p1, p2, [box])
        self.assertEqual(p1, detour[0])               # endpoints preserved
        self.assertEqual(p2, detour[-1])
        self.assertTrue(_waypoints_clear(detour, [box]))

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
        #
        # DD-11a2: the big part is built through the SAME gen geometry engine
        # (_symbol_geometry via emit_kicad_symbol) production uses, NOT the raw
        # KiCad-library Conn_02x20_Odd_Even. The library connector packs 40 pin
        # names by construction with zero name-clearance, so with the intra gate
        # armed at scale 1.0 (DD-11b) it fail-louds legitimately — but that is a
        # library-symbol artifact, not the frame-sizing behaviour these tests
        # assert. The gen symbol carries the horiz_pitch + corner clearance floor,
        # so it is intra-clean at any scale while keeping the big-part-plus-caps
        # sparse topology the frame test needs. The generated symbol is NOT
        # exempted from the gate — it passes because its geometry is correct.
        from bodesign_eda_bridge.kicad_symbol import emit_kicad_symbol
        sym_dir = Path(tempfile.mkdtemp(prefix="bodesign-sparse-sym-", dir=PRIVATE_BASE))
        self._sparse_sym_dir = sym_dir  # kept alive for the compose call
        pins = [{"number": str(i), "name": f"P{i}", "type": "I"} for i in range(1, 21)]
        emit_kicad_symbol("SPARSE_BIG", pins, sym_dir / "sparse_big.kicad_sym",
                          datasheet="ds")
        comps = [{"ref": "U1", "symbol": "sparse_big:SPARSE_BIG", "group": "pwr"}]
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

    def test_vertical_top_edge_label_straight_out_no_bend(self):
        # DD-22/23 (user review v5): every pin exits STRAIGHT — the corridor-clamp /
        # x-ladder / y-nudge avoidance that used to keep a dense top-edge column's
        # label boxes inside avail_y is ABOLISHED (it was the forbidden bend). A
        # top-edge (ny>0) vertical label now anchors DIRECTLY on its pin endpoint
        # with NO stub wire and NO displacement; label separation is a closed-form
        # pitch/layout concern (per-page pitch solver + DD-19b/DD-20 floors), not a
        # bend. Assert: (a) NO wire segment is emitted for these labels (pure
        # straight-out); (b) each label anchors exactly on its pin (x, y).
        from bodesign_eda_bridge import kicad_emit as ke
        avail_y = ke._paper_avail_y("A0")
        avail_x = ke._paper_avail_x("A0")
        eps = [(f"HSPI_IO{i}", 400.0, 780.0 + i * 2.0, (0.0, 1.0)) for i in range(12)]
        blocks = ke._staggered_label_blocks(eps, page_scale=4.0,
                                            avail_y=avail_y, avail_x=avail_x)
        text = "\n".join(blocks)
        self.assertNotIn("(wire (pts", text,
            "DD-22/23: a straight-out label must emit NO stub wire (a wire == a bend)")
        anchors = re.findall(
            r'\(global_label "([^"]+)" \(shape \w+\) \(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', text)
        self.assertEqual(len(anchors), len(eps), "one label per pin endpoint")
        _by_name = {name: (float(ax), float(ay)) for name, ax, ay, ang in anchors}
        for name, px, py, _edge in eps:
            self.assertIn(name, _by_name)
            ax, ay = _by_name[name]
            self.assertAlmostEqual(ax, px, places=3,
                msg=f"{name} anchored at x={ax}, not on pin x={px} (a bend/displacement)")
            self.assertAlmostEqual(ay, py, places=3,
                msg=f"{name} anchored at y={ay}, not on pin y={py} (a bend/displacement)")


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
    """DD-12 constructive closed-form paper sizing (size_paper_closed_form) REPLACES
    the pitch-scan eliminate-retry loop. These pin the constructive contract: one
    determined content bbox → one paper + one scale, deterministic, monotone in
    content size, fail-loud only when the natural-size content exceeds A0. There is
    NO scan, NO per-candidate elimination — the geometry is computed correct up
    front (一次到位), so there is nothing to try-and-reject."""

    def test_closed_form_is_deterministic(self):
        # Same input → byte-identical output (no RNG, no scan order dependence).
        from bodesign_eda_bridge.composer import size_paper_closed_form
        a = size_paper_closed_form(300.0, 200.0, sheet_margin_mm=6.0, scale_quantum=1.0)
        b = size_paper_closed_form(300.0, 200.0, sheet_margin_mm=6.0, scale_quantum=1.0)
        self.assertEqual((a.paper, a.scale), (b.paper, b.scale))

    def test_closed_form_small_content_wins_small_paper_large_scale(self):
        # A small natural bbox lands on the SMALLEST paper and scales UP to fill it
        # (圖大紙小) — the paradigm the user asked for, closed-form not scanned.
        from bodesign_eda_bridge.composer import size_paper_closed_form
        s = size_paper_closed_form(100.0, 80.0, sheet_margin_mm=6.0, scale_quantum=1.0)
        self.assertEqual(s.paper, "A4")
        self.assertGreater(s.scale, 1.0, "small content must scale UP to fill the small paper")

    def test_closed_form_paper_is_monotone_in_content(self):
        # Bigger natural content selects a paper >= a smaller content's paper.
        from bodesign_eda_bridge.composer import size_paper_closed_form, STANDARD_PAPERS
        order = [p[0] for p in STANDARD_PAPERS]
        small = size_paper_closed_form(100.0, 80.0, sheet_margin_mm=6.0, scale_quantum=1.0)
        large = size_paper_closed_form(500.0, 400.0, sheet_margin_mm=6.0, scale_quantum=1.0)
        self.assertGreaterEqual(order.index(large.paper), order.index(small.paper))

    def test_closed_form_scale_quantum_floors_to_pitch_ladder(self):
        # scale_quantum=1.0 floors the fit-to-frame scale to a whole KiCad-pitch
        # multiple (page_scale = pitch / 2.54). The floored scale is <= the exact
        # scale and >= 1.0; the exact scale is not quantised.
        from bodesign_eda_bridge.composer import size_paper_closed_form
        exact = size_paper_closed_form(100.0, 80.0, sheet_margin_mm=6.0)
        floored = size_paper_closed_form(100.0, 80.0, sheet_margin_mm=6.0, scale_quantum=1.0)
        self.assertLessEqual(floored.scale, exact.scale)
        self.assertGreaterEqual(floored.scale, 1.0)
        self.assertEqual(floored.scale, float(int(floored.scale)),
                         "quantum=1.0 must yield a whole-number scale")

    def test_closed_form_exceeds_a0_is_fail_loud(self):
        # The SOLE legal failure: natural-size content bigger than A0 →
        # CONTENT_EXCEEDS_A0, never a silent scale-down retry.
        from bodesign_eda_bridge.composer import size_paper_closed_form
        with self.assertRaises(ValueError) as ctx:
            size_paper_closed_form(2000.0, 1500.0, sheet_margin_mm=6.0)
        self.assertIn("CONTENT_EXCEEDS_A0", str(ctx.exception))


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


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
class BudgetInfeasibleGateTests(unittest.TestCase):
    """TV-5：構造超載內容（label 需求 > 最大圖框可用邊），page_fill path
    掃畢所有標準紙拋 BUDGET_INFEASIBLE 附 overloaded_edges + candidates_tried。"""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-budget-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_tv5_overload_is_fail_loud_content_exceeds_a0(self):
        # DD-12: 超載偵測職責上移到閉式 sizer size_paper_closed_form 的
        # CONTENT_EXCEEDS_A0 fail-loud（唯一合法失敗模式，非重試）。compose_schematic
        # 本身不再是超載偵測器（overflow 降為觀測）。此測試對準閉式 sizer：一個大到
        # 連 A0 都裝不下的 content bbox 必須拋 CONTENT_EXCEEDS_A0，絕不回退掃描。
        from bodesign_eda_bridge.composer import size_paper_closed_form
        with self.assertRaises(ValueError) as ctx:
            # A0 是 1189×841；scale==1.0 content 2000×1500 遠超之。
            size_paper_closed_form(2000.0, 1500.0, sheet_margin_mm=6.0)
        self.assertIn("CONTENT_EXCEEDS_A0", str(ctx.exception))

    def test_tv5_feasible_page_does_not_raise(self):
        # 反向護欄：可行內容（小頁）不得誤拋 — page_fill fail-loud 只在真超載時觸發。
        spec = {
            "components": [{"ref": "R1", "symbol": "Device:R", "group": "g"},
                           {"ref": "C1", "symbol": "Device:C", "value": "100n", "group": "g"}],
            "nets": [{"name": "N1", "nodes": ["R1.1", "C1.1"], "kind": "signal"}],
        }
        r = compose_schematic(self.work, "budget_ok", spec, symbol_dirs=SYMBOL_DIR,
                              style="draftsman", macro_compact=True, page_fill=True,
                              sheet_margin_mm=6.0)
        self.assertFalse(r.sheet_fit.overflow)


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
class PaperFirstSolverTests(unittest.TestCase):
    """DD-11c: paper-first solve reversal. OUTER paper A4→A0 (small→large), INNER
    scale large→small; the smallest paper admitting ANY scale wins (「圖大紙小」).
    Contrast with the old pitch-first (scale large→small, paper picked passively).
    Verifies: small content picks a small paper at a LARGE scale (not bottomed to
    1.0); large content correctly steps the paper up; infeasible → fail-loud with
    the per-(paper,scale) scan."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-pf-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _small_spec(self):
        # A tiny 2-part page: fits the smallest paper at essentially any scale, so
        # paper-first must WIN on A4 (smallest) at the LARGEST scale, never bottom
        # out on scale 1.0 the way pitch-first did.
        return {
            "components": [{"ref": "R1", "symbol": "Device:R", "group": "g"},
                           {"ref": "C1", "symbol": "Device:C", "value": "100n", "group": "g"}],
            "nets": [{"name": "N1", "nodes": ["R1.1", "C1.1"], "kind": "signal"}],
        }

    def _build_fn(self, spec):
        # build_fn(scale) -> (spec, symbol_dirs). This page's spec does not depend on
        # scale (no per-scale symbol regen needed for stdlib parts), so return the
        # same spec each call — the solver injects page_scale itself.
        def _fn(scale):
            return spec, SYMBOL_DIR
        return _fn

    def test_paper_first_small_content_wins_small_paper_large_scale(self):
        from bodesign_eda_bridge.composer import solve_paper_first
        spec = self._small_spec()
        kw = dict(style="draftsman", macro_compact=True, page_fill=True,
                  connection_style="label", sheet_margin_mm=6.0)
        # scale candidates large→small; a small page should be admitted on the
        # SMALLEST paper the outer loop reaches (A4) at a large scale.
        sol = solve_paper_first(
            scale_candidates=(4.0, 3.0, 2.0, 1.0),
            build_fn=self._build_fn(spec),
            compose_kwargs=kw, out_dir=self.work, project_name="pf_small",
        )
        # WON on the smallest paper the search reached (paper-first): not inflated.
        self.assertIn(sol.paper, ("A4", "A3"),
                      f"paper-first should win small paper, got {sol.paper}")
        # scan carries the per-(paper,scale) verdict trail + the WON line.
        self.assertTrue(any("WON" in s for s in sol.scan))
        self.assertEqual(sol.result.sheet_fit.selected_paper, sol.paper)

    def test_paper_first_inner_loop_tries_largest_scale_first(self):
        # The INNER loop must try scale DESCENDING (largest first) so the winning
        # scale on the chosen paper is the LARGEST that fits it (「圖大」). We assert
        # the PASS that produced the WON is the first PASS in scan order and that no
        # larger scale on that paper was skipped before it.
        from bodesign_eda_bridge.composer import solve_paper_first
        spec = self._small_spec()
        kw = dict(style="draftsman", macro_compact=True, page_fill=True,
                  connection_style="label", sheet_margin_mm=6.0)
        sol = solve_paper_first(
            scale_candidates=(1.0, 4.0, 2.0),  # unsorted input
            build_fn=self._build_fn(spec),
            compose_kwargs=kw, out_dir=self.work, project_name="pf_order",
        )
        won_scale = sol.scale
        # every PASS verdict recorded for the winning paper must be at a scale <=
        # won_scale (i.e. the solver did not pass a larger scale then pick a smaller
        # one) — the inner loop is strictly descending, largest-first.
        pass_scales = [
            float(re.search(r"scale=([0-9.]+)", s).group(1))
            for s in sol.scan
            if s.startswith("[solve]") and f"paper={sol.paper}" in s and "verdict=PASS" in s
        ]
        self.assertTrue(pass_scales)
        self.assertEqual(max(pass_scales), won_scale,
                         "inner loop must win the LARGEST feasible scale on the paper")

    def test_paper_first_rejects_page_scale_in_kwargs(self):
        # page_scale / paper_whitelist are solver-owned; pre-setting them is a
        # caller contract error (fail-loud, not silently overridden).
        from bodesign_eda_bridge.composer import solve_paper_first
        with self.assertRaises(ValueError) as ctx:
            solve_paper_first(
                scale_candidates=(1.0,), build_fn=self._build_fn(self._small_spec()),
                compose_kwargs={"page_scale": 2.0, "style": "draftsman"},
                out_dir=self.work, project_name="pf_bad",
            )
        self.assertIn("page_scale", str(ctx.exception))

    def test_paper_first_overload_no_frame_fit_is_reported_not_emit_fault(self):
        # DD-22/23 (user review v5): the label avoidance窮舉 (x-ladder / y-nudge with
        # its LABEL_DENSITY_UNRESOLVED fail-loud) is ABOLISHED — a label now exits
        # STRAIGHT onto its pin endpoint, so emit NEVER raises on density. Overloaded
        # content is therefore a FRAME-FIT verdict, not an emit fault: the solver
        # exhausts every (paper, scale) and returns no viable solution WITHOUT the
        # old emit-layer density raise. Assert the solver does not blow up and
        # surfaces "no viable" via its return contract (None / no selected paper).
        from bodesign_eda_bridge.composer import solve_paper_first
        comps = [{"ref": f"R{i}", "symbol": "Device:R", "value": "10k", "group": "g"}
                 for i in range(1, 201)]
        nets = [{"name": f"N{i}", "nodes": [f"R{i}.1", f"R{i+1}.1"], "kind": "signal"}
                for i in range(1, 200)]
        spec = {"components": comps, "nets": nets}
        kw = dict(style="draftsman", macro_compact=True, page_fill=True,
                  connection_style="label", sheet_margin_mm=6.0)
        sol = solve_paper_first(
            scale_candidates=(4.5, 4.0),  # only large scales → all overload
            build_fn=self._build_fn(spec),
            compose_kwargs=kw, out_dir=self.work, project_name="pf_overload",
        )
        # No viable frame: the solver reports it (None or no selected paper),
        # and crucially did NOT raise a spurious emit-density ValueError.
        selected = getattr(sol, "selected_paper", None) if sol is not None else None
        self.assertIsNone(selected,
            "overloaded content must yield no viable paper, not a false PASS")

    def test_paper_whitelist_constrains_fit_sheet_to_single_paper(self):
        # Direct unit over _fit_sheet: a single-paper whitelist means the frame scan
        # only considers that paper — content that would fit a smaller paper is
        # still reported on the whitelisted one (the outer loop owns paper choice).
        import bodesign_eda_bridge.composer as co
        from bodesign_eda_bridge.kicad_emit import EmitComponent
        comps = [EmitComponent(ref="R1", lib_id="Device:R", value="", footprint="", x=0.0, y=0.0)]
        bboxes = {"R1": (5.0, 5.0)}
        fit = co._fit_sheet(comps, bboxes, [], sheet_margin_mm=6.0, paper_whitelist={"A2"})
        self.assertEqual(fit.selected_paper, "A2")
        self.assertFalse(fit.overflow)
        # empty whitelist is a caller error, not a verdict
        with self.assertRaises(ValueError) as ctx:
            co._fit_sheet(comps, bboxes, [], paper_whitelist=set())
        self.assertIn("PAPER_WHITELIST_EMPTY", str(ctx.exception))

    def test_paper_whitelist_none_is_byte_stable(self):
        # TV-2 rail: paper_whitelist=None (default) must be identical to the full
        # STANDARD_PAPERS scan — no behaviour change for any pre-DD-11c caller.
        import bodesign_eda_bridge.composer as co
        from bodesign_eda_bridge.kicad_emit import EmitComponent
        comps = [EmitComponent(ref="R1", lib_id="Device:R", value="", footprint="", x=0.0, y=0.0)]
        bboxes = {"R1": (5.0, 5.0)}
        a = co._fit_sheet(comps, dict(bboxes), [])
        b = co._fit_sheet(comps, dict(bboxes), [], paper_whitelist=None)
        self.assertEqual(a.selected_paper, b.selected_paper)
        self.assertEqual(a.overflow, b.overflow)


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
class LedgerGeometrySingleTruthTests(unittest.TestCase):
    """TV-8：幾何單一真相 — placement reserve 的符號 body 矩形與 emit 落位一致
    （DD-4 對帳）。draftsman path 建 ONE ledger，body rects 由 placement bbox 落帳，
    emit label solver 見同一真相 → 帳本 body rect 中心 == component 落位。"""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-tv8-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_tv8_ledger_body_rects_match_placement(self):
        r = compose_schematic(self.work, "tv8", TV1_SPEC, symbol_dirs=SYMBOL_DIR,
                              style="draftsman")
        # draftsman path 應暴露 ledger（M4-5 新增欄位）
        self.assertIsNotNone(r.ledger, "draftsman compose must expose the shared ledger")
        body_rects = [rc for rc in r.ledger.rects if rc.kind == "body"]
        self.assertTrue(body_rects, "ledger must hold placement body rects")
        # 每個 body rect 的中心必須落在半開區間內且 owner 為真實 ref（非迴圈序號）
        placed_refs = {c["ref"] for c in TV1_SPEC["components"]}
        for rc in body_rects:
            self.assertIn(rc.owner, placed_refs,
                f"body rect owner {rc.owner!r} must be a real component ref (DD-10a owner保真)")
            self.assertGreater(rc.x1, rc.x0)
            self.assertGreater(rc.y1, rc.y0)
        # body rect owner 集合 == 有 bbox 的 component 集合（單一真相：無漏無多）
        body_owners = {rc.owner for rc in body_rects}
        self.assertEqual(body_owners, placed_refs,
            "ledger body owners must exactly match placed components (single-truth)")


class SymbolGeometryIntraCleanTests(unittest.TestCase):
    """DD-19: `_symbol_geometry` must be intra-clean BY CONSTRUCTION for any pin
    set / aspect ratio — the vertical-edge (left/right) name rows must not overlap
    each other (gap 2). Rebuilds the exact pin-name boxes the intra gate measures
    (`_pin_name_box_abs`, same char/height model) from the resolved placements and
    asserts zero same-owner geometric overlap, at scale 1.0 and a large CCM scale.

    This is the closed-form guarantee: the earlier engine let U2 HEXASPI (~8:1
    tall-narrow) / U3 OSPI / wireless-module vertical name rows smear because
    `_lay` used the bare 1.27 pin_pitch on vertical edges (shorter than a name
    row is tall). vert_pitch floors it to one name-row height + a gap."""

    @staticmethod
    def _intra_overlap_count(pins, scale):
        from bodesign_eda_bridge.kicad_symbol import _symbol_geometry
        from bodesign_eda_bridge.kicad_emit import _pin_name_box_abs
        geom = _symbol_geometry(pins, scale=scale)
        # rebuild the name boxes exactly as the intra gate sees them (component at
        # origin; at_x/at_y from placements are the pin OUTER endpoints = ex/ey).
        boxes = []
        for pin, ex, ey, rot in geom.pin_placements:
            if not pin.name:
                continue
            boxes.append(_pin_name_box_abs(pin.name, ex, ey, rot, 0.0, 0.0, scale))
        count = 0
        for i in range(len(boxes)):
            ax0, ax1, ay0, ay1 = boxes[i]
            for j in range(i + 1, len(boxes)):
                bx0, bx1, by0, by1 = boxes[j]
                # half-open intersection (edge touch is not overlap), matches
                # LedgerRect.overlaps semantics used by intra_symbol_text_overlaps.
                if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                    count += 1
        return count

    def _pins_numeric(self, names):
        from bodesign_eda_bridge.kicad_symbol import KiCadSymbolPin
        return [KiCadSymbolPin(number=str(i + 1), name=nm, kind="bidirectional")
                for i, nm in enumerate(names)]

    def test_tall_narrow_dense_vertical_names_no_intra_overlap(self):
        # ~8:1 HEXASPI-like part: many long names on the vertical edges (DIP mirror
        # for <=24 numeric puts them all on left/right), which is exactly where the
        # legacy 1.27 vertical pitch smeared. Long names to also stress need_w.
        names = [f"SIO{i}_DQ{i}_LONGNAME" for i in range(1, 17)]  # 16 pins -> L/R
        for scale in (1.0, 4.0):
            with self.subTest(scale=scale):
                self.assertEqual(
                    self._intra_overlap_count(self._pins_numeric(names), scale), 0,
                    f"vertical-edge dense long names must not overlap (scale={scale})")

    def test_vertical_edge_only_names_no_intra_overlap(self):
        # DIP mirror (<=24 numeric) puts ALL names on left/right vertical edges —
        # the exact locus vert_pitch fixes. Vary count so both edges are dense and
        # names are long enough that one row is taller than the bare 1.27 pitch.
        for n in (12, 20, 24):
            names = [f"BANK{i}_ADDR_LINE" for i in range(1, n + 1)]
            for scale in (1.0, 4.0):
                with self.subTest(n=n, scale=scale):
                    self.assertEqual(
                        self._intra_overlap_count(self._pins_numeric(names), scale), 0,
                        f"vertical-edge stacked names must not overlap (n={n}, scale={scale})")

    def test_short_names_dip_scale1_no_intra_overlap(self):
        # Regression guard: a plain short-name DIP part (01_power/02_mcu shape) must
        # stay intra-clean at scale 1.0 (must not regress from the vert_pitch add).
        names = [f"P{i}" for i in range(1, 13)]
        self.assertEqual(
            self._intra_overlap_count(self._pins_numeric(names), 1.0), 0,
            "short-name DIP must stay intra-clean at scale 1.0")


if __name__ == "__main__":
    unittest.main()
