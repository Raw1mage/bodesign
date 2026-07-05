import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    c00_orchestration_status,
    c00_orchestration_tick,
    list_work_packets,
    load_agent_registry,
    return_blocker,
    scaffold_c00_prd_package,
)

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"


def _seed_refs(folder: Path) -> None:
    """Minimal 01_refs/ SSOT so the C01 refs-first pre-flight (F7) passes."""
    refs = folder / "01_refs"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "Reference_Baseline.md").write_text(
        "# Reference Baseline\n\nauthority order: formal deck\n", encoding="utf-8")
    (refs / "formal_deck_requirement.md").write_text("# req\n", encoding="utf-8")


def _answer_all(folder: Path) -> None:
    sp = folder / "C00-PRD" / "answer_state.json"
    st = json.loads(sp.read_text())
    for doc in st["documents"].values():
        for sec in doc["sections"]:
            sec["state"] = "answered"
            for f in sec["fields"].values():
                f["state"] = "answered"
                f["value"] = "x"
    sp.write_text(json.dumps(st))


class C00OrchestrationTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-c00orch-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_empty_folder_asks_to_scaffold(self):
        self.assertEqual(c00_orchestration_tick(self.work).kind, "scaffold_c00")
        board = c00_orchestration_status(self.work)
        self.assertFalse(board.c00_scaffolded)

    def test_fresh_scaffold_asks_c00_never_dispatches_blocked_layer(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        act = c00_orchestration_tick(self.work, auto_dispatch=False)
        self.assertEqual(act.kind, "ask_c00")
        self.assertTrue(act.question)
        # No layer dispatched while gates are blocked.
        self.assertEqual(list_work_packets(self.work), [])

    def test_deterministic_same_state_same_action(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        a = c00_orchestration_tick(self.work, auto_dispatch=False)
        b = c00_orchestration_tick(self.work, auto_dispatch=False)
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_full_progression_dispatches_each_layer_once_then_done(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        _answer_all(self.work)
        _seed_refs(self.work)
        dispatched = []
        for _ in range(12):
            act = c00_orchestration_tick(self.work)
            if act.kind == "dispatch":
                dispatched.append(act.layer)
            elif act.kind == "done":
                break
        self.assertEqual(dispatched, ["C01", "C02", "C03", "C04", "C05", "C06"])
        # Idempotent: no layer dispatched twice.
        self.assertEqual(len(dispatched), len(set(dispatched)))
        # Terminal state is done.
        self.assertEqual(c00_orchestration_tick(self.work).kind, "done")

    def test_c04_dispatched_only_after_its_upstream(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        _answer_all(self.work)
        _seed_refs(self.work)
        order = []
        for _ in range(12):
            act = c00_orchestration_tick(self.work)
            if act.kind == "dispatch":
                order.append(act.layer)
            elif act.kind == "done":
                break
        # C04 (no direct C00 gate) appears only after C01 and C03.
        self.assertLess(order.index("C01"), order.index("C04"))
        self.assertLess(order.index("C03"), order.index("C04"))

    def test_unresolved_blocker_preempts_everything(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        _answer_all(self.work)
        _seed_refs(self.work)
        # Dispatch one layer, then it returns a blocker.
        c00_orchestration_tick(self.work)  # dispatches C01
        pkt = list_work_packets(self.work)[0]
        return_blocker(self.work, pkt.packet_id, severity="decision",
                       summary="Need primary face.", question_for_user="Which face is primary?")
        act = c00_orchestration_tick(self.work)
        self.assertEqual(act.kind, "resolve_blocker")
        self.assertEqual(act.question, "Which face is primary?")

    def test_dry_run_recommends_without_dispatching(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        _answer_all(self.work)
        _seed_refs(self.work)
        act = c00_orchestration_tick(self.work, auto_dispatch=False)
        self.assertEqual(act.kind, "dispatch")
        self.assertEqual(act.layer, "C01")
        self.assertEqual(list_work_packets(self.work), [])  # nothing actually dispatched

    def test_tick_never_writes_prd_answer_or_approval(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        sp = self.work / "C00-PRD" / "answer_state.json"
        before = sp.read_text()
        for _ in range(3):
            c00_orchestration_tick(self.work)
        self.assertEqual(sp.read_text(), before)  # PRD answer state untouched

    # ── Declarative backend metadata (records native/worker; spine does NOT branch) ──
    def test_registry_exposes_declarative_backend_metadata(self):
        reg = load_agent_registry()
        self.assertEqual(reg.get("C00").backend["kind"], "native")
        self.assertEqual(reg.get("C02").backend, {"kind": "worker", "group": "me"})
        self.assertEqual(reg.get("C03").backend, {"kind": "worker", "group": "ee"})

    def test_dispatch_uniform_over_native_and_worker_layers(self):
        # The spine dispatches every layer uniformly (work packet); backend is metadata.
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        _answer_all(self.work)
        _seed_refs(self.work)
        dispatched = []
        for _ in range(12):
            act = c00_orchestration_tick(self.work)
            if act.kind == "dispatch":
                self.assertIn(act.evidence.get("backend"), ("native", "worker"))
                dispatched.append(act.layer)
            elif act.kind == "done":
                break
        self.assertEqual(dispatched, ["C01", "C02", "C03", "C04", "C05", "C06"])

    # ── F7: C01 refs-first pre-flight at the tick boundary ──────────────────
    def test_tick_blocks_c01_dispatch_when_refs_ssot_missing(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        _answer_all(self.work)  # gate ready, but NO 01_refs/
        act = c00_orchestration_tick(self.work)
        self.assertEqual(act.kind, "resolve_blocker")
        self.assertEqual(act.owner, "user")
        self.assertEqual(act.layer, "C01")
        self.assertEqual(act.evidence["refs_gate_code"], "REFS_SSOT_MISSING")
        self.assertTrue(act.question)
        # Nothing dispatched, nothing generated — fail-fast, no fabricated package.
        self.assertEqual(list_work_packets(self.work), [])
        self.assertFalse((self.work / "C01-ID").exists())

    def test_tick_blocks_c01_when_refs_ssot_empty(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        _answer_all(self.work)
        (self.work / "01_refs").mkdir()  # visible but EMPTY
        act = c00_orchestration_tick(self.work)
        self.assertEqual(act.kind, "resolve_blocker")
        self.assertEqual(act.evidence["reason"], "no_sources")
        self.assertEqual(list_work_packets(self.work), [])

    def test_tick_dispatches_c01_once_refs_seeded(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        _answer_all(self.work)
        act = c00_orchestration_tick(self.work)
        self.assertEqual(act.kind, "resolve_blocker")  # blocked first
        _seed_refs(self.work)
        act = c00_orchestration_tick(self.work)
        self.assertEqual(act.kind, "dispatch")
        self.assertEqual(act.layer, "C01")

    def test_status_board_lists_all_downstream_layers(self):
        scaffold_c00_prd_package(self.work, project_name="X", include_rf=False)
        board = c00_orchestration_status(self.work)
        self.assertEqual([l.code for l in board.layers], ["C01", "C02", "C03", "C04", "C05", "C06"])
        self.assertTrue(board.c00_scaffolded)


if __name__ == "__main__":
    unittest.main()
