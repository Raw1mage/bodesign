"""WP6 readability form gate — tasks 6.6 / 6.7 controls plus the codomain arms.

Every test states the question it answers. The two load-bearing ones:

  6.6 POSITIVE CONTROL — does the gate pass a genuinely readable drawing, and
      does it keep disclaiming even then?
  6.7 NEGATIVE CONTROL — does the gate PASS the BR_20260905 §8.5.2
      power-clustering fixture, whose form numbers are all excellent while its
      fidelity `moved` is 67 including an open circuit? A threshold that turned
      that fixture red would be a form gate delivering an electrical verdict,
      which DD-07 forbids. This control fails if the gate ever blocks on it.

Scope honesty: the §8.5.2 negative control replays the FROZEN NUMBERS recorded in
test-vectors.json TV-9, not a live power-clustering compose. The clustering path
is gated by an emitter constant that this work package did not exercise, so a
real compose of that variant was NOT run here.
"""

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_eda_bridge.readability_gate import (
    DOES_NOT_AUTHORIZE,
    GATE_AXIS,
    MAX_STUB_SHARE,
    MIN_JUNCTIONS,
    MIN_SUBCIRCUIT_RATIO,
    NOT_SCORED,
    SCORED_SUBJECTS,
    SUBJECT_FROZEN_STATS,
    SUBJECT_LIVE_COMPOSE,
    SUBJECT_ON_DISK,
    ScoredSubjectError,
    compute_n,
    readability_gate,
)


def _stats(**over):
    """A route_stats dict carrying the task-6.0 fields. Overridable per test."""
    base = {
        "wired_nets": 11,
        "labelled_nets": 16,
        "junctions": 6,
        "label_fallback_reasons": [],
        "fanout_proxy": 7,
        "stub_share": 0.715517,
        "drawn_subcircuits": 4,
    }
    base.update(over)
    return base


class _FakeEmit:
    """Stands in for SchematicEmitResult. Carries the task-6.0 fields by default."""

    def __init__(self, *, task_6_0=True):
        if task_6_0:
            self.wire_runs = []
            self.junctions_emitted = 0


class DisclaimerAlwaysPresentTests(unittest.TestCase):
    """DD-07 / task 6.5: does_not_authorize is a FIELD, in EVERY status."""

    def test_present_in_every_reachable_status(self):
        cases = {
            "not-run": readability_gate(None, n=18),
            "not-run-missing-field": readability_gate(
                {k: v for k, v in _stats().items() if k != "stub_share"}, n=18),
            "empty-zero-nets": readability_gate(
                _stats(wired_nets=0, labelled_nets=0), n=18),
            "empty-zero-N": readability_gate(_stats(), n=0),
            "failed": readability_gate(_stats(), n=18),
            "ok": readability_gate(
                _stats(junctions=43, stub_share=0.327, drawn_subcircuits=11), n=18),
            "indeterminate": readability_gate(
                _stats(), n=18, emit=_FakeEmit(task_6_0=False)),
        }
        for label, report in cases.items():
            with self.subTest(case=label):
                self.assertEqual(GATE_AXIS, report["gate_axis"])
                self.assertEqual(DOES_NOT_AUTHORIZE, report["does_not_authorize"])
                self.assertIn("electrical_correctness", report["does_not_authorize"])
        # the statuses really are distinct -- otherwise the loop above proves
        # only that one shape carries the field
        self.assertEqual(
            {"not-run", "empty", "failed", "ok", "indeterminate"},
            {r["status"] for r in cases.values()})

    def test_disclaimer_is_a_copy_not_the_shared_constant(self):
        # a consumer mutating one report must not strip the disclaimer globally
        report = readability_gate(_stats(), n=18)
        report["does_not_authorize"].clear()
        self.assertEqual(["electrical_correctness", "fidelity"], DOES_NOT_AUTHORIZE)
        self.assertIn("electrical_correctness",
                      readability_gate(_stats(), n=18)["does_not_authorize"])


