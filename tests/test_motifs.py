"""Topology, rigid placement and real KiCad motif connectivity regressions."""
import copy
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from bodesign_eda_bridge.motifs import detect_motifs, synthesize_motif_geometry
from bodesign_eda_bridge import compose_schematic


COMPONENTS = [
    {"ref": "U1", "symbol": "Connector:Conn_01x02_Pin"},
    {"ref": "R1", "symbol": "Device:R"},
    {"ref": "R2", "symbol": "Device:R"},
]
NETS = [
    {"name": "VCC", "nodes": ["U1.1", "R1.1"]},
    {"name": "SENSE", "nodes": ["U1.2", "R1.2", "R2.1"]},
    {"name": "GND", "nodes": ["R2.2"]},
]
PINS = {"U1": {"1": (5.08, 2.54, 180), "2": (5.08, 0, 180)},
        "R1": {"1": (0, 3.81, 270), "2": (0, -3.81, 90)},
        "R2": {"1": (0, 3.81, 270), "2": (0, -3.81, 90)}}


class MotifDetectionTests(unittest.TestCase):
    def test_divider_precedes_pull_resistors(self):
        motifs = detect_motifs(COMPONENTS, NETS)
        self.assertEqual([m.kind for m in motifs], ["voltage_divider"])
        self.assertEqual(motifs[0].host, ("U1", "2"))
        self.assertEqual(motifs[0].ground_nodes, (("R2", "2"),))

    def test_input_order_does_not_change_detection(self):
        shuffled = [{**n, "nodes": list(reversed(n["nodes"]))} for n in reversed(NETS)]
        self.assertEqual(detect_motifs(COMPONENTS, NETS), detect_motifs(COMPONENTS[::-1], shuffled))

    def test_rc_filter(self):
        parts = copy.deepcopy(COMPONENTS)
        parts[2]["symbol"] = "Device:C"
        self.assertEqual(detect_motifs(parts, NETS)[0].kind, "rc_filter")

    def test_pull_down(self):
        parts = [COMPONENTS[0], COMPONENTS[2]]
        nets = [{"name": "RESET", "nodes": ["U1.2", "R2.1"]}, NETS[2]]
        self.assertEqual(detect_motifs(parts, nets)[0].kind, "pull_resistor")

    def test_decoupling_shunt(self):
        parts = [COMPONENTS[0], {"ref": "C1", "symbol": "Device:C"}]
        nets = [{"name": "VCC", "nodes": ["U1.1", "C1.1"]},
                {"name": "GND", "nodes": ["C1.2"]}]
        self.assertEqual(detect_motifs(parts, nets)[0].kind, "decoupling_shunt")
        # A shared rail with two possible hosts is not ownership evidence.
        parts.append({"ref": "U2", "symbol": "Connector:Conn_01x02_Pin"})
        nets[0]["nodes"].append("U2.1")
        self.assertEqual(detect_motifs(parts, nets), [])

    def test_duplicate_pin_membership_refused(self):
        nets = copy.deepcopy(NETS)
        nets[2]["nodes"].append("R1.1")
        with self.assertRaisesRegex(ValueError, "MOTIF_PIN_MULTIPLE_NETS"):
            detect_motifs(COMPONENTS, nets)

    def test_unconnected_passive_is_not_a_motif(self):
        self.assertEqual(detect_motifs(COMPONENTS, [NETS[0]]), [])

    def test_geometry_aligns_branch_and_ground(self):
        motif = detect_motifs(COMPONENTS, NETS)[0]
        g = synthesize_motif_geometry(motif, PINS)
        top, bottom = g.pin_alignments[("R1", "2")], g.pin_alignments[("R2", "1")]
        self.assertEqual(top[0], bottom[0])
        self.assertAlmostEqual(bottom[1] - top[1], 5.08)
        gp = g.ground_glyphs[("R2", "2")]
        self.assertAlmostEqual(gp[1] - g.pin_alignments[("R2", "2")][1], 2.54)
        self.assertEqual(g, synthesize_motif_geometry(motif, PINS))

    def test_missing_geometry_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, "MOTIF_PIN_GEOMETRY_MISSING"):
            synthesize_motif_geometry(detect_motifs(COMPONENTS, NETS)[0], {})

    def test_explicit_power_kind(self):
        parts = [COMPONENTS[0], {"ref": "C1", "symbol": "Device:C"}]
        nets = [{"name": "CUSTOM", "kind": "power", "nodes": ["U1.1", "C1.1"]},
                {"name": "GND", "nodes": ["C1.2"]}]
        self.assertEqual(detect_motifs(parts, nets)[0].kind, "decoupling_shunt")

    def test_left_host_and_unsupported_edge(self):
        pins = copy.deepcopy(PINS)
        pins["U1"]["2"] = (-5.08, 0, 0)
        m = detect_motifs(COMPONENTS, NETS)[0]
        self.assertAlmostEqual(synthesize_motif_geometry(m, pins).tap[0], -10.16)
        pins["U1"]["2"] = (0, 5.08, 270)
        with self.assertRaisesRegex(ValueError, "MOTIF_HOST_EDGE_UNSUPPORTED"):
            synthesize_motif_geometry(m, pins)

    def test_reverse_orientation_is_not_silently_rewired(self):
        pins = copy.deepcopy(PINS)
        pins["R2"] = {"1": (0, -3.81, 90), "2": (0, 3.81, 270)}
        with self.assertRaisesRegex(ValueError, "MOTIF_PIN_ORIENTATION_UNSUPPORTED"):
            synthesize_motif_geometry(detect_motifs(COMPONENTS, NETS)[0], pins)


