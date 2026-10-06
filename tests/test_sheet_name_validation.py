"""Task 2.7 / AC-8 / TV-9..TV-11: sheet-name validation (DERIVED, design.md DD-7 c5-6).

SCOPE BOUNDARY, stated because TV-10's plan text names a FILE PATH.
--------------------------------------------------------------------
No file is written anywhere in this module, and none is asserted. Phase 3 owns
emission; this Phase owns the predicate that runs BEFORE it. So TV-10 is realised
here as "the accepted name survives verbatim as the sheet key" -- the stem the
emitter will later use -- and the path assertion `<out_dir>/power_v2-a.kicad_sch`
stays OPEN until Phase 3. Claiming the path here would assert something this code
does not do.

Why TV-9 alone would be worthless: a validator that rejects EVERY name passes all
seven rejection cases. TV-10 is what makes the rejections mean something, and
`test_reject_everything_impostor_fails_tv10` demonstrates that literally rather
than asserting it in prose.
"""
import unittest

from bodesign_eda_bridge.partition import (
    SHEET_NAME_PATTERN,
    SHEET_NAME_RE,
    PartitionError,
    partition_components,
)


def _spec(components):
    return {"components": components}


def _comp(ref, **kwargs):
    out = {"ref": ref, "symbol": "Device:R"}
    out.update(kwargs)
    return out


class SheetNameRejectionTests(unittest.TestCase):
    """TV-9: seven cases, each failing the ONE frozen predicate."""

    #: (ref, value, why). Every entry fails `SHEET_NAME_PATTERN`; this list
    #: DESCRIBES that regex and never extends it.
    CASES = [
        ("R1", "../etc/passwd", "path traversal: '.' and '/' outside the class"),
        ("R2", "power/io", "path separator outside the class"),
        ("R3", "power sheet", "whitespace outside the class"),
        ("R4", "-power", "leading '-' excluded by the first-character class"),
        ("R5", "a" * 65, "65 chars, over the 1..64 bound"),
        ("R6", None, "non-str: JSON null is PRESENT-and-invalid, never absent"),
        ("R7", 7, "non-str: int"),
    ]

    def test_tv9_every_rejection_case_raises_sheet_name_invalid(self):
        for ref, value, why in self.CASES:
            with self.subTest(value=value, why=why):
                with self.assertRaises(PartitionError) as ctx:
                    partition_components(_spec([_comp(ref, sheet=value)]),
                                         project_name="btdongle")
                self.assertEqual(ctx.exception.code, "E_SHEET_NAME_INVALID")

    def test_tv9_case_count_is_seven(self):
        self.assertEqual(len(self.CASES), 7)

    def test_tv9_error_names_the_ref_the_value_and_the_failing_condition(self):
        for ref, value, why in self.CASES:
            with self.subTest(value=value, why=why):
                with self.assertRaises(PartitionError) as ctx:
                    partition_components(_spec([_comp(ref, sheet=value)]),
                                         project_name="btdongle")
                details = ctx.exception.details
                self.assertEqual(details["ref"], ref)
                self.assertEqual(details["received"], value)
                self.assertIn(details["condition"], {"regex", "not-a-str"})

    def test_no_silent_sanitization_the_rejected_name_never_becomes_a_sheet(self):
        """A slugifying implementation would return sheets={'etcpasswd': [...]}
        and raise nothing. This cell is what makes that observable."""
        with self.assertRaises(PartitionError):
            partition_components(_spec([_comp("R1", sheet="../etc/passwd")]),
                                 project_name="btdongle")

    def test_trailing_newline_is_rejected_because_fullmatch_not_dollar(self):
        """Python's `$` also matches before a trailing newline, so `re.match` with
        `$` would ACCEPT 'power\\n' and let it reach a filename. `fullmatch` does
        not. Control: the same string without the newline is accepted below.
        """
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec([_comp("R1", sheet="power\n")]),
                                 project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_SHEET_NAME_INVALID")
        self.assertEqual(ctx.exception.details["condition"], "regex")

    def test_the_dollar_anchored_form_would_have_accepted_it(self):
        """Demonstrates the defect `fullmatch` avoids, so the choice above is a
        measured decision and not a stylistic one."""
        import re
        dollar_form = re.compile(SHEET_NAME_PATTERN)
        self.assertIsNotNone(dollar_form.match("power\n"),
                             "premise of the previous cell: `$` accepts it")
        self.assertIsNone(SHEET_NAME_RE.fullmatch("power\n"),
                          "and fullmatch is what rejects it")

    def test_bool_is_rejected_although_it_is_an_int_subclass(self):
        """`isinstance(True, int)` is True; a naive type check that allowed ints
        would let a bool through. Not in TV-9's list -- added because the schema
        names bool explicitly."""
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec([_comp("R1", sheet=True)]),
                                 project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_SHEET_NAME_INVALID")
        self.assertEqual(ctx.exception.details["received_type"], "bool")

    def test_list_and_dict_are_rejected_as_non_str(self):
        for value in ([], {}, ["power"]):
            with self.subTest(value=value):
                with self.assertRaises(PartitionError) as ctx:
                    partition_components(_spec([_comp("R1", sheet=value)]),
                                         project_name="btdongle")
                self.assertEqual(ctx.exception.code, "E_SHEET_NAME_INVALID")