class PositiveControlTests(unittest.TestCase):
    """Task 6.6: a genuinely readable drawing passes, and still disclaims."""

    def test_readable_drawing_passes_on_form_axis(self):
        report = readability_gate(
            _stats(junctions=43, stub_share=0.20, drawn_subcircuits=12), n=18)
        self.assertEqual("ok", report["status"])
        self.assertEqual([], report["unmet"])
        self.assertEqual(DOES_NOT_AUTHORIZE, report["does_not_authorize"])

    def test_the_pass_is_not_unconditional(self):
        # NEGATIVE CONTROL for the test above: if the gate cannot fail, the pass
        # proves nothing. Degrade each criterion in turn; each must show up.
        for field, bad, name in (
            ("junctions", MIN_JUNCTIONS, "junctions"),
            ("stub_share", MAX_STUB_SHARE + 0.1, "stub_share"),
            ("drawn_subcircuits", 0, "subcircuit_ratio"),
        ):
            with self.subTest(criterion=name):
                good = {"junctions": 43, "stub_share": 0.20, "drawn_subcircuits": 12}
                good[field] = bad
                report = readability_gate(_stats(**good), n=18)
                self.assertEqual("failed", report["status"])
                self.assertIn(name, [u["criterion"] for u in report["unmet"]])


class Br20260905PowerClusteringNegativeControlTests(unittest.TestCase):
    """Task 6.7 — the false-green counterexample.

    BR_20260905 §8.5.2: junction 43, stub 32.7%, 11 subcircuits, every form
    threshold met, while fidelity `moved` went 10 -> 67 including an open
    circuit. The form gate must PASS this and must still disclaim, so that a
    consumer reading the form verdict alone cannot conclude the circuit is
    correct. If this ever goes red, the form gate has started asserting an
    electrical verdict (DD-07 violation).

    Frozen numbers from plans/.../test-vectors.json TV-9; not a live compose.
    """

    TV9 = {"junctions": 43, "stub_share": 0.327, "drawn_subcircuits": 11}

    def test_form_gate_passes_the_open_circuit_fixture(self):
        report = readability_gate(_stats(**self.TV9), n=18)
        self.assertEqual(
            "ok", report["status"],
            "a threshold that reds TV-9 is the form gate issuing an electrical "
            "verdict; DD-07 forbids it")
        self.assertEqual([], report["unmet"])

    def test_and_still_refuses_to_authorize_the_circuit(self):
        report = readability_gate(_stats(**self.TV9), n=18)
        self.assertIn("electrical_correctness", report["does_not_authorize"])
        self.assertIn("fidelity", report["does_not_authorize"])
        self.assertNotIn("fidelity_ok", report)
        self.assertNotIn("electrically_correct", report)

    def test_tv10_head_baseline_fails(self):
        # TV-10: the label-farm state the package exists to make visible.
        report = readability_gate(
            _stats(junctions=5, stub_share=0.730, drawn_subcircuits=3), n=18)
        self.assertEqual("failed", report["status"])
        self.assertEqual(DOES_NOT_AUTHORIZE, report["does_not_authorize"])
        self.assertTrue(report["unmet"])


class LabelFarmVersusFragmentationTests(unittest.TestCase):
    """Anti-control pair: a real label farm fails, and fragmentation raises the
    ratio. Same test, so the two cannot drift apart."""

    def test_label_farm_fails_and_fragmentation_improves_ratio(self):
        farm = readability_gate(
            _stats(junctions=5, stub_share=0.730, drawn_subcircuits=3), n=18)
        fragmented = readability_gate(
            _stats(junctions=6, stub_share=0.7155, drawn_subcircuits=4), n=18)
        self.assertEqual("failed", farm["status"])
        self.assertGreater(fragmented["subcircuit_ratio"], farm["subcircuit_ratio"])
        # both still fail the pinned threshold -- fragmentation was measured as
        # "effect small but clean" (BR §8.5.3), not as a fix
        self.assertEqual("failed", fragmented["status"])


