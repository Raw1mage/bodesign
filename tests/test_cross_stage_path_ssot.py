"""Machine-check that each cross-stage file path has exactly ONE declaration.

BR_20260901e. A stage deliverable's path is an implicit contract between two
modules: the stage that WRITES it and the stage that READS it. When each side
spells the path with its own literal, nothing links them — so an edit to one
side leaves the other pointing at the old location, and the symptom is two
verbs that are each individually correct while disagreeing with each other
(C01 reports "emitted", C04 reports "upstream missing"). That is expensive
precisely because neither side raises.

Scope boundary vs its sibling module:

  tests/test_stage_prefix_invariant.py      -- WITHIN one stage: does every
      C0x_OUTPUTS value carry its own stage dirname, and do the two prefix
      models (constants vs `_c0x_stage_dir()`) agree?
  this module                               -- ACROSS stages: is the reader's
      path the SAME OBJECT as the writer's, rather than an equal-looking copy?

The distinction matters for what a failure means. A prefix-invariant failure
says one module became internally inconsistent. A failure here says two modules
stopped agreeing about a shared file, which no single module can detect.

Why identity (`is`) and not equality: today all these values are byte-identical,
so an equality assertion would pass whether or not the duplication was removed
-- it would pin the FACT "they happen to match today" instead of the CONTRACT
"there is only one of them". Identity is the assertion that has teeth. See
`NegativeControlTests` at the bottom: every pair below has a control proving
the predicate goes red for an independently-constructed equal value.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from bodesign_workflow_core import c00_orchestration
from bodesign_workflow_core import c01_id_package
from bodesign_workflow_core import c03_mechanical_constraints
from bodesign_workflow_core import c04_layout_constraints
from bodesign_workflow_core import mode_contracts
from bodesign_workflow_core import orchestration
from bodesign_workflow_core import upstream_constraints


class SingleDeclarationPerCrossStagePath(unittest.TestCase):
    """Q: is each reader's path the SAME OBJECT as the writer's declaration?

    `assertIs`, not `assertEqual`: two independently-built Paths comparing equal
    is exactly the pre-fix state this BR describes. Only identity distinguishes
    "derived from one declaration" from "spelled twice and currently matching".
    """

    def test_p1_c04_reads_the_path_c01_declares_for_constraints(self) -> None:
        """P1: C04's upstream expectation vs C01's emitter write position."""
        self.assertIs(
            c01_id_package.C01_OUTPUTS["constraints"],
            c04_layout_constraints._C01_CONSTRAINTS_REL,
            "C04 has its own literal for the C01 interface-constraints path again",
        )

    def test_p2_answer_state_has_one_declaration(self) -> None:
        """P2: the canonical C00 answer-state path, used by three modules."""
        owner = orchestration.C00_ANSWER_STATE_REL
        self.assertIs(owner, mode_contracts._C00_ANSWER_STATE_REL)
        self.assertIs(owner, c00_orchestration._C00_ANSWER_STATE_REL)

    def test_p3_legacy_answer_state_has_one_declaration(self) -> None:
        """P3: the legacy position, resolved when the canonical one is absent."""
        owner = orchestration.C00_ANSWER_STATE_REL_LEGACY
        self.assertIs(owner, mode_contracts._C00_ANSWER_STATE_REL_LEGACY)
        self.assertIs(owner, c00_orchestration._C00_ANSWER_STATE_REL_LEGACY)

    def test_p4_upstream_table_reuses_the_c03_emitter_constant(self) -> None:
        """P4: C04's required-upstream table vs C03's own export constant."""
        rel, _schema = upstream_constraints.UPSTREAM_FILES["mechanical"]
        self.assertIs(
            c03_mechanical_constraints.C03_OUTPUT,
            rel,
            "UPSTREAM_FILES['mechanical'] has its own literal again",
        )


class OutwardFacingStringsAreDerivedNotSpelled(unittest.TestCase):
    """Q: do the string-typed copies still derive from the Path declaration?

    These two are the ones a `Path("C0N-...")` scan cannot see, which is why
    BR_20260901e's own survey missed the first of them. They are also the more
    expensive half: both are handed OUTWARD (into a work packet, into a user's
    gap list) rather than used to open a local file, so a drift here produces a
    wrong path with no local read to fail on.
    """

    def test_p5_work_packet_answer_state_pointer_derives_from_the_path(self) -> None:
        """P5: `orchestration._DEFAULT_ANSWER_STATE` is what a work packet hands
        to a downstream agent. It must be the canonical path, rendered."""
        self.assertEqual(
            orchestration.C00_ANSWER_STATE_REL.as_posix(),
            orchestration._DEFAULT_ANSWER_STATE,
        )

    def test_p6_c03_gap_message_names_the_path_the_code_actually_checks(self) -> None:
        """P6: the "missing" gap text vs the constant the existence check uses.

        Before the fix these were two literals in the SAME file (`:176` used the
        constant, `:187` spelled it out). Changing the constant would have made
        the code look in the new place while telling the user to look in the old
        one -- two errors, neither of which raises.
        """
        with self.subTest(scenario="empty root, so every gap fires"):
            result = c04_layout_constraints._assess_upstream_fulfilment(
                Path("/nonexistent/product-root")
            )
        gaps = result["gaps"]
        self.assertTrue(gaps, "no gaps produced -- the check window was empty")
        expected = c03_mechanical_constraints.C03_OUTPUT.as_posix()
        matching = [g for g in gaps if g.startswith(f"{expected} missing")]
        self.assertEqual(
            1,
            len(matching),
            f"no gap message names {expected!r}; gaps were {gaps!r}",
        )


class NegativeControlTests(unittest.TestCase):
    """Prove every assertion above can FAIL. A check that cannot fail is a
    decoration, and a decoration is worse than nothing because it tells the next
    reader this ground is covered.

    Each control constructs an INDEPENDENT value that is byte-equal to the real
    one -- exactly what a re-introduced duplicate literal would look like -- and
    asserts the guard's own predicate rejects it. Equality-based guards would
    accept all of these, which is the whole reason the guards use identity.

    Everything is substituted inside this namespace. Nothing on disk is mutated:
    a same-second, same-length edit to a `.py` leaves a stale `.pyc` valid, the
    mutant is silently not applied, and the run then reports the REVERSE of the
    truth (AGENTS.md 6.3).
    """

    def test_control_p1_an_equal_but_separate_path_is_rejected(self) -> None:
        duplicate = Path("C01-ID") / "Interface_Constraints.json"
        real = c01_id_package.C01_OUTPUTS["constraints"]
        self.assertEqual(real, duplicate, "control is not byte-equal -- it tests nothing")
        self.assertIsNot(
            real,
            duplicate,
            "the identity predicate accepted an independently built equal Path",
        )

    def test_control_p2_an_equal_but_separate_answer_state_is_rejected(self) -> None:
        duplicate = Path("C00-PRD") / "03_output" / "answer_state.json"
        real = orchestration.C00_ANSWER_STATE_REL
        self.assertEqual(real, duplicate)
        self.assertIsNot(real, duplicate)

    def test_control_p3_an_equal_but_separate_legacy_path_is_rejected(self) -> None:
        duplicate = Path("C00-PRD") / "answer_state.json"
        real = orchestration.C00_ANSWER_STATE_REL_LEGACY
        self.assertEqual(real, duplicate)
        self.assertIsNot(real, duplicate)

    def test_control_p4_an_equal_but_separate_mechanical_path_is_rejected(self) -> None:
        duplicate = Path("C03-EE") / "Mechanical_Constraint_Export.json"
        real = c03_mechanical_constraints.C03_OUTPUT
        self.assertEqual(real, duplicate)
        self.assertIsNot(real, duplicate)

    def test_control_p5_a_drifted_pointer_string_is_rejected(self) -> None:
        """The P5 predicate is equality, so its control must show the equality
        actually discriminates: a plausibly-drifted spelling must not match."""
        drifted = "C00-PRD/answer_state.json"  # the legacy position
        self.assertNotEqual(
            orchestration.C00_ANSWER_STATE_REL.as_posix(),
            drifted,
            "the pointer comparison cannot tell the canonical path from the legacy one",
        )

    def test_control_p6_gap_scan_finds_nothing_for_a_path_never_emitted(self) -> None:
        """Reverse control for P6: the same scan, asked about a path no gap
        message names, must come back empty. Without this, a scan that matched
        everything (or a `gaps` list of unexpected shape) would still be green."""
        result = c04_layout_constraints._assess_upstream_fulfilment(
            Path("/nonexistent/product-root")
        )
        never = "C99-NEVER/Not_A_Deliverable.json"
        matching = [g for g in result["gaps"] if g.startswith(f"{never} missing")]
        self.assertEqual([], matching, "the gap scan matches paths that are not there")

    def test_control_p6_scan_is_sensitive_to_the_constant_it_reads(self) -> None:
        """And that the P6 assertion is bound to C03_OUTPUT rather than to a
        string that happens to be right: a mutated expectation must stop
        matching, proving the assertion reads the constant."""
        result = c04_layout_constraints._assess_upstream_fulfilment(
            Path("/nonexistent/product-root")
        )
        mutated = Path("C03-EE") / "Mechanical_Constraint_Export_RENAMED.json"
        matching = [
            g for g in result["gaps"] if g.startswith(f"{mutated.as_posix()} missing")
        ]
        self.assertEqual(
            [],
            matching,
            "gap text matches a renamed constant -- it is not derived from C03_OUTPUT",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
