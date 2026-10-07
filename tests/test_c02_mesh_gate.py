"""Tests for bodesign_c04_board_manifest and bodesign_c02_mesh_gate (DD-19; c04-entry-freeze 2.2/2.3).

STL fixtures are generated at run time (binary STL, hollow box with a known wall) under ~/.cache/scratch;
nothing mesh-shaped is committed. Board fixtures reuse tests/fixtures/c04_placement_gate/.
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import tempfile
import unittest

from bodesign_eda_bridge.c04_gate import C04GateInputError
from bodesign_eda_bridge.c04_manifest import c04_board_manifest, canonical_sha256
from bodesign_eda_bridge.c02_mesh_gate import C02MeshInputError, c02_mesh_gate

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures", "c04_placement_gate")
POS = os.path.join(FX, "positive.kicad_pcb")
OUT = os.path.expanduser("~/products/bodesign/outputs/btdongle_ms")
V2 = os.path.join(OUT, "btdongle_c04-v2.kicad_pcb")
_SCRATCH = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "scratch", "c02-mesh-gate-tests")


def _box(lo, hi, invert=False):
    """12 outward-wound triangles of an axis-aligned box (invert=True => inward-wound, i.e. a cavity)."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    v = {(i, j, k): (x1 if i else x0, y1 if j else y0, z1 if k else z0) for i in (0, 1) for j in (0, 1) for k in (0, 1)}
    quads = [((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)),   # -z
             ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),   # +z
             ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),   # -y
             ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),   # +y
             ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)),   # -x
             ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))]   # +x
    tris = []
    for a, b, c, d in quads:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return [(t[0], t[2], t[1]) for t in tris] if invert else tris


def _hollow(outer_lo, outer_hi, wall):
    cav_lo = tuple(c + wall for c in outer_lo)
    cav_hi = tuple(c - wall for c in outer_hi)
    return _box(outer_lo, outer_hi) + _box(cav_lo, cav_hi, invert=True)


def _write_stl(path, tris):
    with open(path, "wb") as fh:
        fh.write(b"\0" * 80 + struct.pack("<I", len(tris)))
        for t in tris:
            fh.write(struct.pack("<12f", 0, 0, 0, *t[0], *t[1], *t[2]) + b"\0\0")
    return path


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(_SCRATCH, exist_ok=True)
        cls.d = tempfile.mkdtemp(dir=_SCRATCH)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def stl(self, name, tris):
        return _write_stl(os.path.join(self.d, name + ".stl"), tris)

    def run_gate(self, name, tris, wall=1.0, **kw):
        return c02_mesh_gate(self.stl(name, tris), wall, **kw)["parts"][name + ".stl"]


BOX = _hollow((0, 0, 0), (20, 20, 10), 2.0)


