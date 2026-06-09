"""An open cross-stage reconciliation (BlockerReturn) must block the readiness all-clear."""
import os, shutil, tempfile, unittest
from pathlib import Path

from bodesign_workflow_core import assess_package_readiness
from bodesign_workflow_core.orchestration import dispatch_work_packet, return_blocker

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


class ReconciliationGateTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-recon-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_no_blockers_clean(self):
        r = assess_package_readiness(self.work)
        self.assertEqual(r.open_blockers, [])
        self.assertNotIn("reconciliation blocker", r.summary)

    def test_open_blocker_surfaces_and_routes(self):
        wp = dispatch_work_packet(self.work, "C03", "size the power tree")
        return_blocker(
            self.work, wp.packet_id,
            severity="blocked",
            summary="ΣPdiss 4.2W exceeds enclosure dissipation ~2.8W by 1.4W",
            question_for_user="vent (trades IP) or larger enclosure?",
            affected_downstream_layers=["C02"],
            options=["spread+vias (C04)", "vent (C02)", "lower-Pdiss part (C03)"],
            recommended_owner="downstream_agent",
        )
        r = assess_package_readiness(self.work)
        self.assertEqual(len(r.open_blockers), 1)                 # surfaced
        self.assertIn("reconciliation blocker", r.summary)        # counted in summary
        self.assertIn("C02", r.next_step)                         # routed to must_act stage
        self.assertIn(r.open_blockers[0]["blocker_id"], r.next_step)


if __name__ == "__main__":
    unittest.main()
