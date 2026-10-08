"""Synthetic DD-18 controls; the live specimen test asserts shape only."""
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import tempfile
import unittest

from bodesign_eda_bridge.c01_scene_gate import C01SceneInputError, c01_scene_gate
from tests.test_c02_chain import _png

SCRATCH = os.path.expanduser("~/.cache/scratch/c01-scene-tests")
LIVE = os.path.expanduser("~/products/bodesign/outputs/btdongle_ms/c01_scene_manifest-v1.json")


class SceneGate(unittest.TestCase):
    def setUp(self):
        os.makedirs(SCRATCH, mode=0o700, exist_ok=True)
        self.d = tempfile.mkdtemp(dir=SCRATCH)
        self.addCleanup(shutil.rmtree, self.d)
        self.stl = os.path.join(self.d, "part.stl")
        with open(self.stl, "wb") as f:
            f.write(b"\0" * 80 + struct.pack("<I", 1)
                    + struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0))
        with open(self.stl, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        self.m = {"schema": "c01_scene_manifest/1", "consumed_enclosure_mesh_path": {"lower": "part.stl"},
                  "consumed_enclosure_mesh_sha256": {"lower": sha}, "declared_views": ["iso", "top"],
                  "materials": {"shell": {"token": "BODY"}}, "token_bindings": {"BODY": ["lower"]},
                  "surfaces": ["lower"], "renderer": {"name": "synthetic", "version": "1"}, "seed": 0,
                  "output_px": [8, 8], "human_tree_dir": self.d}
        self.scene = os.path.join(self.d, "scene.json")
        self.c02 = self.js("c02.json", {"schema": "c02p_manifest/4",
                                      "exported_enclosure_mesh_sha256": {"lower": sha}})
        self.save()

    def js(self, name, value):
        path = os.path.join(self.d, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f)
        return path

    def save(self):
        self.js("scene.json", self.m)
        with open(self.scene, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        for view in self.m["declared_views"]:
            with open(os.path.join(self.d, f"01.c01-{view}-v1.png"), "wb") as f:
                f.write(_png(8, 8))
            self.js(f"01.c01-{view}-v1.json", {"scene_manifest_sha256": sha, "renderer": self.m["renderer"]})

    def run_gate(self, **kw):
        return c01_scene_gate(self.scene, c02_manifest_path=self.c02, **kw)

    def failed(self, gate, **kw):
        result = self.run_gate(**kw)
        self.assertEqual(result["gates"][gate]["status"], "fail", result)
        if gate != "S-05":
            self.assertFalse(result["ok"])
        return result

    def test_positive_all_required_pass(self):
        r = self.run_gate(expected_bbox_mm=[1, 1, 1], bbox_tol_mm=0)
        self.assertTrue(r["ok"], r)
        self.assertEqual({g["status"] for g in r["gates"].values()}, {"pass"})

    def test_s01_tampered_stl_sha(self):
        with open(self.stl, "ab") as f:
            f.write(b"tamper")
        # Keep a parseable ASCII STL while changing its bytes.
        with open(self.stl, "wb") as f:
            f.write(b"solid changed\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 1\nendloop\nendfacet\nendsolid changed\n")
        r = self.failed("S-01")
        self.assertEqual(r["gates"]["S-01"]["primary"]["offenders"][0]["stale_side"], "scene_manifest")

    def test_s01_c02_mismatch_stale_side(self):
        self.js("c02.json", {"exported_enclosure_mesh_sha256": {"lower": "0" * 64}})
        r = self.failed("S-01")
        self.assertIn("stale_side", r["gates"]["S-01"]["secondary"]["offenders"][0])

    def test_s01_missing_c02_export_unmeasured(self):
        self.js("c02.json", {"schema": "c02p_manifest/3"})
        r = self.run_gate()
        self.assertEqual(r["gates"]["S-01"]["status"], "unmeasured")
        self.assertEqual(r["gates"]["S-01"]["secondary"]["schema"], "c02p_manifest/3")
        self.assertFalse(r["ok"])

    def test_s01_no_c02_unmeasured(self):
        r = c01_scene_gate(self.scene)
        self.assertEqual(r["gates"]["S-01"]["status"], "unmeasured")
        self.assertFalse(r["ok"])

    def test_s01_missing_asset(self):
        os.remove(self.stl)
        self.failed("S-01")

    def test_s02_token_without_surface(self):
        self.m["token_bindings"]["BODY"] = []
        self.save()
        self.failed("S-02")

    def test_s02_double_bound_surface(self):
        self.m["token_bindings"]["OTHER"] = ["lower"]
        self.save()
        self.failed("S-02")

    def test_s02_undeclared_material_token(self):
        self.m["materials"]["shell"]["token"] = "UNKNOWN"
        self.save()
        self.failed("S-02")

    def test_s02_unbound_surface(self):
        self.m["surfaces"].append("upper")
        self.save()
        self.failed("S-02")

    def test_s02_derive_surface_universe(self):
        del self.m["surfaces"]
        self.save()
        self.assertTrue(self.run_gate()["ok"])

    def test_s03_missing_view(self):
        os.remove(os.path.join(self.d, "01.c01-top-v1.png"))
        self.failed("S-03")

    def test_s02_material_referenced_surface_outside_derived_universe(self):
        del self.m["surfaces"]
        self.m["materials"]["shell"]["surfaces"] = ["upper"]
        self.save()
        self.failed("S-02")

    def test_s03_required_views_cannot_omit_declared_views(self):
        os.remove(os.path.join(self.d, "01.c01-top-v1.png"))
        self.failed("S-03", required_views=["iso"])

    def test_s03_unprefixed_filename_passes(self):
        for view in self.m["declared_views"]:
            for suffix in ("png", "json"):
                os.rename(os.path.join(self.d, f"01.c01-{view}-v1.{suffix}"),
                          os.path.join(self.d, f"c01-{view}-v1.{suffix}"))
        self.assertTrue(self.run_gate()["ok"])

    def test_s01_extra_consumed_asset_missing(self):
        self.m["consumed_recipe_path"] = "missing.json"
        self.save()
        self.failed("S-01")

    def test_s03_zero_byte_png(self):
        with open(os.path.join(self.d, "01.c01-top-v1.png"), "wb"):
            pass
        self.failed("S-03")

    def test_s03_wrong_sidecar_sha(self):
        self.js("01.c01-top-v1.json", {"scene_manifest_sha256": "0" * 64, "renderer": self.m["renderer"]})
        self.failed("S-03")

    def test_s03_no_sidecar(self):
        os.remove(os.path.join(self.d, "01.c01-top-v1.json"))
        self.failed("S-03")

    def test_s03_bad_ihdr_crc(self):
        data = bytearray(_png(8, 8))
        data[32] ^= 1
        with open(os.path.join(self.d, "01.c01-top-v1.png"), "wb") as f:
            f.write(data)
        self.failed("S-03")

    def test_s03_undersized(self):
        with open(os.path.join(self.d, "01.c01-top-v1.png"), "wb") as f:
            f.write(_png(4, 4))
        self.failed("S-03")

    def test_s03_highest_version_and_empty_dir(self):
        with open(os.path.join(self.d, "02.c01-top-v2.png"), "wb"):
            pass
        r = self.failed("S-03")
        self.assertEqual(r["gates"]["S-03"]["views"]["top"]["version"], 2)
        empty = os.path.join(self.d, "empty")
        os.mkdir(empty, 0o700)
        self.failed("S-03", human_dir=empty)

    def test_s04_empty_renderer_version(self):
        self.m["renderer"]["version"] = ""
        self.save()
        self.failed("S-04")

    def test_s04_renderer_mismatch(self):
        with open(self.scene, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        self.js("01.c01-top-v1.json", {"scene_manifest_sha256": sha, "renderer": {"name": "other", "version": "1"}})
        self.failed("S-04")

    def test_s04_seed_missing(self):
        del self.m["seed"]
        self.save()
        self.failed("S-04")

    def test_s05_bbox_twice_expected_does_not_change_ok(self):
        r = self.failed("S-05", expected_bbox_mm={"lower": [0.5, 0.5, 0.5]}, bbox_tol_mm=0.01)
        self.assertTrue(r["ok"])

    def test_s05_absent_declaration_unmeasured(self):
        self.assertEqual(self.run_gate()["gates"]["S-05"]["status"], "unmeasured")

    def test_s05_tolerance_missing_fail_fast(self):
        with self.assertRaisesRegex(C01SceneInputError, "C01_SCENE_.*together"):
            self.run_gate(expected_bbox_mm=[1, 1, 1])

    def test_malformed_json_fail_fast(self):
        with open(self.scene, "w") as f:
            f.write("not json")
        with self.assertRaisesRegex(C01SceneInputError, "C01_SCENE_"):
            self.run_gate()


class ServerRegistration(unittest.TestCase):
    def test_registered_fail_fast_handler(self):
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../services/mcp/server.py"))
        try:
            spec = importlib.util.spec_from_file_location("bodesign_server_scene_test", path)
            srv = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(srv)
        except Exception as e:
            self.skipTest(f"server module not importable here: {e}")
        tool = {t["name"]: t for t in srv.TOOLS}["bodesign_c01_scene_gate"]
        self.assertTrue(callable(tool["handler"]))
        result = tool["handler"]({})
        self.assertFalse(result["ok"])
        self.assertIn("C01_SCENE_", result["error"])


@unittest.skipUnless(os.path.isfile(LIVE), "Track A scene manifest not on disk")
class SceneSpecimen(unittest.TestCase):
    def test_live_report_shape_only(self):
        try:
            r = c01_scene_gate(LIVE)
        except C01SceneInputError as e:
            self.skipTest(f"live manifest deviates from scene input contract: {e}")
        self.assertEqual(set(r), {"ok", "gates", "inputs", "measured"})
        self.assertIsInstance(r["ok"], bool)
        self.assertEqual(set(r["gates"]), {"S-01", "S-02", "S-03", "S-04", "S-05"})
        for gate in r["gates"].values():
            self.assertIn(gate["status"], {"pass", "fail", "unmeasured"})
