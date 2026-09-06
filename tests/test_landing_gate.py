"""Tests for the landing-plane verb runner (skills/bodesign/scripts/gate.py).

Covers plans/mcp_r13-landing-webdav-cache AC-1/AC-2/AC-3/AC-9:
  * typed fail-fast errors (python version, packages, unknown/not-landing verbs)
  * the stdout JSON envelope contract (single object; exit!=0 iff ok=false)
  * --list enumeration + registry smoke (every module/callable import-resolves)
  * E2E subprocess cycles on a tmp repo: the C00 Q&A loop and the
    orchestration dispatch → return_blocker → ingest_blocker → status cycle
  * optional-dep verbs gated-omit (no crash) when cairosvg etc. are absent
"""
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE = REPO_ROOT / "skills" / "bodesign" / "scripts" / "gate.py"

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


def _load_gate_module():
    spec = importlib.util.spec_from_file_location("bodesign_landing_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_gate(*argv, env_overrides=None):
    """Run gate.py as a subprocess; return (envelope dict, returncode, stderr)."""
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, str(GATE), *argv],
        capture_output=True, text=True, env=env, timeout=120,
    )
    stdout = proc.stdout.strip()
    envelope = json.loads(stdout) if stdout else None
    return envelope, proc.returncode, proc.stderr


