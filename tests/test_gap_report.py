import glob
import json
import os
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import collect_source_gap_report, render_gap_report_markdown

OPENMV_PLAN = Path("/home/pkcs12/projects/bodesign/plans/product_openmv_datasheet_kicad_source")
HAS_OPENMV = OPENMV_PLAN.exists() and any(OPENMV_PLAN.glob("*.json"))
PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class GapReportTests(unittest.TestCase):
    def test_blocking_artifact_marks_report_blocked(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-gap-", dir=PRIVATE_BASE))
        try:
            artifact = work / "thing-validation.json"
            artifact.write_text(json.dumps({
                "artifact_id": "thing-validation",
                "blockers": ["Exact package variant unresolved; symbol generation blocked."],
                "gaps": ["Footprint pad geometry not yet converted."],
            }), encoding="utf-8")

            report = collect_source_gap_report("pkg", "Test", [str(artifact)])

            self.assertEqual("blocked", report.readiness_state)
            self.assertEqual(1, report.counts["blocking"])
            self.assertEqual(1, report.counts["open"])
            severities = {gap.severity for gap in report.gap_items}
            self.assertIn("blocking", severities)
        finally:
            import shutil
            shutil.rmtree(work, ignore_errors=True)

    def test_stale_blocker_is_superseded_by_resolution_signal(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="bodesign-gap-", dir=PRIVATE_BASE))
        try:
            seed = work / "seed-component-knowledge.json"
            seed.write_text(json.dumps({
                "component_id": "seed",
                "pin_table_status": {"blocked_symbol_generation": True, "reason": "pin table not materialized"},
            }), encoding="utf-8")
            review = work / "pin-table-ai-review.json"
            review.write_text(json.dumps({
                "artifact_id": "pin-table-ai-review",
                "validation_summary": {"o4_unblocked": True},
            }), encoding="utf-8")

            report = collect_source_gap_report("pkg", "Test", [str(seed), str(review)])

            # The stale seed blocker must not count as blocking once O4 is unblocked.
            self.assertEqual(0, report.counts["blocking"])
            self.assertEqual(1, report.counts["resolved_superseded"])
            self.assertTrue(any("Superseded" in fact.text for fact in report.resolved_facts))
        finally:
            import shutil
            shutil.rmtree(work, ignore_errors=True)

    @unittest.skipUnless(HAS_OPENMV, "OpenMV plan artifacts are not present")
    def test_openmv_package_is_reusable_with_gaps_and_no_blockers(self):
        paths = sorted(glob.glob(str(OPENMV_PLAN / "*.json")))

        report = collect_source_gap_report("openmv_n6_kicad_source", "OpenMV N6", paths)

        self.assertEqual("reusable-as-source-evidence-with-gaps", report.readiness_state)
        self.assertEqual(0, report.counts["blocking"])
        self.assertGreater(report.counts["open"], 0)
        # The validated 223-ball pin table must surface as a resolved fact.
        self.assertTrue(any("223 balls" in fact.text for fact in report.resolved_facts))
        markdown = render_gap_report_markdown(report)
        self.assertIn("# Gap & Evidence Report", markdown)
        self.assertIn("Readiness: **reusable-as-source-evidence-with-gaps**", markdown)
        self.assertIn("Per-artifact summary", markdown)


if __name__ == "__main__":
    unittest.main()
