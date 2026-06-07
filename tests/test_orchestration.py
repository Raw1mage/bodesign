import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    OrchestrationError,
    dispatch_work_packet,
    get_work_packet,
    ingest_blocker,
    list_blockers,
    list_work_packets,
    return_blocker,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-orch-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    # ── Dispatch ────────────────────────────────────────────────────
    def test_dispatch_creates_packet_with_inherited_authority(self):
        wp = dispatch_work_packet(
            self.work, "C01", "Produce first-pass ID direction from PRD visual fields.",
            sections=["s05_id_me_requirements"], fields=["s05_id_me_requirements.dimensions"],
        )
        self.assertEqual(wp.packet_id, "C00-WP-0001")
        self.assertEqual(wp.target_layer, "C01")
        self.assertEqual(wp.target_role, "industrial_design")
        self.assertEqual(wp.status, "ready")
        # Authority comes from the registry, not the caller.
        self.assertIn("return_blocker", wp.allowed_actions)
        self.assertIn("change_product_direction", wp.forbidden_actions)
        self.assertTrue(wp.return_to_c00_when)
        # Persisted with the right schema.
        path = self.work / "_orchestration" / "work_packets" / "C00-WP-0001.json"
        self.assertEqual(json.loads(path.read_text())["schema"], "bodesign.c00.work_packet.v1")

    def test_packet_ids_increment_deterministically(self):
        a = dispatch_work_packet(self.work, "C01", "x")
        b = dispatch_work_packet(self.work, "C03", "y")
        self.assertEqual([a.packet_id, b.packet_id], ["C00-WP-0001", "C00-WP-0002"])
        self.assertEqual([w.packet_id for w in list_work_packets(self.work)], ["C00-WP-0001", "C00-WP-0002"])

    def test_cannot_dispatch_to_c00_itself(self):
        with self.assertRaises(OrchestrationError):
            dispatch_work_packet(self.work, "C00", "self-dispatch")

    def test_cannot_dispatch_to_unknown_layer(self):
        with self.assertRaises(OrchestrationError):
            dispatch_work_packet(self.work, "C09", "nope")

    def test_empty_objective_fails_fast(self):
        with self.assertRaises(OrchestrationError):
            dispatch_work_packet(self.work, "C01", "   ")

    def test_blocked_inputs_make_packet_blocked(self):
        wp = dispatch_work_packet(self.work, "C02", "enclosure", inputs={"blocked": ["board outline missing"]})
        self.assertEqual(wp.status, "blocked")

    def test_unknown_input_bucket_fails_fast(self):
        with self.assertRaises(OrchestrationError):
            dispatch_work_packet(self.work, "C01", "x", inputs={"bogus": []})

    # ── Blocker backflow ────────────────────────────────────────────
    def test_blocker_source_layer_is_taken_from_packet(self):
        dispatch_work_packet(self.work, "C01", "id work")
        blk = return_blocker(
            self.work, "C00-WP-0001",
            severity="decision", summary="Need primary face decision.",
            question_for_user="Which face is the primary user-facing surface?",
            affected_c00_fields=["s05_id_me_requirements.primary_face"],
        )
        self.assertEqual(blk.blocker_id, "C01-BLOCK-0001")
        self.assertEqual(blk.source_layer, "C01")
        # Originating packet is now blocked.
        self.assertEqual(get_work_packet(self.work, "C00-WP-0001").status, "blocked")

    def test_blocker_against_unknown_packet_fails_fast(self):
        with self.assertRaises(OrchestrationError):
            return_blocker(self.work, "C00-WP-9999", severity="decision", summary="x", question_for_user="y")

    def test_invalid_severity_owner_state_fail_fast(self):
        dispatch_work_packet(self.work, "C01", "id")
        with self.assertRaises(OrchestrationError):
            return_blocker(self.work, "C00-WP-0001", severity="oops", summary="s", question_for_user="q")
        with self.assertRaises(OrchestrationError):
            return_blocker(self.work, "C00-WP-0001", severity="decision", summary="s", question_for_user="q", recommended_owner="nobody")
        with self.assertRaises(OrchestrationError):
            return_blocker(self.work, "C00-WP-0001", severity="decision", summary="s", question_for_user="q", proposed_state="weird")

    # ── Ingest ──────────────────────────────────────────────────────
    def test_ingest_records_resolution_and_closes_blocker(self):
        dispatch_work_packet(self.work, "C01", "id")
        return_blocker(self.work, "C00-WP-0001", severity="decision", summary="s",
                       question_for_user="q", affected_c00_fields=["s05.x"])
        res = ingest_blocker(self.work, "C01-BLOCK-0001", resolved_state="answered",
                             decision="Top face is primary.", decided_by="user")
        self.assertTrue(res.resolved)
        self.assertEqual(res.proposed_state, "answered")
        self.assertEqual(res.affected_c00_fields, ["s05.x"])
        self.assertEqual(list_blockers(self.work, unresolved_only=True), [])

    def test_ingest_requires_real_decision_no_silent_fill(self):
        dispatch_work_packet(self.work, "C01", "id")
        return_blocker(self.work, "C00-WP-0001", severity="decision", summary="s", question_for_user="q")
        with self.assertRaises(OrchestrationError):
            ingest_blocker(self.work, "C01-BLOCK-0001", resolved_state="answered", decision="  ")

    def test_double_ingest_fails_fast(self):
        dispatch_work_packet(self.work, "C01", "id")
        return_blocker(self.work, "C00-WP-0001", severity="decision", summary="s", question_for_user="q")
        ingest_blocker(self.work, "C01-BLOCK-0001", resolved_state="answered", decision="done")
        with self.assertRaises(OrchestrationError):
            ingest_blocker(self.work, "C01-BLOCK-0001", resolved_state="answered", decision="again")

    def test_log_records_event_sequence(self):
        dispatch_work_packet(self.work, "C01", "id")
        return_blocker(self.work, "C00-WP-0001", severity="decision", summary="s", question_for_user="q")
        ingest_blocker(self.work, "C01-BLOCK-0001", resolved_state="answered", decision="done")
        log = (self.work / "_orchestration" / "log.jsonl").read_text().strip().splitlines()
        events = [json.loads(line)["event"] for line in log]
        self.assertEqual(events, ["dispatch", "blocker_returned", "blocker_ingested"])


if __name__ == "__main__":
    unittest.main()
