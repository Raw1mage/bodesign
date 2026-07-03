"""Unit tests for bodesign_eda_bridge.ato_bridge (tasks 2.1-2.4 + 5.4).

subprocess is mocked throughout — no atopile install required.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bodesign_eda_bridge.ato_bridge import (
    AtoBuildResult,
    ComponentWrapperMissing,
    Deficiency,
    build_constraint_evidence,
    generate_component_wrapper,
    parse_ato_errors,
    run_ato_build,
    to_validation_evidence,
)


class TestDeficiency(unittest.TestCase):
    def test_valid_kinds(self):
        for kind in ("compile_error", "unsat_constraint", "pick_failure",
                     "component_wrapper_missing", "toolchain_missing", "worker_unavailable"):
            d = Deficiency(kind=kind, detail="x")
            self.assertEqual(d.to_dict()["kind"], kind)

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            Deficiency(kind="oops", detail="x")

    def test_anchor_serialization(self):
        d = Deficiency(kind="compile_error", detail="x", source_anchor="main.ato:3")
        self.assertEqual(d.to_dict()["source_anchor"], "main.ato:3")
        self.assertNotIn("source_anchor", Deficiency(kind="compile_error", detail="x").to_dict())


class TestAtoBuildResultInvariant(unittest.TestCase):
    def test_ok_false_requires_deficiencies(self):
        # errors.md principle 3: ok=False + empty list is a bridge defect.
        with self.assertRaises(ValueError):
            AtoBuildResult(ok=False)

    def test_ok_true_allows_empty(self):
        r = AtoBuildResult(ok=True, pcb_path="/tmp/x.kicad_pcb")
        self.assertTrue(r.to_dict()["ok"])


class TestParseAtoErrors(unittest.TestCase):
    def test_compile_error_with_anchor(self):
        log = "ERROR: undefined name 'Resistr' at main.ato:12:5"
        out = parse_ato_errors(log)
        self.assertEqual(out[0].kind, "compile_error")
        self.assertEqual(out[0].source_anchor, "main.ato:12:5")

    def test_unsat_constraint(self):
        log = "ERROR: assertion r.resistance > 20kohm cannot be satisfied (main.ato:7)"
        out = parse_ato_errors(log)
        self.assertEqual(out[0].kind, "unsat_constraint")
        self.assertEqual(out[0].source_anchor, "main.ato:7")

    def test_pick_failure(self):
        log = "ERROR: could not pick a part for C1: no matching component in range"
        out = parse_ato_errors(log)
        self.assertEqual(out[0].kind, "pick_failure")

    def test_multiple_errors_reported_at_once(self):
        # errors.md principle 1: all deficiencies in one pass.
        log = (
            "ERROR: syntax error at main.ato:2\n"
            "some info line\n"
            "ERROR: could not pick a part for R1\n"
            "ERROR: assertion never true at sub.ato:9\n"
        )
        kinds = [d.kind for d in parse_ato_errors(log)]
        self.assertEqual(kinds, ["compile_error", "pick_failure", "unsat_constraint"])

    def test_unparsed_fallback_never_empty(self):
        # errors.md principle 3 backstop.
        out = parse_ato_errors("something exploded in an unrecognizable way")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].kind, "compile_error")
        self.assertIn("unparsed build failure", out[0].detail)

    def test_duplicate_lines_deduped(self):
        log = "ERROR: boom at a.ato:1\nERROR: boom at a.ato:1\n"
        self.assertEqual(len(parse_ato_errors(log)), 1)


class TestBuildConstraintEvidence(unittest.TestCase):
    PICK = {"designator": "R1", "source": "vault", "spec_interval": "9.9kohm..10.1kohm",
            "rated_interval": "9.95kohm..10.05kohm", "mpn": "RC0603FR-0710KL"}

    def test_valid_evidence(self):
        ev = build_constraint_evidence(3, "sat", [self.PICK], "atopile 0.12.5")
        self.assertEqual(ev["constraints_checked"], 3)
        self.assertEqual(ev["solver_verdict"], "sat")
        self.assertEqual(ev["picks"][0]["mpn"], "RC0603FR-0710KL")
        self.assertEqual(ev["atopile_version"], "atopile 0.12.5")

    def test_bad_verdict_rejected(self):
        with self.assertRaises(ValueError):
            build_constraint_evidence(1, "maybe", [], "x")

    def test_pick_missing_fields_rejected(self):
        with self.assertRaises(ValueError):
            build_constraint_evidence(1, "sat", [{"designator": "R1"}], "x")

    def test_pick_bad_source_rejected(self):
        bad = dict(self.PICK, source="guessed")
        with self.assertRaises(ValueError):
            build_constraint_evidence(1, "sat", [bad], "x")

    def test_negative_constraints_rejected(self):
        with self.assertRaises(ValueError):
            build_constraint_evidence(-1, "sat", [], "x")

    def test_to_validation_evidence_shape(self):
        ev = build_constraint_evidence(2, "sat", [], "atopile 0.12.5")
        env = to_validation_evidence(ev)
        self.assertEqual(env["oracle"], "constraint_solve")
        self.assertEqual(env["verdict"], "pass")
        env_fail = to_validation_evidence(build_constraint_evidence(2, "unsat", [], "x"))
        self.assertEqual(env_fail["verdict"], "fail")


class TestGenerateComponentWrapper(unittest.TestCase):
    ENTRY = {"name": "R_10k_0603", "value": "10kohm", "tolerance": "1%",
             "package": "R0603", "mpn": "RC0603FR-0710KL"}

    def test_resistor_wrapper(self):
        text = generate_component_wrapper("Resistor", self.ENTRY)
        self.assertIn("component R_10k_0603 from Resistor:", text)
        self.assertIn("resistance = 10kohm +/- 1%", text)
        self.assertIn('mpn = "RC0603FR-0710KL"', text)

    def test_capacitor_and_inductor(self):
        cap = dict(self.ENTRY, name="C1", value="100nF")
        self.assertIn("capacitance = 100nF", generate_component_wrapper("Capacitor", cap))
        ind = dict(self.ENTRY, name="L1", value="10uH")
        self.assertIn("inductance = 10uH", generate_component_wrapper("Inductor", ind))

    def test_unknown_class_raises_named_exception(self):
        with self.assertRaises(ComponentWrapperMissing) as ctx:
            generate_component_wrapper("SomeExoticFpga", self.ENTRY)
        self.assertIn("SomeExoticFpga", str(ctx.exception))

    def test_incomplete_vault_entry_rejected(self):
        with self.assertRaises(ValueError):
            generate_component_wrapper("Resistor", {"name": "R1", "value": "10kohm"})


def _make_project(tmp: str) -> Path:
    project = Path(tmp) / "proj"
    project.mkdir()
    (project / "ato.yaml").write_text("builds:\n  default:\n    entry: main.ato:App\n")
    (project / "main.ato").write_text("module App:\n    assert 1kohm < 2kohm\n")
    return project


class TestRunAtoBuild(unittest.TestCase):
    def test_bad_component_source_rejected(self):
        with self.assertRaises(ValueError):
            run_ato_build("/nonexistent", component_source="auto")

    def test_missing_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_ato_build(str(Path(tmp) / "nope"))
        self.assertFalse(r.ok)
        self.assertEqual(r.deficiencies[0].kind, "compile_error")
        self.assertIn("ato.yaml", r.deficiencies[0].detail)

    def test_workspace_escape_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            with tempfile.TemporaryDirectory() as other_ws:
                r = run_ato_build(str(project), workspace_root=other_ws)
        self.assertFalse(r.ok)
        self.assertIn("escapes workspace root", r.deficiencies[0].detail)

    def test_toolchain_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            with mock.patch("bodesign_eda_bridge.ato_bridge.shutil.which", return_value=None):
                r = run_ato_build(str(project))
        self.assertFalse(r.ok)
        self.assertEqual(r.deficiencies[0].kind, "toolchain_missing")

    def test_failed_build_parses_log_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            proc = mock.Mock(returncode=1, stdout="", stderr="ERROR: assertion cannot be satisfied at main.ato:2")
            with mock.patch("bodesign_eda_bridge.ato_bridge.shutil.which", return_value="/usr/bin/ato"), \
                 mock.patch("bodesign_eda_bridge.ato_bridge.subprocess.run", return_value=proc):
                r = run_ato_build(str(project))
            self.assertFalse(r.ok)
            self.assertEqual(r.deficiencies[0].kind, "unsat_constraint")
            self.assertTrue(Path(r.build_log_path).is_file())
            self.assertIn("cannot be satisfied", Path(r.build_log_path).read_text())

    def test_success_with_pcb_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            (project / "build").mkdir()
            (project / "build" / "default.kicad_pcb").write_text("(kicad_pcb)")
            proc = mock.Mock(returncode=0, stdout="Build complete", stderr="")
            with mock.patch("bodesign_eda_bridge.ato_bridge.shutil.which", return_value="/usr/bin/ato"), \
                 mock.patch("bodesign_eda_bridge.ato_bridge.subprocess.run", return_value=proc), \
                 mock.patch("bodesign_eda_bridge.ato_bridge.get_atopile_version", return_value="atopile 0.12.5"):
                r = run_ato_build(str(project))
            self.assertTrue(r.ok)
            self.assertTrue(r.pcb_path.endswith("default.kicad_pcb"))
            self.assertEqual(r.evidence["solver_verdict"], "sat")
            self.assertEqual(r.evidence["constraints_checked"], 1)
            self.assertEqual(r.evidence["atopile_version"], "atopile 0.12.5")

    def test_success_without_pcb_is_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            proc = mock.Mock(returncode=0, stdout="done", stderr="")
            with mock.patch("bodesign_eda_bridge.ato_bridge.shutil.which", return_value="/usr/bin/ato"), \
                 mock.patch("bodesign_eda_bridge.ato_bridge.subprocess.run", return_value=proc):
                r = run_ato_build(str(project))
            self.assertFalse(r.ok)
            self.assertIn("no .kicad_pcb artifact", r.deficiencies[0].detail)

    def test_timeout_no_retry(self):
        import subprocess as sp
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project(tmp)
            with mock.patch("bodesign_eda_bridge.ato_bridge.shutil.which", return_value="/usr/bin/ato"), \
                 mock.patch("bodesign_eda_bridge.ato_bridge.subprocess.run",
                            side_effect=sp.TimeoutExpired(cmd=["ato"], timeout=1, output="partial", stderr="")) as m:
                r = run_ato_build(str(project), timeout_s=1)
            self.assertFalse(r.ok)
            self.assertIn("timed out", r.deficiencies[0].detail)
            self.assertEqual(m.call_count, 1)  # errors.md #4: exactly one attempt


# ── real atopile 0.12.5 log samples (in-container calibration, 2026-07-03) ──
# Captured from actual `ato build` runs in bodesign-ee (TV-2/TV-3/TV-4/import).
# These lock the parser to the REAL rich-formatted block output.

_REAL_TV2_UNSAT = """\
[02:31:10] INFO     Building 'default'
                    ✗ Picking parts 0/1 [0.0s]
           ERROR    Pick Error
                    Contradiction: Intersection of literals is empty

                    Origins:
                     - E{S|()}
                       - r.resistance ohm{S|[10kΩ ± 1.00%]}

                    Literals:
                     - ([0, ∞])
                     - ([10000 ± 1.00%])
                     - ([20000, ∞])