# ----------------------------------------------------------------------------- board manifest
class BoardManifest(unittest.TestCase):
    def test_positive_fixture_packet(self):
        m = c04_board_manifest(POS, ["R1", "C1"])
        self.assertTrue(m["ok"])
        self.assertEqual(m["thickness"], 1.6)
        self.assertEqual(m["outline"]["bbox"], [0.0, 0.0, 20.0, 20.0])
        self.assertEqual(m["outline"]["area_mm2"], 400.0)
        self.assertEqual(m["mounting_holes"], [])
        self.assertEqual(m["measured"]["mounting_holes"]["status"], "measured")
        self.assertEqual(sorted(m["connectors"]), ["C1", "R1"])
        r1 = m["connectors"]["R1"]
        for k in ("origin", "rotation_deg", "side", "courtyard_bbox", "pad_bbox"):
            self.assertIn(k, r1)
        self.assertEqual(r1["origin"], [5.0, 5.0])
        self.assertEqual(r1["side"], "F")

    def test_hashes_are_canonical_json_of_the_subobjects(self):
        m = c04_board_manifest(POS, ["R1"])
        self.assertEqual(m["exported_outline_sha256"], canonical_sha256(m["outline"]))
        self.assertEqual(m["exported_mounting_holes_sha256"], canonical_sha256(m["mounting_holes"]))
        rt = json.loads(json.dumps(m))
        self.assertEqual(canonical_sha256(rt["outline"]), m["exported_outline_sha256"])
        # determinism and sensitivity
        self.assertEqual(c04_board_manifest(POS, ["R1"])["exported_outline_sha256"], m["exported_outline_sha256"])
        bigger = json.loads(json.dumps(m["outline"]))
        bigger["polygon"][2][0] += 0.01
        self.assertNotEqual(canonical_sha256(bigger), m["exported_outline_sha256"])

    def _variant(self, name, old, new):
        os.makedirs(_SCRATCH, exist_ok=True)
        d = tempfile.mkdtemp(dir=_SCRATCH)
        self.addCleanup(shutil.rmtree, d, True)
        with open(POS, encoding="utf-8") as fh:
            s = fh.read()
        self.assertEqual(s.count(old), 1, old)
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(s.replace(old, new))
        return p

    def test_missing_thickness_fails_fast(self):
        p = self._variant("nothick.kicad_pcb", "(general (thickness 1.6) (legacy_teardrops no))", "(general (legacy_teardrops no))")
        with self.assertRaisesRegex(C04GateInputError, "C04_MANIFEST_THICKNESS_MISSING"):
            c04_board_manifest(p, ["R1"])

    def test_missing_outline_and_open_outline_fail_fast(self):
        p = self._variant("noedge.kicad_pcb", '(layer "Edge.Cuts") (uuid "c04a0000-0000-4000-8000-000000000001")', '(layer "User.1") (uuid "c04a0000-0000-4000-8000-000000000001")')
        with self.assertRaisesRegex(C04GateInputError, "C04_MANIFEST_OUTLINE_MISSING"):
            c04_board_manifest(p, ["R1"])
        q = self._variant("open.kicad_pcb", "(gr_rect (start 0 0) (end 20 20) (stroke (width 0.05) (type default)) (fill no)",
                          "(gr_line (start 0 0) (end 20 0) (stroke (width 0.05) (type default))")
        with self.assertRaisesRegex(C04GateInputError, "C04_GATE_BOARD_FIELD|C04_MANIFEST_OUTLINE"):
            c04_board_manifest(q, ["R1"])

    def test_connector_refs_required_and_checked(self):
        with self.assertRaisesRegex(C04GateInputError, "connector_refs is required"):
            c04_board_manifest(POS, None)
        with self.assertRaisesRegex(C04GateInputError, "C04_MANIFEST_CONNECTOR_MISSING.*ZZ9"):
            c04_board_manifest(POS, ["R1", "ZZ9"])

    def test_mounting_hole_footprint_is_listed(self):
        hole = ('\t(footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu") (uuid "c04a0000-0000-4000-8000-0000000000f9") (at 3 3)\n'
                '\t\t(property "Reference" "H1" (at 0 -3 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n'
                '\t\t(attr through_hole)\n'
                '\t\t(pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask"))\n\t)\n')
        with open(POS, encoding="utf-8") as fh:
            s = fh.read()
        i = s.index('\t(footprint "Resistor_SMD')
        os.makedirs(_SCRATCH, exist_ok=True)
        d = tempfile.mkdtemp(dir=_SCRATCH)
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, "hole.kicad_pcb")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(s[:i] + hole + s[i:])
        m = c04_board_manifest(p, ["R1"])
        self.assertEqual(len(m["mounting_holes"]), 1)
        h = m["mounting_holes"][0]
        self.assertEqual((h["ref"], h["x"], h["y"], h["drill_mm"], h["plated"]), ("H1", 3.0, 3.0, 3.2, False))
        self.assertNotEqual(m["exported_mounting_holes_sha256"], c04_board_manifest(POS, ["R1"])["exported_mounting_holes_sha256"])


