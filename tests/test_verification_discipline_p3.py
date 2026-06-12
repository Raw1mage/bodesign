"""P3 (workflow_verification-discipline) — A3 Evidence Backflow + A5 ValidationEvidence.

Covers spec.md scenarios:
- 工具輸出包裝為 envelope (TV-A5-01)
- 驗證證據回流並持久化 (TV-A3-01)
- malformed payload fail fast (TV-A3-02)
- C00 消費 evidence (TV-A3-03)
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    ValidationEvidenceError,
    dispatch_work_packet,
    get_evidence_return,
    ingest_evidence,
    list_evidence_returns,
    return_evidence,
    wrap_validation_evidence,
)
from bodesign_workflow_core.orchestration import OrchestrationError

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class ValidationEvidenceEnvelopeTests(unittest.TestCase):
    """TV-A5-01 / DD-6: wrapper layer, native fields preserved, never reinterpreted."""

    def test_si_check_wrapped_raw_preserved(self):
        raw = {"z0": 50.0, "rs": 22.0,
               "nets": [{"net": "USB_DP", "len_mm": 12.3, "overshoot_pct": 12.3,
                         "undershoot_pct": 3.0, "status": "warn"}],
               "worst": "warn", "effective": {"vdd": 1.8}}
        env = wrap_validation_evidence("si_check", raw, inputs={"board": "b.kicad_pcb"},
                                       requirement_refs=["usb_dp_dm_skew"])
        d = env.to_dict()
        for f in ("tool", "inputs", "findings", "severity", "anchors", "requirement_refs", "raw_result"):
            self.assertIn(f, d)
        self.assertEqual(d["raw_result"], raw)  # invariant: untouched
        self.assertEqual(d["requirement_refs"], ["usb_dp_dm_skew"])
        self.assertEqual(d["severity"], "minor")  # warn -> minor finding
        self.assertEqual(d["findings"][0]["anchor"]["kind"], "net")

    def test_clean_drc_is_info_with_no_findings(self):
        env = wrap_validation_evidence("drc_gate", {"copper": 0, "unconnected": 0, "silk": 0, "clean": True})
        self.assertEqual(env.severity, "info")
        self.assertEqual(env.findings, [])

    def test_dirty_drc_severity_is_max_across_findings(self):
        env = wrap_validation_evidence("drc_gate", {"copper": 2, "unconnected": 1, "silk": 3, "clean": False})
        self.assertEqual(env.severity, "major")
        ids = {f.id for f in env.findings}
        self.assertEqual(ids, {"drc-copper", "drc-unconnected", "drc-silk"})

    def test_crosscheck_missing_is_major_extra_is_minor(self):
        env = wrap_validation_evidence("crosscheck", {"matched": ["GND"], "missing": ["INT_N"],
                                                      "extra": ["DBG"], "coverage_pct": 50})
        sev = {f.id: f.severity for f in env.findings}
        self.assertEqual(sev["xchk-missing-INT_N"], "major")
        self.assertEqual(sev["xchk-extra-DBG"], "minor")

    def test_unknown_tool_fails_fast(self):
        with self.assertRaises(ValidationEvidenceError) as ctx:
            wrap_validation_evidence("magic", {"x": 1})
        self.assertIn("ENV_TOOL_UNKNOWN", str(ctx.exception))

    def test_empty_raw_result_fails_fast(self):
        with self.assertRaises(ValidationEvidenceError) as ctx:
            wrap_validation_evidence("drc_gate", {})
        self.assertIn("ENV_RAW_RESULT_MISSING", str(ctx.exception))


class EvidenceReturnSpineTests(unittest.TestCase):
    """TV-A3-01/02: persistence mirrors spine patterns; malformed pollutes nothing."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-evreturn-", dir=PRIVATE_BASE))
        self.packet = dispatch_work_packet(self.work, "C04", "route board")
        self.envelope = wrap_validation_evidence(
            "drc_gate", {"copper": 0, "unconnected": 0, "silk": 0, "clean": True},
            requirement_refs=["board_length"]).to_dict()

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_tv_a3_01_persistence_and_log(self):
        ev = return_evidence(self.work, self.packet.packet_id, envelope=self.envelope,
                             requirement_verdicts=[{"requirement_key": "board_length",
                                                    "verdict": "pass", "measured_value": "58.4"}])
        self.assertEqual(ev.evidence_id, "C04-EV-0001")
        path = self.work / "_orchestration" / "evidence_returns" / "C04-EV-0001.json"
        self.assertTrue(path.exists())
        data = json.loads(path.read_text())
        self.assertEqual(data["schema"], "bodesign.c00.evidence_return.v1")
        events = [json.loads(l) for l in
                  (self.work / "_orchestration" / "log.jsonl").read_text().strip().splitlines()]
        self.assertEqual(events[-1]["event"], "evidence.returned")
        self.assertEqual(events[-1]["requirement_verdicts_count"], 1)

    def test_count_based_ids(self):
        e1 = return_evidence(self.work, self.packet.packet_id, envelope=self.envelope)
        e2 = return_evidence(self.work, self.packet.packet_id, envelope=self.envelope)
        self.assertEqual([e1.evidence_id, e2.evidence_id], ["C04-EV-0001", "C04-EV-0002"])

    def test_tv_a3_02_malformed_envelope_fails_and_pollutes_nothing(self):
        cases = [
            {},                                       # empty
            {"schema": "wrong"},                      # wrong schema
            {"schema": "bodesign.validation_evidence.v1"},  # missing required keys
        ]
        for payload in cases:
            with self.assertRaises(OrchestrationError, msg=payload):
                return_evidence(self.work, self.packet.packet_id, envelope=payload)
        self.assertEqual(list_evidence_returns(self.work), [])
        log_path = self.work / "_orchestration" / "log.jsonl"
        if log_path.exists():
            events = [json.loads(l) for l in log_path.read_text().strip().splitlines()]
            self.assertFalse(any(e["event"] == "evidence.returned" for e in events))

    def test_unknown_packet_fails_fast(self):
        with self.assertRaises(OrchestrationError):
            return_evidence(self.work, "C00-WP-9999", envelope=self.envelope)

    def test_invalid_verdict_rows_fail_fast(self):
        with self.assertRaises(OrchestrationError):
            return_evidence(self.work, self.packet.packet_id, envelope=self.envelope,
                            requirement_verdicts=[{"requirement_key": "x", "verdict": "maybe"}])
        with self.assertRaises(OrchestrationError):
            return_evidence(self.work, self.packet.packet_id, envelope=self.envelope,
                            requirement_verdicts=[{"verdict": "pass"}])

    def test_roundtrip(self):
        ev = return_evidence(self.work, self.packet.packet_id, envelope=self.envelope,
                             requirement_verdicts=[{"requirement_key": "board_length", "verdict": "pass"}])
        loaded = get_evidence_return(self.work, ev.evidence_id)
        self.assertEqual(loaded.envelope["tool"], "drc_gate")
        self.assertEqual(loaded.requirement_verdicts[0]["verdict"], "pass")
        self.assertFalse(loaded.resolved)


