"""Tasks 2.2-2.6: strict partition, fail-fast codes, per-sheet `(sheet, group)` scope.

Every cell here names the plan vector it implements (TV-3..TV-8, TV-12) and, where
the vector's own description says so, why the neighbouring cell cannot carry the claim
alone. Sheet-NAME validation (TV-9/10/11) lives in test_sheet_name_validation.py.
"""
import unittest

from bodesign_eda_bridge.partition import (
    AUTHORITY_COMPOSER_LEGACY,
    AUTHORITY_PARTITION,
    COUNTERS,
    KIND_DECLARED,
    KIND_UNGROUPED,
    LEGACY_BUCKET,
    ClusterKey,
    PartitionError,
    assert_partition_identity,
    partition_components,
)


def _spec(components):
    return {"components": components}


def _comp(ref, **kwargs):
    out = {"ref": ref, "symbol": "Device:R"}
    out.update(kwargs)
    return out


class StrictPartitionTests(unittest.TestCase):
    """TV-3 / TV-4: the partition is strict, and the check can go red."""

    def test_tv3_real_board_field5_partition_is_22_9_14(self):
        """TV-3 treatment: the real-board assignment reproduces K3's 22/9/14.

        Population: the btdongle field-5 assignment as recorded in K3 (45 refs,
        22 power / 9 mcu / 14 io, zero cross-sheet duplicates). The refs here are
        SYNTHESISED in those counts, not copied from the board -- this cell asserts
        that the partition function preserves a declared 22/9/14 split and that
        the sum equals the distinct count, which is what tasks 2.5 asks of THIS
        module. Reading the real design.py is a GUEST-repo action outside this
        package's boundary.
        """
        components = (
            [_comp(f"P{i}", sheet="power") for i in range(22)]
            + [_comp(f"M{i}", sheet="mcu") for i in range(9)]
            + [_comp(f"I{i}", sheet="io") for i in range(14)]
        )
        self.assertEqual(len(components), 45)
        result = partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(
            {name: len(refs) for name, refs in result.sheets.items()},
            {"power": 22, "mcu": 9, "io": 14})
        self.assertEqual(result.partition_source, "declared")
        total = sum(len(refs) for refs in result.sheets.values())
        distinct = len({ref for refs in result.sheets.values() for ref in refs})
        self.assertEqual(total, 45)
        self.assertEqual(distinct, 45, "sum must equal distinct: no ref on two sheets")

    def test_tv4_partial_declaration_raises_unassigned_naming_every_missing_ref(self):
        """TV-4 negative control for TV-3: without it, TV-3's PASS cannot show the
        check goes red when it should."""
        components = [
            _comp("R1"),                      # no `sheet` key at all
            _comp("R2", sheet="power"),
            _comp("R3", sheet="io"),
        ]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_UNASSIGNED_REFS")
        self.assertEqual(ctx.exception.details["unassigned_refs"], ["R1"])
        self.assertIn("R1", str(ctx.exception))

    def test_unassigned_lists_every_missing_ref_not_only_the_first(self):
        """A message naming one ref out of three sends the caller back N times."""
        components = [
            _comp("R1"), _comp("R2"), _comp("R3", sheet="power"),
        ]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components))
        self.assertEqual(ctx.exception.details["unassigned_refs"], ["R1", "R2"])

    def test_same_ref_on_two_sheets_raises_ref_on_multiple_sheets(self):
        components = [
            _comp("R1", sheet="power"),
            _comp("R1", sheet="io"),
        ]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_REF_ON_MULTIPLE_SHEETS")
        self.assertEqual(
            ctx.exception.details["refs_on_multiple_sheets"], {"R1": ["io", "power"]})

    def test_repeated_ref_on_one_sheet_raises_duplicate_ref(self):
        """Round 2 shipped this input as ACCEPTED, returning sheets={'power':
        ['R1','R1']} -- sum=2 while distinct=1, which breaks the frozen identity.
        It is now rejected under its own code."""
        components = [
            _comp("R1", sheet="power"),
            _comp("R1", sheet="power"),
        ]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_DUPLICATE_REF")
        self.assertEqual(ctx.exception.details["duplicate_refs"], {"R1": 2})

    def test_duplicate_on_one_sheet_and_across_sheets_get_different_codes(self):
        """The two repetition shapes have different repairs, so they must not share
        a code. A single generic duplicate code would pass each cell above."""
        codes = []
        for components in (
            [_comp("R1", sheet="power"), _comp("R1", sheet="io")],
            [_comp("R1", sheet="power"), _comp("R1", sheet="power")],
        ):
            with self.assertRaises(PartitionError) as ctx:
                partition_components(_spec(components), project_name="btdongle")
            codes.append(ctx.exception.code)
        self.assertEqual(codes, ["E_REF_ON_MULTIPLE_SHEETS", "E_DUPLICATE_REF"])

    def test_duplicate_is_rejected_on_the_legacy_route_too(self):
        """The check runs BEFORE the legacy early return. Placed after it, a
        duplicate would be accepted whenever no sheet was declared -- the same
        defect surviving in the branch that carries most real specs."""
        components = [_comp("R1"), _comp("R1")]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components))
        self.assertEqual(ctx.exception.code, "E_DUPLICATE_REF")

    def test_identity_holds_on_both_routes(self):
        """sum == distinct == components, asserted rather than trusted."""
        declared = partition_components(
            _spec([_comp("R1", sheet="power"), _comp("R2", sheet="io")]),
            project_name="btdongle")
        assert_partition_identity(declared, 2)
        legacy = partition_components(_spec([_comp("R1"), _comp("R2")]))
        assert_partition_identity(legacy, 2)

    def test_identity_assertion_itself_goes_red_on_a_broken_map(self):
        """Positive control for the assertion: a hand-broken SheetMap must raise,
        otherwise the two cells above prove only that it never fires."""
        broken = partition_components(_spec([_comp("R1", sheet="power")]),
                                      project_name="btdongle")
        broken.sheets["power"].append("R1")
        with self.assertRaises(PartitionError) as ctx:
            assert_partition_identity(broken, 1)
        self.assertEqual(ctx.exception.code, "E_PARTITION_IDENTITY_BROKEN")