@unittest.skipUnless(os.path.isfile(V2), "btdongle r2 board not on disk")
class BoardManifestSpecimen(unittest.TestCase):
    def test_r2_zero_holes_and_connectors_present(self):
        refs = ["J1", "J2", "SW1", "SW2", "SW3", "D2", "D3", "D4", "D5"]
        m = c04_board_manifest(V2, refs)
        self.assertEqual(m["mounting_holes"], [])
        self.assertEqual(m["measured"]["mounting_holes"]["count"], 0)
        self.assertEqual(sorted(m["connectors"]), sorted(refs))
        self.assertEqual(m["thickness"], 1.6)
        self.assertEqual(m["outline"]["bbox"], [100.0, 50.0, 128.0, 143.0])


# ----------------------------------------------------------------------------- M-01 / M-02 / M-03 / M-04
class MeshGates(_Base):
    def test_positive_hollow_box_passes_m01_to_m04_and_measures_wall_2(self):
        p = self.run_gate("pos", BOX, wall=1.0, expected_bbox_mm=[20, 20, 10], bbox_tol_mm=0.01)
        for g in ("M-01", "M-02", "M-03", "M-04"):
            self.assertEqual(p[g]["status"], "pass", (g, p[g]))
        self.assertEqual(p["M-01"]["measured"]["triangle_count"], 24)
        self.assertEqual(p["M-02"]["measured"]["boundary_edges"], 0)
        self.assertEqual(p["M-02"]["measured"]["components"], 2)
        self.assertAlmostEqual(p["M-02"]["measured"]["signed_volume_mm3"], 20 * 20 * 10 - 16 * 16 * 6, places=3)
        self.assertAlmostEqual(p["M-04"]["measured"]["min_thickness_mm"], 2.0, places=3)
        self.assertTrue(p["M-04"]["measured"]["sampled_all_faces"])

    def test_m04_wall_thinner_than_threshold_fails(self):
        p = self.run_gate("thin", _hollow((0, 0, 0), (20, 20, 10), 1.0), wall=1.5)
        self.assertEqual(p["M-02"]["status"], "pass")
        self.assertEqual(p["M-04"]["status"], "fail")
        self.assertAlmostEqual(p["M-04"]["measured"]["min_thickness_mm"], 1.0, places=3)
        self.assertTrue(p["M-04"]["offenders"])

    def test_m02_open_mesh_one_face_removed(self):
        p = self.run_gate("open", BOX[1:])
        self.assertEqual(p["M-02"]["status"], "fail")
        self.assertGreater(p["M-02"]["measured"]["boundary_edges"], 0)
        self.assertEqual(p["M-04"]["status"], "unmeasured")  # never pass on an undefined inward direction

    def test_m02_single_inverted_face_is_inconsistent_orientation(self):
        t = BOX[0]
        p = self.run_gate("flip1", [(t[0], t[2], t[1])] + BOX[1:])
        self.assertEqual(p["M-02"]["status"], "fail")
        self.assertGreater(p["M-02"]["measured"]["inconsistent_orientation_edges"], 0)

    def test_m02_fully_inverted_shell_fails_on_volume(self):
        p = self.run_gate("inv", _box((0, 0, 0), (20, 20, 10), invert=True))
        self.assertEqual(p["M-02"]["status"], "fail")
        self.assertLess(p["M-02"]["measured"]["signed_volume_mm3"], 0)
        self.assertEqual(p["M-02"]["measured"]["inconsistent_orientation_edges"], 0)

    def test_m02_non_manifold_edge_three_faces(self):
        t = BOX[0]
        p = self.run_gate("nonman", BOX + [(t[0], t[1], (-5.0, -5.0, -5.0))])
        self.assertEqual(p["M-02"]["status"], "fail")
        self.assertGreaterEqual(p["M-02"]["measured"]["non_manifold_edges"], 1)

    def test_m01_zero_area_triangle(self):
        p = self.run_gate("zero", BOX + [((1.0, 1.0, 1.0), (2.0, 2.0, 2.0), (3.0, 3.0, 3.0))])
        self.assertEqual(p["M-01"]["status"], "fail")
        self.assertEqual(p["M-01"]["measured"]["degenerate_count"], 1)
        self.assertEqual(p["M-01"]["offenders"][0]["triangle"], 24)

    def test_m01_empty_and_garbage_files_fail(self):
        self.assertEqual(self.run_gate("empty", [])["M-01"]["status"], "fail")
        g = os.path.join(self.d, "garbage.stl")
        with open(g, "wb") as fh:
            fh.write(b"not an stl at all")
        r = c02_mesh_gate(g, 1.0)["parts"]["garbage.stl"]
        self.assertEqual(r["M-01"]["status"], "fail")
        self.assertEqual(r["M-02"]["status"], "unmeasured")

    def test_m03_bbox_off_by_2x_fails_and_exact_passes(self):
        bad = self.run_gate("bb", BOX, expected_bbox_mm=[10, 10, 5], bbox_tol_mm=0.5)["M-03"]
        self.assertEqual(bad["status"], "fail")
        self.assertEqual([o["ratio"] for o in bad["offenders"]], [2.0, 2.0, 2.0])
        ok = self.run_gate("bb2", BOX, expected_bbox_mm=[20, 20, 10], bbox_tol_mm=0.5)["M-03"]
        self.assertEqual(ok["status"], "pass")

    def test_m03_unmeasured_without_declaration_and_tolerance_required(self):
        self.assertEqual(self.run_gate("nb", BOX)["M-03"]["status"], "unmeasured")
        with self.assertRaisesRegex(C02MeshInputError, "bbox_tol_mm is required"):
            self.run_gate("nt", BOX, expected_bbox_mm=[20, 20, 10])

    def test_per_part_expected_bbox_map_must_name_every_part(self):
        a, b = self.stl("pa", BOX), self.stl("pb", BOX)
        with self.assertRaisesRegex(C02MeshInputError, "no entry for"):
            c02_mesh_gate([a, b], 1.0, expected_bbox_mm={"pa.stl": [20, 20, 10]}, bbox_tol_mm=0.1)
        r = c02_mesh_gate([a, b], 1.0, expected_bbox_mm={"pa.stl": [20, 20, 10], "pb.stl": [20, 20, 10]}, bbox_tol_mm=0.1)
        self.assertTrue(r["ok"])

    def test_input_errors_are_explicit(self):
        with self.assertRaisesRegex(C02MeshInputError, "wall_min_mm is required"):
            c02_mesh_gate(self.stl("e1", BOX), None)
        with self.assertRaisesRegex(C02MeshInputError, "C02_MESH_INPUT_NOT_FOUND"):
            c02_mesh_gate("/nonexistent/x.stl", 1.0)
        with self.assertRaisesRegex(C02MeshInputError, "stl_path is required"):
            c02_mesh_gate([], 1.0)

    def test_ok_false_when_any_measured_gate_fails_and_trimesh_never_decides(self):
        r = c02_mesh_gate(self.stl("okf", BOX[1:]), 1.0)
        self.assertFalse(r["ok"])
        cc = r["parts"]["okf.stl"]["trimesh_crosscheck"]
        self.assertIn("available", cc)


