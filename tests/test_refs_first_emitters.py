"""Acceptance tests for plan capability_refs-first-emitters (BR_20260704 §5).

TV-1: emit without 01_refs/ fails fast, zero files written.
TV-2: provenance tagging — answered → answer; corpus-inferred → derived.
TV-3: BR §5b — components without resolvable provenance → dod_ok false + gaps.
TV-4: BR §5a — refs-attributed items resolve; schema v2; no gaps.
TV-5: BR §5c — c02 provenance blocker semantics + legacy v1 readiness (gap, no crash).
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from bodesign_workflow_core import (
    assess_c01_package_readiness,
    assess_c02_constraint_readiness,
    emit_c01_rockbox_package,
    emit_c02_enclosure_package,
)
from bodesign_workflow_core.refs_gate import RefsGateError

PRIVATE_BASE = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".cache")) / "claude-work"

C01_CONSTRAINTS_REL = Path("C01-ID") / "Interface_Constraints.json"
C02_CONSTRAINTS_REL = Path("C02-ME") / "Mechanical_Constraints.json"


def _seed_refs(work: Path, name: str = "owner_brief.md", stage: str = "C01-ID") -> None:
    """Seed a stage's ``01_refs/`` SSOT.

    ``01_refs/`` is a PER-STAGE bucket (stage-structure.md), so the refs gate
    resolves ``<product-root>/<STAGE>/01_refs/``. ``work`` is the product root.
    """
    refs = work / stage / "01_refs"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / name).write_text("# Owner brief\n\nAuthority source content.\n", encoding="utf-8")


class RefsFirstEmitterTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_BASE.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="bodesign-refs1st-", dir=PRIVATE_BASE))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    # ── TV-1: gate fail-fast, nothing generated ──────────────────────────
    def test_tv1_c01_emit_without_refs_fails_fast_no_files(self):
        with self.assertRaises(RefsGateError):
            emit_c01_rockbox_package(self.work, c00="camera and usb-c device")
        self.assertFalse((self.work / "C01-ID").exists())

    def test_tv1_c02_emit_without_refs_fails_fast_no_files(self):
        with self.assertRaises(RefsGateError):
            emit_c02_enclosure_package(
                self.work, constraints={"board_outline": {"width_mm": 80, "height_mm": 50}})
        self.assertFalse((self.work / "C02-ME").exists())

    # ── TV-2: provenance tagging ─────────────────────────────────────────
    def test_tv2_answered_components_tagged_answer(self):
        _seed_refs(self.work)
        emit_c01_rockbox_package(
            self.work, c00="mentions usb-c and antenna",
            answers={"exposed_components": ["camera", "led"]})
        data = json.loads((self.work / C01_CONSTRAINTS_REL).read_text(encoding="utf-8"))
        kinds = {c["name"]: c["provenance"]["kind"] for c in data["exposed_components"]}
        self.assertEqual({"camera": "answer", "led": "answer"}, kinds)

    def test_tv2_corpus_inferred_components_tagged_derived(self):
        _seed_refs(self.work)
        emit_c01_rockbox_package(self.work, c00="A wearable with usb-c and a status led.")
        data = json.loads((self.work / C01_CONSTRAINTS_REL).read_text(encoding="utf-8"))
        comps = {c["name"]: c["provenance"] for c in data["exposed_components"]}
        self.assertIn("usb-c", comps)
        self.assertEqual("derived", comps["usb-c"]["kind"])
        self.assertEqual("c00_corpus", comps["usb-c"]["source"])
        self.assertTrue(comps["usb-c"]["detail"])  # matched keyword recorded

    # ── TV-3 / BR §5b: unattributed content can no longer pass dod ──────
    def test_tv3_derived_components_block_dod(self):
        _seed_refs(self.work)
        emit_c01_rockbox_package(self.work, c00="Handheld with camera, usb-c, led.")
        out = assess_c01_package_readiness(self.work).to_dict()
        self.assertTrue(out["provenance_gaps"])
        self.assertFalse(out["dod_ok"])
        reasons = {g["reason"] for g in out["provenance_gaps"]}
        self.assertIn("kind_derived", reasons)

    def test_tv3_legacy_v1_file_reports_provenance_missing_without_crash(self):
        _seed_refs(self.work)
        emit_c01_rockbox_package(
            self.work, answers={"exposed_components": ["camera"]})
        # Strip provenance to simulate a legacy v1 artifact.
        path = self.work / C01_CONSTRAINTS_REL
        data = json.loads(path.read_text(encoding="utf-8"))
        data["schema"] = "bodesign.c01.interface_constraints.v1"
        for comp in data["exposed_components"]:
            comp.pop("provenance", None)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        out = assess_c01_package_readiness(self.work).to_dict()
        self.assertFalse(out["dod_ok"])
        self.assertEqual(
            {"provenance_missing"}, {g["reason"] for g in out["provenance_gaps"]})

    # ── TV-4 / BR §5a: refs-attributed items resolve, schema v2 ─────────
    def test_tv4_refs_attributed_components_pass_gate(self):
        _seed_refs(self.work, name="component_list.md")
        emit_c01_rockbox_package(
            self.work,
            answers={"exposed_components": [
                {"name": "camera", "source": "component_list.md", "detail": "## exposed"},
                {"name": "usb-c", "source": "component_list.md", "detail": "## exposed"},
            ]})
        data = json.loads((self.work / C01_CONSTRAINTS_REL).read_text(encoding="utf-8"))
        self.assertEqual("bodesign.c01.interface_constraints.v2", data["schema"])
        self.assertIsNotNone(data["refs_manifest"])
        self.assertEqual([], data["provenance_gaps"])
        for comp in data["exposed_components"]:
            self.assertIn(comp["provenance"]["kind"], ("refs", "answer"))
        out = assess_c01_package_readiness(self.work).to_dict()
        self.assertEqual([], out["provenance_gaps"])

    def test_tv4_unresolvable_refs_source_is_a_gap(self):
        _seed_refs(self.work)
        emit_c01_rockbox_package(
            self.work,
            answers={"exposed_components": [
                {"name": "camera", "source": "nonexistent.md"},
            ]})
        out = assess_c01_package_readiness(self.work).to_dict()
        self.assertFalse(out["dod_ok"])
        self.assertEqual(
            {"refs_source_unresolvable"}, {g["reason"] for g in out["provenance_gaps"]})

    # ── TV-5 / BR §5c: c02 provenance blocker semantics ─────────────────
    def test_tv5_c02_present_constraints_without_provenance_add_blocker(self):
        readiness = assess_c02_constraint_readiness({
            "board_outline": {"width_mm": 80, "height_mm": 50},
            "component_heights": [{"ref": "J1", "height_mm": 8}],
        })
        keys = {item.key: item for item in readiness.items}
        self.assertIn("constraint_provenance", keys)
        self.assertEqual("missing", keys["constraint_provenance"].status)

    def test_tv5_c02_refs_provenance_clears_blocker(self):
        _seed_refs(self.work, name="mech_brief.md", stage="C02-ME")
        readiness = assess_c02_constraint_readiness({
            "board_outline": {"width_mm": 80, "height_mm": 50},
            "component_heights": [{"ref": "J1", "height_mm": 8}],
            "provenance": {
                "board_outline": {"kind": "refs", "source": "mech_brief.md", "detail": "outline"},
                "component_heights": {"kind": "refs", "source": "mech_brief.md", "detail": "heights"},
            },
        }, folder=self.work)
        keys = {item.key for item in readiness.items}
        self.assertNotIn("constraint_provenance", keys)
        self.assertTrue(readiness.can_generate_cad_source)

    def test_tv5_c02_emitted_json_carries_provenance_gaps(self):
        _seed_refs(self.work, stage="C02-ME")
        emit_c02_enclosure_package(
            self.work,
            constraints={"board_outline": {"width_mm": 80, "height_mm": 50}},
            project_summary="desk sensor")
        data = json.loads((self.work / C02_CONSTRAINTS_REL).read_text(encoding="utf-8"))
        gaps = data["constraint_status"]["provenance_gaps"]
        self.assertTrue(gaps)
        self.assertEqual("board_outline", gaps[0]["item"])


    # ── Review hardening (F1/F2/F3/F6, review of c790e8b) ────────────────
    def test_f1_answer_claim_without_answer_state_is_a_gap(self):
        _seed_refs(self.work)
        emit_c01_rockbox_package(
            self.work, answers={"exposed_components": ["flux capacitor", "warp coil"]})
        out = assess_c01_package_readiness(self.work).to_dict()
        self.assertFalse(out["dod_ok"])
        self.assertEqual(
            {"answer_unverified"}, {g["reason"] for g in out["provenance_gaps"]})

    def test_f1_answer_claim_backed_by_answer_state_passes(self):
        from bodesign_workflow_core import c01_update_answers
        _seed_refs(self.work)
        c01_update_answers(self.work, {"exposed_components": "camera, led"})
        out = assess_c01_package_readiness(self.work).to_dict()
        reasons = {g["reason"] for g in out["provenance_gaps"]}
        self.assertNotIn("answer_unverified", reasons)

    def test_f2_refs_source_traversal_escaping_refs_is_a_gap(self):
        _seed_refs(self.work)
        (self.work / "outside.md").write_text("outside the SSOT\n", encoding="utf-8")
        emit_c01_rockbox_package(
            self.work,
            answers={"exposed_components": [{"name": "camera", "source": "../outside.md"}]})
        out = assess_c01_package_readiness(self.work).to_dict()
        self.assertFalse(out["dod_ok"])
        self.assertEqual(
            {"refs_source_unresolvable"}, {g["reason"] for g in out["provenance_gaps"]})

    def test_f3_folderless_refs_claim_fails_closed(self):
        readiness = assess_c02_constraint_readiness({
            "board_outline": {"width_mm": 80, "height_mm": 50},
            "provenance": {"board_outline": {"kind": "refs", "source": "totally_bogus.md"}},
        })
        keys = {item.key for item in readiness.items}
        self.assertIn("constraint_provenance", keys)

    def test_f6_dict_component_without_name_fails_fast(self):
        _seed_refs(self.work)
        with self.assertRaises(ValueError):
            emit_c01_rockbox_package(
                self.work, answers={"exposed_components": [{"source": "owner_brief.md"}]})

    def test_f6_dict_component_without_source_is_derived_caller_unattributed(self):
        _seed_refs(self.work)
        emit_c01_rockbox_package(
            self.work, answers={"exposed_components": [{"name": "camera"}]})
        data = json.loads((self.work / C01_CONSTRAINTS_REL).read_text(encoding="utf-8"))
        prov = data["exposed_components"][0]["provenance"]
        self.assertEqual(("derived", "caller_unattributed"), (prov["kind"], prov["source"]))


if __name__ == "__main__":
    unittest.main()