class InputValidationTests(unittest.TestCase):
    """Precedence steps 0-1: the public pure function validates its own input.

    Round 2 accepted three malformed shapes silently: a non-list `components` became
    an empty list, a missing `components` key became an empty list, and a component
    without `ref` was given the synthetic identifier `<component#N>` -- which was then
    counted in the strict-partition sum as though it were a real component.
    """

    def setUp(self):
        COUNTERS.reset()

    def test_none_spec_raises_rather_than_partitioning_zero_components(self):
        with self.assertRaises(PartitionError) as ctx:
            partition_components(None)
        self.assertEqual(ctx.exception.code, "E_SPEC_MALFORMED")

    def test_missing_components_key_raises_rather_than_coercing_to_empty(self):
        """A typo'd key ('componets') used to partition zero components and return a
        clean-looking empty result."""
        with self.assertRaises(PartitionError) as ctx:
            partition_components({"componets": [_comp("R1")]})
        self.assertEqual(ctx.exception.code, "E_SPEC_MALFORMED")
        self.assertEqual(ctx.exception.details["keys"], ["componets"])

    def test_non_list_components_raises_for_each_wrong_type(self):
        for value in (None, "R1,R2", {"ref": "R1"}, 7):
            with self.subTest(value=value):
                with self.assertRaises(PartitionError) as ctx:
                    partition_components({"components": value})
                self.assertEqual(ctx.exception.code, "E_SPEC_MALFORMED")

    def test_an_explicitly_empty_list_is_still_accepted(self):
        """Positive control for the three cells above: without it, a validator that
        rejected every spec would also pass them. `{'components': []}` is the
        supported way to say 'no components'."""
        result = partition_components({"components": []})
        self.assertEqual(result.sheets, {LEGACY_BUCKET: []})
        self.assertEqual(COUNTERS.raised_spec_malformed, 0)

    def test_a_bare_list_spec_is_still_accepted(self):
        result = partition_components([_comp("R1", sheet="power")],
                                      project_name="btdongle")
        self.assertEqual(result.sheets, {"power": ["R1"]})

    def test_missing_ref_raises_and_fabricates_no_identifier(self):
        """The round-2 defect in one cell: `<component#1>` used to be created, land
        on a sheet, and be counted in the identity sum."""
        components = [_comp("R1", sheet="power"), {"symbol": "Device:R",
                                                   "sheet": "power"}]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_REF_MISSING")
        self.assertEqual(ctx.exception.details["index"], 1)
        self.assertNotIn("<component#", str(ctx.exception.details.get("ref", "")))

    def test_ref_none_is_a_missing_ref_not_a_blank_one(self):
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec([{"ref": None, "sheet": "power"}]),
                                 project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_REF_MISSING")
        self.assertTrue(ctx.exception.details["ref_key_present"])

    def test_blank_ref_has_its_own_code_separate_from_missing(self):
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec([{"ref": "   ", "sheet": "power"}]),
                                 project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_REF_BLANK")

    def test_a_scalar_component_raises_component_malformed(self):
        for value in ("R1", 7, None, True):
            with self.subTest(value=value):
                with self.assertRaises(PartitionError) as ctx:
                    partition_components(_spec([value]))
                self.assertEqual(ctx.exception.code, "E_COMPONENT_MALFORMED")

    def test_the_four_input_codes_are_distinct(self):
        """Same discriminating shape as the sheet-name cells: four inputs, four
        codes, asserted in one run so a collapse into one generic code is visible."""
        codes = []
        for spec in (
            {"componets": []},
            _spec([{"symbol": "Device:R"}]),
            _spec([{"ref": "  "}]),
            _spec(["R1"]),
        ):
            with self.assertRaises(PartitionError) as ctx:
                partition_components(spec)
            codes.append(ctx.exception.code)
        self.assertEqual(codes, ["E_SPEC_MALFORMED", "E_REF_MISSING",
                                 "E_REF_BLANK", "E_COMPONENT_MALFORMED"])
        self.assertEqual(len(set(codes)), 4)

    def test_input_validation_precedes_sheet_validation(self):
        """A spec that is both ref-broken and sheet-broken reports the ref defect:
        an unidentifiable component cannot be usefully told its sheet is wrong."""
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec([{"sheet": "../etc"}]))
        self.assertEqual(ctx.exception.code, "E_REF_MISSING")