class SheetNameAcceptanceTests(unittest.TestCase):
    """TV-10: the positive control. Without it, TV-9 has no discriminating power."""

    def test_tv10_a_legal_name_passes_through_verbatim(self):
        result = partition_components(
            _spec([_comp("R1", sheet="power_v2-a", group="g0")]),
            project_name="btdongle")
        self.assertEqual(list(result.sheets), ["power_v2-a"])
        self.assertEqual(result.sheets["power_v2-a"], ["R1"])
        self.assertEqual(result.partition_source, "declared")

    def test_tv10_boundary_names_at_both_length_bounds_are_accepted(self):
        for name in ("a", "_", "a" * 64, "Z9_-x"):
            with self.subTest(name=name):
                result = partition_components(_spec([_comp("R1", sheet=name)]),
                                              project_name="btdongle")
                self.assertEqual(list(result.sheets), [name])

    def test_reject_everything_impostor_fails_tv10(self):
        """The literal demonstration that TV-10 is load-bearing: a validator that
        rejects every name satisfies all of TV-9, and is caught only here."""
        def impostor(value):
            return False

        for _ref, value, _why in SheetNameRejectionTests.CASES:
            self.assertFalse(impostor(value), "impostor passes every TV-9 case")
        self.assertFalse(impostor("power_v2-a"))
        self.assertIsNotNone(SHEET_NAME_RE.fullmatch("power_v2-a"),
                             "the real predicate accepts what the impostor rejects")


class SheetNameCollisionTests(unittest.TestCase):
    """TV-11: leaf-vs-root, the ONE reachable collision."""

    def test_tv11_leaf_stem_equal_to_project_name_raises_collision(self):
        components = [
            _comp("U1", sheet="btdongle", group="g0"),
            _comp("U2", sheet="io", group="g0"),
        ]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_SHEET_NAME_COLLISION")
        self.assertEqual(ctx.exception.details["colliding_name"], "btdongle")

    def test_the_same_names_are_individually_legal_which_is_why_it_needs_a_check(self):
        """Control: 'btdongle' passes the regex, so nothing upstream stops it. This
        is what makes the collision reachable rather than decorative."""
        self.assertIsNotNone(SHEET_NAME_RE.fullmatch("btdongle"))
        result = partition_components(_spec([_comp("U1", sheet="btdongle")]),
                                      project_name="other_project")
        self.assertEqual(list(result.sheets), ["btdongle"])

    def test_collision_is_case_sensitive_exact_equality(self):
        """The contract says exact string equality -- no case folding. On a
        case-insensitive filesystem 'BTDongle' would still clash, and that is
        deliberately NOT claimed here: the check is what the contract says it is.
        """
        result = partition_components(_spec([_comp("U1", sheet="BTDongle")]),
                                      project_name="btdongle")
        self.assertEqual(list(result.sheets), ["BTDongle"])

    def test_leaf_versus_leaf_is_deliberately_unchecked(self):
        """Two distinct legal names in one directory cannot collide with verbatim
        stems, so no check exists. Asserting one would have no violating input."""
        components = [_comp("U1", sheet="power"), _comp("U2", sheet="io")]
        result = partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(sorted(result.sheets), ["io", "power"])

    def test_omitting_project_name_reports_the_check_as_not_performed(self):
        """`collision_checked=False` separates "no collision" from "never looked".
        Without this field a caller could not tell the two apart."""
        result = partition_components(_spec([_comp("U1", sheet="btdongle")]))
        self.assertFalse(result.collision_checked)
        checked = partition_components(_spec([_comp("U1", sheet="power")]),
                                       project_name="btdongle")
        self.assertTrue(checked.collision_checked)


class ErrorPrecedenceTests(unittest.TestCase):
    """The precedence is a decision, not an accident -- so it is asserted."""

    def test_partial_declaration_beats_an_invalid_name(self):
        """A spec that is BOTH partially declared AND carries a bad name reports the
        shape defect first: repairing the name would still leave it unusable."""
        components = [_comp("R1"), _comp("R2", sheet="../etc")]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_UNASSIGNED_REFS")

    def test_blank_beats_the_generic_regex_failure(self):
        """A blank string also fails the regex; the blank code must win so that
        "declared but empty" keeps its own signal."""
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec([_comp("R1", sheet="  ")]),
                                 project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_SHEET_NAME_EMPTY")

    def test_invalid_name_beats_the_collision(self):
        components = [
            _comp("U1", sheet="../btdongle"),
            _comp("U2", sheet="btdongle"),
        ]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_SHEET_NAME_INVALID")

    def test_multi_sheet_ref_beats_the_collision(self):
        components = [
            _comp("U1", sheet="power"),
            _comp("U1", sheet="btdongle"),
        ]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_REF_ON_MULTIPLE_SHEETS")


if __name__ == "__main__":
    unittest.main()