class AbsenceIsNeverAPassTests(unittest.TestCase):
    """Absent input and failed thresholds must not share an output."""

    def test_no_route_stats_is_not_run(self):
        report = readability_gate(None, n=18)
        self.assertEqual("not-run", report["status"])
        self.assertNotEqual("ok", report["status"])

    def test_missing_task_6_0_field_names_it(self):
        for field in ("stub_share", "drawn_subcircuits"):
            with self.subTest(missing=field):
                stats = {k: v for k, v in _stats().items() if k != field}
                report = readability_gate(stats, n=18)
                self.assertEqual("not-run", report["status"])
                self.assertEqual([field], report["missing_fields"])

    def test_missing_field_is_not_read_as_zero(self):
        # a defaulted 0 would score as "no stubs" and could PASS the stub
        # criterion. It must be not-run instead.
        stats = {k: v for k, v in _stats(junctions=43, drawn_subcircuits=11).items()
                 if k != "stub_share"}
        report = readability_gate(stats, n=18)
        self.assertEqual("not-run", report["status"])

    def test_stub_share_none_is_not_scored_as_zero(self):
        # None means no run was measurable; 0.0 means runs existed and none was
        # short. The first must not silently satisfy "< 40%".
        report = readability_gate(
            _stats(junctions=43, stub_share=None, drawn_subcircuits=11), n=18)
        self.assertIn("stub_share_note", report)
        self.assertNotIn("stub_share", [u["criterion"] for u in report["unmet"]])

    def test_caller_must_supply_a_denominator(self):
        with self.assertRaises(ValueError):
            readability_gate(_stats())


class DenominatorTests(unittest.TestCase):
    """DD-09: N is spec-derived, and is reported beside the ratio."""

    SPEC = {"nets": [
        {"name": "SW_NODE", "nodes": ["U1.3", "U1.4", "L1.1"]},      # has L  -> in
        {"name": "ISET1", "nodes": ["U1.11", "R3.1"]},               # has R  -> in
        {"name": "GND", "nodes": ["C1.2", "R1.2"]},                  # power  -> out
        {"name": "+3V3", "nodes": ["C10.1", "R8.1"]},                # power  -> out
        {"name": "SWCLK", "nodes": ["U2.D1", "J3.1"]},               # no RCL -> out
        {"name": "BIG", "nodes": [f"R9.{i}" for i in range(7)]},     # 7 nodes-> out
        {"name": "DECL", "kind": "power", "nodes": ["R1.1", "R2.1"]},  # declared
    ]}

    def test_n_counts_only_eligible_nets(self):
        self.assertEqual(2, compute_n(self.SPEC))

    def test_n_is_reported_beside_the_ratio(self):
        # a low ratio and a small denominator must be distinguishable
        report = readability_gate(_stats(drawn_subcircuits=1), n=20)
        self.assertEqual(20, report["N"])
        self.assertEqual(round(1 / 20, 6), report["subcircuit_ratio"])

    def test_zero_denominator_is_empty_not_a_verdict(self):
        report = readability_gate(_stats(), n=0)
        self.assertEqual("empty", report["status"])
        self.assertIsNone(report["subcircuit_ratio"])

    def test_compute_n_control_empty_spec(self):
        self.assertEqual(0, compute_n({"nets": []}))
        self.assertEqual(0, compute_n({}))


class IndeterminateArmTests(unittest.TestCase):
    """DD-11: the arm asks whether the emitter carried the task-6.0 emissions."""

    def test_old_emitter_with_wired_nets_is_indeterminate(self):
        report = readability_gate(_stats(), n=18, emit=_FakeEmit(task_6_0=False))
        self.assertEqual("indeterminate", report["status"])
        self.assertEqual(["wire_runs", "junctions_emitted"],
                         report["missing_emitter_fields"])

    def test_current_emitter_is_not_indeterminate(self):
        # CONTROL: the arm must be able to come back clean, or it is not a check
        report = readability_gate(_stats(), n=18, emit=_FakeEmit(task_6_0=True))
        self.assertNotEqual("indeterminate", report["status"])

    def test_no_emit_supplied_does_not_fabricate_indeterminate(self):
        report = readability_gate(_stats(), n=18)
        self.assertNotEqual("indeterminate", report["status"])


class AntiFusionCriterionTests(unittest.TestCase):
    """BR §7 criterion 3: zero downgrades, or each keeps a drawn fragment."""

    def test_downgrade_without_fragment_is_unmet(self):
        report = readability_gate(
            _stats(junctions=43, stub_share=0.2, drawn_subcircuits=12,
                   label_fallback_reasons=[{"net": "CHG_LED_A", "reason": "anti-fusion"}]),
            n=18)
        self.assertEqual("failed", report["status"])
        self.assertIn("antifusion_downgrades", [u["criterion"] for u in report["unmet"]])

    def test_downgrade_with_fragment_is_met(self):
        report = readability_gate(
            _stats(junctions=43, stub_share=0.2, drawn_subcircuits=12,
                   label_fallback_reasons=[
                       {"net": "VBAT_SENSE", "reason": "anti-fusion",
                        "drawn_fragments": 1}]),
            n=18)
        self.assertEqual("ok", report["status"])

    def test_forced_label_reason_is_not_a_downgrade(self):
        report = readability_gate(
            _stats(junctions=43, stub_share=0.2, drawn_subcircuits=12,
                   label_fallback_reasons=[{"net": "VBUS", "reason": "power-rail"}]),
            n=18)
        self.assertEqual("ok", report["status"])
        self.assertEqual(0, report["antifusion_downgrades"])


SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
HAS_SYMBOLS = (SYMBOL_DIR / "Device.kicad_sym").exists()
PRIVATE_BASE = (Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache"))
                / "bodesign-wp6-tests")

# Same 4-component divider tests/test_composer.py composes. Small on purpose: the
# acceptance corpus is the REAL board (task 6.3 / BR §8.5.5), and this spec is
# here only to prove the emission points FIRE, not to calibrate a threshold.
_LIVE_SPEC = {
    "components": [
        {"ref": "R1", "symbol": "Device:R", "value": "10k"},
        {"ref": "R2", "symbol": "Device:R", "value": "10k"},
        {"ref": "C1", "symbol": "Device:C", "value": "100nF"},
        {"ref": "J1", "symbol": "Connector:Conn_01x02_Pin", "value": "IN"},
    ],
    "nets": [
        {"name": "VIN", "nodes": ["J1.1", "R1.1"]},
        {"name": "MID", "nodes": ["R1.2", "R2.1", "C1.1"]},
        {"name": "GND", "nodes": ["J1.2", "R2.2", "C1.2"]},
    ],
}


@unittest.skipUnless(HAS_SYMBOLS, "KiCad symbol libraries not installed")
class LiveEmissionTests(unittest.TestCase):
    """Task 6.0 emission points, exercised through a REAL compose.

    Why this class exists, recorded because it is the finding rather than the
    plan: the fixture-driven tests above all stayed green under a mutation that
    replaced the `drawn_subcircuits` computation with the constant 0. They score
    the GATE, and the gate is fed hand-written dicts, so no assertion in them can
    see the emission point at all. Fixture coverage of a consumer is not coverage
    of the producer, and the two look identical from the pass count.

    Each assertion below fails under exactly one disabled emission:
      - `drawn_subcircuits` pinned to a live value  -> kills the constant-0 mutant
      - `len(wire_runs)` == the `(wire` count on disk -> kills the no-append mutant
      - `junctions_emitted` == the `(junction` count on disk -> kills DD-11 drift
    """

    @classmethod
    def setUpClass(cls):
        from bodesign_eda_bridge import compose_schematic

        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        cls._work = Path(tempfile.mkdtemp(prefix="wp6-live-", dir=PRIVATE_BASE))
        cls.result = compose_schematic(
            out_dir=str(cls._work), project_name="wp6_live", spec=_LIVE_SPEC,
            symbol_dirs=SYMBOL_DIR, style="draftsman", validate=False, fidelity=False)
        cls.text = Path(cls.result.emit.schematic_path).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._work, ignore_errors=True)

    def test_wire_runs_mirrors_what_was_written(self):
        # DD-10: the count must equal the emitted file's, because the point of
        # emitting it is to avoid a second parser that could drift from it.
        disk = len(re.findall(r"\(wire\s", self.text))
        self.assertEqual(disk, len(self.result.emit.wire_runs))
        self.assertGreater(disk, 0, "control: wires WERE drawn, so 0 would be a defect "
                                    "and not an empty corpus")

    def test_junctions_emitted_mirrors_what_was_written(self):
        disk = len(re.findall(r"\(junction\s", self.text))
        self.assertEqual(disk, self.result.emit.junctions_emitted)

    def test_stub_share_is_measured_not_defaulted(self):
        stats = self.result.route_stats.to_dict()
        self.assertIsNotNone(stats["stub_share"])
        runs = self.result.emit.wire_runs
        expected = round(sum(1 for r in runs if r["len_mm"] <= 5.2) / len(runs), 6)
        self.assertEqual(expected, stats["stub_share"])

    def test_drawn_subcircuits_is_computed_not_constant(self):
        # R1-R2-C1 are joined by the one net that stays wired -> exactly 1 group
        # spanning >=2 refs. A constant 0 (or a constant anything) fails here.
        self.assertEqual(1, self.result.route_stats.to_dict()["drawn_subcircuits"])

    def test_dd11_junctions_is_landed_count_and_proxy_retained(self):
        stats = self.result.route_stats.to_dict()
        self.assertEqual(self.result.emit.junctions_emitted, stats["junctions"])
        self.assertIn("fanout_proxy", stats)

    def test_gate_consumes_a_live_compose_end_to_end(self):
        report = readability_gate(self.result.route_stats, spec=_LIVE_SPEC,
                                  emit=self.result.emit)
        self.assertIn(report["status"], ("ok", "failed", "empty"))
        self.assertNotEqual("not-run", report["status"],
                            "a live compose carries both task-6.0 fields, so not-run "
                            "here would mean to_dict() lost one")
        self.assertEqual(DOES_NOT_AUTHORIZE, report["does_not_authorize"])