class DeclaredBlankAndTypeTests(unittest.TestCase):
    """Task 2.3: the three fail-fast codes must never collapse into one another."""

    def test_blank_after_strip_raises_name_empty_not_unassigned(self):
        components = [
            _comp("R1", sheet="   "),
            _comp("R2", sheet="power"),
        ]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_SHEET_NAME_EMPTY")
        self.assertEqual(ctx.exception.details["ref"], "R1")

    def test_json_null_counts_as_declared_and_is_invalid_not_absent(self):
        """`None` must NOT take the legacy path: "author wrote null" and "author
        wrote nothing" mean different things and get different codes."""
        components = [
            _comp("R1", sheet=None),
            _comp("R2", sheet="power"),
        ]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(ctx.exception.code, "E_SHEET_NAME_INVALID")
        self.assertEqual(ctx.exception.details["received_type"], "NoneType")

    def test_all_null_does_not_degrade_to_the_legacy_path(self):
        """The dual of the cell above: if `None` were read as absent, a spec of all
        nulls would silently emit one legacy file."""
        components = [_comp("R1", sheet=None), _comp("R2", sheet=None)]
        with self.assertRaises(PartitionError) as ctx:
            partition_components(_spec(components))
        self.assertEqual(ctx.exception.code, "E_SHEET_NAME_INVALID")

    def test_three_codes_are_distinct_for_the_three_input_shapes(self):
        """The discriminating assertion: same module, three inputs, three codes.
        A single generic code would pass each cell above individually."""
        codes = []
        for components in (
            [_comp("R1"), _comp("R2", sheet="power")],          # partial
            [_comp("R1", sheet=""), _comp("R2", sheet="power")],  # blank
            [_comp("R1", sheet=7), _comp("R2", sheet="power")],   # wrong type
        ):
            with self.assertRaises(PartitionError) as ctx:
                partition_components(_spec(components))
            codes.append(ctx.exception.code)
        self.assertEqual(
            codes,
            ["E_UNASSIGNED_REFS", "E_SHEET_NAME_EMPTY", "E_SHEET_NAME_INVALID"])
        self.assertEqual(len(set(codes)), 3)


