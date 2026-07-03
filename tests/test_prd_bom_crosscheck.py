"""Tests for prd_bom_crosscheck (plans/quality_prd-bom-crosscheck L1, TV-1..TV-5).

Each TV-* test maps to plans/quality_prd-bom-crosscheck/test-vectors.json.
Netlist fixtures use the real KiCad .net S-expr shape (taken from
experiments/e2e-led-driver/C03-EE/e2e-led-driver.net).
"""
import hashlib
import json
import os
import tempfile
import unittest

from bodesign_workflow_core import prd_bom_crosscheck
from bodesign_workflow_core.prd_bom_crosscheck import REPORT_FILENAME


def _netlist_sexpr(comps: list[dict]) -> str:
    """Render components in the real KiCad .net shape (footprint via fields)."""
    blocks = []
    for c in comps:
        fp = c.get("footprint", "")
        lib, _, part = c.get("libsymbol", ":").partition(":")
        blocks.append(
            f'    (comp (ref "{c["ref"]}")\n'
            f'      (value "{c["value"]}")\n'
            f'      (fields\n'
            f'        (field (name "Footprint") "{fp}")\n'
            f'        (field (name "Datasheet")))\n'
            f'      (libsource (lib "{lib}") (part "{part}") (description ""))\n'
            f'      (sheetpath (names "/") (tstamps "/"))\n'
            f'      (tstamps "0000"))'
        )
    return (
        '(export (version "E")\n'
        "  (components\n" + "\n".join(blocks) + ")\n"
        "  (nets))\n"
    )


TV1_MANIFEST = {
    "schema": "bodesign.c00.main_components_structured.v1",
    "source_field": "s04_system_architecture.main_components",
    "source_text": "test",
    "source_answer_state_sha256": None,
    "roles": [
        {
            "role": "current-regulator",
            "description": "CC regulator or NPN sink",
            "qty_min": 1,
            "patterns": ["AL5809", "regulator", "current.?sink"],
            "allowed_alternatives": [
                {"name": "npn-linear-sink",
                 "patterns": ["NPN", "SOT-23", "SOT-89", "BC8[0-9]{2}", "MMBT"]}
            ],
        }
    ],
    "approvals": [],
}

TV1_COMPONENTS = [
    {"ref": "R3", "value": "140R", "footprint": "R_0603_1608Metric", "libsymbol": "Device:R"},
]


class PrdBomCrosscheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def _write(self, name: str, content: str) -> str:
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(content)
        return path

    def _write_manifest(self, manifest: dict) -> str:
        return self._write("main_components_structured.json",
                           json.dumps(manifest, ensure_ascii=False))

    def _write_netlist(self, comps: list[dict]) -> str:
        return self._write("test.net", _netlist_sexpr(comps))

    # TV-1: missing role → BLOCKING → gate FAIL
    def test_tv1_missing_role_blocks_gate(self):
        m = self._write_manifest(TV1_MANIFEST)
        n = self._write_netlist(TV1_COMPONENTS)
        r = prd_bom_crosscheck(m, n)
        self.assertEqual(r.gate, "FAIL")
        self.assertEqual(r.blocking, ["current-regulator"])
        v = r.verdicts[0]
        self.assertEqual(v.status, "missing")
        self.assertTrue(v.blocking)
        self.assertEqual(r.netlist_components, 1)

    # TV-2: in-envelope alternative → substituted in_envelope, gate PASS
    def test_tv2_in_envelope_alternative_passes(self):
        manifest = {
            **TV1_MANIFEST,
            "roles": [{
                "role": "current-regulator", "description": "", "qty_min": 1,
                "patterns": ["AL5809"],
                "allowed_alternatives": [
                    {"name": "npn-linear-sink", "patterns": ["NPN", "MMBT"]}],
            }],
        }
        m = self._write_manifest(manifest)
        n = self._write_netlist([{
            "ref": "Q1", "value": "MMBT2222A", "footprint": "SOT-23",
            "libsymbol": "Transistor_BJT:MMBT2222A"}])
        r = prd_bom_crosscheck(m, n)
        self.assertEqual(r.gate, "PASS")
        v = r.verdicts[0]
        self.assertEqual(v.status, "substituted")
        self.assertTrue(v.in_envelope)
        self.assertFalse(v.blocking)
        self.assertEqual(v.matched_refs, ["Q1"])
        self.assertEqual(r.blocking, [])

    # TV-3: out-of-envelope substitution WITH user approval → PASS
    def test_tv3_approved_substitution_passes(self):
        manifest = {
            **TV1_MANIFEST,
            "roles": [{
                "role": "current-regulator", "description": "", "qty_min": 1,
                "patterns": ["AL5809"], "allowed_alternatives": [],
            }],
            "approvals": [{
                "role": "current-regulator", "substitute": "resistor-ballast",
                "approved_by": "user", "quote": "純電阻方案我批准", "date": "2026-07-03"}],
        }
        m = self._write_manifest(manifest)
        n = self._write_netlist(TV1_COMPONENTS)
        r = prd_bom_crosscheck(m, n)
        self.assertEqual(r.gate, "PASS")
        v = r.verdicts[0]
        self.assertEqual(v.status, "substituted")
        self.assertFalse(v.in_envelope)
        self.assertTrue(v.approved)
        self.assertFalse(v.blocking)
        self.assertEqual(r.blocking, [])

    # TV-4: manifest absent → MANIFEST_MISSING, never a silent pass
    def test_tv4_manifest_missing_fails_fast(self):
        n = self._write_netlist(TV1_COMPONENTS)
        with self.assertRaises(ValueError) as ctx:
            prd_bom_crosscheck(os.path.join(self.dir, "nonexistent.json"), n)
        self.assertIn("MANIFEST_MISSING", str(ctx.exception))

    # TV-5: determinism — same inputs twice → byte-identical serialized report
    def test_tv5_determinism_byte_identical(self):
        m = self._write_manifest(TV1_MANIFEST)
        n = self._write_netlist(TV1_COMPONENTS)
        out1 = os.path.join(self.dir, "run1")
        out2 = os.path.join(self.dir, "run2")
        prd_bom_crosscheck(m, n, out_dir=out1)
        prd_bom_crosscheck(m, n, out_dir=out2)
        with open(os.path.join(out1, REPORT_FILENAME), "rb") as f1:
            b1 = f1.read()
        with open(os.path.join(out2, REPORT_FILENAME), "rb") as f2:
            b2 = f2.read()
        self.assertEqual(b1, b2)
        self.assertGreater(len(b1), 0)

    # MANIFEST_INVALID: all violations reported in ONE pass
    def test_manifest_invalid_reports_all_violations_in_one_pass(self):
        manifest = {
            "schema": "bodesign.c00.main_components_structured.v1",
            "roles": [
                {"role": "", "qty_min": 0, "patterns": ["[unclosed"],
                 "allowed_alternatives": [{"name": "x", "patterns": []}]},
            ],
            "approvals": "not-a-list",
        }
        m = self._write_manifest(manifest)
        n = self._write_netlist(TV1_COMPONENTS)
        with self.assertRaises(ValueError) as ctx:
            prd_bom_crosscheck(m, n)
        msg = str(ctx.exception)
        self.assertIn("MANIFEST_INVALID", msg)
        self.assertIn("roles[0].role", msg)
        self.assertIn("roles[0].qty_min", msg)
        self.assertIn("roles[0].patterns[0]", msg)
        self.assertIn("roles[0].allowed_alternatives[0].patterns", msg)
        self.assertIn("approvals", msg)

    # NETLIST_MISSING
    def test_netlist_missing_fails_fast(self):
        m = self._write_manifest(TV1_MANIFEST)
        with self.assertRaises(ValueError) as ctx:
            prd_bom_crosscheck(m, os.path.join(self.dir, "nope.net"))
        self.assertIn("NETLIST_MISSING", str(ctx.exception))

    # NETLIST_PARSE_ERROR: garbage and zero-component files both refuse
    def test_netlist_parse_error_fails_fast(self):
        m = self._write_manifest(TV1_MANIFEST)
        n_bad = self._write("bad.net", "(export (version E) (components")
        with self.assertRaises(ValueError) as ctx:
            prd_bom_crosscheck(m, n_bad)
        self.assertIn("NETLIST_PARSE_ERROR", str(ctx.exception))
        n_empty = self._write("empty.net", '(export (version "E") (components) (nets))')
        with self.assertRaises(ValueError) as ctx2:
            prd_bom_crosscheck(m, n_empty)
        self.assertIn("NETLIST_PARSE_ERROR", str(ctx2.exception))

    # qty_min: present requires matched count >= qty_min
    def test_qty_min_enforced(self):
        manifest = {
            **TV1_MANIFEST,
            "roles": [{
                "role": "white-led", "description": "4x LED", "qty_min": 4,
                "patterns": ["LED"], "allowed_alternatives": [],
            }],
        }
        m = self._write_manifest(manifest)
        n = self._write_netlist([
            {"ref": f"D{i}", "value": "LED_WHITE_0603",
             "footprint": "LED_0603_1608Metric", "libsymbol": "Device:LED"}
            for i in range(2, 5)  # only 3 LEDs, need 4
        ])
        r = prd_bom_crosscheck(m, n)
        self.assertEqual(r.gate, "FAIL")
        self.assertEqual(r.verdicts[0].status, "missing")
        self.assertEqual(r.verdicts[0].matched_refs, ["D2", "D3", "D4"])

    # MANIFEST_STALE: recorded hash differs from sibling answer_state.json → warn field
    def test_manifest_stale_flag(self):
        answer_path = self._write("answer_state.json", '{"v": 1}')
        actual = hashlib.sha256(open(answer_path, "rb").read()).hexdigest()
        manifest_fresh = {**TV1_MANIFEST, "source_answer_state_sha256": actual}
        m = self._write_manifest(manifest_fresh)
        n = self._write_netlist(TV1_COMPONENTS)
        self.assertFalse(prd_bom_crosscheck(m, n).manifest_stale)
        manifest_stale = {**TV1_MANIFEST, "source_answer_state_sha256": "0" * 64}
        m2 = self._write_manifest(manifest_stale)
        self.assertTrue(prd_bom_crosscheck(m2, n).manifest_stale)


if __name__ == "__main__":
    unittest.main()
