"""M1-4 registry + M1-5 threshold resolver tests.

Covers plan spec.md scenarios / test-vectors:
- registry no-fabrication guard: partial/todo control cannot register as T-A
- registry envelope_tool must be an ORACLE_TOOLS member
- registry summary panel counts (landed/stub/advisory + tier)
- threshold resolver reads the materialized block from ragbase (DD-3 runtime coupling)
- threshold resolver fails fast on absent block (refuses body_md prose) — no-fabrication
- threshold resolver rejects a block with no source_anchor — datasheet-grounded
- decoupling checker end-to-end wired through the resolver
"""

import json
import os
import sqlite3
import tempfile
import unittest

from bodesign_workflow_core.checkers import (
    AdvisoryScenario,
    CheckerBinding,
    CheckerError,
    CheckerRegistry,
    build_advisory_scenarios,
    build_pilot_registry,
    check_decoupling_pdn,
    resolve_threshold_block,
)


def _make_db(rows: list[tuple[str, str, str]]) -> str:
    """Build a throwaway ragbase.sqlite with (id, confidence, metadata_json) rows."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE ragbase_objects (id TEXT PRIMARY KEY, confidence TEXT, metadata_json TEXT)"
    )
    conn.executemany(
        "INSERT INTO ragbase_objects (id, confidence, metadata_json) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return path


class RegistryTests(unittest.TestCase):
    def test_pilot_registry_builds_and_summary(self) -> None:
        reg = build_pilot_registry()
        s = reg.summary()
        # The registry aggregates every landed milestone cluster, so the exact
        # total grows as clusters land. Assert the invariants that must always
        # hold rather than a brittle cross-cluster count: the M1 pilots + the
        # M2-1 spacing T-A checker are landed, and the counters are internally
        # consistent.
        for cid in (
            "control.power.decoupling-pdn-strategy",
            "control.mech.board-edge-keepout",
            "control.verify.kicad-default-severities",
            "control.si.spacing-via-return-path",
        ):
            b = reg.lookup(cid)
            self.assertIsNotNone(b, f"{cid} should be registered")
            self.assertEqual(b.status, "landed", f"{cid} should be landed")
        self.assertEqual(s["total"], s["landed"] + s["stub"] + s["advisory"])
        self.assertEqual(s["total"], s["T-A"] + s["T-B"] + s["T-C"])
        self.assertGreaterEqual(s["landed"], 4)

    def test_partial_control_cannot_register_as_TA(self) -> None:
        with self.assertRaises(CheckerError) as ctx:
            CheckerBinding(
                control_id="control.dfm.injection-molding-geometry",
                tier="T-A", trust_layer=2, stage="C02", status="landed",
                confidence="partial", envelope_tool="drc_gate",
            )
        self.assertEqual(ctx.exception.code, "CHK_TIER_FORBIDDEN_PARTIAL")

    def test_todo_control_cannot_register_as_TA(self) -> None:
        with self.assertRaises(CheckerError) as ctx:
            CheckerBinding(
                control_id="control.some.todo-one",
                tier="T-A", trust_layer=1, stage="C00", status="landed",
                confidence="todo", envelope_tool="erc",
            )
        self.assertEqual(ctx.exception.code, "CHK_TIER_FORBIDDEN_PARTIAL")

    def test_partial_control_allowed_as_TC_advisory(self) -> None:
        # no exception: partial is fine as advisory (T-C)
        b = CheckerBinding(
            control_id="control.dfm.injection-molding-geometry",
            tier="T-C", trust_layer=2, stage="C02", status="advisory",
            confidence="partial",
        )
        self.assertEqual(b.tier, "T-C")

    def test_unknown_envelope_tool_rejected(self) -> None:
        with self.assertRaises(CheckerError) as ctx:
            CheckerBinding(
                control_id="control.x", tier="T-A", trust_layer=1, stage="C04",
                status="landed", confidence="verified", envelope_tool="not_an_oracle",
            )
        self.assertEqual(ctx.exception.code, "CHK_BINDING_INVALID")

    def test_bad_trust_layer_rejected(self) -> None:
        with self.assertRaises(CheckerError):
            CheckerBinding(
                control_id="control.x", tier="T-A", trust_layer=9, stage="C04",
                status="landed", confidence="verified", envelope_tool="drc_gate",
            )

    def test_duplicate_registration_rejected(self) -> None:
        reg = CheckerRegistry()
        b = CheckerBinding(
            control_id="control.dup", tier="T-B", trust_layer=2, stage="C04",
            status="stub", confidence="verified",
        )
        reg.register(b)
        with self.assertRaises(CheckerError) as ctx:
            reg.register(b)
        self.assertEqual(ctx.exception.code, "CHK_BINDING_DUPLICATE")


class ThresholdResolverTests(unittest.TestCase):
    def test_resolves_materialized_block(self) -> None:
        block = {"threshold_block": {"metric": "decoupling_distance_mm",
                                     "value": 12.5, "unit": "mm",
                                     "source_anchor": "TI SPRABV2; batch14"}}
        db = _make_db([("control.power.decoupling-pdn-strategy", "verified",
                        json.dumps(block))])
        try:
            tb = resolve_threshold_block(db, "control.power.decoupling-pdn-strategy")
            self.assertEqual(tb["value"], 12.5)
            self.assertEqual(tb["unit"], "mm")
            self.assertTrue(tb["source_anchor"])
        finally:
            os.unlink(db)

    def test_absent_block_fails_fast_no_prose_parse(self) -> None:
        # metadata_json empty → resolver must NOT invent a number from body_md
        db = _make_db([("control.power.decoupling-pdn-strategy", "verified", "")])
        try:
            with self.assertRaises(CheckerError) as ctx:
                resolve_threshold_block(db, "control.power.decoupling-pdn-strategy")
            self.assertEqual(ctx.exception.code, "CHK_THRESHOLD_UNBOUND")
        finally:
            os.unlink(db)

    def test_block_without_source_anchor_rejected(self) -> None:
        block = {"threshold_block": {"metric": "d", "value": 10, "unit": "mm"}}
        db = _make_db([("control.x", "verified", json.dumps(block))])
        try:
            with self.assertRaises(CheckerError) as ctx:
                resolve_threshold_block(db, "control.x")
            self.assertEqual(ctx.exception.code, "CHK_SOURCE_ANCHOR_MISSING")
        finally:
            os.unlink(db)

    def test_control_not_found(self) -> None:
        db = _make_db([("control.other", "verified", "")])
        try:
            with self.assertRaises(CheckerError) as ctx:
                resolve_threshold_block(db, "control.missing")
            self.assertEqual(ctx.exception.code, "CHK_CONTROL_NOT_FOUND")
        finally:
            os.unlink(db)

    def test_decoupling_checker_wired_through_resolver(self) -> None:
        # end-to-end: resolve block from DB, feed the checker (DD-3 runtime coupling)
        block = {"threshold_block": {"metric": "decoupling_distance_mm",
                                     "value": 12.5, "unit": "mm",
                                     "source_anchor": "TI SPRABV2; batch14"}}
        db = _make_db([("control.power.decoupling-pdn-strategy", "verified",
                        json.dumps(block))])
        try:
            tb = resolve_threshold_block(db, "control.power.decoupling-pdn-strategy")
            ir = {
                "components": [
                    {"refdes": "C1", "placement": {"x": 0.0, "y": 0.0}},   # 0mm, ok
                    {"refdes": "C2", "placement": {"x": 50.0, "y": 0.0}},  # 50mm, over 12.5
                ],
                "power_pin": {"x": 0.0, "y": 0.0},
            }
            ev = check_decoupling_pdn(
                ir, control_id="control.power.decoupling-pdn-strategy",
                threshold_block=tb,
            )
            # C2 exceeds → exactly one major finding, evidence carries source_anchor
            self.assertEqual(len(ev.findings), 1)
            self.assertEqual(ev.findings[0].id, "decoupling-C2")
            self.assertEqual(ev.inputs["source_anchor"], "TI SPRABV2; batch14")
        finally:
            os.unlink(db)


def _make_body_db(rows: list[tuple[str, str, str]]) -> str:
    """Build a throwaway ragbase.sqlite with (id, confidence, body_md) rows."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE ragbase_objects (id TEXT PRIMARY KEY, confidence TEXT, body_md TEXT)"
    )
    conn.executemany(
        "INSERT INTO ragbase_objects (id, confidence, body_md) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return path


class AdvisoryInjectorTests(unittest.TestCase):
    """M3 — qualitative verified controls → G2 advisory review prompts (DD-5)."""

    def test_qualitative_verified_projected_as_scenario(self) -> None:
        db = _make_body_db([
            ("control.si.crystal-oscillator-layout", "verified",
             "時鐘 layout 須對晶體擺位檢核（來源：NXP AN1706）\n**規則**：..."),
        ])
        try:
            scenarios = build_advisory_scenarios(db, registered_control_ids=frozenset())
            self.assertEqual(len(scenarios), 1)
            s = scenarios[0]
            self.assertEqual(s.control_id, "control.si.crystal-oscillator-layout")
            self.assertTrue(s.source_anchor)
            self.assertIn("NXP AN1706", s.source_anchor)
            d = s.to_scenario_dict()
            self.assertEqual(d["conclusion"], "")
            self.assertEqual(d["severity"], "info")
        finally:
            os.unlink(db)

    def test_meta_controls_excluded(self) -> None:
        db = _make_body_db([
            ("control.no-fabrication", "verified", "Never fabricate native files."),
            ("control.no-silent-fallback", "verified", "Fail fast, never default."),
        ])
        try:
            scenarios = build_advisory_scenarios(db, registered_control_ids=frozenset())
            self.assertEqual(scenarios, ())
        finally:
            os.unlink(db)

    def test_registered_control_not_double_counted(self) -> None:
        db = _make_body_db([
            ("control.power.decoupling-pdn-strategy", "verified", "decoupling body"),
            ("control.si.crystal-oscillator-layout", "verified", "crystal body"),
        ])
        try:
            scenarios = build_advisory_scenarios(
                db, registered_control_ids=frozenset({"control.power.decoupling-pdn-strategy"}))
            ids = {s.control_id for s in scenarios}
            self.assertNotIn("control.power.decoupling-pdn-strategy", ids)
            self.assertIn("control.si.crystal-oscillator-layout", ids)
        finally:
            os.unlink(db)

    def test_partial_control_not_advisory_injected(self) -> None:
        db = _make_body_db([
            ("control.some.partial-one", "partial", "partial body"),
        ])
        try:
            scenarios = build_advisory_scenarios(db, registered_control_ids=frozenset())
            self.assertEqual(scenarios, ())
        finally:
            os.unlink(db)

    def test_deterministic_stable_ordering(self) -> None:
        rows = [
            ("control.si.zeta-layout", "verified", "z body (來源：Z)"),
            ("control.si.alpha-layout", "verified", "a body (來源：A)"),
        ]
        db1 = _make_body_db(rows)
        db2 = _make_body_db(list(reversed(rows)))
        try:
            s1 = build_advisory_scenarios(db1, registered_control_ids=frozenset())
            s2 = build_advisory_scenarios(db2, registered_control_ids=frozenset())
            self.assertEqual([s.control_id for s in s1], [s.control_id for s in s2])
            self.assertEqual([s.control_id for s in s1],
                             ["control.si.alpha-layout", "control.si.zeta-layout"])
        finally:
            os.unlink(db1)
            os.unlink(db2)

    def test_missing_table_fails_fast(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        try:
            with self.assertRaises(CheckerError) as ctx:
                build_advisory_scenarios(path, registered_control_ids=frozenset())
            self.assertEqual(ctx.exception.code, "CHK_CONTROL_NOT_FOUND")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