class GroupScopingTests(unittest.TestCase):
    """AC-7, tasks 2.6 -- all THREE cells, per the plan's own reasoning."""

    def test_tv7_same_group_on_two_sheets_stays_two_clusters(self):
        components = [
            _comp("R1", sheet="power", group="g0"),
            _comp("R2", sheet="power", group="g0"),
            _comp("R3", sheet="io", group="g0"),
            _comp("R4", sheet="io", group="g0"),
        ]
        result = partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(result.sheets, {"power": ["R1", "R2"], "io": ["R3", "R4"]})
        self.assertEqual(
            [key.as_tuple() for key in result.cluster_keys],
            [("power", KIND_DECLARED, "g0"), ("io", KIND_DECLARED, "g0")])
        self.assertEqual(len(result.cluster_keys), 2)
        self.assertEqual(
            result.clusters[ClusterKey("power", KIND_DECLARED, "g0")], ["R1", "R2"])
        self.assertEqual(
            result.clusters[ClusterKey("io", KIND_DECLARED, "g0")], ["R3", "R4"])

    def test_tv8_no_sheet_anywhere_takes_the_legacy_path_and_names_no_sheet_after_a_group(self):
        """TV-8: the mechanical retirement of R2/K11.

        SCOPE LIMIT, stated because round 1 overclaimed it: this cell detects sheets
        being CREATED from group values. It does NOT detect `group` being ignored --
        both behaviours emit one legacy bucket here. TV-12 is that control.
        """
        components = [_comp(f"R{i}", group=f"g{i % 4}") for i in range(8)]
        result = partition_components(_spec(components))
        self.assertEqual(result.partition_source, "none-declared")
        self.assertEqual(list(result.sheets), [LEGACY_BUCKET])
        for group_name in ("g0", "g1", "g2", "g3"):
            self.assertNotIn(group_name, result.sheets)
        self.assertEqual(result.clustering_authority, AUTHORITY_COMPOSER_LEGACY)
        self.assertEqual(result.clusters, {},
                         "legacy clustering belongs to composer._cluster, which uses "
                         "net-degree topology this function never sees")

    def test_tv12_within_one_sheet_equal_groups_cocluster_and_a_different_group_stays_apart(self):
        """TV-12: the ONLY cell that goes red when `group` is ignored entirely.

        TV-7 cannot: two sheets give two clusters either way. TV-8 cannot: its
        fixture declares no sheet, so both behaviours emit one legacy bucket.
        """
        components = [
            _comp("R1", sheet="power", group="g0"),
            _comp("R2", sheet="power", group="g0"),
            _comp("R3", sheet="power", group="g1"),
        ]
        result = partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(result.sheets, {"power": ["R1", "R2", "R3"]})
        clusters = result.clusters_on("power")
        self.assertEqual(len(clusters), 2, f"expected 2 clusters, got {clusters}")
        self.assertEqual(clusters, [["R1", "R2"], ["R3"]])

    def test_an_ungrouped_component_is_its_own_cluster(self):
        """A ref without a group must not be absorbed into a neighbour's cluster."""
        components = [
            _comp("R1", sheet="power", group="g0"),
            _comp("R2", sheet="power"),
        ]
        result = partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(result.clusters_on("power"), [["R1"], ["R2"]])
        self.assertEqual(
            [key.as_tuple() for key in result.cluster_keys],
            [("power", KIND_DECLARED, "g0"), ("power", KIND_UNGROUPED, "R2")])
        self.assertEqual(result.clustering_authority, AUTHORITY_PARTITION)

    def test_ungrouped_ref_never_merges_with_a_declared_group_of_the_same_spelling(self):
        """COUNTEREXAMPLE to the round-2 scheme, which keyed clusters on a plain
        string and synthesised `auto-<ref>` for ungrouped components. R1 (no group)
        became the key "auto-R1"; R2 declaring group="auto-R1" produced the SAME key,
        so two unrelated components merged into one cluster.

        Under `ClusterKey`, `kind` differs, so the two cannot collide regardless of
        spelling -- the fix is structural rather than a rarer prefix.
        """
        components = [
            _comp("R1", sheet="power"),
            _comp("R2", sheet="power", group="auto-R1"),
        ]
        result = partition_components(_spec(components), project_name="btdongle")
        self.assertEqual(
            [key.as_tuple() for key in result.cluster_keys],
            [("power", KIND_UNGROUPED, "R1"), ("power", KIND_DECLARED, "auto-R1")])
        self.assertEqual(result.clusters_on("power"), [["R1"], ["R2"]])
        self.assertNotEqual(result.cluster_keys[0], result.cluster_keys[1])

    def test_the_old_string_scheme_would_have_merged_that_pair(self):
        """Demonstrates the defect the cell above prevents, so its necessity is
        shown rather than asserted in prose."""
        old_keys = [
            ("power", "auto-R1"),
            ("power", "auto-R1"),
        ]
        self.assertEqual(old_keys[0], old_keys[1], "old scheme: identical keys")
        new_keys = [
            ClusterKey("power", KIND_UNGROUPED, "R1"),
            ClusterKey("power", KIND_DECLARED, "auto-R1"),
        ]
        self.assertNotEqual(new_keys[0], new_keys[1], "new scheme: disjoint")