class EvidenceIngestTests(unittest.TestCase):
    """TV-A3-03: C00 consumes evidence, updates statuses, never auto-executes."""

    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-evingest-", dir=PRIVATE_BASE))
        self.packet = dispatch_work_packet(self.work, "C04", "route board")
        envelope = wrap_validation_evidence(
            "drc_gate", {"copper": 1, "unconnected": 0, "silk": 0, "clean": False}).to_dict()
        self.ev = return_evidence(self.work, self.packet.packet_id, envelope=envelope,
                                  requirement_verdicts=[
                                      {"requirement_key": "board_length", "verdict": "pass"},
                                      {"requirement_key": "net_parity", "verdict": "fail"}])

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_tv_a3_03_status_updates_and_failed_list(self):
        result = ingest_evidence(self.work, self.ev.evidence_id)
        self.assertEqual(result["requirement_status_updates"],
                         {"board_length": "pass", "net_parity": "fail"})
        self.assertEqual(result["failed_requirements"], ["net_parity"])
        self.assertIn("never auto-executes", result["note"])

    def test_ingest_marks_resolved_and_logs(self):
        ingest_evidence(self.work, self.ev.evidence_id)
        self.assertTrue(get_evidence_return(self.work, self.ev.evidence_id).resolved)
        events = [json.loads(l) for l in
                  (self.work / "_orchestration" / "log.jsonl").read_text().strip().splitlines()]
        self.assertEqual(events[-1]["event"], "requirement.status_changed")

    def test_double_ingest_fails_fast(self):
        ingest_evidence(self.work, self.ev.evidence_id)
        with self.assertRaises(OrchestrationError):
            ingest_evidence(self.work, self.ev.evidence_id)

    def test_unresolved_only_filter(self):
        self.assertEqual(len(list_evidence_returns(self.work, unresolved_only=True)), 1)
        ingest_evidence(self.work, self.ev.evidence_id)
        self.assertEqual(len(list_evidence_returns(self.work, unresolved_only=True)), 0)
        self.assertEqual(len(list_evidence_returns(self.work)), 1)


