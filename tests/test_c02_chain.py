"""Tests for bodesign_c02_chain_check and bodesign_c02_view_coverage (c04-entry-freeze 2.3 / DD-19(a))."""
from __future__ import annotations

import json
import os
import shutil
import struct
import tempfile
import unittest
import zlib

from bodesign_eda_bridge.c02_chain import C02ChainInputError, c02_chain_check, c02_view_coverage, DEFAULT_VIEWS
from bodesign_eda_bridge.c04_manifest import c04_board_manifest

HERE = os.path.dirname(os.path.abspath(__file__))
POS = os.path.join(HERE, "fixtures", "c04_placement_gate", "positive.kicad_pcb")
OUT = os.path.expanduser("~/products/bodesign/outputs/btdongle_ms")
V2 = os.path.join(OUT, "btdongle_c04-v2.kicad_pcb")
PARAMS = os.path.join(OUT, ".src", "c02p_params_resolved-v1.json")
_SCRATCH = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "scratch", "c02-chain-tests")


def _png(w, h):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x80" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class _Base(unittest.TestCase):
    def setUp(self):
        os.makedirs(_SCRATCH, exist_ok=True)
        self.d = tempfile.mkdtemp(dir=_SCRATCH)
        self.addCleanup(shutil.rmtree, self.d, True)

    def js(self, name, doc):
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        return p


class ChainCheck(_Base):
    def setUp(self):
        super().setUp()
        self.m = c04_board_manifest(POS, ["R1"])

    def c02(self, **kw):
        doc = {"consumed_board_outline_sha256": self.m["exported_outline_sha256"],
               "consumed_mounting_holes_sha256": self.m["exported_mounting_holes_sha256"]}
        doc.update(kw)
        return self.js("c02.json", doc)

    def test_positive_both_links_pass(self):
        r = c02_chain_check(POS, self.c02())
        self.assertTrue(r["ok"], r)
        self.assertEqual({k: v["status"] for k, v in r["links"].items()}, {"outline": "pass", "mounting_holes": "pass"})

    def test_outline_mismatch_fails_and_names_the_stale_side(self):
        r = c02_chain_check(POS, self.c02(consumed_board_outline_sha256="8975fdfd" + "0" * 56))
        self.assertFalse(r["ok"])
        l = r["links"]["outline"]
        self.assertEqual((l["status"], l["stale_side"], l["kind"]), ("fail", "c02_manifest", "STALE_UPSTREAM_MANIFEST"))
        self.assertEqual(l["recomputed"], self.m["exported_outline_sha256"])
        self.assertEqual(r["links"]["mounting_holes"]["status"], "pass")

    def test_mounting_hole_mismatch_fails(self):
        r = c02_chain_check(POS, self.c02(consumed_mounting_holes_sha256="f" * 64))
        self.assertFalse(r["ok"])
        self.assertEqual(r["links"]["mounting_holes"]["status"], "fail")

    def test_absent_consumed_value_is_unmeasured_never_pass(self):
        p = self.js("c02_absent.json", {"consumed_board_outline_sha256": self.m["exported_outline_sha256"]})
        r = c02_chain_check(POS, p)
        self.assertFalse(r["ok"])
        self.assertEqual(r["links"]["mounting_holes"]["status"], "unmeasured")
        self.assertEqual(r["unmeasured"], ["mounting_holes"])

    def test_board_manifest_file_fresh_vs_stale(self):
        fresh = self.js("bm_fresh.json", self.m)
        r = c02_chain_check(POS, self.c02(), fresh)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["board_manifest_file"]["status"], "pass")
        stale = json.loads(json.dumps(self.m))
        stale["exported_outline_sha256"] = "0" * 64
        r = c02_chain_check(POS, self.c02(), self.js("bm_stale.json", stale))
        self.assertFalse(r["ok"])
        self.assertEqual((r["board_manifest_file"]["status"], r["board_manifest_file"]["stale_side"]),
                         ("fail", "board_manifest_file"))

    def test_board_manifest_with_tampered_outline_content_is_stale(self):
        t = json.loads(json.dumps(self.m))
        t["outline"]["polygon"][2][0] += 0.5
        r = c02_chain_check(POS, self.c02(), self.js("bm_tamper.json", t))
        self.assertEqual(r["board_manifest_file"]["status"], "fail")
        self.assertTrue(any("content vs its own" in o["field"] for o in r["board_manifest_file"]["offenders"]))

    def test_input_errors_are_explicit(self):
        with self.assertRaisesRegex(C02ChainInputError, "board_path is required"):
            c02_chain_check("", self.c02())
        with self.assertRaisesRegex(C02ChainInputError, "C02_CHAIN_INPUT_NOT_FOUND"):
            c02_chain_check(POS, "/nonexistent/c02.json")
        with self.assertRaisesRegex(C02ChainInputError, "C04_GATE_INPUT_NOT_FOUND"):
            c02_chain_check("/nonexistent/x.kicad_pcb", self.c02())


@unittest.skipUnless(os.path.isfile(V2) and os.path.isfile(PARAMS), "Track A r2 board / c02p_params_resolved-v1.json not on disk")
class ChainCheckSpecimen(unittest.TestCase):
    """Real-world negative control: the producer's hand-written outline hash must NOT match the tool's recompute."""

    def test_track_a_params_fail_against_tool_recompute(self):
        with open(PARAMS, encoding="utf-8") as fh:
            consumed = json.load(fh)["consumed_board_outline_sha256"]
        r = c02_chain_check(V2, PARAMS)
        self.assertFalse(r["ok"])
        l = r["links"]["outline"]
        self.assertEqual(l["status"], "fail")
        self.assertEqual(l["consumed"], consumed)
        self.assertNotEqual(l["recomputed"], consumed)
        self.assertEqual(l["stale_side"], "c02_manifest")
        self.assertTrue(l["recomputed"].startswith("6e66f4e9"), l["recomputed"])