class ScoredSubjectTests(unittest.TestCase):
    """BR_20260906 §7 — which drawing did this report score?

    The defect: `ratio 0.2222 FAIL` on btdongle read as a verdict on the
    DELIVERED schematic while it scored a live compose. The two populations
    differ by an order of magnitude (delivered 426 wires / 56 junctions across 3
    sheets vs the scored 116 / 6, single sheet) and nothing in the report told
    them apart.
    """

    def test_field_present_in_every_reachable_status(self):
        # Question: can a report ever carry a verdict and no subject?
        # Same rationale as does_not_authorize (task 6.5): a key survives an
        # aggregator that drops a sentence.
        cases = {
            "not-run": readability_gate(None, n=18),
            "not-run-missing-field": readability_gate(
                {k: v for k, v in _stats().items() if k != "stub_share"}, n=18),
            "empty-zero-nets": readability_gate(
                _stats(wired_nets=0, labelled_nets=0), n=18),
            "empty-zero-N": readability_gate(_stats(), n=0),
            "failed": readability_gate(_stats(), n=18),
            "ok": readability_gate(
                _stats(junctions=43, stub_share=0.327, drawn_subcircuits=11), n=18),
            "indeterminate": readability_gate(
                _stats(), n=18, emit=_FakeEmit(task_6_0=False)),
        }
        for label, report in cases.items():
            with self.subTest(case=label):
                self.assertIn("scored_subject", report)
                self.assertIn(report["scored_subject"]["subject"], SCORED_SUBJECTS)
                # absent evidence must never reach a report as "" or {}
                self.assertTrue(report["scored_subject"]["source"])
                self.assertEqual(NOT_SCORED, report["not_scored"])
        # CONTROL: the statuses really are distinct, else the loop proves only
        # that ONE shape carries the field
        self.assertEqual(
            {"not-run", "empty", "failed", "ok", "indeterminate"},
            {r["status"] for r in cases.values()})

    def test_live_compose_and_frozen_replay_report_different_subjects(self):
        # Question: is the value DERIVED from what happened, or is it a constant?
        # This is the discriminating pair. If both arms said the same thing the
        # field would carry no information at all.
        spec = DenominatorTests.SPEC
        live = readability_gate(_stats(), spec=spec)
        frozen = readability_gate(_stats(), n=18)
        self.assertEqual(SUBJECT_LIVE_COMPOSE, live["scored_subject"]["subject"])
        self.assertEqual(SUBJECT_FROZEN_STATS, frozen["scored_subject"]["subject"])
        self.assertNotEqual(live["scored_subject"], frozen["scored_subject"])

    def test_emission_site_mutation_is_caught(self):
        # MUTATION TEST (dispatcher's J-2, and the gap recorded in
        # BR gate_unit_fixtures_blind_to_emission_site_mutation): pin the
        # producer's subject to a CONSTANT and this must go red. A suite that
        # only asserts "the key exists" would stay green under exactly that
        # mutation, which is how the field would rot into a decoration.
        spec = DenominatorTests.SPEC
        subjects = {
            readability_gate(_stats(), spec=spec)["scored_subject"]["subject"],
            readability_gate(_stats(), n=18)["scored_subject"]["subject"],
        }
        self.assertEqual(2, len(subjects),
                         "both arms reported the same subject: the emission site "
                         "has been replaced by a constant, so the field no longer "
                         "says which drawing was scored")

    def test_source_is_derived_from_the_spec_that_was_scored(self):
        # Question: can the source disagree with what was actually scored?
        report = readability_gate(_stats(), spec={**DenominatorTests.SPEC,
                                                 "source": "/x/y/design.py"})
        self.assertEqual("source", report["scored_subject"]["source"]["from_spec"])
        self.assertEqual("/x/y/design.py", report["scored_subject"]["source"]["value"])

    def test_unnamed_spec_yields_a_positive_statement_not_an_empty_string(self):
        # "no source was supplied" and "the source is empty" must not share an
        # output. An unnamed spec still gets a POSITIVE description + its shape.
        report = readability_gate(_stats(), spec=DenominatorTests.SPEC)
        source = report["scored_subject"]["source"]
        self.assertIsNone(source["from_spec"])
        self.assertTrue(source["value"])
        self.assertIn("nets", source["shape"])

    def test_unknown_subject_is_refused_not_coerced(self):
        with self.assertRaises(ScoredSubjectError):
            readability_gate(_stats(), n=18, scored_subject="whatever-i-like",
                             subject_source={"x": 1})

    def test_explicitly_empty_evidence_is_refused(self):
        # fail fast rather than emitting "" — the field exists to be quoted
        for empty in ({}, "", []):
            with self.subTest(evidence=repr(empty)):
                with self.assertRaises(ScoredSubjectError):
                    readability_gate(_stats(), n=18,
                                     scored_subject=SUBJECT_LIVE_COMPOSE,
                                     subject_source=empty)

    def test_on_disk_is_reserved_and_structurally_unreachable(self):
        # Question: can this module CLAIM to have scored a delivered .kicad_sch?
        # It has no reader for one, so it must not be able to say it did. When a
        # disk entry point lands (BR §8), this test flips — deliberately, so the
        # capability and the claim cannot diverge silently.
        self.assertIn(SUBJECT_ON_DISK, SCORED_SUBJECTS)
        with self.assertRaises(ScoredSubjectError):
            readability_gate(_stats(), n=18, scored_subject=SUBJECT_ON_DISK,
                             subject_source={"path": "/real/board.kicad_sch",
                                             "sha256": "deadbeef"})

    def test_not_scored_names_the_delivered_schematic(self):
        # The BR's core reading defect: a `failed` verdict on one drawing read as
        # a verdict on another. The report must say what it did NOT look at.
        report = readability_gate(_stats(), n=18)
        blob = " ".join(report["not_scored"])
        self.assertIn("on-disk", blob)
        self.assertIn("not-run", blob)

    def test_measure_run_is_labelled_so_it_is_not_read_as_the_subject(self):
        # BR §3.3: measure_run and scored_subject have similar shapes and
        # opposite meanings, and measure_run carries a spec PATH that reads like
        # a subject. It must announce which one it is.
        report = readability_gate(_stats(), n=18)
        self.assertIn("scored_subject", report["measure_run"]["what"])
        self.assertNotEqual(report["measure_run"].get("spec"),
                            report["scored_subject"]["source"].get("value"))