Unfortunately errors ^^^ stopped the build. If you need a hand jump on Discord!
"""

_REAL_TV3_PICK = """\
[02:31:25] ERROR    Pick Error
                    No matching component found for c
                    - `package`: `[BackendPackage.C0402]`
                    - `qty`: `1`
                    - `endpoint`: "capacitors"
                    - `capacitance`: `([123.455µF, 123.457µF])`
                    - `max_voltage`: **unconstrained**

Unfortunately errors ^^^ stopped the build. If you need a hand jump on Discord!
"""

_REAL_TV4_UNIT = """\
           ERROR    Incompatible Unit Error
                    Given units (microfarad) are incompatible with existing
                    units (ohm).
                    Source: main.ato:5:7
                      4
                    ❱ 5 module App:
                      6 │   r = new Resistor
                    Code causing the error:
                    Source: main.ato:7:4
                      6 │   r = new Resistor
                    ❱ 7 │   r.resistance = 10uF
                      8 │   r.package = "R0402"

Unfortunately errors ^^^ stopped the build. If you need a hand jump on Discord!
"""

_REAL_IMPORT_ERR = """\
           ERROR    Exception
                    Build failed
           ERROR    File Not Found Error
                    Unable to resolve import `generics/resistors.ato`
                    Code causing the error:
                    Source: main.ato:3
                      2
                    ❱ 3 import Resistor from "generics/resistors.ato"
                      4

