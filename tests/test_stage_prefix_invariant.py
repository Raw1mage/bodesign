"""Machine-check the stage-prefix claims made in the C01/C02 block comments.

BR_20260804h: the comment above ``C02_STAGE_DIRNAME`` used to claim the stage
prefix was derived "in ONE place" so "no two code paths can disagree". It was
false, and a false claim in a comment is worse than no comment because it makes
the reader stop looking for the second source of truth.

The comments are now factual (2026-09-01) and describe THREE roles the
``C0x_OUTPUTS`` values serve. This module turns the machine-checkable half of
those comments into assertions, so a claim that stops being true fails here
instead of silently misleading the next reader.

Question each test answers is written beside it. Every assertion below is one a
deliberate edit can break: see ``NegativeControlTests`` at the bottom, which
proves the guards actually go red rather than being permanently-green scenery.

Scope: WITHIN one stage. The ACROSS-stage question -- is a reader's path the same
object as the writer's declaration, or an equal-looking copy -- is BR_20260901e
and lives in ``tests/test_cross_stage_path_ssot.py``.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from bodesign_workflow_core.c01_id_package import (
    C01_OUTPUTS,
    C01_STAGE_DIRNAME,
    _c01_stage_dir,
)
from bodesign_workflow_core.c02_me_package import (
    C02_OUTPUTS,
    C02_STAGE_DIRNAME,
    _c02_stage_dir,
)
from bodesign_workflow_core.c01_id_template import load_c01_id_template
from bodesign_workflow_core.readiness_common import STAGE_FOLDER


def _first_segment(rel: Path) -> str:
    return rel.parts[0]


class StagePrefixCarriedByEveryConstant(unittest.TestCase):
    """Q: does EVERY C0x_OUTPUTS value carry its stage dirname as segment 0?

    This is the claim "each of those constants carries its own prefix". If a
    future edit drops the prefix from one entry, role 1 (filesystem join) still
    writes SOMEWHERE and role 2 returns a rel path one segment short — the
    failure BR_20260804h §4 describes as "blows up on the next hop". This test
    is the hop.
    """

    def test_c02_every_output_starts_with_stage_dirname(self) -> None:
        self.assertTrue(C02_OUTPUTS, "C02_OUTPUTS is empty — nothing was checked")
        for key, rel in C02_OUTPUTS.items():
            with self.subTest(key=key):
                self.assertEqual(
                    C02_STAGE_DIRNAME,
                    _first_segment(rel),
                    f"C02_OUTPUTS[{key!r}] = {rel.as_posix()!r} does not start with "
                    f"{C02_STAGE_DIRNAME!r}",
                )

    def test_c01_every_output_starts_with_stage_dirname(self) -> None:
        self.assertTrue(C01_OUTPUTS, "C01_OUTPUTS is empty — nothing was checked")
        for key, rel in C01_OUTPUTS.items():
            with self.subTest(key=key):
                self.assertEqual(
                    C01_STAGE_DIRNAME,
                    _first_segment(rel),
                    f"C01_OUTPUTS[{key!r}] = {rel.as_posix()!r} does not start with "
                    f"{C01_STAGE_DIRNAME!r}",
                )

    def test_stage_dirnames_match_the_central_stage_folder_map(self) -> None:
        """Q: do the per-module dirnames agree with readiness_common.STAGE_FOLDER?

        Two independent spellings of the same folder are exactly the drift this
        BR is about, one level up.
        """
        self.assertEqual(STAGE_FOLDER["c01"], C01_STAGE_DIRNAME)
        self.assertEqual(STAGE_FOLDER["c02"], C02_STAGE_DIRNAME)


class StageDirHelperDerivesTheSameSegment(unittest.TestCase):
    """Q: does _c0x_stage_dir(root) equal root / <stage dirname>?

    The helper is the OTHER prefix model. If it and the constants ever disagree,
    the provenance path and the export path resolve to different directories —
    and nothing in the running code would say so.
    """

    def test_c02_stage_dir(self) -> None:
        root = Path("/nonexistent/product-root")
        self.assertEqual(root / C02_STAGE_DIRNAME, _c02_stage_dir(root))

    def test_c01_stage_dir(self) -> None:
        root = Path("/nonexistent/product-root")
        self.assertEqual(root / C01_STAGE_DIRNAME, _c01_stage_dir(root))

    def test_both_helpers_still_fail_closed_on_none(self) -> None:
        """Q: does a missing folder still return None rather than cwd?"""
        self.assertIsNone(_c02_stage_dir(None))
        self.assertIsNone(_c01_stage_dir(None))

    def test_helper_output_is_the_prefix_the_constants_carry(self) -> None:
        """Q: are the TWO prefix models actually producing the same segment?

        This is the load-bearing one: it is the assertion the old "in ONE place"
        comment was gesturing at but could not make, because there were two
        places and nothing compared them.
        """
        root = Path("/nonexistent/product-root")
        for key, rel in C02_OUTPUTS.items():
            with self.subTest(stage="c02", key=key):
                self.assertEqual(root / rel, _c02_stage_dir(root) / Path(*rel.parts[1:]))
        for key, rel in C01_OUTPUTS.items():
            with self.subTest(stage="c01", key=key):
                self.assertEqual(root / rel, _c01_stage_dir(root) / Path(*rel.parts[1:]))


class TemplateReconciliationRoleStillHolds(unittest.TestCase):
    """Q: is role 3 (reconciliation set) still satisfied?

    ``c01_id_template.py:121`` diffs the template's own prefixed carriers against
    ``{p.as_posix() for p in C01_OUTPUTS.values()}``. This role is neither a
    filesystem join nor a returned rel path, and BR_20260804h's own §4 analysis
    counted only two roles and missed it. Pinning it here is what stops the next
    person from making the same count.
    """

    def test_template_carriers_are_a_subset_of_emitter_carriers(self) -> None:
        tpl = load_c01_id_template()
        template_carriers = {f"{tpl.folder}/{c}" for c in tpl.draft_carriers()}
        emitter_carriers = {p.as_posix() for p in C01_OUTPUTS.values()}
        self.assertTrue(
            template_carriers,
            "template declares no draft carriers — the check window was empty",
        )
        self.assertLessEqual(
            template_carriers,
            emitter_carriers,
            "template declares carriers the emitter does not produce: "
            f"{sorted(template_carriers - emitter_carriers)}",
        )

    def test_template_folder_equals_the_stage_dirname(self) -> None:
        """Q: is the template's independently-declared prefix the same string?"""
        tpl = load_c01_id_template()
        self.assertEqual(C01_STAGE_DIRNAME, tpl.folder)