# ----------------------------------------------------------------------------- M-05 / M-06
ENC = _hollow((-5, -5, -3), (25, 25, 8), 2.0)  # cavity (-3,-3,-1)..(23,23,6); board 0..20 x 0..20 x 0..1.6 sits inside


class AssemblyGates(_Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.board = c04_board_manifest(POS, ["R1"])
        cls.bpath = os.path.join(cls.d, "board_manifest.json")
        with open(cls.bpath, "w", encoding="utf-8") as fh:
            json.dump(cls.board, fh)
        cls.enc = cls_stl = _write_stl(os.path.join(cls.d, "enc.stl"), ENC)

    def asm(self, **kw):
        kw.setdefault("clearance_min_mm", 0.5)
        return c02_mesh_gate(self.enc, 1.0, board_manifest_path=self.bpath, **kw)["assembly"]

    def test_m05_positive_board_inside_cavity_with_measured_distance(self):
        g = self.asm(clearance_min_mm=0.5, board_placement_mm=[0, 0, 0])["M-05"]
        self.assertEqual(g["status"], "pass", g)
        self.assertAlmostEqual(g["measured"]["min_distance_mm"], 1.0, places=3)  # board bottom z=0 vs cavity floor z=-1

    def test_m05_clearance_too_small_fails(self):
        g = self.asm(clearance_min_mm=2.0, board_placement_mm=[0, 0, 0])["M-05"]
        self.assertEqual(g["status"], "fail")
        self.assertTrue(g["offenders"])

    def test_m05_board_outside_enclosure_fails(self):
        g = self.asm(clearance_min_mm=0.5, board_placement_mm=[40, 0, 0])["M-05"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["offenders"][0]["reason"], "outside enclosure")

    def test_m05_unmeasured_never_pass_without_registration_or_manifest(self):
        self.assertEqual(self.asm(clearance_min_mm=0.5)["M-05"]["status"], "unmeasured")
        r = c02_mesh_gate(self.enc, 1.0)["assembly"]["M-05"]
        self.assertEqual(r["status"], "unmeasured")
        with self.assertRaisesRegex(C02MeshInputError, "clearance_min_mm is required"):
            c02_mesh_gate(self.enc, 1.0, board_manifest_path=self.bpath)

    def test_m05_unmeasured_when_a_part_is_not_manifold(self):
        bad = _write_stl(os.path.join(self.d, "bad.stl"), ENC[1:])
        r = c02_mesh_gate(bad, 1.0, board_manifest_path=self.bpath, clearance_min_mm=0.5, board_placement_mm=[0, 0, 0])
        self.assertEqual(r["assembly"]["M-05"]["status"], "unmeasured")
        self.assertIn("M-05", r["unmeasured_gates"])

    def _c02(self, name, doc):
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        return p

    def test_m06_chain_pass_fail_unmeasured(self):
        exp = self.board["exported_outline_sha256"]
        holes = self.board["exported_mounting_holes_sha256"]
        ok = self._c02("c02_ok.json", {"consumed_board_outline_sha256": exp, "consumed_mounting_holes_sha256": holes})
        self.assertEqual(self.asm(c02_manifest_path=ok)["M-06"]["status"], "pass")
        stale = self._c02("c02_stale.json", {"consumed_board_outline_sha256": "0" * 64})
        g = self.asm(c02_manifest_path=stale)["M-06"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["offenders"][0]["kind"], "STALE_UPSTREAM_MANIFEST")
        absent = self._c02("c02_absent.json", {"something_else": 1})
        self.assertEqual(self.asm(c02_manifest_path=absent)["M-06"]["status"], "unmeasured")
        self.assertEqual(self.asm()["M-06"]["status"], "unmeasured")

    def test_m06_detects_tampered_board_manifest(self):
        tampered = json.loads(json.dumps(self.board))
        tampered["outline"]["polygon"][2][0] += 0.5
        tp = self._c02("board_tampered.json", tampered)
        ok = self._c02("c02_ok2.json", {"consumed_board_outline_sha256": self.board["exported_outline_sha256"]})
        g = c02_mesh_gate(self.enc, 1.0, board_manifest_path=tp, c02_manifest_path=ok, clearance_min_mm=0.5)["assembly"]["M-06"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["offenders"][0]["kind"], "STALE_BOARD_MANIFEST")

    def _with_placement(self, name, placement):
        return self._c02(name, {"consumed_board_outline_sha256": self.board["exported_outline_sha256"],
                                "board_placement_mm": placement})

    def test_m05_placement_read_from_c02_manifest_is_measured(self):
        g = self.asm(c02_manifest_path=self._with_placement("pl_ok.json", [0, 0, 0]))["M-05"]
        self.assertEqual(g["status"], "pass", g)
        self.assertEqual(g["measured"]["placement_source"], "c02_manifest")
        self.assertEqual(g["measured"]["board_placement_mm"], [0.0, 0.0, 0.0])

    def test_m05_explicit_argument_wins_over_manifest(self):
        bad = self._with_placement("pl_bad.json", [40, 0, 0])  # manifest says outside the enclosure
        g = self.asm(c02_manifest_path=bad, board_placement_mm=[0, 0, 0])["M-05"]
        self.assertEqual(g["status"], "pass", g)
        self.assertEqual(g["measured"]["placement_source"], "argument")

    def test_m05_tampered_manifest_placement_is_still_measured_and_attributed(self):
        g = self.asm(c02_manifest_path=self._with_placement("pl_tamper.json", [40, 0, 0]))["M-05"]
        self.assertEqual(g["status"], "fail")
        self.assertEqual(g["offenders"][0]["reason"], "outside enclosure")
        self.assertEqual(g["measured"]["placement_source"], "c02_manifest")

    def test_m05_both_absent_stays_unmeasured(self):
        absent = self._c02("pl_none.json", {"consumed_board_outline_sha256": self.board["exported_outline_sha256"]})
        self.assertEqual(self.asm(c02_manifest_path=absent)["M-05"]["status"], "unmeasured")

    def test_m06_mounting_hole_chain_mismatch_fails(self):
        bad = self._c02("c02_holes.json", {"consumed_board_outline_sha256": self.board["exported_outline_sha256"],
                                          "consumed_mounting_holes_sha256": "f" * 64})
        self.assertEqual(self.asm(c02_manifest_path=bad)["M-06"]["status"], "fail")


# ----------------------------------------------------------------------------- registration
def _load_server():
    import importlib.util
    path = os.path.join(HERE, "..", "services", "mcp", "server.py")
    spec = importlib.util.spec_from_file_location("bodesign_server_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ServerRegistration(unittest.TestCase):
    def test_tools_registered_and_handlers_fail_fast(self):
        try:
            srv = _load_server()
        except Exception as e:  # server imports are environment dependent; say why
            self.skipTest(f"server module not importable here: {e}")
        tools = {t["name"]: t for t in srv.TOOLS}
        for name in ("bodesign_c04_board_manifest", "bodesign_c02_mesh_gate"):
            self.assertIn(name, tools)
            self.assertTrue(callable(tools[name]["handler"]))
        self.assertEqual(tools["bodesign_c04_board_manifest"]["schema"]["required"], ["board_path", "connector_refs"])
        r = tools["bodesign_c04_board_manifest"]["handler"]({"board_path": POS})
        self.assertFalse(r["ok"])
        self.assertIn("connector_refs is required", r["error"])
        r = tools["bodesign_c02_mesh_gate"]["handler"]({"wall_min_mm": 1.0})
        self.assertFalse(r["ok"])
        self.assertIn("C02_MESH_INPUT_MISSING", r["error"])
        r = tools["bodesign_c02_mesh_gate"]["handler"]({"stl_path": "/nonexistent/x.stl", "wall_min_mm": 1.0})
        self.assertFalse(r["ok"])


# ----------------------------------------------------------------------------- Track A C02' specimen (skip if absent)
C02P = [os.path.join(OUT, f"c02p_enclosure_{p}-v1.stl") for p in ("lower", "upper")]
C02P_BOARD = os.path.join(OUT, ".src", "c04_board_manifest-v1.json")


@unittest.skipUnless(all(os.path.isfile(p) for p in C02P), "Track A C02' STLs not landed (c02p_enclosure_{lower,upper}-v1.stl)")
class C02pSpecimenShape(unittest.TestCase):
    """Shape only: no verdict is asserted for the producer's parts."""

    def test_shape_only(self):
        kw = {"board_manifest_path": C02P_BOARD, "clearance_min_mm": 0.3} if os.path.isfile(C02P_BOARD) else {}
        r = c02_mesh_gate(C02P, 1.2, **kw)
        self.assertEqual(sorted(r["parts"]), sorted(os.path.basename(p) for p in C02P))
        for part in r["parts"].values():
            for g in ("M-01", "M-02", "M-03", "M-04"):
                self.assertIn(part[g]["status"], ("pass", "fail", "unmeasured"))
        for g in ("M-05", "M-06"):
            self.assertIn(r["assembly"][g]["status"], ("pass", "fail", "unmeasured"))
        self.assertEqual(r["assembly"]["M-05"]["status"], "unmeasured")  # no board_placement_mm declared here


if __name__ == "__main__":
    unittest.main()