SYMBOLS = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))


@unittest.skipUnless((SYMBOLS / "Device.kicad_sym").exists(), "KiCad libraries unavailable")
class MotifIntegrationTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "scratch" / "motif-tests"
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.work = Path(tempfile.mkdtemp(dir=base))
        self.addCleanup(shutil.rmtree, self.work)

    def test_divider_emits_junction_wires_and_local_ground(self):
        try:
            result = compose_schematic(self.work, "divider", {"components": COMPONENTS, "nets": NETS},
                                       style="draftsman", symbol_dirs=SYMBOLS,
                                       fidelity=bool(shutil.which("kicad-cli")))
        except Exception as exc:
            text = (self.work / "divider.kicad_sch").read_text()
            self.fail(f"{exc}\n" + "\n".join(line for line in text.splitlines()
                      if any(key in line for key in ("(wire", "(junction", "(label", "(global_label", "(at ", '"Reference"'))))
        text = (self.work / "divider.kicad_sch").read_text()
        self.assertGreaterEqual(text.count("(junction "), 1)
        self.assertGreaterEqual(text.count("(wire "), 2)
        self.assertIn('(lib_id "power:GND")', text)
        self.assertNotIn("(global_label ", text)
        self.assertEqual(result.emit.unresolved_pins, [])

    def test_decoupling_emits_in_situ(self):
        parts = [COMPONENTS[0], {"ref": "C1", "symbol": "Device:C"}]
        nets = [{"name": "VCC", "nodes": ["U1.1", "C1.1"]},
                {"name": "GND", "nodes": ["C1.2"]}]
        result = compose_schematic(self.work, "decap", {"components": parts, "nets": nets},
                                   style="draftsman", symbol_dirs=SYMBOLS,
                                   fidelity=bool(shutil.which("kicad-cli")))
        text = (self.work / "decap.kicad_sch").read_text()
        self.assertIn('(lib_id "power:GND")', text)
        self.assertEqual(result.emit.unresolved_pins, [])

    def test_macro_survives_compaction_and_page_fill(self):
        from bodesign_eda_bridge.kicad_emit import emit_kicad_schematic
        from bodesign_eda_bridge.composer import _refine
        seen = []
        def capture(members, *args, **kwargs):
            seen.append(list(members))
            return _refine(members, *args, **kwargs)
        with patch("bodesign_eda_bridge.composer._refine", side_effect=capture), \
             patch("bodesign_eda_bridge.composer.emit_kicad_schematic", wraps=emit_kicad_schematic) as emit:
            compose_schematic(self.work, "macro", {"components": COMPONENTS, "nets": NETS},
                              style="draftsman", macro_compact=True, page_fill=True,
                              symbol_dirs=SYMBOLS)
        self.assertEqual(seen, [["U1"]])
        placements = {c.ref: c for c in emit.call_args.args[2]}
        for host, geometry in emit.call_args.kwargs["motif_geometries"]:
            for ref, (dx, dy) in geometry.offsets.items():
                self.assertAlmostEqual(placements[ref].x - placements[host].x, dx)
                self.assertAlmostEqual(placements[ref].y - placements[host].y, dy)

    def test_decoupling_distance_measured_at_emission(self):
        from bodesign_eda_bridge.kicad_emit import emit_kicad_schematic
        parts = [COMPONENTS[0], {"ref": "C1", "symbol": "Device:C"}]
        nets = [{"name": "VCC", "nodes": ["U1.1", "C1.1"]},
                {"name": "GND", "nodes": ["C1.2"]}]
        with patch("bodesign_eda_bridge.composer.emit_kicad_schematic", wraps=emit_kicad_schematic) as emit:
            compose_schematic(self.work, "distance", {"components": parts, "nets": nets},
                              style="draftsman", symbol_dirs=SYMBOLS)
        geometry = emit.call_args.kwargs["motif_geometries"][0][1]
        x, y = geometry.pin_alignments[("C1", "1")]
        self.assertAlmostEqual(((x - 5.08) ** 2 + y ** 2) ** 0.5, 5.08)

    def test_ground_never_enters_chain_router(self):
        from bodesign_eda_bridge.kicad_emit import _bus_chain_points
        parts = [{"ref": f"R{i}", "symbol": "Device:R"} for i in range(1, 4)]
        nets = [{"name": "GND", "nodes": [f"R{i}.2" for i in range(1, 4)]}]
        with patch("bodesign_eda_bridge.kicad_emit._bus_chain_points", wraps=_bus_chain_points) as chain:
            compose_schematic(self.work, "grounds", {"components": parts, "nets": nets},
                              style="draftsman", connection_style="wire", symbol_dirs=SYMBOLS)
        chain.assert_not_called()


if __name__ == "__main__":
    unittest.main()
