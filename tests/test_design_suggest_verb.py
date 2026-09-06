"""WP5 — `bodesign_design_suggest`, the pin-class router.

plan c03_delivery_contract_and_engine_seams DD-02, errors.md §WP5.

The red line this verb must not cross (`concept.bodesign.netlist-synthesis-gap`):
it may SUGGEST, it may not DECIDE. DD-02 turns that sentence into four properties
a test can actually fail on:

  (1) `committed` is not in the status codomain — by construction, not convention
  (2) `review_required` is true on EVERY path, including the ones suggesting nothing
  (3) every suggested value carries an `evidence.kb_object` that REALLY EXISTS in
      ragbase — asserted against the database, not against string non-emptiness
  (4) a class with no KB anchor returns `no-rule` and no value, never a guess

The hardest property here is (3). A test that asserts `kb_object != ""` passes
for a fabricated id, which is precisely the failure it is supposed to catch, so
these tests resolve every id against `.specbase/ragbase.sqlite` and carry a
control row proving the lookup can come back empty.
"""
from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from bodesign_eda_bridge.design_suggest import (PIN_CLASSES, SUGGEST_STATUSES,
                                                DesignSuggestInputError,
                                                design_suggest)

REPO_ROOT = Path(__file__).resolve().parent.parent
RAGBASE_DB = REPO_ROOT / ".specbase" / "ragbase.sqlite"


def _kb_object_exists(object_id: str) -> bool:
    """Resolve an id against the real KB. Not a string check."""
    con = sqlite3.connect(f"file:{RAGBASE_DB}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT 1 FROM ragbase_objects WHERE id = ?",
                          (object_id,)).fetchone()
        return row is not None
    finally:
        con.close()


_POWER_CTX = {"power_pins": ["1", "12", "23", "34", "45"],
              "rail": "+3V3", "ref": "U1"}


class KbLookupHasDiscriminatingPowerTests(unittest.TestCase):
    """The control for property (3). Run FIRST in spirit: if this fails, every
    `kb_object` assertion below is vacuous."""

    def test_the_database_is_reachable_and_can_answer_no(self):
        self.assertTrue(RAGBASE_DB.is_file(), f"{RAGBASE_DB} missing")
        self.assertFalse(_kb_object_exists("zzz.this.id.cannot.exist"),
                         "the lookup returned true for a fabricated id — it is "
                         "not resolving anything and every assertion using it "
                         "would pass regardless of the value under test")
        self.assertTrue(_kb_object_exists("control.power.decoupling-pdn-strategy"),
                        "the lookup returned false for an id that IS in the KB — "
                        "a zero here would be a broken query, not an absent rule")


class Dd02Property1Tests(unittest.TestCase):
    """(1) `committed` is not a reachable status."""

    def test_committed_is_not_in_the_codomain(self):
        self.assertNotIn("committed", SUGGEST_STATUSES)
        self.assertEqual(set(SUGGEST_STATUSES),
                         {"suggested", "no-rule", "indeterminate"})

    def test_no_input_in_the_matrix_produces_a_status_outside_the_codomain(self):
        matrix = [
            ("power", _POWER_CTX),
            ("power", {"power_pins": []}),
            ("analog-reference", {"vref_pins": ["14"], "ref": "U3"}),
            ("ground", {"gnd_pins": ["10"]}),
            ("reset-en", {}),
            ("boot-strapping", {}),
            ("nc-dnc", {}),
            ("clock", {}),
            ("io-gpio", {}),
            ("high-speed", {}),
        ]
        for pin_class, ctx in matrix:
            with self.subTest(pin_class=pin_class, ctx=ctx):
                out = design_suggest(mpn="TEST", pin_class=pin_class, context=ctx)
                self.assertIn(out["status"], SUGGEST_STATUSES)
                self.assertNotEqual(out["status"], "committed")


class Dd02Property2Tests(unittest.TestCase):
    """(2) `review_required` is true everywhere — including empty answers.

    A flag that is only true when there is something to review would be exactly
    backwards: the paths that suggest nothing are the ones where a caller is most
    tempted to treat the output as settled.
    """

    def test_review_required_is_true_on_every_status(self):
        seen = {}
        for pin_class, ctx in (("power", _POWER_CTX),
                               ("power", {"power_pins": []}),
                               ("analog-reference", {"vref_pins": ["9"]}),
                               ("ground", {})):
            out = design_suggest(pin_class=pin_class, context=ctx)
            seen[out["status"]] = seen.get(out["status"], 0) + 1
            self.assertTrue(out["review_required"],
                            f"{pin_class}/{out['status']} did not require review")
        # The loop must actually have reached more than one status, or "true on
        # every status" is a claim about one status.
        self.assertGreaterEqual(len(seen), 3, f"statuses exercised: {seen}")


