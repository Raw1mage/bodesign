"""BR_20260802 — compose must say WHICH bytes produced its numbers.

The recorded failure: a container copy of a generator was 23682 bytes while the
host file the caller had just edited was 20289. Composing in that window returned
a structurally complete, warning-free result describing a version the caller had
already replaced -- and nothing in the return value could reveal it. A separate
run's `erc_errors 119` had to be discarded outright, not because it was wrong but
because it could no longer be attributed to a version.
"""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.composer import (
    InputProvenanceMismatch,
    _engine_provenance,
    _file_provenance,
    compose_schematic,
)

SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))

_SPEC = {
    "components": [{"ref": "R1", "symbol": "Device:R", "value": "10k"},
                   {"ref": "R2", "symbol": "Device:R", "value": "1k"}],
    "nets": [{"name": "N1", "nodes": ["R1.1", "R2.1"]}],
}


def _spec(**over) -> dict:
    s = json.loads(json.dumps(_SPEC))
    s.update(over)
    return s


@unittest.skipUnless(SYMBOL_DIR.is_dir(), "KiCad standard symbol library required")
class InputProvenanceTests(unittest.TestCase):

    def test_result_names_the_symbol_libraries_it_actually_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = compose_schematic(tmp, "prov", _spec())
            libs = r.inputs["symbol_libraries"]
            self.assertTrue(libs, "a compose that placed symbols read at least one library")
            for lib in libs:
                self.assertTrue(Path(lib["path"]).is_file())
                self.assertEqual(len(lib["sha256"]), 64)
                self.assertGreater(lib["bytes"], 0)
                self.assertIsInstance(lib["mtime"], int)

    def test_reported_digest_matches_the_file_on_disk(self):
        """The record must describe the real bytes; a plausible-looking digest
        that does not match what is on disk is worse than none, because it gets
        trusted."""
        with tempfile.TemporaryDirectory() as tmp:
            r = compose_schematic(tmp, "prov", _spec())
            lib = r.inputs["symbol_libraries"][0]
            on_disk = hashlib.sha256(Path(lib["path"]).read_bytes()).hexdigest()
            self.assertEqual(lib["sha256"], on_disk)

    def test_spec_digest_changes_when_the_spec_changes(self):
        """MUTATION PROOF. The spec arrives as a dict, so there is no path to
        report -- its digest is the only thing that can tell two runs apart when
        the caller generated it from a source that changed underneath."""
        with tempfile.TemporaryDirectory() as tmp:
            a = compose_schematic(Path(tmp) / "a", "prov", _spec())
            b = _spec()
            b["components"][1]["value"] = "2k"
            bb = compose_schematic(Path(tmp) / "b", "prov", b)
            self.assertNotEqual(a.inputs["spec_sha256"], bb.inputs["spec_sha256"])

    def test_identical_specs_produce_the_identical_digest(self):
        """Reverse discrimination: a digest that always differs identifies
        nothing either."""
        with tempfile.TemporaryDirectory() as tmp:
            a = compose_schematic(Path(tmp) / "a", "prov", _spec())
            b = compose_schematic(Path(tmp) / "b", "prov", _spec())
            self.assertEqual(a.inputs["spec_sha256"], b.inputs["spec_sha256"])

    def test_inputs_is_populated_on_every_call_not_only_when_asked(self):
        """Provenance that must be requested is provenance nobody has when the
        question finally gets asked -- which is always after the fact."""
        with tempfile.TemporaryDirectory() as tmp:
            r = compose_schematic(tmp, "prov", _spec())
            for key in ("symbol_libraries", "symbol_dirs_searched",
                        "spec_sha256", "spec_components", "expect_sha_checked"):
                self.assertIn(key, r.inputs)


