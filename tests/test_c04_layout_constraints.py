import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    assess_c04_layout_readiness,
    emit_c04_layout_package,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

_C01 = {
    "schema": "bodesign.c01.interface_constraints.v1",
    "exposed_components": [{"ref": "U1", "kind": "display"}],
    "downstream_targets": {"C04": ["preferred component faces", "placement keepouts"]},
}
def _write_c03_gate_reports(
    root: Path,
    entry_gate: dict | str | None = "default",
    prd_crosscheck: dict | str | None = "default",
) -> None:
    """Materialise C03's signed verdicts at the PINNED paths C04 entry reads.

    A value of `None` writes nothing (the report is absent); a `str` is written
    verbatim (to build a malformed payload); a `dict` is written as JSON.
    """
    c03 = root / "C03-EE"
    c03.mkdir(parents=True, exist_ok=True)
    defaults = {
        "entry_gate": {
            "schema": "bodesign.c03.stage_entry_gate.v1",
            "gate": "PASS",
            "blocking": [],
            "netlist_crosscheck": {"status": "checked", "rows_matched": 1},
            "ssot_crosscheck": {"status": "checked"},
            "pin_polarity": {"status": "checked"},
        },
        "prd_crosscheck": {
            "schema": "bodesign.crosscheck.prd_bom.v1",
            "gate": "PASS",
            "blocking": [],
        },
    }
    for key, payload, name in (
        ("entry_gate", entry_gate, "check_c03.report.json"),
        ("prd_crosscheck", prd_crosscheck, "prd_bom_crosscheck.report.json"),
    ):
        if payload is None:
            continue
        if payload == "default":
            payload = defaults[key]
        text = payload if isinstance(payload, str) else json.dumps(payload)
        (c03 / name).write_text(text, encoding="utf-8")


_C03 = {
    "constraints": {
        "component_heights": [{"ref": "U1", "height_mm": 1.2}],
        "connector_openings": [{"ref": "J1", "type": "usb-c"}],
        "heat_sources": [{"ref": "U2", "watts": 1.5}],
        "antenna_keepouts": [{"area": "top-left"}],
        "battery_envelope": {"type": "18650"},
        "esd_emc_notes": ["protect USB lines"],
    }
}