class ViewCoverage(_Base):
    def put(self, view, ver=1, size=(1000, 700), prefix="02.c02p-", raw=None):
        p = os.path.join(self.d, f"{prefix}{view}-v{ver}.png")
        with open(p, "wb") as fh:
            fh.write(_png(*size) if raw is None else raw)
        return p

    def full(self):
        for v in DEFAULT_VIEWS:
            self.put(v)

    def test_full_set_passes(self):
        self.full()
        r = c02_view_coverage(human_dir=self.d)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["status"], "pass")
        self.assertEqual(sorted(r["views"]), sorted(DEFAULT_VIEWS))
        self.assertTrue(all(v["status"] == "present" for v in r["views"].values()))

    def test_one_missing_fails_with_list(self):
        self.full()
        os.remove(os.path.join(self.d, "02.c02p-plan-v1.png"))
        r = c02_view_coverage(human_dir=self.d)
        self.assertFalse(r["ok"])
        self.assertEqual(r["missing"], ["plan"])

    def test_zero_byte_png_fails(self):
        self.full()
        self.put("iso", raw=b"")
        r = c02_view_coverage(human_dir=self.d)
        self.assertFalse(r["ok"])
        self.assertEqual(r["invalid"][0]["view"], "iso")
        self.assertIn("zero-byte", r["invalid"][0]["reason"])

    def test_non_png_and_undersized_png_fail(self):
        self.full()
        self.put("plan", raw=b"GIF89a" + b"\0" * 100)
        self.put("exploded", size=(100, 100))
        r = c02_view_coverage(human_dir=self.d)
        self.assertFalse(r["ok"])
        self.assertEqual(sorted(i["view"] for i in r["invalid"]), ["exploded", "plan"])
        self.assertEqual(c02_view_coverage(human_dir=self.d, min_px=[50, 50])["invalid"][0]["view"], "plan")

    def test_highest_version_is_examined_and_empty_dir_fails_not_passes(self):
        self.full()
        self.put("iso", ver=2, raw=b"")
        self.assertEqual(c02_view_coverage(human_dir=self.d)["views"]["iso"]["version"], 2)
        empty = tempfile.mkdtemp(dir=_SCRATCH)
        self.addCleanup(shutil.rmtree, empty, True)
        r = c02_view_coverage(human_dir=empty)
        self.assertFalse(r["ok"])
        self.assertEqual(r["missing"], list(DEFAULT_VIEWS))

    def test_manifest_supplies_human_dir_and_inputs_are_checked(self):
        self.full()
        m = self.js("c02.json", {"human_tree_dir": self.d})
        self.assertTrue(c02_view_coverage(c02_manifest_path=m)["ok"])
        with self.assertRaisesRegex(C02ChainInputError, "no human_tree_dir"):
            c02_view_coverage(c02_manifest_path=self.js("c02b.json", {"x": 1}))
        with self.assertRaisesRegex(C02ChainInputError, "human_dir"):
            c02_view_coverage()
        with self.assertRaisesRegex(C02ChainInputError, "C02_VIEWS_INPUT_NOT_FOUND"):
            c02_view_coverage(human_dir="/nonexistent/dir")
        with self.assertRaisesRegex(C02ChainInputError, "required_views"):
            c02_view_coverage(human_dir=self.d, required_views=["Bad View"])

    def test_custom_required_set_and_prefix(self):
        self.put("iso", prefix="02.other-")
        self.assertTrue(c02_view_coverage(human_dir=self.d, stage_prefix="02.other-", required_views=["iso"])["ok"])
        self.assertFalse(c02_view_coverage(human_dir=self.d, required_views=["iso"])["ok"])


HUMAN = os.path.expanduser("~/products/bodesign/btdongle_ms")


@unittest.skipUnless(os.path.isdir(HUMAN), "btdongle human tree not on disk")
class ViewCoverageSpecimen(unittest.TestCase):
    def test_live_human_tree_report_shape_only(self):
        # SHAPE only: the live deliverable tree moves, so no verdict (ok / missing) is asserted here.
        # The negative control is synthetic (test_one_missing_fails_with_list).
        r = c02_view_coverage(human_dir=HUMAN)
        self.assertIsInstance(r["ok"], bool)
        present = {v for v, e in r["views"].items() if e["status"] == "present"}
        self.assertEqual(present | set(r["missing"]), set(DEFAULT_VIEWS))
        self.assertFalse(present & set(r["missing"]))
        for v in present:
            f = r["views"][v]["file"]
            p = f if os.path.isabs(f) else os.path.join(HUMAN, f)
            self.assertTrue(os.path.isfile(p), p)
            self.assertGreater(os.path.getsize(p), 0, p)


class ServerRegistration(unittest.TestCase):
    def test_tools_registered_with_fail_fast_handlers(self):
        import importlib.util
        path = os.path.join(HERE, "..", "services", "mcp", "server.py")
        try:
            spec = importlib.util.spec_from_file_location("bodesign_server_chain_test", path)
            srv = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(srv)
        except Exception as e:
            self.skipTest(f"server module not importable here: {e}")
        tools = {t["name"]: t for t in srv.TOOLS}
        for n in ("bodesign_c02_chain_check", "bodesign_c02_view_coverage"):
            self.assertTrue(callable(tools[n]["handler"]))
        self.assertFalse(tools["bodesign_c02_chain_check"]["handler"]({})["ok"])
        self.assertFalse(tools["bodesign_c02_view_coverage"]["handler"]({})["ok"])


if __name__ == "__main__":
    unittest.main()