class Dd02Property3Tests(unittest.TestCase):
    """(3) every suggested value is anchored to a KB object that exists."""

    def test_every_power_suggestion_carries_a_resolvable_kb_object(self):
        out = design_suggest(mpn="STM32F4", pin_class="power", context=_POWER_CTX)
        self.assertEqual(out["status"], "suggested")
        self.assertTrue(out["suggestions"])
        for sug in out["suggestions"]:
            kb = sug["evidence"]["kb_object"]
            self.assertTrue(_kb_object_exists(kb),
                            f"{kb!r} is not in {RAGBASE_DB} — a value stamped "
                            "with an id that does not resolve is a fabrication "
                            "wearing an evidence block")
            self.assertIsNotNone(sug["component"]["value"])

    def test_no_suggestion_anywhere_carries_a_value_without_evidence(self):
        """The universal form of (3), across the whole class matrix."""
        for pin_class in PIN_CLASSES:
            ctx = {"power_pins": ["1", "2"], "vref_pins": ["3"]}
            with self.subTest(pin_class=pin_class):
                out = design_suggest(pin_class=pin_class, context=ctx)
                for sug in out.get("suggestions", []):
                    kb = sug.get("evidence", {}).get("kb_object")
                    self.assertTrue(kb, f"{pin_class}: value with no kb_object")
                    self.assertTrue(_kb_object_exists(kb),
                                    f"{pin_class}: kb_object {kb!r} unresolvable")


class Dd02Property4Tests(unittest.TestCase):
    """(4) NEGATIVE CONTROL (task 5.8) — an uncovered class must not produce a value.

    `ground` is fed a COMPLETE, plausible context on purpose. The rule is not
    "we lacked input"; it is "there is no KB rule", and the only way to show the
    verb honours that is to give it everything it would need if a rule existed.
    """

    def test_ground_returns_no_rule_even_with_a_complete_context(self):
        out = design_suggest(
            mpn="STM32F407", pin_class="ground",
            context={"gnd_pins": ["10", "19", "22", "50"], "ref": "U1",
                     "exposed_pad": True, "rail": "+3V3",
                     "thermal_via_pitch_mm": 1.0})
        self.assertEqual(out["status"], "no-rule")
        self.assertEqual(out["suggestions"], [])
        self.assertEqual(out["evidence"], {},
                         "the uncovered-class arm must carry NO evidence — a "
                         "populated block here would be indistinguishable from "
                         "the zero-subject arm")
        self.assertFalse(out["rule_matched"])
        self.assertTrue(out["review_required"])

    def test_all_four_uncovered_classes_return_no_rule(self):
        for pin_class in ("ground", "reset-en", "boot-strapping", "nc-dnc"):
            with self.subTest(pin_class=pin_class):
                out = design_suggest(pin_class=pin_class,
                                     context={"pins": ["1", "2", "3"]})
                self.assertEqual(out["status"], "no-rule")
                self.assertEqual(out["suggestions"], [])
                self.assertFalse(out["rule_matched"])


class NoRuleVersusNoRuleEmptyTests(unittest.TestCase):
    """The two `no-rule` outcomes must be TELLABLE APART, side by side.

    Both say `no-rule` with an empty suggestion list. They mean opposite things:
    one says the KB has no rule for this class, the other says a rule ran and the
    board has no such pin. A caller acting on the first writes a KB rule; on the
    second, nothing. Asserting them in one test is the point — separately, each
    passes without ever showing they differ.
    """

    def test_the_two_are_distinguished_by_the_evidence_block(self):
        uncovered = design_suggest(pin_class="ground", context={"gnd_pins": ["1"]})
        zero_subject = design_suggest(pin_class="power", context={"power_pins": []})

        self.assertEqual(uncovered["status"], zero_subject["status"], "no-rule")
        self.assertEqual(uncovered["suggestions"], zero_subject["suggestions"], [])

        # ... and here is the only thing that separates them:
        self.assertEqual(uncovered["evidence"], {})
        self.assertTrue(zero_subject["evidence"],
                        "the zero-subject arm must NAME the rule that found "
                        "nothing to do, or it is indistinguishable from a class "
                        "with no rule at all")
        self.assertTrue(_kb_object_exists(zero_subject["evidence"]["kb_object"]))
        self.assertFalse(uncovered["rule_matched"])
        self.assertTrue(zero_subject["rule_matched"])