class C04LayoutTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c04-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _seed_c03_netlist(self):
        """Realise the disk-of-truth that C03 has emitted a netlist (components landed)."""
        (self.work / "C03-EE").mkdir(parents=True, exist_ok=True)
        (self.work / "C03-EE" / "board.net").write_text(
            '(export (version "E") (components (comp (ref R1) (value 1k))))', encoding="utf-8")
        (self.work / "C03-EE" / "Mechanical_Constraint_Export.json").write_text(
            json.dumps(_C03), encoding="utf-8")

    def _seed_c03_gate_reports(self, **overrides):
        """Write the signed C03 verdicts C04 entry consumes (tier-1 acceptance).

        Tier-0 (files exist) is necessary but not sufficient; C04 also reads the
        reports C03 signs. Passing everything here is the RELEASE control group:
        it proves the gate opens when it should, not merely that it closes.
        """
        _write_c03_gate_reports(self.work, **overrides)

    def test_emit_merges_c01_c03_and_leaves_board_pending(self):
        self._seed_c03_netlist()  # upstream C03 has realised a netlist
        self._seed_c03_gate_reports()  # ...and its stage-entry gates signed off
        res = emit_c04_layout_package(self.work, c01=_C01, c03=_C03)
        self.assertIn("C04-Layout/Layout_Constraints.json", res.files)
        c = res.constraints
        self.assertEqual(c["schema"], "bodesign.c04.layout_constraints.v1")
        self.assertTrue(c["component_heights"])
        self.assertTrue(c["connector_edge_openings"])
        self.assertEqual(c["placement_intent"], ["preferred component faces", "placement keepouts"])
        # Layout-owned items stay pending and unfabricated.
        pending_items = {p["item"] for p in res.pending}
        self.assertIn("board_outline", pending_items)
        self.assertIn("placement_coordinates", pending_items)
        # No board/Gerber/approval claims.
        rd = res.readiness.to_dict()
        self.assertFalse(rd["board_ready"])
        self.assertFalse(rd["gerber_ready"])
        self.assertFalse(rd["layout_approval"])
        # With a realised netlist upstream, this is a genuine layout draft.
        self.assertEqual(rd["status"], "layout_constraints_drafted")
        self.assertTrue(rd["upstream_fulfilled"])

    def test_emit_without_c03_netlist_is_blocked_upstream_not_drafted(self):
        # C01/C03 dicts passed in-memory, but no C03 netlist on disk → components have
        # NOT landed on a board. Must be BLOCKING, never a delivered-looking draft.
        res = emit_c04_layout_package(self.work, c01=_C01, c03=_C03)
        rd = res.readiness.to_dict()
        self.assertEqual(rd["status"], "blocked_upstream_c03_missing")
        self.assertFalse(rd["upstream_fulfilled"])
        self.assertTrue(rd["warnings"])
        self.assertEqual(res.constraints["state"], "blocked_on_upstream")
        # The gap list names the missing netlist explicitly (no silent pass).
        gaps = " ".join(rd["upstream"]["gaps"])
        self.assertIn("netlist", gaps)

    def test_readiness_without_upstream_is_blocked_not_fabricated(self):
        res = emit_c04_layout_package(self.work, c01=None, c03=None)
        self.assertEqual(res.readiness.status, "blocked_upstream_c03_missing")
        self.assertEqual(res.readiness.present_groups, [])
        self.assertFalse(res.readiness.to_dict()["upstream_fulfilled"])

    def test_tier3_signals_route_to_si_handoff(self):
        self._seed_c03_netlist()
        self._seed_c03_gate_reports()
        signals = {"layer_count": 8, "finest_bga_pitch_mm": 0.4, "hdi_required": True,
                   "high_speed_nets": 24, "rf": True}
        res = emit_c04_layout_package(self.work, c01=_C01, c03=_C03, feasibility_signals=signals)
        rd = res.readiness.to_dict()
        self.assertEqual(rd["feasibility_tier"], 3)
        self.assertEqual(rd["status"], "layout_constraints_drafted_tier3_handoff")
        self.assertIn("emit_si_constraint_export", rd["next_step"])

    def test_no_signals_tier_not_guessed(self):
        self._seed_c03_netlist()
        res = emit_c04_layout_package(self.work, c01=_C01, c03=_C03)
        rd = res.readiness.to_dict()
        # Honesty model: no complexity signals → tier is not-assessed, never guessed.
        self.assertIsNone(rd["feasibility_tier"])
        self.assertEqual(rd["feasibility"]["label"], "not-assessed")

    def test_auto_loads_upstream_from_folder(self):
        # Drop the C01 + C03 exports where the emitter auto-discovers them.
        (self.work / "C01-ID").mkdir(parents=True, exist_ok=True)
        (self.work / "C01-ID" / "Interface_Constraints.json").write_text(json.dumps(_C01), encoding="utf-8")
        (self.work / "C03-EE").mkdir(parents=True, exist_ok=True)
        (self.work / "C03-EE" / "Mechanical_Constraint_Export.json").write_text(json.dumps(_C03), encoding="utf-8")
        res = emit_c04_layout_package(self.work)
        self.assertTrue(res.constraints["source"]["from_c01"])
        self.assertTrue(res.constraints["source"]["from_c03"])
        self.assertIn("component_heights", res.readiness.present_groups)

    def test_readiness_missing_before_emit(self):
        rd = assess_c04_layout_readiness(self.work)
        self.assertEqual(rd.status, "missing")
        self.assertFalse(rd.constraints_present)