class OutcomeCodomainTests(unittest.TestCase):
    """Task 2.4: `not-run` / `empty` / `ok` must not share an output."""

    def setUp(self):
        COUNTERS.reset()

    def test_not_run_is_distinguishable_from_a_legacy_single_bucket(self):
        """The whole point of a branch-ENTRY counter: a result-shaped field cannot
        tell "never called" from "called and produced one bucket"."""
        self.assertEqual(COUNTERS.calls_entered, 0, "not-run: nothing invoked yet")
        result = partition_components(_spec([_comp("R1")]))
        self.assertEqual(result.partition_source, "none-declared")
        self.assertEqual(COUNTERS.calls_entered, 1)
        self.assertEqual(COUNTERS.legacy_branch_entered, 1)
        self.assertEqual(COUNTERS.declared_branch_entered, 0)

    def test_declared_branch_entry_is_counted_separately(self):
        partition_components(_spec([_comp("R1", sheet="power")]),
                             project_name="btdongle")
        self.assertEqual(COUNTERS.declared_branch_entered, 1)
        self.assertEqual(COUNTERS.legacy_branch_entered, 0)

    def test_empty_component_list_is_the_legacy_branch_with_an_empty_bucket(self):
        result = partition_components(_spec([]))
        self.assertEqual(result.partition_source, "none-declared")
        self.assertEqual(result.sheets, {LEGACY_BUCKET: []})
        self.assertEqual(COUNTERS.legacy_branch_entered, 1)

    def test_each_raise_increments_its_own_counter(self):
        with self.assertRaises(PartitionError):
            partition_components(_spec([_comp("R1"), _comp("R2", sheet="power")]))
        self.assertEqual(COUNTERS.raised_unassigned, 1)
        self.assertEqual(COUNTERS.raised_name_invalid, 0,
                         "a wrong counter incrementing would misattribute the cause")

    def test_one_declared_sheet_is_not_rewritten_to_the_legacy_bucket(self):
        """design.md Q5, decided literally: an explicitly declared single sheet keeps
        partition_source="declared" and its own name. Folding it into the legacy
        bucket would make "nothing declared" and "one sheet declared" identical.
        """
        result = partition_components(_spec([_comp("R1", sheet="power")]),
                                      project_name="btdongle")
        self.assertEqual(result.partition_source, "declared")
        self.assertEqual(list(result.sheets), ["power"])
        self.assertNotIn(LEGACY_BUCKET, result.sheets)


if __name__ == "__main__":
    unittest.main()
