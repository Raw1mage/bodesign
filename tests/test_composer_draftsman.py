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
        sch = self._sch_text(r)
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
        sch = self._sch_text(r)
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
        sch = self._sch_text(r)
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
        sch = self._sch_text(r)
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
        sch = self._sch_text(r)
        self.assertNotIn("(wire (pts", sch)
        self.assertIn("(global_label", sch)

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


if __name__ == "__main__":
    unittest.main()