class NegativeControlTests(unittest.TestCase):
    """Prove the guards above can FAIL. A check that cannot fail is not a check.

    Each control mutates a COPY of the real data in exactly the way a careless
    refactor would (drop the stage prefix / change one character of the dirname)
    and asserts the guard's own predicate goes red. If these ever pass silently,
    the guards above are scenery.
    """

    def test_control_dropping_a_prefix_breaks_the_segment_check(self) -> None:
        mutated = dict(C02_OUTPUTS)
        mutated["stl"] = Path("Enclosure.stl")  # prefix removed, as a bad refactor would
        offenders = [
            k for k, rel in mutated.items() if _first_segment(rel) != C02_STAGE_DIRNAME
        ]
        self.assertEqual(["stl"], offenders, "the segment predicate did not notice a dropped prefix")

    def test_control_changing_the_dirname_breaks_the_helper_check(self) -> None:
        root = Path("/nonexistent/product-root")
        wrong = root / "C02-MECH"  # one word off, as a rename would produce
        self.assertNotEqual(wrong, _c02_stage_dir(root))

    def test_control_extra_template_carrier_breaks_the_subset_check(self) -> None:
        emitter_carriers = {p.as_posix() for p in C01_OUTPUTS.values()}
        mutated_template = {f"{C01_STAGE_DIRNAME}/Not_Produced_By_Emitter.md"}
        self.assertFalse(
            mutated_template <= emitter_carriers,
            "the subset predicate did not notice a carrier the emitter never produces",
        )

    def test_control_stage_folder_map_comparison_is_not_vacuous(self) -> None:
        """A wrong dirname must not compare equal to the central map."""
        self.assertNotEqual(STAGE_FOLDER["c02"], "C02-MECH")
        self.assertNotEqual(STAGE_FOLDER["c01"], "C01-INDUSTRIAL")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