_SERVER_PY = Path(__file__).parent.parent / "services" / "mcp" / "server.py"

# Parameters that deliberately do NOT cross the MCP facade, each with the reason.
# An exemption is only safe while it is self-invalidating: a test below asserts
# every key here still names a real parameter, so a rename or removal turns this
# dict red instead of leaving a stale excuse that quietly widens over time.
_FACADE_EXEMPT = {
    "emit": "a live compose-result OBJECT read by attribute (hasattr on "
            "wire_runs / junctions_emitted). It has no JSON form, so an MCP "
            "caller cannot supply it and its absence is not a coverage gap.",
}


class FacadeReachabilityTests(unittest.TestCase):
    """Can an MCP caller reach every scoring path this gate implements?

    WHY THIS EXISTS, and why it is not the skip reason round=8 asked for.
    The dispatch assumed the live-compose path was carried by a skipped test and
    asked for a skip reason naming the gap. Measured on this host: HAS_SYMBOLS is
    True, all six LiveEmissionTests execute (`live_ok=6 live_skipped=0`) and the
    module reports `skipped` zero times. There is no skip to annotate, and a skip
    reason nobody reaches is not a carrier. Worse, unittest prints skip reasons
    only at -v (measured with a marker probe: default 0 hits, -v 1 hit), so the
    stated audience -- someone reading `Ran N / skipped=52` -- would never see it.

    The gap that IS real and IS red-capable sits one layer over, and it is the
    same shape BR_20260906 is about: a path that exists in the function but not
    where the caller stands. `check_c03` already paid for this once -- netlist_path
    and covers_boards were added to the function and never to the facade, so R5/R6
    were unreachable for every MCP caller while the direct-call tests stayed green.
    This gate is now exposed on two planes, so it inherits that failure mode: when
    the `.kicad_sch` reader lands (BR_20260906 §8), it will add a parameter, and
    nothing but this class would notice it never reached the schema.

    Paired with test_on_disk_is_refused, which goes red the day that reader lands.
    That one says the capability is absent; this one says the door is wired.
    """

    def _params(self) -> list[str]:
        import inspect
        return [p for p in inspect.signature(readability_gate).parameters]

    def _facade(self) -> tuple[str, str]:
        """(schema_properties_fragment, handler_source) for bodesign_readability_gate."""
        src = _SERVER_PY.read_text(encoding="utf-8")
        i = src.find('"name": "bodesign_readability_gate"')
        self.assertNotEqual(i, -1, "bodesign_readability_gate is not registered")
        # Bound the entry at the NEXT tool rather than a magic byte count: a
        # fixed window is the fixed-line-window failure this round already hit
        # once -- it truncates silently and the truncation reads like absence.
        j = src.find('{"name": "bodesign_', i + 10)
        entry = src[i:j if j != -1 else len(src)]
        m = re.search(r'"schema":\s*\{"type": "object", "properties": \{(.*?)\},\s*"required"',
                      entry, re.S)
        self.assertIsNotNone(m, "could not locate the tool's schema properties")
        h_start = src.find("def _h_readability_gate")
        self.assertNotEqual(h_start, -1, "_h_readability_gate handler not found")
        h_end = src.find("\ndef ", h_start + 1)
        return m.group(1), src[h_start:h_end]

    def test_the_scans_actually_find_something(self):
        # Reverse discrimination for BOTH scans. If either returned empty, every
        # assertion below would pass vacuously forever -- a green row asserting
        # nothing, which is the one outcome worse than no row at all.
        params = self._params()
        self.assertIn("route_stats", params)
        self.assertIn("scored_subject", params)
        self.assertGreaterEqual(len(params), 5, f"suspiciously few params: {params}")
        props, handler = self._facade()
        self.assertIn("route_stats", props)
        self.assertIn("readability_gate(", handler)

    def test_every_parameter_is_declared_in_the_facade_schema(self):
        props, _ = self._facade()
        missing = [p for p in self._params()
                   if p not in _FACADE_EXEMPT and f'"{p}"' not in props]
        self.assertEqual(
            missing, [],
            f"readability_gate accepts {missing} but the MCP inputSchema does not "
            f"declare them -- an MCP caller cannot discover or pass them, so those "
            f"paths are unreachable through the facade exactly as check_c03's "
            f"netlist_path was. Declare them, or add a justified _FACADE_EXEMPT entry.")

    def test_every_parameter_is_forwarded_by_the_handler(self):
        # Declaring a parameter in the schema while the handler drops it is the
        # same defect with a friendlier face: discoverable, accepted, ignored.
        _, handler = self._facade()
        dropped = [p for p in self._params()
                   if p not in _FACADE_EXEMPT and f'"{p}"' not in handler]
        self.assertEqual(
            dropped, [],
            f"_h_readability_gate does not forward {dropped}; a caller supplying "
            f"them would be silently ignored and get the derived default instead.")

    def test_each_exemption_still_names_a_real_parameter(self):
        # Guards the exemption list itself. Without this, deleting `emit` would
        # leave a permanent licence to omit a name that no longer means anything,
        # and the list only ever grows.
        params = self._params()
        stale = [k for k in _FACADE_EXEMPT if k not in params]
        self.assertEqual(stale, [],
                         f"_FACADE_EXEMPT still excuses {stale}, which readability_gate "
                         f"no longer accepts -- a stale exemption is a silent widening.")


if __name__ == "__main__":
    unittest.main()