class IndeterminateEmissionPointTests(unittest.TestCase):
    """`indeterminate` — the anchor states an obligation but carries no value.

    Measured, not assumed: `step.sch.mcu-adc-frontend-review` was read in full
    and its entire VREF content is one sentence naming the obligation. Suggesting
    the customary 100nF under that id would attach a real KB anchor to a number
    the object does not contain.
    """

    def test_analog_reference_is_indeterminate_and_names_the_obligation(self):
        out = design_suggest(mpn="STM32", pin_class="analog-reference",
                             context={"vref_pins": ["14"], "ref": "U3"})
        self.assertEqual(out["status"], "indeterminate")
        self.assertEqual(out["suggestions"], [])
        self.assertEqual(out["evidence"]["kb_object"],
                         "step.sch.mcu-adc-frontend-review")
        self.assertTrue(_kb_object_exists(out["evidence"]["kb_object"]))
        self.assertFalse(out["evidence"]["value_bearing"])
        self.assertIsNone(out["evidence"]["formula"])
        self.assertEqual(out["obligation"]["applies_to"], ["U3.14"])
        self.assertIn("filtering", out["obligation"]["statement"])
        self.assertTrue(out["review_required"])

    def test_indeterminate_is_distinct_from_no_rule(self):
        """REVERSE CONTROL: if every unanswerable class collapsed to `no-rule`,
        the caller could not tell "no rule exists" from "a rule exists and cannot
        give you a number" — different next actions."""
        aref = design_suggest(pin_class="analog-reference",
                              context={"vref_pins": ["1"]})
        ground = design_suggest(pin_class="ground", context={"gnd_pins": ["1"]})
        self.assertNotEqual(aref["status"], ground["status"])
        self.assertEqual(aref["status"], "indeterminate")
        self.assertEqual(ground["status"], "no-rule")


class InputInvalidIsNotAStatusTests(unittest.TestCase):
    """A malformed call is `ok:false`, never `no-rule`."""

    def test_missing_pin_list_raises_rather_than_answering_zero(self):
        with self.assertRaises(DesignSuggestInputError) as ctx:
            design_suggest(pin_class="power", context={"ref": "U1"})
        self.assertEqual(ctx.exception.code, "DESIGN_SUGGEST_INPUT_INVALID")

    def test_unknown_pin_class_raises(self):
        with self.assertRaises(DesignSuggestInputError) as ctx:
            design_suggest(pin_class="not-a-real-class", context={})
        self.assertEqual(ctx.exception.code, "DESIGN_SUGGEST_INPUT_INVALID")

    def test_missing_pin_class_raises(self):
        with self.assertRaises(DesignSuggestInputError):
            design_suggest(pin_class=None, context={})

    def test_an_absent_pin_list_and_an_empty_one_do_not_share_an_output(self):
        """The §9 rule at this seam: "you gave me no pins" and "this part has no
        such pins" are different facts and must not produce the same result."""
        empty = design_suggest(pin_class="power", context={"power_pins": []})
        self.assertEqual(empty["status"], "no-rule")
        with self.assertRaises(DesignSuggestInputError):
            design_suggest(pin_class="power", context={})


class DeterminismTests(unittest.TestCase):
    """Side-effect free and deterministic — the honesty contract of the module."""

    def test_the_caller_context_is_not_mutated(self):
        ctx = {"power_pins": ["1", "2", "3"], "rail": "+3V3"}
        before = dict(ctx)
        design_suggest(pin_class="power", context=ctx)
        self.assertEqual(ctx, before)

    def test_same_input_same_output(self):
        a = design_suggest(mpn="X", pin_class="power", context=dict(_POWER_CTX))
        b = design_suggest(mpn="X", pin_class="power", context=dict(_POWER_CTX))
        self.assertEqual(a, b)


class PowerCascadeArithmeticTests(unittest.TestCase):
    """The counts are the KB rule's, ceil'd — spot-checked at the boundaries."""

    def test_counts_follow_the_kb_ratios(self):
        for pins, want_pin_caps, want_bulk in ((1, 1, 1), (2, 1, 1), (3, 2, 1),
                                               (10, 5, 1), (11, 6, 2)):
            with self.subTest(pins=pins):
                out = design_suggest(
                    pin_class="power",
                    context={"power_pins": [str(i) for i in range(pins)]})
                self.assertEqual(out["computed"]["pin_caps"], want_pin_caps)
                self.assertEqual(out["computed"]["bulk_caps"], want_bulk)


if __name__ == "__main__":
    unittest.main()