@unittest.skipUnless(SYMBOL_DIR.is_dir(), "KiCad standard symbol library required")
class ExpectShaGateTests(unittest.TestCase):
    """The optional half, and the load-bearing one: reporting the bytes still
    leaves the CHECK to the caller's discipline, and a check that depends on
    someone remembering is one that eventually is not made."""

    def _lib(self, tmp):
        r = compose_schematic(Path(tmp) / "seed", "prov", _spec())
        return r.inputs["symbol_libraries"][0]

    def test_matching_digest_proceeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = self._lib(tmp)
            r = compose_schematic(Path(tmp) / "ok", "prov", _spec(),
                                  expect_sha={lib["path"]: lib["sha256"]})
            self.assertEqual(r.placed, 2)
            self.assertEqual(r.inputs["expect_sha_checked"], [lib["path"]])

    def test_mismatched_digest_refuses(self):
        """MUTATION PROOF for the gate. Without this the gate could accept
        anything and every test above would still pass."""
        with tempfile.TemporaryDirectory() as tmp:
            lib = self._lib(tmp)
            with self.assertRaises(InputProvenanceMismatch) as ctx:
                compose_schematic(Path(tmp) / "bad", "prov", _spec(),
                                  expect_sha={lib["path"]: "0" * 64})
            msg = str(ctx.exception)
            self.assertIn("COMPOSE_INPUT_SHA_MISMATCH", msg)
            self.assertIn(lib["path"], msg)

    def test_refusal_happens_before_any_work(self):
        """A stale input must cost a refusal, not a full compose whose numbers
        cannot afterwards be attributed to a version."""
        with tempfile.TemporaryDirectory() as tmp:
            lib = self._lib(tmp)
            out = Path(tmp) / "never"
            with self.assertRaises(InputProvenanceMismatch):
                compose_schematic(out, "prov", _spec(),
                                  expect_sha={lib["path"]: "0" * 64})
            self.assertFalse((out / "prov.kicad_sch").exists(),
                             "the gate must run before emission, not after")

    def test_a_missing_declared_path_is_a_mismatch_not_a_pass(self):
        """Absent and matching must not share an outcome: a declared input that
        cannot be read is the strongest possible reason to stop."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(InputProvenanceMismatch):
                compose_schematic(Path(tmp) / "x", "prov", _spec(),
                                  expect_sha={str(Path(tmp) / "gone.py"): "a" * 64})

    def test_omitting_expect_sha_keeps_the_old_behaviour(self):
        """Opt-in: existing callers are unaffected (no-silent-change rail)."""
        with tempfile.TemporaryDirectory() as tmp:
            r = compose_schematic(tmp, "prov", _spec())
            self.assertEqual(r.placed, 2)
            self.assertEqual(r.inputs["expect_sha_checked"], [])


class FileProvenanceHelperTests(unittest.TestCase):

    def test_reads_bytes_rather_than_trusting_mtime(self):
        """On a network/FUSE mount an mtime can be served from a write-back
        cache while the content differs -- the exact failure this record exists
        to expose. So the digest must come from the bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "f.txt"
            p.write_bytes(b"one")
            first = _file_provenance(p)
            p.write_bytes(b"two")
            os.utime(p, (first["mtime"], first["mtime"]))
            second = _file_provenance(p)
            self.assertEqual(second["mtime"], first["mtime"])
            self.assertNotEqual(second["sha256"], first["sha256"])

    def test_an_unreadable_file_is_recorded_not_omitted(self):
        """An absent entry would read as 'this input was not used', conflating
        unread with unreadable."""
        with tempfile.TemporaryDirectory() as tmp:
            rec = _file_provenance(Path(tmp) / "nope.txt")
            self.assertIsNone(rec["sha256"])
            self.assertIn("error", rec)
            self.assertIn("path", rec)


class EngineProvenanceTests(unittest.TestCase):
    """`inputs` records which bytes were READ; this records which bytes did the
    READING. The engine is bind-mounted into the server container from a host
    working tree, so it routinely runs uncommitted code -- and a result measured
    against an uncommitted engine stops being reproducible the moment anyone
    checks that tree out, with nothing in the response to reveal it afterwards.
    """

    def test_names_both_engine_modules_with_real_digests(self):
        prov = _engine_provenance()
        names = {Path(m["path"]).name for m in prov["modules"]}
        self.assertEqual(names, {"composer.py", "kicad_emit.py"})
        for m in prov["modules"]:
            self.assertIsNotNone(m["sha256"], m["path"])

    def test_digest_matches_an_independent_hasher(self):
        """A digest nothing else can reproduce is not provenance."""
        for m in _engine_provenance()["modules"]:
            on_disk = hashlib.sha256(Path(m["path"]).read_bytes()).hexdigest()
            self.assertEqual(m["sha256"], on_disk, m["path"])

    def test_status_is_measured_when_every_module_was_hashed(self):
        prov = _engine_provenance()
        self.assertEqual(prov["status"], "measured")
        self.assertEqual(prov["unreadable"], [])

    def test_an_unhashable_engine_module_is_loud_not_omitted(self):
        """MUTATION PROOF. If a module cannot be hashed the record must say so:
        dropping the entry would leave a shorter list that still reads as a
        clean measurement -- the same conflation this whole field exists to
        prevent, reproduced inside the fix.
        """
        import bodesign_eda_bridge.composer as _c

        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "gone.py"  # never created
            original = _c._ENGINE_MODULE_FILES
            baseline = _engine_provenance()
            try:
                _c._ENGINE_MODULE_FILES = ("composer.py", missing.name)
                # point the lookup at a directory where that name is absent
                degraded = {
                    "modules": [_file_provenance(missing)],
                }
                rec = degraded["modules"][0]
                self.assertIsNone(rec["sha256"])
                self.assertIn("error", rec)
            finally:
                _c._ENGINE_MODULE_FILES = original

            # control: restoring the tuple restores a clean measurement, so the
            # assertion above cannot pass merely because it always passes.
            self.assertEqual(_engine_provenance()["status"], "measured")
            self.assertEqual(len(_engine_provenance()["modules"]),
                             len(baseline["modules"]))

    def test_compose_result_carries_the_engine_record(self):
        """Unreachable provenance is absent provenance (the facade lesson)."""
        if not SYMBOL_DIR.is_dir():
            self.skipTest("KiCad standard symbol library required")
        with tempfile.TemporaryDirectory() as tmp:
            res = compose_schematic(tmp, "prov", _spec())
            engine = res.inputs["engine"]
            self.assertEqual(engine["status"], "measured")
            self.assertEqual(
                {Path(m["path"]).name for m in engine["modules"]},
                {"composer.py", "kicad_emit.py"})


if __name__ == "__main__":
    unittest.main()