Unfortunately errors ^^^ stopped the build. If you need a hand jump on Discord!
"""


class TestParseRealAtopile0125Logs(unittest.TestCase):
    """Regression lock on real atopile 0.12.5 diagnostics (TV-2/3/4 + import)."""

    def test_tv2_always_false_assert_is_unsat(self):
        out = parse_ato_errors(_REAL_TV2_UNSAT)
        self.assertEqual([d.kind for d in out], ["unsat_constraint"])
        self.assertIn("Contradiction", out[0].detail)

    def test_tv3_exotic_spec_is_pick_failure(self):
        out = parse_ato_errors(_REAL_TV3_PICK)
        self.assertEqual([d.kind for d in out], ["pick_failure"])
        self.assertIn("No matching component found", out[0].detail)

    def test_tv4_unit_error_is_compile_error_with_culprit_anchor(self):
        out = parse_ato_errors(_REAL_TV4_UNIT)
        self.assertEqual([d.kind for d in out], ["compile_error"])
        # anchor = last Source: in the block (the culprit line, not the module)
        self.assertEqual(out[0].source_anchor, "main.ato:7:4")
        self.assertIn("Incompatible Unit Error", out[0].detail)

    def test_import_error_two_blocks_both_compile(self):
        out = parse_ato_errors(_REAL_IMPORT_ERR)
        self.assertEqual([d.kind for d in out], ["compile_error", "compile_error"])
        self.assertEqual(out[1].source_anchor, "main.ato:3")
        self.assertIn("Unable to resolve import", out[1].detail)

    def test_footer_noise_not_an_error(self):
        out = parse_ato_errors(
            "Unfortunately errors ^^^ stopped the build. If you need a hand jump on Discord!")
        # footer alone -> unparsed fallback, not a bogus classified entry
        self.assertEqual(len(out), 1)
        self.assertIn("unparsed build failure", out[0].detail)



_REAL_OFFLINE_UNCAUGHT = """\
                    ✗ Picking parts 0/2 [0.1s]
           ERROR    Uncaught compiler exception
                    ╭─────────── Traceback (most recent call last) ────────────╮
                    │ /root/.local/share/uv/tools/atopile/lib/python3.13/site- │
                    │ packages/httpx/_transports/default.py:101 in             │
                    │ map_httpcore_exceptions                                  │
                    │   100 │   try:                                           │
                    │   224 │   │   else:                                      │
                    ╰──────────────────────────────────────────────────────────╯
                    AttributeError: 'str' object has no attribute '__cause__'

Unfortunately errors ^^^ stopped the build. If you need a hand jump on Discord!
"""


class TestParseOfflineUncaughtException(unittest.TestCase):
    """Registry-unreachable (offline) build: infra failure, NOT unsat/pick."""

    def test_offline_uncaught_is_compile_error(self):
        out = parse_ato_errors(_REAL_OFFLINE_UNCAUGHT)
        self.assertEqual([d.kind for d in out], ["compile_error"])
        self.assertIn("Uncaught compiler exception", out[0].detail)



if __name__ == "__main__":
    unittest.main()