class GateSkeletonTests(unittest.TestCase):
    """AC-2: typed errors + envelope shape (tasks 3.1)."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-gate-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_python_version_fail_fast(self):
        gate = _load_gate_module()
        with mock.patch.object(gate.sys, "version_info", (3, 9, 0)):
            with self.assertRaises(gate.LandingError) as ctx:
                gate._check_python()
        self.assertEqual(ctx.exception.code, "LANDING_PYTHON_TOO_OLD")
        self.assertIn("3.10", ctx.exception.message)

    def test_packages_not_found_fail_fast(self):
        empty = self.work / "empty-src"
        empty.mkdir()
        env = {"BODESIGN_SRC": str(empty)}
        envelope, rc, _ = _run_gate("c00_readiness", "--repo", str(self.work), env_overrides=env)
        self.assertNotEqual(rc, 0)
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["error"]["code"], "LANDING_PACKAGES_NOT_FOUND")
        self.assertIn(str(empty), envelope["error"]["message"])  # tried paths shown
        self.assertIn("BODESIGN_SRC", envelope["error"]["message"])

    def test_unknown_verb(self):
        envelope, rc, _ = _run_gate("no_such_verb", "--repo", str(self.work))
        self.assertNotEqual(rc, 0)
        self.assertEqual(envelope["error"]["code"], "VERB_UNKNOWN")
        self.assertIn("--list", envelope["error"]["message"])

    def test_not_landing_verb_refused_with_container_hint(self):
        envelope, rc, _ = _run_gate("emit_fab", "--repo", str(self.work))
        self.assertNotEqual(rc, 0)
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["error"]["code"], "VERB_NOT_LANDING")
        self.assertIn("bodesign_emit_fab", envelope["error"]["hint"])

    def test_args_invalid_missing_repo(self):
        envelope, rc, _ = _run_gate("c00_readiness")
        self.assertNotEqual(rc, 0)
        self.assertEqual(envelope["error"]["code"], "VERB_ARGS_INVALID")
        self.assertIn("--repo", envelope["error"]["message"])

    def test_args_invalid_relative_repo(self):
        envelope, rc, _ = _run_gate("c00_readiness", "--repo", "relative/path")
        self.assertNotEqual(rc, 0)
        self.assertEqual(envelope["error"]["code"], "VERB_ARGS_INVALID")

    def test_args_invalid_bad_json(self):
        envelope, rc, _ = _run_gate("c00_update_answers", "--repo", str(self.work),
                                    "--json", "{not json")
        self.assertNotEqual(rc, 0)
        self.assertEqual(envelope["error"]["code"], "VERB_ARGS_INVALID")

    def test_runtime_error_typed_with_traceback_on_stderr(self):
        # c00_update_answers on an unscaffolded folder raises C00TemplateError → VERB_RUNTIME_ERROR
        envelope, rc, stderr = _run_gate("c00_update_answers", "--repo", str(self.work),
                                         "--json", json.dumps({"answers": {"x": "y"}}))
        self.assertNotEqual(rc, 0)
        self.assertEqual(envelope["error"]["code"], "VERB_RUNTIME_ERROR")
        self.assertIn("Traceback", stderr)

    def test_envelope_shape_success(self):
        envelope, rc, stderr = _run_gate("c00_scaffold_prd", "--repo", str(self.work))
        self.assertEqual(rc, 0)
        self.assertEqual(set(envelope) & {"ok", "verb", "result"}, {"ok", "verb", "result"})
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["verb"], "c00_scaffold_prd")
        self.assertIsInstance(envelope["result"], dict)
        self.assertIn("landing_verb_ok verb=c00_scaffold_prd", stderr)

    def test_stdout_is_a_single_json_object(self):
        proc = subprocess.run([sys.executable, str(GATE), "--list"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0)
        # exactly one JSON document on stdout — nothing before or after
        json.loads(proc.stdout)
        self.assertEqual(proc.stdout.strip().count("\n"), 0)


class GateRegistryTests(unittest.TestCase):
    """AC-1: --list enumerates; every registry row import-resolves (tasks 3.3)."""

    @classmethod
    def setUpClass(cls):
        cls.gate = _load_gate_module()

    def test_list_count_and_shape(self):
        envelope, rc, _ = _run_gate("--list")
        self.assertEqual(rc, 0)
        self.assertTrue(envelope["ok"])
        result = envelope["result"]
        self.assertGreaterEqual(result["count"], 40)
        self.assertEqual(result["count"], len(result["verbs"]))
        for row in result["verbs"]:
            self.assertTrue({"verb", "module", "callable", "required_args", "summary"} <= set(row))
        listed = {row["verb"] for row in result["verbs"]}
        for expected in ("c00_scaffold_prd", "c00_readiness", "dispatch_work_packet",
                         "impedance_solve", "ingest_project", "reference_crosscheck"):
            self.assertIn(expected, listed)
        # heavy verbs are declared not-landing, not silently absent
        self.assertIn("emit_fab", result["not_landing"])
        self.assertEqual(result["not_landing"]["emit_fab"], "bodesign_emit_fab")

    def test_every_registry_row_import_resolves(self):
        for verb, (module, callable_name, _req, _summary) in self.gate.VERBS.items():
            with self.subTest(verb=verb):
                mod = importlib.import_module(module)
                self.assertTrue(callable(getattr(mod, callable_name)),
                                f"{module}.{callable_name} not callable")

    def test_every_verb_has_a_handler(self):
        self.assertEqual(set(self.gate.VERBS), set(self.gate.HANDLERS))

    def test_no_overlap_between_landing_and_not_landing(self):
        self.assertFalse(set(self.gate.VERBS) & set(self.gate.NOT_LANDING))


class GateC00CycleE2ETests(unittest.TestCase):
    """AC-3: the C00 Q&A loop entirely on host via subprocess (tasks 3.2)."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-gate-c00-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_c00_scaffold_readiness_update_emit_cycle(self):
        env, rc, _ = _run_gate("c00_scaffold_prd", "--repo", str(self.work))
        self.assertEqual(rc, 0, env)
        # Paths come from the envelope, not from a hand-written guess. This line
        # asserted `C00-PRD/answer_state.json` while the scaffold has always
        # written `C00-PRD/03_output/answer_state.json`
        # (c00_prd_template.py:184), so the module was RED at HEAD -- which cost
        # it its whole job: a permanently-failing gate module cannot tell anyone
        # that gate.py broke, because the new breakage hides behind the same
        # rc=1. Reading the paths back from `result.files` also strengthens the
        # assertion: it now checks that everything the verb CLAIMS to have
        # written is actually on disk, rather than that one remembered path is.
        written = env["result"]["files"]
        self.assertIn("C00-PRD/03_output/answer_state.json", written)
        for rel in written:
            self.assertTrue((self.work / rel).is_file(),
                            f"envelope claims {rel} but it is not on disk")

        env, rc, _ = _run_gate("c00_readiness", "--repo", str(self.work))
        self.assertEqual(rc, 0, env)
        self.assertEqual(env["result"]["readiness_pct"], 0)

        env, rc, _ = _run_gate("c00_update_answers", "--repo", str(self.work),
                               "--json", json.dumps({"answers": {"target_customer": "makers"}}))
        self.assertEqual(rc, 0, env)

        env, rc, _ = _run_gate("c00_readiness", "--repo", str(self.work))
        self.assertEqual(rc, 0, env)
        self.assertGreater(env["result"]["readiness_pct"], 0)

        env, rc, _ = _run_gate("c00_emit_prd", "--repo", str(self.work))
        self.assertEqual(rc, 0, env)
        generated = env["result"].get("files") or []
        self.assertTrue(generated, env["result"])
        # files landed directly in the caller's folder — no token, no tarball
        listed = list((self.work / "C00-PRD").rglob("*.md"))
        self.assertTrue(listed)

    def test_c00_emit_prd_docx_render_only_and_assemble_rejected(self):
        env, rc, _ = _run_gate("c00_scaffold_prd", "--repo", str(self.work))
        self.assertEqual(rc, 0, env)

        env, rc, _ = _run_gate("c00_emit_prd_docx", "--repo", str(self.work))
        self.assertEqual(rc, 0, env)
        self.assertEqual(env["result"]["assembled"], [])
        self.assertIn("assemble_hint", env["result"])

        env, rc, _ = _run_gate("c00_emit_prd_docx", "--repo", str(self.work),
                               "--json", json.dumps({"assemble": True}))
        self.assertNotEqual(rc, 0)
        self.assertEqual(env["error"]["code"], "VERB_ARGS_INVALID")
        self.assertIn("bodesign_c00_emit_prd_docx", env["error"]["hint"])