class McpToolLayerTests(unittest.TestCase):
    """3.4: MCP tool wiring for envelope wrap + evidence return/ingest."""

    def setUp(self):
        import importlib
        self.server = importlib.import_module("services.mcp.server")
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-evmcp-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def _rt(self, name, args):
        result = self.server.run_tool(name, args)
        self.assertTrue(result.get("ok"), result)
        return result["result"]

    def test_end_to_end_through_mcp(self):
        p = self._rt("bodesign_dispatch_work_packet",
                     {"folder": str(self.work), "target_layer": "C04", "objective": "route"})
        env = self._rt("bodesign_wrap_validation_evidence",
                       {"tool": "drc_gate",
                        "raw_result": {"copper": 1, "unconnected": 0, "silk": 0, "clean": False},
                        "requirement_refs": ["board_length"]})
        ev = self._rt("bodesign_return_evidence",
                      {"folder": str(self.work), "packet_id": p["packet_id"], "envelope": env,
                       "requirement_verdicts": [{"requirement_key": "board_length", "verdict": "fail"}]})
        result = self._rt("bodesign_ingest_evidence",
                          {"folder": str(self.work), "evidence_id": ev["evidence_id"]})
        self.assertEqual(result["requirement_status_updates"], {"board_length": "fail"})
        listing = self._rt("bodesign_list_evidence_returns", {"folder": str(self.work)})
        self.assertEqual(len(listing["evidence_returns"]), 1)

    def test_blocker_simple_fix_candidates_through_mcp(self):
        p = self._rt("bodesign_dispatch_work_packet",
                     {"folder": str(self.work), "target_layer": "C04", "objective": "route"})
        b = self._rt("bodesign_return_blocker",
                     {"folder": str(self.work), "packet_id": p["packet_id"], "severity": "blocked",
                      "summary": "s", "question_for_user": "q",
                      "simple_fix_candidates": [{"hypothesis": "h", "check_method": "m", "ruled_out": False}]})
        self.assertEqual(len(b["simple_fix_candidates"]), 1)

    def test_tool_error_surfaces_as_data(self):
        bad = self.server.run_tool("bodesign_wrap_validation_evidence",
                                   {"tool": "magic", "raw_result": {"x": 1}})
        self.assertFalse(bad["ok"])
        self.assertIn("ENV_TOOL_UNKNOWN", bad["error"])


if __name__ == "__main__":
    unittest.main()