class C04EntryAcceptanceTests(unittest.TestCase):
    """Tier-1 entry acceptance: C04 consumes the verdicts C03 signs.

    Every blocking case below is paired with the RELEASE control group in
    `test_signed_passing_reports_release_entry` — without it these tests would
    only prove the gate can close, which is compatible with a gate that is welded
    shut. A gate is only shown to work when the same harness demonstrates it
    opening on adequate evidence and closing on each distinct inadequacy.
    """

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c04-entry-", dir=PRIVATE_BASE))
        # Tier-0 satisfied throughout: C03 ran and left its three files on disk.
        # This is exactly the BR_20260707 symptom condition — the files exist, so
        # the incumbent existence check passes and only tier-1 can refuse.
        (self.work / "C03-EE").mkdir(parents=True, exist_ok=True)
        (self.work / "C03-EE" / "board.net").write_text(
            '(export (version "E") (components (comp (ref R1) (value 1k))))', encoding="utf-8")
        (self.work / "C03-EE" / "Mechanical_Constraint_Export.json").write_text(
            json.dumps(_C03), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _readiness(self, **overrides):
        _write_c03_gate_reports(self.work, **overrides)
        emit_c04_layout_package(self.work, c01=_C01, c03=_C03)
        return assess_c04_layout_readiness(self.work).to_dict()

    def test_tier0_passes_while_tier1_refuses(self):
        """The BR's core defect: files present, delivery unacceptable.

        Tier-0 must report fulfilled (nothing is wrong with its own question) while
        tier-1 refuses entry. If this ever collapses into tier-0 failing, the two
        checks have been conflated and the acceptance question has been lost again.
        """
        rd = self._readiness(entry_gate=None, prd_crosscheck=None)
        self.assertTrue(rd["upstream_fulfilled"])
        self.assertEqual(rd["status"], "blocked_c03_entry_gate_not_run")
        self.assertFalse(rd["c03_accepted"])

    def test_absent_report_is_not_run_never_presumed_pass(self):
        rd = self._readiness(entry_gate=None)
        self.assertEqual(rd["status"], "blocked_c03_entry_gate_not_run")
        gaps = " ".join(rd["c03_acceptance"]["gaps"])
        # The error must carry both the expected path and the command that makes it,
        # so a blocked reader never has to choose between hunting and bypassing.
        self.assertIn("check_c03.report.json", gaps)
        self.assertIn(str(self.work / "C03-EE" / "check_c03.report.json"), gaps)
        self.assertIn("bodesign_check_c03(", gaps)

    def test_failing_gate_blocks_and_is_distinct_from_not_run(self):
        rd = self._readiness(entry_gate={
            "gate": "FAIL",
            "blocking": [{"code": "R2_READINESS", "ref": "U4", "detail": "status=draft"}],
            "netlist_crosscheck": {"status": "checked"},
        })
        self.assertEqual(rd["status"], "blocked_c03_entry_gate_failed")
        self.assertEqual(rd["c03_acceptance"]["reports"]["entry_gate"]["blocking_count"], 1)

    def test_pass_without_netlist_scope_is_blocking(self):
        """Q2: a PASS whose netlist_crosscheck never ran does not clear layout.

        `check_c03`'s own docstring states such a PASS "must NOT be read as 'every
        BOM row is drawn'". C04 placement rests on precisely that guarantee, so
        consuming it as clean would be reading not-checked as checked — the exact
        defect this BR is about.
        """
        rd = self._readiness(entry_gate={
            "gate": "PASS",
            "blocking": [],
            "netlist_crosscheck": {"status": "not_run", "reason": "netlist_path not supplied"},
            "ssot_crosscheck": {"status": "checked"},
            "pin_polarity": {"status": "checked"},
        })
        self.assertEqual(rd["status"], "blocked_c03_entry_gate_scope_incomplete")
        # Distinct from a FAIL: the gate did not reject the BOM, it never looked.
        self.assertEqual(rd["c03_acceptance"]["reports"]["entry_gate"]["gate"], "PASS")

    def test_missing_scope_block_is_not_run_not_clean(self):
        """An older report that never carried the field did not check that scope."""
        rd = self._readiness(entry_gate={"gate": "PASS", "blocking": []})
        self.assertEqual(rd["status"], "blocked_c03_entry_gate_scope_incomplete")

    def test_malformed_report_is_distinct_from_absent(self):
        """A corrupt report and a missing one need different remedies, so they must
        not share an output — and neither is ever read as a pass."""
        rd = self._readiness(entry_gate="{not valid json")
        self.assertEqual(rd["status"], "blocked_c03_entry_gate_report_unusable")
        self.assertIn("not valid JSON", " ".join(rd["c03_acceptance"]["gaps"]))

    def test_report_without_gate_field_is_unusable_not_pass(self):
        rd = self._readiness(entry_gate={"schema": "something.else.v1", "rows": 12})
        self.assertEqual(rd["status"], "blocked_c03_entry_gate_report_unusable")

    def test_prd_crosscheck_absent_also_blocks(self):
        """Q3: the sister gate rides the same mechanism — GUIDE:505 and GUIDE:508
        are one rule, and leaving one of them as prose would be knowing about the
        hole and keeping it."""
        rd = self._readiness(prd_crosscheck=None)
        self.assertEqual(rd["status"], "blocked_c03_entry_gate_not_run")
        self.assertIn("prd_bom_crosscheck.report.json",
                      " ".join(rd["c03_acceptance"]["gaps"]))

    def test_prd_crosscheck_failing_blocks(self):
        rd = self._readiness(prd_crosscheck={"gate": "FAIL", "blocking": ["role:mcu missing"]})
        self.assertEqual(rd["status"], "blocked_c03_entry_gate_failed")

    def test_secondary_scopes_warn_but_do_not_block(self):
        """ssot_crosscheck / pin_polarity are quality signals, not preconditions for
        starting layout: they warn, and entry still opens."""
        rd = self._readiness(entry_gate={
            "gate": "PASS",
            "blocking": [],
            "netlist_crosscheck": {"status": "checked"},
            "ssot_crosscheck": {"status": "not_run"},
            "pin_polarity": {"status": "not_run"},
        })
        self.assertEqual(rd["status"], "layout_constraints_drafted")
        self.assertTrue(rd["c03_accepted"])
        joined = " ".join(rd["warnings"])
        self.assertIn("ssot_crosscheck", joined)
        self.assertIn("pin_polarity", joined)

    def test_signed_passing_reports_release_entry(self):
        """RELEASE CONTROL GROUP — the gate opens on adequate evidence.

        Without this, every other test here is satisfied by a gate that refuses
        everything unconditionally.
        """
        rd = self._readiness()
        self.assertEqual(rd["status"], "layout_constraints_drafted")
        self.assertTrue(rd["c03_accepted"])
        self.assertEqual(rd["c03_acceptance"]["gaps"], [])
        self.assertEqual(rd["c03_acceptance"]["reports"]["entry_gate"]["status"], "pass")
        self.assertEqual(rd["c03_acceptance"]["reports"]["prd_bom_crosscheck"]["status"], "pass")

    def test_tier1_not_consulted_while_tier0_blocks(self):
        """With no netlist on disk there is nothing for a BOM<->netlist verdict to be
        about. `c03_accepted` must read None (never reached) rather than False
        (reached and refused), so the first action stays 'run C03'."""
        empty = Path(tempfile.mkdtemp(prefix="bodesign-c04-t0-", dir=PRIVATE_BASE))
        try:
            emit_c04_layout_package(empty, c01=_C01, c03=_C03)
            rd = assess_c04_layout_readiness(empty).to_dict()
            self.assertEqual(rd["status"], "blocked_upstream_c03_missing")
            self.assertIsNone(rd["c03_accepted"])
            self.assertEqual(rd["c03_acceptance"], {})
        finally:
            shutil.rmtree(empty, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