class GateOrchestrationCycleE2ETests(unittest.TestCase):
    """AC-3: dispatch → return_blocker → ingest_blocker → status cycle (tasks 3.2)."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-gate-orch-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_dispatch_blocker_ingest_status_cycle(self):
        env, rc, _ = _run_gate("dispatch_work_packet", "--repo", str(self.work),
                               "--json", json.dumps({"target_layer": "C01", "objective": "id work"}))
        self.assertEqual(rc, 0, env)
        packet_id = env["result"]["packet_id"]
        self.assertTrue((self.work / "_orchestration" / "work_packets" / f"{packet_id}.json").is_file())

        env, rc, _ = _run_gate("return_blocker", "--repo", str(self.work),
                               "--json", json.dumps({
                                   "packet_id": packet_id, "severity": "decision",
                                   "summary": "colour undecided",
                                   "question_for_user": "matte or gloss?"}))
        self.assertEqual(rc, 0, env)
        blocker_id = env["result"]["blocker_id"]

        env, rc, _ = _run_gate("list_blockers", "--repo", str(self.work),
                               "--json", json.dumps({"unresolved_only": True}))
        self.assertEqual(rc, 0, env)
        self.assertEqual(len(env["result"]["blockers"]), 1)

        env, rc, _ = _run_gate("ingest_blocker", "--repo", str(self.work),
                               "--json", json.dumps({
                                   "blocker_id": blocker_id, "resolved_state": "answered",
                                   "decision": "matte"}))
        self.assertEqual(rc, 0, env)

        env, rc, _ = _run_gate("c00_orchestration_status", "--repo", str(self.work))
        self.assertEqual(rc, 0, env)
        self.assertIn("layers", env["result"])


class GateOptionalDepTests(unittest.TestCase):
    """R2: optional-dep verbs gated-omit (never crash) when cairosvg etc. absent (tasks 2.9)."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-gate-opt-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_c03_partition_diagram_svg_without_pptx(self):
        model = {"boards": [{"name": "main", "role": "host", "modules": [{"name": "mcu", "type": "mcu"}]}],
                 "interconnect": []}
        env, rc, _ = _run_gate("c03_emit_partition_diagram", "--repo", str(self.work),
                               "--json", json.dumps({"model": model}))
        self.assertEqual(rc, 0, env)
        # png is cairosvg-gated: either rendered or honestly omitted — never a crash
        self.assertIn("png_rendered", env["result"])

    def test_c03_partition_diagram_pptx_rejected_to_container(self):
        model = {"boards": [{"name": "main", "role": "host", "modules": []}], "interconnect": []}
        env, rc, _ = _run_gate("c03_emit_partition_diagram", "--repo", str(self.work),
                               "--json", json.dumps({"model": model, "emit_pptx": True}))
        self.assertNotEqual(rc, 0)
        self.assertEqual(env["error"]["code"], "VERB_ARGS_INVALID")
        self.assertIn("bodesign_c03_emit_partition_diagram", env["error"]["hint"])

    def test_pure_verbs_run_without_optional_deps(self):
        env, rc, _ = _run_gate("impedance_solve", "--repo", str(self.work),
                               "--json", json.dumps({
                                   "stackup": {"dielectric_height_mm": 0.18, "er": 4.2},
                                   "targets": {"se": 50}}))
        self.assertEqual(rc, 0, env)

        env, rc, _ = _run_gate("reference_crosscheck", "--repo", str(self.work),
                               "--json", json.dumps({
                                   "generated_nets": ["GND", "V3V3"],
                                   "reference_nets": ["GND", "V3V3", "VBUS"]}))
        self.assertEqual(rc, 0, env)
        self.assertEqual(env["result"]["missing"], ["VBUS"])


if __name__ == "__main__":
    unittest.main()
